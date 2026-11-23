"""Codificação e autenticação do formato PVLT versão 1."""

import base64
import binascii
import json
import secrets
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .constants import (MAGIC, MAX_ARQUIVO, MAX_CABECALHO, MAX_MEMORIA, N, P, R,
                        TAMANHO_CHAVE, VERSAO)
from .errors import DadosInvalidos, InvalidMasterPassword, VaultCorrupted


@dataclass(frozen=True)
class Parametros:
    """Parâmetros da chave mantidos entre gravações."""

    salt: bytes
    n: int = N
    r: int = R
    p: int = P

    @classmethod
    def novos(cls) -> "Parametros":
        """Cria salt exclusivo para uma senha mestra."""
        return cls(secrets.token_bytes(16))

    def validar(self) -> None:
        """Verifica os limites antes de qualquer alocação do scrypt."""
        n, r, p = self.n, self.r, self.p
        if not all(type(i) is int for i in (n, r, p)):
            raise VaultCorrupted()
        if not (2**14 <= n <= 2**20 and n & (n - 1) == 0 and 1 <= r <= 32 and 1 <= p <= 16):
            raise VaultCorrupted()
        if len(self.salt) != 16 or 128 * r * (n + p + 2) > MAX_MEMORIA:
            raise VaultCorrupted()


def derivar(senha: str, parametros: Parametros) -> bytearray:
    """Deriva uma chave de sessão passível de sobrescrita."""
    parametros.validar()
    kdf = Scrypt(salt=parametros.salt, length=TAMANHO_CHAVE,
                 n=parametros.n, r=parametros.r, p=parametros.p)
    return bytearray(kdf.derive(senha.encode("utf-8")))


def apagar(chave: bytearray) -> None:
    """Sobrescreve o buffer mutável da chave."""
    chave[:] = bytes(len(chave))


def compacto(valor: object) -> bytes:
    """Serializa JSON compacto em UTF-8."""
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def cifrar(dados: bytes, chave: bytearray, parametros: Parametros) -> bytes:
    """Cifra com um nonce novo e autentica os bytes exatos do cabeçalho."""
    nonce = secrets.token_bytes(12)
    cab = compacto(dict(v=VERSAO, kdf="scrypt", n=parametros.n, r=parametros.r,
                        p=parametros.p, dklen=TAMANHO_CHAVE,
                        salt=base64.b64encode(parametros.salt).decode("ascii"),
                        nonce=base64.b64encode(nonce).decode("ascii")))
    if 9 + len(cab) + len(dados) + 16 > MAX_ARQUIVO:
        raise DadosInvalidos("O cofre excederia o limite de 16 MiB.")
    return MAGIC + struct.pack(">BI", VERSAO, len(cab)) + cab + AESGCM(chave).encrypt(
        nonce, dados, cab)


@dataclass(frozen=True)
class Envelope:
    """Partes de um arquivo com estrutura já verificada."""

    parametros: Parametros
    nonce: bytes
    cabecalho: bytes
    cifrado: bytes

    def abrir(self, chave: bytearray) -> bytes:
        """Verifica a tag antes de entregar os dados."""
        try:
            return AESGCM(chave).decrypt(self.nonce, self.cifrado, self.cabecalho)
        except InvalidTag:
            raise InvalidMasterPassword() from None


def ler_envelope(arquivo: bytes) -> Envelope:
    """Rejeita arquivos inválidos antes de derivar a chave."""
    if not 9 <= len(arquivo) <= MAX_ARQUIVO or arquivo[:5] != MAGIC + bytes([VERSAO]):
        raise VaultCorrupted()
    tamanho = int.from_bytes(arquivo[5:9], "big")
    fim = 9 + tamanho
    if not 0 < tamanho <= MAX_CABECALHO or len(arquivo) < fim + 16:
        raise VaultCorrupted()
    cab = arquivo[9:fim]
    try:
        h = json.loads(cab.decode("utf-8"))
        if (type(h["v"]) is not int or h["v"] != VERSAO or h["kdf"] != "scrypt"
                or type(h["dklen"]) is not int or h["dklen"] != TAMANHO_CHAVE):
            raise VaultCorrupted()
        salt = base64.b64decode(h["salt"], validate=True)
        nonce = base64.b64decode(h["nonce"], validate=True)
        parametros = Parametros(salt, h["n"], h["r"], h["p"])
        parametros.validar()
        if len(nonce) != 12:
            raise VaultCorrupted()
    except (ValueError, KeyError, TypeError, RecursionError, binascii.Error):
        raise VaultCorrupted() from None
    return Envelope(parametros, nonce, cab, arquivo[fim:])

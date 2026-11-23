"""Testes criptográficos somente com chaves fictícias."""

import json
import unittest
from unittest.mock import patch

from passvault import crypto
from passvault.errors import InvalidMasterPassword, VaultCorrupted


class Criptografia(unittest.TestCase):
    def setUp(self) -> None:
        self.param = crypto.Parametros.novos()
        self.chave = crypto.derivar("mestra-fictícia", self.param)
        self.dados = b"SENHA-FAKE-123"
        self.arquivo = crypto.cifrar(self.dados, self.chave, self.param)
        self.env = crypto.ler_envelope(self.arquivo)

    def cabecalho(self, novo: bytes) -> bytes:
        return self.arquivo[:5] + len(novo).to_bytes(4, "big") + novo + self.env.cifrado

    def test_ida_e_volta(self) -> None:
        self.assertTrue(self.arquivo.startswith(b"PVLT"))
        self.assertNotIn(self.dados, self.arquivo)
        self.assertEqual(self.env.abrir(self.chave), self.dados)

    def test_senha_incorreta(self) -> None:
        with self.assertRaises(InvalidMasterPassword):
            self.env.abrir(crypto.derivar("outra", self.param))

    def test_cabecalho_autenticado_byte_a_byte(self) -> None:
        modificado = self.cabecalho(self.env.cabecalho + b" ")
        with self.assertRaises(InvalidMasterPassword):
            crypto.ler_envelope(modificado).abrir(self.chave)

    def test_conteudo_adulterado(self) -> None:
        modificado = self.arquivo[:-1] + bytes([self.arquivo[-1] ^ 1])
        with self.assertRaises(InvalidMasterPassword):
            crypto.ler_envelope(modificado).abrir(self.chave)

    def test_nonce_por_gravacao_e_salt_por_chave(self) -> None:
        outro = crypto.ler_envelope(crypto.cifrar(self.dados, self.chave, self.param))
        self.assertNotEqual(outro.nonce, self.env.nonce)
        self.assertEqual(outro.parametros.salt, self.env.parametros.salt)
        self.assertNotEqual(crypto.Parametros.novos().salt, self.param.salt)

    def test_limites_antes_da_derivacao(self) -> None:
        with patch("passvault.crypto.Scrypt") as kdf:
            for campo, valor in (("n", 5), ("n", 32769), ("n", 2**20), ("r", 33),
                                 ("p", False), ("p", 18), ("dklen", 16), ("salt", "YQ=="),
                                 ("nonce", "####"), ("kdf", "outro")):
                cab = dict(json.loads(self.env.cabecalho), **{campo: valor})
                with self.subTest(campo=campo), self.assertRaises(VaultCorrupted):
                    crypto.ler_envelope(self.cabecalho(crypto.compacto(cab)))
            with self.assertRaises(VaultCorrupted):
                crypto.derivar("", crypto.Parametros(bytes(16), n=2**20))
            kdf.assert_not_called()

    def test_formato_invalido(self) -> None:
        for dados in (self.arquivo[:8], self.arquivo[:12], b"X" + self.arquivo[1:],
                      self.arquivo[:4] + b"\x02" + self.arquivo[5:], self.cabecalho(b"null"),
                      self.cabecalho(b"{"), self.cabecalho(b" " * 4097)):
            with self.assertRaises(VaultCorrupted):
                crypto.ler_envelope(dados)

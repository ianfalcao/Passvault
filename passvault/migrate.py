"""Análise e importação assistida de arquivos JSON legados."""

import argparse
import getpass
import hashlib
import json
import logging
import os
import stat
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

from . import plataforma as so
from .constants import MAX_ARQUIVO
from .errors import DadosInvalidos, ErroPassVault, LegacyParseError
from .storage import Armazenamento, configurar_log, sincronizar, tratar_io
from .vault import Cofre, Conta, agora, validar_senha


def _json(texto: str) -> Any:
    try:
        return json.loads(texto)
    except json.JSONDecodeError as erro:
        raise LegacyParseError(
            f"JSON inválido na linha {erro.lineno}, coluna {erro.colno}."
        ) from None
    except (RecursionError, ValueError):
        raise LegacyParseError("O JSON excede os limites de leitura.") from None


def repair_json_text(texto: str) -> str:
    """Insere vírgulas entre objetos adjacentes do array superior."""
    texto = texto.removeprefix("\ufeff")
    partes = []
    inicio = 0
    pilha: list[str] = []
    em_string = escape = False
    for i, c in enumerate(texto):
        if em_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                em_string = False
        elif c == '"':
            em_string = True
        elif c in "{[":
            pilha.append(c)
        elif c in "}]":
            esperado = "{" if c == "}" else "["
            if not pilha or pilha.pop() != esperado:
                break
            if c == "}" and pilha == ["{", "["]:
                proximo = i + 1
                while proximo < len(texto) and texto[proximo] in " \r\t\n":
                    proximo += 1
                if texto[proximo:proximo + 1] == "{":
                    partes.extend((texto[inicio:i + 1], ","))
                    inicio = i + 1
    partes.append(texto[inicio:])
    reparado = "".join(partes)
    _json(reparado)
    return reparado


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (dict, list, bool)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def _conta(item: dict[str, Any]) -> Conta:
    usados = {"service"}

    def primeiro(nomes: tuple[str, ...]) -> str:
        for nome in nomes:
            valor = _texto(item.get(nome))
            if valor != "":
                usados.add(nome)
                return valor
        return ""

    usuario = primeiro(("username", "email", "user", "id"))
    senha = primeiro(("password", "pin", "key", "code"))
    extra = {k: _texto(v) for k, v in item.items() if k not in usados}
    return Conta(_texto(item.get("service")).strip() or "Desconhecido", usuario, senha, extra=extra)


@dataclass
class Analise:
    """Resultado em memória, com resumo público sem credenciais."""

    origem: Path
    sha256: str
    contas: list[Conta]
    ignoradas: int
    reparado: bool

    def duplicadas(self, existentes: list[Conta]) -> int:
        """Conta repetições do par serviço/usuário dentro e fora do lote."""
        vistos = {(c.service.casefold(), c.username.casefold()) for c in existentes}
        quantidade = 0
        for conta in self.contas:
            par = conta.service.casefold(), conta.username.casefold()
            quantidade += int(par in vistos)
            vistos.add(par)
        return quantidade

    def repetida(self, cofre: Cofre) -> bool:
        """Compara com a assinatura da última importação."""
        return cofre.conteudo.meta.get("legacy_import", {}).get("sha256") == self.sha256

    def resumo(self, existentes: list[Conta]) -> str:
        """Apresenta exclusivamente contagens e avisos."""
        return (f"Contas válidas: {len(self.contas)}. Ignoradas: {self.ignoradas}. "
                f"Duplicadas (mantidas): {self.duplicadas(existentes)}. "
                + ("Vírgulas ausentes reparadas." if self.reparado else "JSON válido."))


def _abrir(origem: Path) -> BinaryIO:
    fd = so.abrir_regular(origem, os.O_RDONLY)
    return os.fdopen(fd, "rb")


def _ler(f: BinaryIO) -> bytes:
    info = os.fstat(f.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARQUIVO:
        raise LegacyParseError("Selecione um arquivo regular de até 16 MiB.")
    dados = f.read(MAX_ARQUIVO + 1)
    if len(dados) > MAX_ARQUIVO:
        raise LegacyParseError("O arquivo excede 16 MiB.")
    return dados


def analisar(origem: Path) -> Analise:
    """Lê e normaliza em memória sem alterar arquivos nem permissões."""
    origem = origem.expanduser().absolute()
    with tratar_io(), _abrir(origem) as f:
        dados = _ler(f)
    try:
        texto = dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise LegacyParseError("O arquivo deve estar em UTF-8.") from None
    reparado = repair_json_text(texto)
    obj = _json(reparado)
    if not isinstance(obj, dict) or not isinstance(obj.get("accounts"), list):
        raise LegacyParseError("O JSON deve conter uma lista chamada accounts.")
    itens = obj["accounts"]
    contas = [_conta(item) for item in itens if isinstance(item, dict)]
    try:
        for c in contas:
            for s in (c.service, c.username, c.password, *c.extra.keys(), *c.extra.values()):
                s.encode("utf-8")
    except UnicodeEncodeError:
        raise LegacyParseError("O JSON contém um caractere Unicode inválido.") from None
    return Analise(origem, hashlib.sha256(dados).hexdigest(), contas, len(itens) - len(contas),
                   reparado != texto)


def _backup_legado(origem: Path, dados: bytes) -> Path:
    data = datetime.now()
    while True:
        copia = origem.with_name(f"{origem.name}.bak-{data:%Y%m%d-%H%M%S}")
        try:
            fd = so.abrir_regular(copia, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            break
        except FileExistsError:
            data += timedelta(seconds=1)
    try:
        with os.fdopen(fd, "wb") as f:
            so.proteger(fd)
            f.write(dados)
            f.flush()
            os.fsync(fd)
        sincronizar(origem.parent)
    except OSError:
        copia.unlink(missing_ok=True)
        raise
    return copia


def importar(analise: Analise, cofre: Cofre, permitir_repetida: bool = False) -> Path:
    """Confere os bytes analisados e guarda o original antes da gravação do lote."""
    if analise.repetida(cofre) and not permitir_repetida:
        raise DadosInvalidos("Este arquivo já foi importado. Confirme para importar novamente.")
    with tratar_io(), _abrir(analise.origem) as f:
        dados = _ler(f)
        if hashlib.sha256(dados).hexdigest() != analise.sha256:
            raise DadosInvalidos("O arquivo mudou. Analise novamente.")
        copia = _backup_legado(analise.origem, dados)
        so.proteger(f.fileno())
        if not so.WINDOWS:
            os.fsync(f.fileno())
    cofre.incorporar(analise.contas, dict(source=str(analise.origem), sha256=analise.sha256,
                                         imported_at=agora(), count=len(analise.contas)))
    logging.getLogger("passvault").info("Importação.")
    return copia


def principal() -> int:
    """Executa o diagnóstico ou a migração usando entrada oculta no terminal."""
    parser = argparse.ArgumentParser(description="Migração local para o PassVault")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="analisar sem gravar")
    args = parser.parse_args()
    disco = Armazenamento()
    cofre = Cofre(disco)
    try:
        analise = analisar(args.source or so.caminho_legado_padrao())
        if args.dry_run:
            print(analise.resumo([]))
            return 0
        disco.adquirir()
        configurar_log()
        existe = disco.cofre.exists()
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            senha = getpass.getpass("Senha mestra: " if existe else "Crie a senha mestra: ")
            if existe:
                cofre.desbloquear(senha)
                del senha
            else:
                validar_senha(senha)
                print("A senha mestra não pode ser recuperada.")
                if len(senha) < 12:
                    print("Recomenda-se usar 12 caracteres ou mais.")
                if senha != getpass.getpass("Confirme a senha mestra: "):
                    raise DadosInvalidos("As senhas não coincidem.")
        print(analise.resumo(cofre.buscar("") if existe else []))
        repetida = existe and analise.repetida(cofre)
        if repetida:
            print("Este arquivo já foi importado.")
        if input("Importar e criar backup do original? Digite SIM: ").strip() != "SIM":
            return 0
        if not existe:
            cofre.criar(senha)
            del senha
        anterior = len(cofre.conteudo.contas)
        copia = importar(analise, cofre, permitir_repetida=repetida)
        cofre.recarregar()
        if (len(cofre.conteudo.contas) != anterior + len(analise.contas)
                or not analise.repetida(cofre)):
            raise DadosInvalidos("Não foi possível conferir a contagem após a importação.")
        from .config import Config
        config = Config.ler(disco.pasta)
        config.ultimo_import = str(analise.origem)
        config.salvar(disco.pasta)
        print(f"Importadas: {len(analise.contas)}. Backup: {copia}. Original preservado.")
        return 0
    except ErroPassVault as erro:
        print(erro)
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Migração interrompida. Use um terminal com entrada oculta de senha.")
    finally:
        cofre.bloquear()
        disco.liberar()
    return 1


if __name__ == "__main__":
    raise SystemExit(principal())

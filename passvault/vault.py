"""Modelo de contas e sessão com gravação imediata e autenticada."""

import json
import logging
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from . import crypto
from .errors import DadosInvalidos, ErroPassVault, SessaoBloqueada, VaultCorrupted
from .storage import Armazenamento


def agora() -> str:
    """Retorna data UTC com fuso."""
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto: str) -> str:
    """Remove diferenças de caixa e acentos para busca."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto).casefold()
                   if not unicodedata.combining(c))


def validar_senha(senha: str) -> None:
    """Aplica o mínimo de criação, inclusive na troca de senha."""
    if len(senha) < 8:
        raise DadosInvalidos("Use pelo menos 8 caracteres na senha mestra.")


def data_valida(valor: str) -> bool:
    """Exige uma data ISO com fuso UTC."""
    return isinstance(valor, str) and datetime.fromisoformat(valor).utcoffset() == timedelta(0)


@dataclass(frozen=True)
class Conta:
    """Registro de uma conta dentro do conteúdo cifrado."""

    service: str
    username: str = ""
    password: str = ""
    url: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=agora)
    updated_at: str = field(default_factory=agora)

    def __post_init__(self) -> None:
        if not all(isinstance(x, str) for x in (self.service, self.username, self.password,
                                                self.url, self.notes)) or not self.service.strip():
            raise DadosInvalidos("Informe o nome do serviço.")
        if not isinstance(self.tags, list) or not all(isinstance(t, str) for t in self.tags):
            raise DadosInvalidos("Tags inválidas.")
        if not isinstance(self.extra, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in self.extra.items()):
            raise DadosInvalidos("Campos extras inválidos.")
        if (not isinstance(self.id, str) or UUID(self.id).version != 4
                or str(UUID(self.id)) != self.id or not data_valida(self.created_at)
                or not data_valida(self.updated_at)):
            raise DadosInvalidos("Identificador ou data inválida.")
        unicas: dict[str, str] = {}
        for tag in self.tags:
            if nome := tag.strip():
                unicas.setdefault(nome.casefold(), nome)
        object.__setattr__(self, "service", self.service.strip())
        object.__setattr__(self, "tags", list(unicas.values()))
        object.__setattr__(self, "extra", self.extra.copy())


@dataclass
class Conteudo:
    """Metadados e registros decifrados."""

    meta: dict[str, Any]
    contas: dict[str, Conta]

    @classmethod
    def ler(cls, dados: bytes) -> "Conteudo":
        """Verifica o esquema e a unicidade dos IDs."""
        try:
            obj = json.loads(dados.decode("utf-8"))
            meta, itens = obj["meta"], obj["entries"]
            if (type(obj["version"]) is not int or obj["version"] != 1
                    or not isinstance(itens, list) or not isinstance(meta, dict)
                    or not all(data_valida(meta[k]) for k in ("created_at", "updated_at"))):
                raise VaultCorrupted()
            if "legacy_import" in meta:
                legado = meta["legacy_import"]
                if (not isinstance(legado["source"], str) or not data_valida(legado["imported_at"])
                        or len(bytes.fromhex(legado["sha256"])) != 32
                        or type(legado["count"]) is not int or legado["count"] < 0):
                    raise VaultCorrupted()
            contas = {}
            for item in itens:
                if not isinstance(item, dict) or item.keys() != Conta.__dataclass_fields__.keys():
                    raise VaultCorrupted()
                conta = Conta(**item)
                contas[conta.id] = conta
            if len(itens) != len(contas):
                raise VaultCorrupted()
            return cls(meta, contas)
        except (KeyError, TypeError, ValueError, DadosInvalidos, RecursionError, OverflowError):
            raise VaultCorrupted() from None

    def serializar(self) -> bytes:
        """Preserva a estrutura versionada do conteúdo."""
        return crypto.compacto(dict(version=1, meta=self.meta,
                                    entries=[asdict(c) for c in self.contas.values()]))


class Cofre:
    """Mantém a sessão em memória e só publica alterações após persistência."""

    def __init__(self, disco: Armazenamento) -> None:
        self.disco = disco
        self._chave: bytearray | None = None
        self._parametros: crypto.Parametros | None = None
        self._conteudo: Conteudo | None = None

    @property
    def aberto(self) -> bool:
        """Indica se existe chave de sessão."""
        return self._chave is not None

    @property
    def conteudo(self) -> Conteudo:
        """Dá acesso aos dados somente durante a sessão."""
        if self._conteudo is None:
            raise SessaoBloqueada("Desbloqueie o cofre.")
        return self._conteudo

    def criar(self, senha: str) -> None:
        """Cria um cofre vazio sem substituir um arquivo já existente."""
        validar_senha(senha)
        if self.disco.cofre.exists():
            raise DadosInvalidos("Já existe um cofre.")
        instante = agora()
        conteudo = Conteudo(dict(created_at=instante, updated_at=instante), {})
        self._nova_chave(senha, conteudo)
        logging.getLogger("passvault").info("Criação.")

    def _nova_chave(self, senha: str, conteudo: Conteudo) -> None:
        parametros = crypto.Parametros.novos()
        chave = crypto.derivar(senha, parametros)
        try:
            self.disco.gravar(crypto.cifrar(conteudo.serializar(), chave, parametros))
        except BaseException:
            crypto.apagar(chave)
            raise
        self._ativar(chave, parametros, conteudo)

    def _ativar(self, chave: bytearray, parametros: crypto.Parametros, conteudo: Conteudo) -> None:
        self.bloquear()
        self._chave, self._parametros, self._conteudo = chave, parametros, conteudo

    def desbloquear(self, senha: str) -> None:
        """Autentica o arquivo antes de abrir a sessão."""
        try:
            env = crypto.ler_envelope(self.disco.ler())
            chave = crypto.derivar(senha, env.parametros)
            try:
                conteudo = Conteudo.ler(env.abrir(chave))
            except BaseException:
                crypto.apagar(chave)
                raise
        except ErroPassVault:
            logging.getLogger("passvault").info("Falha de desbloqueio.")
            raise
        self._ativar(chave, env.parametros, conteudo)
        logging.getLogger("passvault").info("Desbloqueio.")

    def bloquear(self) -> None:
        """Descarta as contas e sobrescreve o buffer da chave."""
        if self._chave is not None:
            crypto.apagar(self._chave)
            logging.getLogger("passvault").info("Bloqueio.")
        self._chave = self._parametros = self._conteudo = None

    def recarregar(self) -> None:
        """Relê e autentica o cofre com a chave atual."""
        if self._chave is None:
            raise SessaoBloqueada("Desbloqueie o cofre.")
        env = crypto.ler_envelope(self.disco.ler())
        dados = Conteudo.ler(env.abrir(self._chave))
        self._conteudo, self._parametros = dados, env.parametros

    def _gravar(self, contas: dict[str, Conta], **metadados: Any) -> None:
        atual = self.conteudo
        assert self._parametros is not None and self._chave is not None
        novo = Conteudo(dict(atual.meta, **metadados, updated_at=agora()), contas)
        self.disco.gravar(crypto.cifrar(novo.serializar(), self._chave, self._parametros))
        self._conteudo = novo

    def adicionar(self, conta: Conta) -> None:
        """Adiciona uma conta preservando IDs existentes."""
        if conta.id in self.conteudo.contas:
            raise DadosInvalidos("Identificador já utilizado.")
        self._gravar({**self.conteudo.contas, conta.id: conta})

    def editar(self, identificador: str, **campos: Any) -> None:
        """Altera apenas os campos editáveis mantendo o UUID."""
        if campos.keys() - {"service", "username", "password", "notes", "url", "tags"}:
            raise DadosInvalidos("Campo não editável.")
        conta = replace(self.obter(identificador), updated_at=agora(), **campos)
        self._gravar({**self.conteudo.contas, identificador: conta})

    def obter(self, identificador: str) -> Conta:
        """Localiza uma conta pelo UUID."""
        try:
            return self.conteudo.contas[identificador]
        except KeyError:
            raise DadosInvalidos("Selecione uma conta.") from None

    def excluir(self, identificador: str) -> None:
        """Remove pelo UUID."""
        self.obter(identificador)
        contas = self.conteudo.contas.copy()
        del contas[identificador]
        self._gravar(contas)

    def buscar(self, texto: str) -> list[Conta]:
        """Filtra por serviço, usuário, URL e tags."""
        termo = normalizar(texto)
        return [c for c in self.conteudo.contas.values()
                if any(termo in normalizar(s) for s in (c.service, c.username, c.url, *c.tags))]

    def trocar_senha(self, atual: str, nova: str) -> None:
        """Autentica a senha anterior e troca salt, chave e nonce."""
        validar_senha(nova)
        conteudo = self.conteudo
        env = crypto.ler_envelope(self.disco.ler())
        chave = crypto.derivar(atual, env.parametros)
        try:
            env.abrir(chave)
        finally:
            crypto.apagar(chave)
        self._nova_chave(nova, Conteudo(dict(conteudo.meta, updated_at=agora()), conteudo.contas))

    def incorporar(self, contas: list[Conta], registro: dict[str, Any]) -> None:
        """Grava o lote de importação em uma única transação."""
        todas = self.conteudo.contas.copy()
        for conta in contas:
            if conta.id in todas:
                raise DadosInvalidos("Identificador já utilizado.")
            todas[conta.id] = conta
        self._gravar(todas, legacy_import=registro)

    def restaurar(self, dados: bytes, senha: str, confirmar: Callable[[], bool]) -> bool:
        """Valida, confirma e preserva o estado atual antes de restaurar."""
        env = crypto.ler_envelope(dados)
        chave = crypto.derivar(senha, env.parametros)
        try:
            conteudo = Conteudo.ler(env.abrir(chave))
            if not confirmar():
                return False
            if self.disco.cofre.exists():
                self.disco.criar_backup()
            self.disco.gravar(dados)
            self._ativar(chave, env.parametros, conteudo)
            return True
        finally:
            if chave is not self._chave:
                crypto.apagar(chave)

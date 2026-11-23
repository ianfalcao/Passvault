"""Armazenamento privado, gravação atômica, retenção e exclusão mútua."""

import fcntl
import logging
import os
import re
import stat
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator

from .constants import MAX_ARQUIVO, MAX_BACKUPS, pasta_xdg
from .errors import ErroArmazenamento, InstanciaAberta, SemCofre, VaultCorrupted


@contextmanager
def tratar_io() -> Iterator[None]:
    """Converte falhas do sistema em avisos sem dados particulares."""
    try:
        yield
    except OSError:
        raise ErroArmazenamento(
            "Falha no acesso ao disco. Verifique as permissões e o espaço disponível."
        ) from None


def pasta_privada(pasta: Path) -> None:
    """Garante uma pasta privada real, sem seguir link no componente final."""
    pasta.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(pasta, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(fd, 0o700)
    finally:
        os.close(fd)


def sincronizar(pasta: Path) -> None:
    """Persiste as alterações nas entradas do diretório."""
    fd = os.open(pasta, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ler_privado(caminho: Path) -> bytes:
    """Lê um arquivo regular com limite e corrige seu modo."""
    fd = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARQUIVO:
            raise VaultCorrupted()
        if stat.S_IMODE(info.st_mode) != 0o600:
            os.fchmod(fd, 0o600)
            logging.getLogger("passvault").warning("Permissões de arquivo corrigidas.")
        dados = f.read(MAX_ARQUIVO + 1)
        if len(dados) > MAX_ARQUIVO:
            raise VaultCorrupted()
        return dados


def escrever_atomico(caminho: Path, dados: bytes) -> None:
    """Publica após fsync e reverte a troca se o fsync do diretório falhar."""
    fd, nome = tempfile.mkstemp(dir=caminho.parent, prefix=".pv-")
    temporario = Path(nome)
    anterior = temporario.with_suffix(".anterior")
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(fd, 0o600)
            f.write(dados)
            f.flush()
            os.fsync(fd)
        if caminho.exists():
            os.link(caminho, anterior, follow_symlinks=False)
        os.replace(temporario, caminho)
        try:
            sincronizar(caminho.parent)
        except OSError:
            if anterior.exists():
                os.replace(anterior, caminho)
            else:
                caminho.unlink()
            raise
    finally:
        temporario.unlink(missing_ok=True)
        anterior.unlink(missing_ok=True)


class LogPrivado(RotatingFileHandler):
    """Cria arquivos de log com modo restrito, inclusive após rotação."""

    def _open(self):
        fd = os.open(self.baseFilename, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW,
                     0o600)
        try:
            os.fchmod(fd, 0o600)
            return os.fdopen(fd, "a", encoding="utf-8")
        except OSError:
            os.close(fd)
            raise


def configurar_log() -> None:
    """Registra eventos locais com rotação."""
    log = logging.getLogger("passvault")
    if log.handlers:
        return
    with tratar_io():
        pasta = pasta_xdg("XDG_STATE_HOME", ".local/state")
        pasta_privada(pasta)
        handler = LogPrivado(pasta / "passvault.log", maxBytes=1024**2, backupCount=2)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


@dataclass(frozen=True)
class Backup:
    """Informações públicas de uma cópia cifrada."""

    caminho: Path
    data: datetime
    tamanho: int


class Armazenamento:
    """Controla os arquivos de um único cofre."""

    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or pasta_xdg("XDG_DATA_HOME", ".local/share")
        self.cofre = self.pasta / "vault.enc"
        self.anterior = self.pasta / "vault.enc.bak"
        self.backups = self.pasta / "backups"
        self._lock: int | None = None

    def adquirir(self) -> None:
        """Obtém o lock durante toda a vida do aplicativo ou da migração."""
        if self._lock is not None:
            return
        with tratar_io():
            pasta_privada(self.pasta)
            fd = os.open(self.pasta / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise InstanciaAberta("O PassVault já está aberto em outra janela.") from None
            except OSError:
                os.close(fd)
                raise
            self._lock = fd

    def liberar(self) -> None:
        """Libera o lock sem remover seu inode."""
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None

    def ler(self) -> bytes:
        """Lê o cofre atual."""
        with tratar_io():
            try:
                return ler_privado(self.cofre)
            except FileNotFoundError:
                raise SemCofre("Cofre ainda não criado.") from None

    def gravar(self, dados: bytes) -> None:
        """Preserva a versão anterior e substitui o cofre atomicamente."""
        if len(dados) > MAX_ARQUIVO:
            raise VaultCorrupted()
        with tratar_io():
            pasta_privada(self.pasta)
            if self.cofre.exists():
                escrever_atomico(self.anterior, self.ler())
            escrever_atomico(self.cofre, dados)
            logging.getLogger("passvault").info("Gravação.")

    def listar(self) -> list[Backup]:
        """Lista as cópias datadas, mais recentes primeiro."""
        with tratar_io():
            if not self.backups.exists():
                return []
            pasta_privada(self.backups)
            resultado = []
            for caminho in sorted(self.backups.iterdir(), reverse=True):
                if not re.fullmatch(r"vault-\d{8}-\d{6}\.enc", caminho.name):
                    continue
                info = caminho.lstat()
                if stat.S_ISREG(info.st_mode):
                    with suppress(ValueError):
                        data = datetime.strptime(caminho.stem[6:], "%Y%m%d-%H%M%S")
                        resultado.append(Backup(caminho, data, info.st_size))
            return resultado

    def criar_backup(self) -> Path:
        """Salva uma cópia cifrada e mantém as cinco mais recentes."""
        with tratar_io():
            dados = self.ler()
            pasta_privada(self.backups)
            copias = self.listar()
            data = datetime.now().replace(microsecond=0)
            if copias:
                data = max(data, copias[0].data + timedelta(seconds=1))
            destino = self.backups / f"vault-{data:%Y%m%d-%H%M%S}.enc"
            escrever_atomico(destino, dados)
            for copia in copias[MAX_BACKUPS - 1:]:
                copia.caminho.unlink()
            sincronizar(self.backups)
            logging.getLogger("passvault").info("Backup.")
            return destino

    def ler_backup(self, caminho: Path) -> bytes:
        """Restringe a seleção aos backups conhecidos."""
        if caminho != self.anterior and caminho not in [item.caminho for item in self.listar()]:
            raise ErroArmazenamento("Backup indisponível.")
        with tratar_io():
            return ler_privado(caminho)

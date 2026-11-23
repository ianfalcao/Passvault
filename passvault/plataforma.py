"""Integração com os serviços nativos do sistema operacional."""

import ctypes
import errno
import os
import stat
import sys
import time
from pathlib import Path

from .errors import ErroArmazenamento, InstanciaAberta

WINDOWS = os.name == "nt"


def _xdg(variavel: str, padrao: str) -> Path:
    base = Path(os.getenv(variavel, ""))
    return (base if base.is_absolute() else Path.home() / padrao) / "passvault"


def pasta_dados() -> Path:
    if override := os.getenv("PASSVAULT_HOME"):
        return Path(override).expanduser().absolute()
    if WINDOWS:
        return Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData/Local") / "PassVault"
    return _xdg("XDG_DATA_HOME", ".local/share")


def pasta_config() -> Path:
    return pasta_dados()


def pasta_logs() -> Path:
    if WINDOWS or os.getenv("PASSVAULT_HOME"):
        return pasta_dados() / "logs"
    return _xdg("XDG_STATE_HOME", ".local/state")


def caminho_legado_padrao() -> Path:
    nomes = ["my/4.json", "4.json"]
    if WINDOWS:
        nomes.extend(["Documents/4.json", "Downloads/4.json"])
    candidatos = [Path.home() / nome for nome in nomes]
    return next((p for p in candidatos if p.is_file()), candidatos[0])


def verificar_tipo(caminho: Path, diretorio: bool = False) -> None:
    """Aceita um destino novo ou do tipo esperado, sem redirecionamentos."""
    try:
        info = caminho.lstat()
    except FileNotFoundError:
        return
    tipo = stat.S_ISDIR if diretorio else stat.S_ISREG
    if not tipo(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ErroArmazenamento("O caminho selecionado contém um vínculo ou tipo inválido.")


def verificar_interno(base: Path, caminho: Path) -> None:
    verificar_tipo(base, diretorio=True)
    for pasta in caminho.relative_to(base).parents:
        verificar_tipo(base / pasta, diretorio=True)
    if not caminho.resolve().is_relative_to(base.resolve()):
        raise ErroArmazenamento("O arquivo está fora da pasta de dados.")
    verificar_tipo(caminho)


def abrir_regular(caminho: Path, flags: int) -> int:
    verificar_tipo(caminho)
    for nome in ("O_BINARY", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, nome, 0)
    fd = os.open(caminho, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ErroArmazenamento("Selecione um arquivo regular.")
    except BaseException:
        os.close(fd)
        raise
    return fd


def proteger(fd: int, modo: int = 0o600) -> None:
    if not WINDOWS:
        os.fchmod(fd, modo)


def pasta_privada(pasta: Path) -> None:
    verificar_tipo(pasta, diretorio=True)
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not WINDOWS:
        fd = os.open(pasta, getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            proteger(fd, 0o700)
        finally:
            os.close(fd)


def sincronizar(pasta: Path) -> None:
    if not WINDOWS:
        fd = os.open(pasta, getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def substituir(origem: Path, destino: Path) -> None:
    for tentativa in range(5):
        try:
            os.replace(origem, destino)
            return
        except PermissionError:
            if not WINDOWS or tentativa == 4:
                raise
            time.sleep(0.04 * (tentativa + 1))


def travar_instancia(fd: int) -> None:
    try:
        if WINDOWS:
            import msvcrt
            if not os.fstat(fd).st_size:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            raise
        raise InstanciaAberta("O PassVault já está aberto em outra janela.") from None


def destravar_instancia(fd: int) -> None:
    try:
        if WINDOWS:
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def preparar_windows() -> None:
    if not WINDOWS:
        return
    from contextlib import suppress
    with suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PassVault.App.1")
    with suppress(AttributeError, OSError):
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    with suppress(AttributeError, OSError):
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    with suppress(AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()


def caps_lock() -> bool:
    return WINDOWS and bool(ctypes.windll.user32.GetKeyState(0x14) & 1)


def resource_path(nome: str) -> Path:
    pacote = Path(__file__).parent
    if hasattr(sys, "_MEIPASS"):
        pacote = Path(sys._MEIPASS) / "passvault"
    return pacote / "assets" / nome


def erro_fatal(titulo: str, texto: str) -> None:
    if WINDOWS:
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
    elif sys.stderr:
        print(texto, file=sys.stderr)

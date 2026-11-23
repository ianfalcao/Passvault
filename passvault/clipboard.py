"""Cópia local com prazo de expiração, sem segredos em argv."""

import hashlib
import hmac
import secrets
import os
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from typing import Callable

from . import plataforma as so
from .clipboard_windows import ApiWindows, ClipboardWindows
from .constants import MS_CLIPBOARD


class Clipboard:
    """Gerencia apenas as cópias iniciadas pelo aplicativo."""

    def __init__(self, janela: tk.Misc, avisar: Callable[[str], None],
                 api: ApiWindows | None = None) -> None:
        self.janela = janela
        self.avisar = avisar
        self._temporizador: str | None = None
        self._win = None
        if so.WINDOWS or api is not None:
            try:
                self._win = ClipboardWindows(janela.winfo_id(), api)
            except (OSError, AttributeError):
                pass
        self._wl = None if so.WINDOWS else shutil.which("wl-copy")
        self._processo: subprocess.Popen | None = None
        self._marca: bytes | None = None
        self._sal = secrets.token_bytes(32)
        self._modo = ""

    def _wayland(self, limpar: bool, dados: bytes = b"") -> bool:
        if not self._wl:
            return False
        try:
            if limpar:
                if self._processo is None or self._processo.poll() is not None:
                    self._processo = None
                    return True
                subprocess.run([self._wl, "--clear"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=3, check=True)
            else:
                # O compositor pode exigir uma superfície gráfica temporária em memória.
                montagens = Path("/proc/self/mountinfo").read_text().splitlines()
                if not any(l.split()[4] == "/dev/shm" and l.split(" - ")[1].startswith("tmpfs ")
                           for l in montagens):
                    return False
                # A entrada anônima e pesquisável dispensa uma cópia do segredo em disco.
                with os.fdopen(os.memfd_create("passvault-clipboard"), "w+b") as entrada:
                    entrada.write(dados)
                    entrada.seek(0)
                    self._processo = subprocess.Popen(
                        [self._wl, "--foreground", "--sensitive", "--type", "text/plain"],
                        stdin=entrada, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        env={**os.environ, "TMPDIR": "/dev/shm"})
                try:
                    self._processo.wait(timeout=.15)
                except subprocess.TimeoutExpired:
                    return True
                self._processo = None
                return False
            if self._processo:
                try:
                    self._processo.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    self._processo.terminate()
                    self._processo.wait(timeout=1)
                self._processo = None
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def copiar(self, senha: str, rotulo: str = "Senha") -> None:
        """Copia a senha por stdin no Wayland ou pelo Tk."""
        self.limpar()
        if self._win and self._win.copiar(senha):
            self._modo = "windows"
            mensagem = f"{rotulo} na área de transferência. Limpeza em 30 s."
        elif self._wayland(False, senha.encode()):
            self._modo = "wayland"
            mensagem = f"{rotulo} na área de transferência. Limpeza em 30 s."
        else:
            try:
                self.janela.clipboard_clear()
                self.janela.clipboard_append(senha)
            except tk.TclError:
                self.avisar("Não foi possível copiar para a área de transferência.")
                return
            self._marca = hmac.digest(self._sal, senha.encode(), hashlib.sha256)
            if self._win:
                self._win.sequencia = self._win.api.GetClipboardSequenceNumber()
            self._modo = "tk"
            mensagem = "Cópia via Tk. A limpeza em 30 s pode não sobreviver ao fechamento."
        self._temporizador = self.janela.after(MS_CLIPBOARD, self.limpar)
        self.avisar(mensagem)

    def limpar(self) -> None:
        """Cancela o prazo e descarta a cópia durante lock ou saída."""
        if self._temporizador is not None:
            self.janela.after_cancel(self._temporizador)
            self._temporizador = None
        if not self._modo:
            return
        if self._modo == "windows" or self._modo == "tk" and self._win:
            sucesso = self._win.limpar()
        elif self._modo == "wayland":
            sucesso = self._wayland(True)
        else:
            try:
                atual = self.janela.clipboard_get()
            except tk.TclError:
                atual = None
            try:
                if atual is not None and hmac.compare_digest(
                        self._marca, hmac.digest(self._sal, atual.encode(), hashlib.sha256)):
                    self.janela.clipboard_clear()
                sucesso = True
            except tk.TclError:
                sucesso = False
        if sucesso:
            self._marca = None
            self._modo = ""
        else:
            self.avisar("Falha ao limpar a área de transferência. Limpe-a manualmente.")

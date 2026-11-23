"""Cópia local com prazo de expiração, sem segredos em argv."""

import os
import shutil
import subprocess
import tkinter as tk
from pathlib import Path
from typing import Callable

from .constants import MS_CLIPBOARD


class Clipboard:
    """Gerencia apenas as cópias iniciadas pelo aplicativo."""

    def __init__(self, janela: tk.Misc, avisar: Callable[[str], None]) -> None:
        self.janela = janela
        self.avisar = avisar
        self._temporizador: str | None = None
        self._wl = shutil.which("wl-copy")
        self._modo = ""

    def _wayland(self, limpar: bool, dados: bytes = b"") -> bool:
        if not self._wl:
            return False
        try:
            if limpar:
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
                    subprocess.run([self._wl, "--sensitive", "--type", "text/plain"],
                                   stdin=entrada, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=3, check=True,
                                   env={**os.environ, "TMPDIR": "/dev/shm"})
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def copiar(self, senha: str) -> None:
        """Copia a senha por stdin no Wayland ou pelo Tk."""
        self.limpar()
        if self._wayland(False, senha.encode()):
            self._modo = "wayland"
            mensagem = "Senha copiada. Limpeza em 30 s."
        else:
            try:
                self.janela.clipboard_clear()
                self.janela.clipboard_append(senha)
            except tk.TclError:
                self.avisar("Não foi possível copiar para a área de transferência.")
                return
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
        if self._modo == "wayland":
            sucesso = self._wayland(True)
        else:
            try:
                self.janela.clipboard_clear()
                sucesso = True
            except tk.TclError:
                sucesso = False
        if sucesso:
            self._modo = ""
        else:
            self.avisar("Falha ao limpar a área de transferência. Limpe-a manualmente.")

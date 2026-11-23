"""Clipboard Win32 com transferência de ownership e controle de sequência."""

import ctypes as c
import time
from ctypes import wintypes as w


class ApiWindows:
    """Assinaturas Win32 explícitas para preservar handles de 64 bits."""

    def __init__(self) -> None:
        user = c.WinDLL("user32", use_last_error=True)
        kernel = c.WinDLL("kernel32", use_last_error=True)
        funcoes = (
            (user, "OpenClipboard", [w.HWND], w.BOOL),
            (user, "CloseClipboard", [], w.BOOL),
            (user, "EmptyClipboard", [], w.BOOL),
            (user, "SetClipboardData", [w.UINT, w.HANDLE], w.HANDLE),
            (user, "GetClipboardSequenceNumber", [], w.DWORD),
            (user, "RegisterClipboardFormatW", [w.LPCWSTR], w.UINT),
            (kernel, "GlobalAlloc", [w.UINT, c.c_size_t], w.HGLOBAL),
            (kernel, "GlobalLock", [w.HGLOBAL], c.c_void_p),
            (kernel, "GlobalUnlock", [w.HGLOBAL], w.BOOL),
            (kernel, "GlobalFree", [w.HGLOBAL], w.HGLOBAL),
        )
        for lib, nome, args, retorno in funcoes:
            func = getattr(lib, nome)
            func.argtypes, func.restype = args, retorno
            setattr(self, nome, func)


class ClipboardWindows:
    def __init__(self, janela: int, api: ApiWindows | None = None) -> None:
        self.janela = janela
        self.api = api or ApiWindows()
        self.sequencia: int | None = None

    def _abrir(self) -> bool:
        for i in range(10):
            if self.api.OpenClipboard(self.janela):
                return True
            if i < 9:
                time.sleep(0.02)
        return False

    def _publicar(self, formato: int, dados: bytes) -> bool:
        handle = self.api.GlobalAlloc(2, len(dados))
        if not handle:
            return False
        try:
            ptr = self.api.GlobalLock(handle)
            if not ptr:
                return False
            try:
                c.memmove(ptr, dados, len(dados))
            finally:
                self.api.GlobalUnlock(handle)
            if not self.api.SetClipboardData(formato, handle):
                return False
            handle = None  # O sistema é dono do bloco a partir desta chamada.
            return True
        finally:
            if handle:
                self.api.GlobalFree(handle)

    def copiar(self, texto: str) -> bool:
        if not self._abrir():
            return False
        try:
            if not self.api.EmptyClipboard():
                return False
            for nome in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard",
                         "ExcludeClipboardContentFromMonitorProcessing"):
                formato = self.api.RegisterClipboardFormatW(nome)
                if formato:
                    self._publicar(formato, bytes(4))
            if not self._publicar(13, texto.encode("utf-16-le") + bytes(2)):
                return False
            self.sequencia = self.api.GetClipboardSequenceNumber()
            return True
        finally:
            self.api.CloseClipboard()

    def limpar(self) -> bool:
        if not self._abrir():
            return False
        try:
            if self.sequencia == self.api.GetClipboardSequenceNumber():
                if not self.api.EmptyClipboard():
                    return False
            self.sequencia = None
            return True
        finally:
            self.api.CloseClipboard()

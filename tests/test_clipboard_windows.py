"""API Win32 simulada, sem acesso ao clipboard pessoal."""
import ctypes
import os
import unittest
from unittest.mock import Mock, patch

from passvault.clipboard import Clipboard
from passvault.clipboard_windows import ClipboardWindows


class ApiFalsa:
    def __init__(self):
        self.blocos = {}
        self.formatos = {}
        self.seq = 1
        self.CloseClipboard = Mock()
        self.OpenClipboard = Mock(return_value=True)
        self.GlobalUnlock = Mock()
        self.GlobalFree = Mock()
        self.RegisterClipboardFormatW = Mock(side_effect=(21, 22, 23))

    def GlobalAlloc(self, flags, n):
        buf = ctypes.create_string_buffer(n)
        ptr = ctypes.addressof(buf)
        self.blocos[ptr] = buf
        return ptr

    def GlobalLock(self, handle):
        return handle

    def SetClipboardData(self, formato, handle):
        self.formatos[formato] = self.blocos[handle].raw
        self.seq += 1
        return handle

    def EmptyClipboard(self):
        self.formatos.clear()
        self.seq += 1
        return True

    def GetClipboardSequenceNumber(self):
        return self.seq


class ClipboardNativo(unittest.TestCase):
    def test_unicode_formatos_e_ownership(self):
        api = ApiFalsa()
        clip = ClipboardWindows(987, api)
        self.assertTrue(clip.copiar("fictícia🔐"))
        api.OpenClipboard.assert_called_with(987)
        self.assertEqual(api.formatos[13], "fictícia🔐\0".encode("utf-16le"))
        self.assertEqual([api.formatos[i] for i in (21, 22, 23)], [bytes(4)] * 3)
        api.GlobalFree.assert_not_called()
        self.assertTrue(clip.limpar())
        self.assertEqual(api.formatos, {})

    def test_alteracao_externa_preservada(self):
        api = ApiFalsa()
        clip = ClipboardWindows(987, api)
        clip.copiar("teste")
        api.seq += 1
        api.formatos[13] = b"outro"
        self.assertTrue(clip.limpar())
        self.assertEqual(api.formatos[13], b"outro")

    def test_falha_de_transferencia_libera_memoria(self):
        api = ApiFalsa()
        api.SetClipboardData = Mock(return_value=0)
        self.assertFalse(ClipboardWindows(987, api).copiar("teste"))
        self.assertEqual(api.GlobalFree.call_count, 4)
        api.CloseClipboard.assert_called_once()

    def test_fallback_e_concorrencia(self):
        api = ApiFalsa()
        api.OpenClipboard.return_value = False
        janela = Mock()
        with patch("time.sleep"), patch("passvault.clipboard.so.WINDOWS", True):
            clip = Clipboard(janela, Mock(), api)
            clip.copiar("teste")
            self.assertEqual(api.OpenClipboard.call_count, 10)
            janela.clipboard_append.assert_called_once_with("teste")
            api.OpenClipboard.return_value = True
            api.seq += 1
            clip.limpar()
            self.assertEqual(janela.clipboard_clear.call_count, 1)


@unittest.skipUnless(os.name == "nt" and
                     os.getenv("PASSVAULT_CLIPBOARD_ISOLADO") == "1",
                     "Requer clipboard descartável em um runner Windows")
class ClipboardWindowsIntegracao(unittest.TestCase):
    def test_prazo_conteudo_externo_e_limpeza_imediata(self):
        import tkinter as tk

        raiz = tk.Tk()
        raiz.withdraw()
        clip = Clipboard(raiz, lambda mensagem: None)
        try:
            clip.copiar("amostra-sintética")
            self.assertEqual(clip._modo, "windows")
            self.assertEqual(raiz.clipboard_get(), "amostra-sintética")
            fim = tk.BooleanVar(raiz)
            raiz.after(31000, lambda: fim.set(True))
            raiz.wait_variable(fim)
            self.assertEqual(clip._modo, "")
            self.assertFalse(ctypes.windll.user32.IsClipboardFormatAvailable(13))
            clip.copiar("segunda-amostra")
            raiz.clipboard_clear()
            raiz.clipboard_append("conteúdo posterior")
            raiz.update()
            clip.limpar()
            self.assertEqual(raiz.clipboard_get(), "conteúdo posterior")
            clip.copiar("terceira-amostra")
            clip.limpar()
            self.assertFalse(ctypes.windll.user32.IsClipboardFormatAvailable(13))
        finally:
            clip.limpar()
            raiz.clipboard_clear()
            raiz.destroy()

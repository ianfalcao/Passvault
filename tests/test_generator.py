"""Testes do gerador e do prazo de cópia sem usar o clipboard real."""

import os
import string
import unittest
from unittest.mock import Mock, patch

from passvault.clipboard import Clipboard
from passvault.errors import DadosInvalidos
from passvault.generator import Opcoes


class Gerador(unittest.TestCase):
    def test_comprimento_e_classes(self) -> None:
        for n in (8, 24, 128):
            senha = Opcoes(n).gerar()
            self.assertEqual(len(senha), n)
            for grupo in (string.ascii_uppercase, string.ascii_lowercase,
                          string.digits, string.punctuation):
                self.assertTrue(set(senha) & set(grupo))

    def test_exclusao_de_ambiguos(self) -> None:
        opc = Opcoes(128, maiusculas=False, simbolos=False, evitar_ambiguos=True)
        self.assertFalse(set(opc.gerar()) & set("Il1O0o" + string.ascii_uppercase))
        self.assertTrue(opc.entropia() > Opcoes(8).entropia())

    def test_validacao(self) -> None:
        for opcoes in (Opcoes(7), Opcoes(129), Opcoes(24, False, False, False, False)):
            with self.assertRaises(DadosInvalidos):
                opcoes.gerar()

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "memfd_create"), "Wayland Linux")
    def test_clipboard_wayland(self) -> None:
        janela, aviso = Mock(), Mock()
        janela.after.return_value = "prazo"
        with patch("passvault.clipboard.shutil.which", return_value="wl-copy"), \
                patch("passvault.clipboard.subprocess.run") as executar:
            import subprocess
            lido = []
            processo = Mock()
            processo.poll.return_value = None
            processo.wait.side_effect = [subprocess.TimeoutExpired("wl-copy", .15), 0]
            def iniciar(args, **opcoes):
                self.assertNotIn("FAKE", args)
                lido.append(opcoes["stdin"].read())
                return processo

            clip = Clipboard(janela, aviso)
            with patch("passvault.clipboard.subprocess.Popen", side_effect=iniciar):
                clip.copiar("FAKE")
            self.assertEqual(lido, [b"FAKE"])
            janela.after.assert_called_once_with(30000, clip.limpar)
            clip.limpar()
            self.assertEqual(executar.call_args.args[0], ["wl-copy", "--clear"])
            janela.after_cancel.assert_called_once_with("prazo")

    def test_clipboard_tk(self) -> None:
        janela, aviso = Mock(), Mock()
        with patch("passvault.clipboard.so.WINDOWS", False), \
                patch("passvault.clipboard.shutil.which", return_value=None):
            clip = Clipboard(janela, aviso)
            clip.copiar("FAKE")
            janela.clipboard_append.assert_called_once_with("FAKE")
            self.assertIn("fechamento", aviso.call_args.args[0])
            janela.clipboard_get.return_value = "FAKE"
            clip.limpar()
            self.assertEqual(janela.clipboard_clear.call_count, 2)

"""Testes do gerador e do prazo de cópia sem usar o clipboard real."""

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

    def test_clipboard_wayland(self) -> None:
        janela, aviso = Mock(), Mock()
        janela.after.return_value = "prazo"
        with patch("passvault.clipboard.shutil.which", return_value="wl-copy"), \
                patch("passvault.clipboard.subprocess.run") as executar:
            lido = []
            def observar(argumentos: list[str], **opcoes: object) -> None:
                if "--clear" not in argumentos:
                    lido.append(opcoes["stdin"].read())

            executar.side_effect = observar
            clip = Clipboard(janela, aviso)
            clip.copiar("FAKE")
            argumentos, opcoes = executar.call_args
            self.assertNotIn("FAKE", argumentos[0])
            self.assertEqual(lido, [b"FAKE"])
            janela.after.assert_called_once_with(30000, clip.limpar)
            clip.limpar()
            self.assertEqual(executar.call_args.args[0], ["wl-copy", "--clear"])
            janela.after_cancel.assert_called_once_with("prazo")

    def test_clipboard_tk(self) -> None:
        janela, aviso = Mock(), Mock()
        with patch("passvault.clipboard.shutil.which", return_value=None):
            clip = Clipboard(janela, aviso)
            clip.copiar("FAKE")
            janela.clipboard_append.assert_called_once_with("FAKE")
            self.assertIn("fechamento", aviso.call_args.args[0])
            clip.limpar()
            self.assertEqual(janela.clipboard_clear.call_count, 2)

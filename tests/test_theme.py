import unittest

from passvault.ui.theme import CLARA, ESCURA, contraste, escolher_fonte


class Temas(unittest.TestCase):
    def test_contraste_textos(self):
        for p in (CLARA, ESCURA):
            for fundo in (p.superficie, p.fundo, p.alternada, p.selecao):
                self.assertGreaterEqual(contraste(p.texto, fundo), 4.5)
            for texto in (p.secundario, p.perigo, p.sucesso, p.aviso):
                self.assertGreaterEqual(contraste(texto, p.superficie), 4.5)
            for fundo in (p.destaque, p.hover, p.perigo):
                self.assertGreaterEqual(contraste(p.sobre_botao, fundo), 4.5)

    def test_fallback_fontes(self):
        self.assertEqual(escolher_fonte({"B"}, ("A", "B"), "C"), "B")
        self.assertEqual(escolher_fonte(set(), ("A", "B"), "C"), "C")

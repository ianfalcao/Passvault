import tempfile
import unittest
from pathlib import Path

from passvault.config import Config


class Preferencias(unittest.TestCase):
    def test_leitura_gravacao_e_corrupcao(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            cfg = Config("escuro", "1000x700+20+40", 570, "importacao-sintetica.json")
            cfg.salvar(pasta)
            self.assertEqual(Config.ler(pasta), cfg)
            for dados in (b"nao-json", b"null", b'{"tema":[],"geometria":false}', b"x"*65537):
                (pasta / "config.json").write_bytes(dados)
                self.assertEqual(Config.ler(pasta), Config())

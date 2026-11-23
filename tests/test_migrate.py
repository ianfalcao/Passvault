"""Migração de um legado sintético, incluindo BOM e objetos adjacentes."""

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from passvault.errors import DadosInvalidos, LegacyParseError
from passvault.migrate import analisar, importar, repair_json_text
from passvault.storage import Armazenamento
from passvault.vault import Cofre


class Migracao(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.pasta = Path(temp.name)
        self.origem = self.pasta / "legado.json"
        shutil.copyfile(Path(__file__).parent / "fixtures/legacy_broken.json", self.origem)
        self.origem.chmod(0o777)
        self.cofre = Cofre(Armazenamento(self.pasta / "dados"))

    def test_reparo_bom_e_strings(self) -> None:
        texto = self.origem.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith("\ufeff"))
        contas = json.loads(repair_json_text(texto))["accounts"]
        self.assertEqual(contas[0]["campo"], 'literal } { e "aspas"')
        with self.assertRaises(LegacyParseError):
            repair_json_text('{"accounts":[{"aninhado":[{} {}]}]}')

    def test_analise_sem_gravar(self) -> None:
        a = analisar(self.origem)
        self.assertTrue(a.reparado)
        self.assertEqual([c.username for c in a.contas], ["teste@exemplo.invalid", "beta",
                                                         "123", "delta", "delta"])
        self.assertEqual([c.password for c in a.contas], ["SENHA-FAKE-123", "0000",
                                                         "CHAVE-FAKE", "COD-FAKE", "OUTRO-FAKE"])
        self.assertEqual(a.contas[1].extra, {"email": "reserva"})
        self.assertEqual(json.loads(a.contas[2].extra["info"]), {"a": 1})
        self.assertEqual((len(a.contas), a.ignoradas, a.duplicadas([])), (5, 1, 1))
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(self.origem.stat().st_mode), 0o777)
        self.assertEqual(list(self.pasta.iterdir()), [self.origem])

    def test_importacao_backup_e_repeticao(self) -> None:
        a = analisar(self.origem)
        original = self.origem.read_bytes()
        self.cofre.criar("mestra-fake")
        copia = importar(a, self.cofre)
        for arq in (copia, self.origem):
            self.assertEqual(arq.read_bytes(), original)
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(arq.stat().st_mode), 0o600)
        self.cofre.bloquear()
        self.cofre.desbloquear("mestra-fake")
        self.assertTrue(a.repetida(self.cofre))
        with self.assertRaises(DadosInvalidos):
            importar(analisar(self.origem), self.cofre)
        importar(analisar(self.origem), self.cofre, permitir_repetida=True)
        self.assertEqual(len(self.cofre.buscar("")), 10)

    def test_json_irrecuperavel(self) -> None:
        self.origem.write_text('{"accounts":[\n{]')
        with self.assertRaisesRegex(LegacyParseError, "linha 2, coluna"):
            analisar(self.origem)
        self.assertEqual(list(self.pasta.iterdir()), [self.origem])

    def test_origem_mudou(self) -> None:
        self.cofre.criar("mestra-fake")
        a = analisar(self.origem)
        self.origem.write_text('{"accounts":[]}')
        with self.assertRaises(DadosInvalidos):
            importar(a, self.cofre)
        self.assertEqual(self.cofre.buscar(""), [])
        self.assertFalse(list(self.pasta.glob("*.bak-*")))

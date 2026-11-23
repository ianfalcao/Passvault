"""Armazenamento isolado em diretórios temporários."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from passvault.errors import ErroArmazenamento, InstanciaAberta, SemCofre, VaultCorrupted
from passvault.storage import Armazenamento
from passvault.vault import Cofre


class Disco(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.d = Armazenamento(Path(temp.name) / "dados")
        self.d.adquirir()
        self.addCleanup(self.d.liberar)

    def test_permissoes_e_correcao(self) -> None:
        self.d.gravar(b"a")
        self.assertEqual(stat.S_IMODE(self.d.pasta.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.d.cofre.stat().st_mode), 0o600)
        self.d.cofre.chmod(0o666)
        with self.assertLogs("passvault", "WARNING"):
            self.d.ler()
        self.assertEqual(stat.S_IMODE(self.d.cofre.stat().st_mode), 0o600)

    def test_backup_anterior(self) -> None:
        self.d.gravar(b"a")
        self.d.gravar(b"b")
        self.assertEqual(self.d.anterior.read_bytes(), b"a")
        self.assertEqual(stat.S_IMODE(self.d.anterior.stat().st_mode), 0o600)

    def test_erro_de_substituicao_remove_temporarios(self) -> None:
        self.d.gravar(b"original")
        substituir = os.replace

        def simular(origem: Path, destino: Path) -> None:
            if destino == self.d.cofre:
                raise OSError
            substituir(origem, destino)

        with patch("passvault.storage.os.replace", simular), self.assertRaises(ErroArmazenamento):
            self.d.gravar(b"novo")
        self.assertEqual(self.d.ler(), b"original")
        self.assertFalse(list(self.d.pasta.glob(".pv-*")))

    def test_falha_de_fsync_do_diretorio_reverte(self) -> None:
        self.d.gravar(b"original")
        with patch("passvault.storage.sincronizar", side_effect=[None, OSError()]):
            with self.assertRaises(ErroArmazenamento):
                self.d.gravar(b"novo")
        self.assertEqual(self.d.ler(), b"original")
        self.assertFalse(list(self.d.pasta.glob(".pv-*")))

    def test_inexistente_e_corrompido(self) -> None:
        with self.assertRaises(SemCofre):
            self.d.ler()
        self.d.gravar(b"invalido")
        with self.assertRaises(VaultCorrupted):
            Cofre(self.d).desbloquear("fictícia")

    def test_instancia_unica(self) -> None:
        outra = Armazenamento(self.d.pasta)
        with self.assertRaises(InstanciaAberta):
            outra.adquirir()
        self.d.liberar()
        outra.adquirir()
        outra.liberar()

    def test_retencao_e_colisoes(self) -> None:
        for i in range(7):
            self.d.gravar(bytes([i]))
            self.d.criar_backup()
        copias = self.d.listar()
        self.assertEqual([self.d.ler_backup(c.caminho) for c in copias],
                         [bytes([i]) for i in range(6, 1, -1)])
        self.assertTrue(all(stat.S_IMODE(c.caminho.stat().st_mode) == 0o600 for c in copias))

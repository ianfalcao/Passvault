"""Isolamento de pastas e operações nativas."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from passvault import plataforma as so
from passvault.errors import ErroArmazenamento, InstanciaAberta
from passvault.storage import Armazenamento


class Plataforma(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)

    def test_caminhos(self):
        with patch.dict(os.environ, {"PASSVAULT_HOME": str(self.base)}):
            self.assertEqual(so.pasta_dados(), self.base)
            self.assertEqual(so.pasta_config(), self.base)
            self.assertEqual(so.pasta_logs(), self.base / "logs")
        with patch.dict(os.environ, {"PASSVAULT_HOME": "", "LOCALAPPDATA": str(self.base),
                                     "XDG_DATA_HOME": str(self.base), "XDG_STATE_HOME": str(self.base)}):
            with patch.object(so, "WINDOWS", True):
                self.assertEqual(so.pasta_logs(), self.base / "PassVault/logs")
            with patch.object(so, "WINDOWS", False):
                self.assertEqual(so.pasta_dados(), self.base / "passvault")
                self.assertEqual(so.pasta_logs(), self.base / "passvault")

    def test_candidato_legado(self):
        with patch.object(Path, "home", return_value=self.base), patch.object(so, "WINDOWS", True):
            self.assertEqual(so.caminho_legado_padrao(), self.base / "my/4.json")
            pasta = self.base / "Documents"
            pasta.mkdir()
            (pasta / "4.json").touch()
            self.assertEqual(so.caminho_legado_padrao(), pasta / "4.json")

    def test_lock_windows_em_um_byte(self):
        api = Mock()
        api.LK_NBLCK, api.LK_UNLCK = 2, 0
        fd = os.open(self.base / ".lock", os.O_CREAT | os.O_RDWR)
        with patch.object(so, "WINDOWS", True), patch.dict(sys.modules, msvcrt=api):
            so.proteger(fd)
            so.travar_instancia(fd)
            api.locking.assert_called_with(fd, 2, 1)
            self.assertEqual(os.fstat(fd).st_size, 1)
            self.assertEqual(os.lseek(fd, 0, 1), 0)
            api.locking.side_effect = PermissionError(13, "ocupado")
            with self.assertRaises(InstanciaAberta):
                so.travar_instancia(fd)
            api.locking.side_effect = None
            so.destravar_instancia(fd)
            api.locking.assert_called_with(fd, 0, 1)

    def test_retry_somente_permissionerror(self):
        with patch.object(so, "WINDOWS", True), patch("time.sleep"), patch("os.replace") as mover:
            mover.side_effect = [PermissionError(), PermissionError(), None]
            so.substituir(self.base / "a", self.base / "b")
            self.assertEqual(mover.call_count, 3)
            mover.side_effect = PermissionError()
            with self.assertRaises(PermissionError):
                so.substituir(self.base / "a", self.base / "b")
            self.assertEqual(mover.call_count, 8)

    def test_sem_hardlink(self):
        d = Armazenamento(self.base)
        with patch("os.link", side_effect=AssertionError):
            d.gravar(b"um")
            d.gravar(b"dois")
        self.assertEqual(d.anterior.read_bytes(), b"um")

    @unittest.skipIf(os.name == "nt", "Links podem exigir privilégio no Windows")
    def test_rejeita_links(self):
        d = Armazenamento(self.base / "dados")
        d.gravar(b"exemplo")
        fora = self.base / "externo"
        fora.mkdir()
        d.backups.symlink_to(fora, target_is_directory=True)
        with self.assertRaises(ErroArmazenamento):
            d.criar_backup()
        self.assertEqual(list(fora.iterdir()), [])
        d.anterior.symlink_to(fora / "inexistente")
        with self.assertRaises(ErroArmazenamento):
            d.gravar(b"outro")
        self.assertEqual(d.ler(), b"exemplo")

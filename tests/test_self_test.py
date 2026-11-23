import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Autoteste(unittest.TestCase):
    def test_isolado_sem_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, DISPLAY="", WAYLAND_DISPLAY="", PASSVAULT_HOME=tmp)
            for opcao in ("--version", "--self-test"):
                p = subprocess.run([sys.executable, "-B", "-m", "passvault", opcao],
                                   capture_output=True, env=env, timeout=30)
                self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

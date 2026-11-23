"""Parâmetros do formato, limites e caminhos da aplicação."""

import os
from pathlib import Path

MAGIC = b"PVLT"
VERSAO = 1
MAX_ARQUIVO = 16 * 1024 * 1024
MAX_CABECALHO = 4096
MAX_MEMORIA = 64 * 1024 * 1024
N, R, P = 2**15, 8, 1
TAMANHO_CHAVE = 32
SEGUNDOS_BLOQUEIO = 300
MS_VERIFICACAO = 5_000
MS_CLIPBOARD = 30_000
MAX_BACKUPS = 5
LEGADO = Path("/home/ianfalcao/my/4.json")


def pasta_xdg(variavel: str, padrao: str) -> Path:
    """Resolve a pasta privada conforme a convenção XDG."""
    valor = Path(os.getenv(variavel, ""))
    base = valor if valor.is_absolute() else Path.home() / padrao
    return base / "passvault"

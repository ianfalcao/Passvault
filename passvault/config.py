"""Preferências locais de apresentação, sem informações de contas."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from . import plataforma as so
from .errors import ErroPassVault
from .storage import escrever_atomico, tratar_io

GEOMETRIA = re.compile(r"(\d{2,5})x(\d{2,5})([+-]\d{1,6})([+-]\d{1,6})")


@dataclass
class Config:
    tema: str = "sistema"
    geometria: str = ""
    posicao_sash: int = 0
    ultimo_import: str = ""

    @classmethod
    def ler(cls, pasta: Path | None = None) -> "Config":
        pasta = pasta or so.pasta_config()
        caminho = pasta / "config.json"
        cfg = cls()
        try:
            so.verificar_interno(pasta, caminho)
            import os
            with os.fdopen(so.abrir_regular(caminho, os.O_RDONLY), "rb") as f:
                bruto = f.read(65537)
            if len(bruto) > 65536:
                return cfg
            obj = json.loads(bruto)
            if not isinstance(obj, dict):
                return cfg
            if obj.get("tema") in ("claro", "escuro", "sistema"):
                cfg.tema = obj["tema"]
            geom = obj.get("geometria")
            if isinstance(geom, str) and GEOMETRIA.fullmatch(geom):
                cfg.geometria = geom
            sash = obj.get("posicao_sash")
            if type(sash) is int and 0 < sash < 65536:
                cfg.posicao_sash = sash
            if isinstance(obj.get("ultimo_import"), str):
                cfg.ultimo_import = obj["ultimo_import"]
        except (OSError, ValueError, ErroPassVault, RecursionError):
            pass
        return cfg

    def salvar(self, pasta: Path | None = None) -> None:
        pasta = pasta or so.pasta_config()
        with tratar_io():
            so.pasta_privada(pasta)
            escrever_atomico(pasta / "config.json", json.dumps(asdict(self)).encode())

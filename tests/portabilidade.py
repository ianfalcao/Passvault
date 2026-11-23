"""Produz ou abre exclusivamente o cofre sintético trocado entre runners da CI."""

import sys
from pathlib import Path

from passvault.storage import Armazenamento
from passvault.vault import Cofre, Conta


def conferir(pasta: Path, criar: bool) -> None:
    disco = Armazenamento(pasta)
    cofre = Cofre(disco)
    disco.adquirir()
    try:
        if criar:
            cofre.criar("senha-ci-fictícia")
            cofre.adicionar(Conta("Portabilidade", "usuário", "sintética"))
        else:
            cofre.desbloquear("senha-ci-fictícia")
            (conta,) = cofre.buscar("portabilidade")
            if (conta.username, conta.password) != ("usuário", "sintética"):
                raise ValueError("Dados sintéticos divergentes.")
    finally:
        cofre.bloquear()
        disco.liberar()


if __name__ == "__main__":
    acao, destino = sys.argv[1:]
    conferir(Path(destino), acao == "criar")

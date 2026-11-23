"""Geração local de senhas com aleatoriedade criptográfica."""

import math
import secrets
import string
from dataclasses import dataclass

from .errors import DadosInvalidos


@dataclass(frozen=True)
class Opcoes:
    """Comprimento e alfabetos para a geração."""

    comprimento: int = 24
    maiusculas: bool = True
    minusculas: bool = True
    digitos: bool = True
    simbolos: bool = True
    evitar_ambiguos: bool = False

    def classes(self) -> list[str]:
        """Seleciona e valida os alfabetos disjuntos."""
        if type(self.comprimento) is not int or not 8 <= self.comprimento <= 128:
            raise DadosInvalidos("Escolha um comprimento entre 8 e 128.")
        grupos = [(self.maiusculas, string.ascii_uppercase),
                  (self.minusculas, string.ascii_lowercase),
                  (self.digitos, string.digits), (self.simbolos, string.punctuation)]
        ativos = [grupo for usar, grupo in grupos if usar]
        if not ativos:
            raise DadosInvalidos("Selecione pelo menos uma classe de caracteres.")
        if self.evitar_ambiguos:
            return ["".join(c for c in grupo if c not in "Il1O0o") for grupo in ativos]
        return ativos

    def gerar(self) -> str:
        """Amostra uniformemente entre as senhas que satisfazem as classes."""
        classes = self.classes()
        alfabeto = "".join(classes)
        while True:
            senha = "".join(secrets.choice(alfabeto) for _ in range(self.comprimento))
            if all(any(c in grupo for c in senha) for grupo in classes):
                return senha

    def entropia(self) -> float:
        """Calcula log2 da quantidade de senhas válidas por inclusão-exclusão."""
        classes = self.classes()
        total = 0
        for mascara in range(1 << len(classes)):
            livres = sum(len(g) for i, g in enumerate(classes) if not mascara & (1 << i))
            total += (-1) ** mascara.bit_count() * livres ** self.comprimento
        return math.log2(total)

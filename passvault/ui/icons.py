"""Ícones vetoriais desenhados diretamente pelo Canvas."""

import tkinter as tk


def desenhar(c: tk.Canvas, nome: str, cor: str, x: int, y: int, escala: float = 1) -> None:
    def forma(tipo: str, pontos: tuple, **estilo: object) -> None:
        coords = [v * escala + (x if i % 2 == 0 else y) for i, v in enumerate(pontos)]
        getattr(c, "create_" + tipo)(*coords, **estilo)

    def linha(*pontos: int) -> None:
        forma("line", pontos, fill=cor, width=2, capstyle="round", joinstyle="round")

    def oval(*pontos: int) -> None:
        forma("oval", pontos, outline=cor, width=2)

    if nome == "busca":
        oval(2, 2, 13, 13)
        linha(12, 12, 18, 18)
    elif nome in ("olho", "ocultar"):
        linha(1, 10, 5, 5, 10, 3, 15, 5, 19, 10, 15, 15, 10, 17, 5, 15, 1, 10)
        oval(8, 8, 12, 12)
        if nome == "ocultar":
            linha(2, 2, 18, 18)
    elif nome in ("copiar", "backup"):
        forma("rectangle", (6, 6, 17, 18), outline=cor, width=2)
        linha(3, 13, 3, 2, 13, 2)
    elif nome == "bloquear":
        oval(5, 1, 15, 14)
        forma("rectangle", (3, 9, 17, 18), fill=c.cget("background"), outline=cor, width=2)
    elif nome == "adicionar":
        linha(10, 2, 10, 18)
        linha(2, 10, 18, 10)
    elif nome == "excluir":
        linha(2, 5, 18, 5)
        linha(5, 5, 6, 18, 14, 18, 15, 5)
        linha(8, 2, 12, 2)
    elif nome == "chave":
        oval(2, 2, 11, 11)
        linha(10, 10, 18, 18, 18, 14)
    elif nome == "escudo":
        linha(10, 1, 18, 4, 17, 12, 14, 16, 10, 19, 6, 16, 3, 12, 2, 4, 10, 1)
    elif nome == "sol":
        oval(5, 5, 15, 15)
        for pontos in ((10, 0, 10, 3), (10, 17, 10, 20), (0, 10, 3, 10), (17, 10, 20, 10)):
            linha(*pontos)
    elif nome == "lua":
        linha(13, 2, 8, 3, 4, 7, 3, 12, 6, 17, 12, 18, 17, 15, 12, 14, 9, 10, 9, 6, 13, 2)
    else:
        linha(3, 10, 16, 10, 11, 5)
        linha(16, 10, 11, 15)

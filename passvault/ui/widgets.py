"""Controles reutilizáveis e navegáveis por teclado."""

import tkinter as tk
from tkinter import font, ttk
from typing import Callable

from .icons import desenhar
from .theme import Tema


def abreviar(texto: str, largura: int, fonte: font.Font) -> str:
    """Mantém o começo legível em uma única linha, dentro da largura disponível."""
    if fonte.measure(texto) <= largura:
        return texto
    inicio, fim = 0, len(texto)
    while inicio < fim:
        meio = (inicio + fim + 1) // 2
        if fonte.measure(texto[:meio] + "…") <= largura:
            inicio = meio
        else:
            fim = meio - 1
    return texto[:inicio] + "…"


class Cartao(ttk.Frame):
    def __init__(self, pai: tk.Misc, **kw) -> None:
        super().__init__(pai, style="Cartao.TFrame", padding=16, **kw)


class BotaoPrimario(ttk.Button):
    def __init__(self, pai: tk.Misc, **kw) -> None:
        super().__init__(pai, style="Primario.TButton", **kw)


class BotaoSecundario(ttk.Button):
    pass


class BotaoPerigo(ttk.Button):
    def __init__(self, pai: tk.Misc, **kw) -> None:
        super().__init__(pai, style="Perigo.TButton", **kw)


class BotaoIcone(tk.Canvas):
    def __init__(self, pai: tk.Misc, tema: Tema, nome: str, rotulo: str,
                 comando: Callable[[], object]) -> None:
        self.tema, self.nome, self.rotulo = tema, nome, rotulo
        super().__init__(pai, height=max(34, tema.pequena.metrics("linespace") + 12),
                         width=36 + tema.pequena.measure(rotulo), takefocus=1,
                         highlightthickness=1, borderwidth=0, cursor="hand2")
        self.bind("<Configure>", lambda _: self.redesenhar())
        for evento in ("<ButtonRelease-1>", "<Return>", "<space>"):
            self.bind(evento, lambda _: comando() or "break")
        self.redesenhar()

    def redesenhar(self) -> None:
        p = self.tema.p
        self.configure(bg=p.superficie, highlightcolor=p.destaque, highlightbackground=p.borda)
        self.delete("all")
        meio = int(self.cget("height")) // 2
        desenhar(self, self.nome, p.texto, 6, meio - 9, .9)
        self.create_text(29, meio, text=self.rotulo, anchor="w", fill=p.texto,
                         font=self.tema.pequena)


class CampoBusca(ttk.Frame):
    def __init__(self, pai: tk.Misc, var: tk.StringVar) -> None:
        super().__init__(pai)
        self.entrada = ttk.Entry(self, textvariable=var)
        self.entrada.pack(side="left", fill="both", expand=True)
        dica = ttk.Label(self.entrada, text="Buscar por serviço, usuário ou tag…",
                         style="Secundario.TLabel")
        def atualizar(*_) -> None:
            if var.get() or self.entrada.focus_get() == self.entrada:
                dica.place_forget()
            else:
                dica.place(x=10, rely=.5, anchor="w")
        dica.bind("<Button-1>", lambda _: self.entrada.focus_set())
        self.entrada.bind("<FocusIn>", atualizar)
        self.entrada.bind("<FocusOut>", atualizar)
        token = var.trace_add("write", atualizar)
        self.bind("<Destroy>", lambda e: var.trace_remove("write", token) if e.widget == self else None)
        ttk.Button(self, text="Limpar", command=lambda: var.set("")).pack(side="left", padx=4)
        atualizar()


class BarraForca(tk.Canvas):
    def __init__(self, pai: tk.Misc, tema: Tema) -> None:
        self.tema, self.bits = tema, 0.0
        super().__init__(pai, height=32, width=180, highlightthickness=0)
        self.bind("<Configure>", lambda _: self.redesenhar())

    def definir(self, bits: float) -> None:
        self.bits = bits
        self.redesenhar()

    def redesenhar(self) -> None:
        p = self.tema.p
        cor, nome = ((p.perigo, "Fraca") if self.bits < 50 else
                     (p.aviso, "Média") if self.bits < 80 else (p.sucesso, "Forte"))
        self.configure(bg=p.superficie)
        self.delete("all")
        largura = max(1, self.winfo_width())
        self.create_rectangle(0, 2, largura, 6, fill=p.borda, outline="")
        self.create_rectangle(0, 2, largura * min(1, self.bits / 100), 6, fill=cor, outline="")
        self.create_text(0, 19, anchor="w", text=nome, fill=p.texto, font=self.tema.pequena)


class Toast(ttk.Label):
    def __init__(self, pai: tk.Misc, texto: str) -> None:
        super().__init__(pai, text=texto, padding=(16, 10), relief="solid", wraplength=420)
        self.place(relx=1, rely=1, x=-16, y=-38, anchor="se")
        self.prazo = self.after(3000, self.destroy)

    def destroy(self) -> None:
        self.after_cancel(self.prazo)
        super().destroy()


def centralizar(janela: tk.Toplevel, pai: tk.Misc) -> None:
    janela.update_idletasks()
    w, h = janela.winfo_reqwidth(), janela.winfo_reqheight()
    x = pai.winfo_rootx() + (pai.winfo_width() - w) // 2
    y = pai.winfo_rooty() + (pai.winfo_height() - h) // 2
    janela.geometry(f"+{max(0, min(x, janela.winfo_screenwidth()-w))}"
                    f"+{max(0, min(y, janela.winfo_screenheight()-h))}")


class Confirmar(tk.Toplevel):
    def __init__(self, pai: tk.Misc, texto: str) -> None:
        super().__init__(pai)
        self.resultado = False
        self.title("Confirmar operação")
        self.transient(pai)
        self.resizable(False, False)
        caixa = Cartao(self)
        caixa.pack(fill="both", expand=True)
        ttk.Label(caixa, text=texto, wraplength=430).pack(pady=(0, 16))
        cancelar = BotaoSecundario(caixa, text="Cancelar", command=self.destroy)
        cancelar.pack(side="left")
        BotaoPerigo(caixa, text="Confirmar", command=self.aceitar).pack(side="right")
        self.bind("<Escape>", lambda _: self.destroy())
        centralizar(self, pai)
        self.grab_set()
        cancelar.focus_set()

    def aceitar(self) -> None:
        self.resultado = True
        self.destroy()


class EstadoVazio(ttk.Frame):
    def __init__(self, pai: tk.Misc, tema: Tema, comando: Callable) -> None:
        super().__init__(pai, padding=12)
        self.tema = tema
        self.icone = tk.Canvas(self, width=32, height=32, highlightthickness=0)
        self.icone.pack()
        self.icone.configure(bg=tema.p.superficie)
        desenhar(self.icone, "escudo", tema.p.destaque, 4, 4, 1.2)
        self.texto = ttk.Label(self, style="Subtitulo.TLabel")
        self.texto.pack(pady=6)
        self.botao = BotaoPrimario(self, text="Adicionar primeira conta", command=comando)

    def apresentar(self, ha_contas: bool) -> None:
        self.texto.configure(text="Nenhuma conta encontrada" if ha_contas else "Nenhuma conta ainda")
        if ha_contas:
            self.botao.pack_forget()
        else:
            self.botao.pack()
        self.place(relx=.5, rely=.5, anchor="center")

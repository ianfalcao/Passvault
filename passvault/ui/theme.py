"""Paletas, tipografia e estilos de toda a interface."""

import os
import subprocess
import tkinter as tk
from dataclasses import dataclass
from tkinter import font, ttk

from .. import plataforma as so


@dataclass(frozen=True)
class Paleta:
    fundo: str
    superficie: str
    alternada: str
    texto: str
    secundario: str
    borda: str
    destaque: str
    hover: str
    suave: str
    perigo: str
    sucesso: str
    aviso: str
    selecao: str
    sobre_botao: str


CLARA = Paleta("#F4F6FB", "#FFFFFF", "#EEF2F8", "#111827", "#596273", "#DCE3EE",
               "#2964D9", "#1E5BD6", "#E8F0FE", "#B52E33", "#116643", "#80510D",
               "#DCE9FF", "#FFFFFF")
ESCURA = Paleta("#0F172A", "#172033", "#1E293B", "#E5E7EB", "#A5B2C5", "#45536A",
                "#5B9CFF", "#7AB0FF", "#1E3A5F", "#F87171", "#34D399", "#F4C76C",
                "#23406B", "#101827")


def contraste(a: str, b: str) -> float:
    def luminancia(cor: str) -> float:
        rgb = [int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * peso for v, peso in zip(linear, (.2126, .7152, .0722)))
    menor, maior = sorted((luminancia(a), luminancia(b)))
    return (maior + .05) / (menor + .05)


def tema_sistema() -> str:
    if so.WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return "claro" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "escuro"
        except OSError:
            return "claro"
    if "dark" in os.getenv("GTK_THEME", "").lower():
        return "escuro"
    try:
        valor = subprocess.check_output(["gsettings", "get", "org.gnome.desktop.interface",
                                         "color-scheme"], stderr=subprocess.DEVNULL, timeout=.4)
        if b"dark" in valor:
            return "escuro"
    except (OSError, subprocess.SubprocessError):
        pass
    return "claro"


def escolher_fonte(disponiveis: set[str], preferencias: tuple[str, ...], padrao: str) -> str:
    return next((f for f in preferencias if f in disponiveis), padrao)


class Tema:
    def __init__(self, raiz: tk.Tk, escolha: str) -> None:
        self.raiz = raiz
        self.estilo = ttk.Style(raiz)
        self.estilo.theme_use("clam")
        familias = set(font.families(raiz))
        fonte = font.nametofont("TkDefaultFont")
        corpo = escolher_fonte(familias, ("Segoe UI",) if so.WINDOWS else
                              ("Noto Sans", "DejaVu Sans"), fonte.actual("family"))
        mono = escolher_fonte(familias, ("Cascadia Mono", "Consolas", "DejaVu Sans Mono"),
                              font.nametofont("TkFixedFont").actual("family"))
        fonte.configure(family=corpo, size=10)
        font.nametofont("TkTextFont").configure(family=corpo, size=10)
        self.titulo = font.Font(raiz, family=corpo, size=18, weight="bold")
        self.subtitulo = font.Font(raiz, family=corpo, size=11, weight="bold")
        self.pequena = font.Font(raiz, family=corpo, size=9)
        self.mono = font.Font(raiz, family=mono, size=10)
        self.aplicar(escolha)

    def aplicar(self, escolha: str) -> None:
        modo = tema_sistema() if escolha == "sistema" else escolha
        p = self.p = ESCURA if modo == "escuro" else CLARA
        e = self.estilo
        self.raiz.configure(bg=p.fundo)
        e.configure(".", background=p.superficie, foreground=p.texto, bordercolor=p.borda,
                    lightcolor=p.superficie, darkcolor=p.borda, focuscolor=p.destaque,
                    troughcolor=p.alternada, selectbackground=p.selecao, selectforeground=p.texto,
                    font="TkDefaultFont")
        e.configure("Fundo.TFrame", background=p.fundo)
        e.configure("Cartao.TFrame", relief="solid", borderwidth=1)
        e.configure("Titulo.TLabel", font=self.titulo)
        e.configure("Subtitulo.TLabel", font=self.subtitulo)
        e.configure("Secundario.TLabel", foreground=p.secundario, font=self.pequena)
        e.configure("Erro.TLabel", foreground=p.perigo)
        e.configure("Aviso.TLabel", foreground=p.aviso)
        for estilo in ("TEntry", "TCombobox", "TSpinbox"):
            e.configure(estilo, fieldbackground=p.superficie, foreground=p.texto,
                        insertcolor=p.texto, padding=(7, 5), arrowcolor=p.texto)
            e.map(estilo, fieldbackground=[("readonly", p.alternada)],
                  foreground=[("readonly", p.texto)], bordercolor=[("focus", p.destaque)])
        for nome, fundo, fg, ativo in (("TButton", p.alternada, p.texto, p.selecao),
                                       ("Primario.TButton", p.destaque, p.sobre_botao, p.hover),
                                       ("Perigo.TButton", p.perigo, p.sobre_botao, p.perigo)):
            e.configure(nome, background=fundo, foreground=fg, padding=(14, 8), anchor="center")
            e.map(nome, background=[("disabled", p.alternada), ("active", ativo)],
                  foreground=[("disabled", p.secundario)], bordercolor=[("focus", p.destaque)])
        e.configure("Treeview", background=p.superficie, fieldbackground=p.superficie,
                    rowheight=max(34, font.nametofont("TkDefaultFont").metrics("linespace") + 12))
        e.map("Treeview", background=[("selected", p.selecao)], foreground=[("selected", p.texto)])
        e.configure("Treeview.Heading", background=p.alternada, foreground=p.texto,
                    padding=6, relief="flat")
        e.map("Treeview.Heading", background=[("active", p.selecao)])
        e.configure("TScrollbar", arrowcolor=p.texto, background=p.alternada)
        e.map("TCheckbutton", background=[("active", p.alternada)])
        for opt, valor in (("background", p.superficie), ("foreground", p.texto),
                           ("selectBackground", p.selecao), ("selectForeground", p.texto)):
            self.raiz.option_add(f"*TCombobox*Listbox.{opt}", valor)
        self.colorir(self.raiz)

    def colorir(self, widget: tk.Misc) -> None:
        p = self.p
        if isinstance(widget, tk.Text):
            widget.configure(bg=p.superficie, fg=p.texto, insertbackground=p.texto,
                             selectbackground=p.selecao, selectforeground=p.texto,
                             highlightcolor=p.destaque, highlightbackground=p.borda, relief="flat")
        elif isinstance(widget, tk.Menu):
            widget.configure(bg=p.superficie, fg=p.texto, activebackground=p.selecao,
                             activeforeground=p.texto)
        elif isinstance(widget, ttk.Treeview):
            widget.tag_configure("alternada", background=p.alternada)
        elif isinstance(widget, tk.Canvas) and hasattr(widget, "redesenhar"):
            widget.redesenhar()
        for filho in widget.winfo_children():
            self.colorir(filho)

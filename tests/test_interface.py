"""Fluxo gráfico sintético para runners com display, incluindo escalas de fonte."""

import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from passvault.app import Aplicacao
from passvault.config import Config
from passvault.dialogs import Editor, Gerar, Importar, Restaurar, TrocarSenha
from passvault.storage import Armazenamento
from passvault.ui.widgets import Confirmar


def controles(pai):
    for filho in pai.winfo_children():
        yield filho
        yield from controles(filho)


def botao(pai, texto):
    return next(w for w in controles(pai) if isinstance(w, ttk.Button) and w.cget("text") == texto)


@unittest.skipUnless(os.getenv("PASSVAULT_TESTAR_GUI") == "1", "Requer display de teste")
class Interface(unittest.TestCase):
    def test_fluxos_e_escalas(self):
        for escala in (1, 1.5, 2):
            with self.subTest(escala=escala), tempfile.TemporaryDirectory() as tmp:
                self.exercitar(Path(tmp), escala)

    def exercitar(self, pasta, escala):
        raiz = tk.Tk()
        raiz.tk.call("tk", "scaling", escala * 96 / 72)
        disco = Armazenamento(pasta / "dados")
        disco.adquirir()
        app = None
        falhas = []
        try:
            app = Aplicacao(raiz, disco)
            raiz.report_callback_exception = lambda tipo, exc, tb: falhas.append(exc)
            raiz.update()
            entradas = [w for w in controles(raiz) if isinstance(w, ttk.Entry)]
            for entrada in entradas:
                entrada.insert(0, "mestra-fictícia")
            botao(raiz, "Criar cofre").invoke()
            raiz.update()
            self.assertTrue(app.cofre.aberto)
            if falhas:
                raise falhas[0]
            editor = Editor(app)
            self.assertTrue(editor.botoes["Salvar"].instate(["disabled"]))
            editor.servico.insert(0, "Café fictício " * 12)
            editor.url.insert(0, "https://exemplo.invalid/" + "a"*180)
            editor.notas.insert("end", "Nota fictícia. " * 300)
            gerador = Gerar(app, editor, editor.senha)
            gerador.usar()
            self.assertEqual(len(editor.senha.get()), 24)
            editor.botoes["Salvar"].invoke()
            raiz.update()
            if falhas:
                raise falhas[0]
            self.assertIn("…", app.titulo_conta.cget("text"))
            self.assertTrue(app.segredo.winfo_ismapped())
            self.assertLess(app.segredo.winfo_rooty() + app.segredo.winfo_height(),
                            raiz.winfo_rooty() + raiz.winfo_height())
            primeiro = app.selecionada()
            self.assertTrue(primeiro)
            app._busca.set("cafe")
            self.assertEqual(app.selecionada().id, primeiro.id)
            app.mudar_tema("escuro")
            self.assertEqual(Config.ler(disco.pasta).tema, "escuro")
            app.mudar_tema("claro")
            app.backup()
            raiz.after(30, lambda: next(c for c in controles(raiz)
                                         if isinstance(c, Confirmar)).aceitar())
            app.excluir()
            self.assertFalse(app.cofre.buscar(""))
            restaurar = Restaurar(app)
            restaurar.senha.insert(0, "mestra-fictícia")
            with patch.object(app, "confirmar", return_value=True):
                restaurar.restaurar()
            self.assertEqual(app.selecionada().id, primeiro.id)
            origem = pasta / "legado.json"
            origem.write_text('{"accounts":[{"service":"Exemplo sintético"}]}', encoding="utf-8")
            with patch("passvault.dialogs.caminho_legado_padrao", return_value=origem):
                importar = Importar(app)
            self.assertTrue(importar.botoes["Importar"].instate(["disabled"]))
            importar.analisar()
            self.assertFalse(importar.botoes["Importar"].instate(["disabled"]))
            with patch.object(app, "confirmar", return_value=True), patch("tkinter.messagebox.showinfo"):
                importar.importar()
            trocar = TrocarSenha(app)
            for campo, texto in ((trocar.atual, "mestra-fictícia"), (trocar.nova, "nova-fictícia"),
                                 (trocar.confirmacao, "nova-fictícia")):
                campo.insert(0, texto)
            with patch.object(app, "confirmar", return_value=True):
                trocar.trocar()
            app.bloquear()
            entrada = next(w for w in controles(raiz) if isinstance(w, ttk.Entry))
            entrada.insert(0, "incorreta")
            botao(raiz, "Desbloquear").invoke()
            self.assertFalse(app.cofre.aberto)
            entrada.delete(0, "end")
            entrada.insert(0, "nova-fictícia")
            botao(raiz, "Desbloquear").invoke()
            self.assertEqual(len(app.cofre.buscar("")), 2)
            raiz.update()
            if falhas:
                raise falhas[0]
        finally:
            if app:
                app.sair()
            else:
                raiz.destroy()
            disco.liberar()

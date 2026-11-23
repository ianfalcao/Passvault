"""Janela principal e ciclo de vida da sessão desktop."""

import logging
import time
import tkinter as tk
from datetime import datetime
from tkinter import font, messagebox, ttk
from typing import Callable

from . import __version__, plataforma as so
from .config import Config, GEOMETRIA
from .ui.theme import Tema, ESCURA
from .ui.widgets import (BarraForca, BotaoIcone, BotaoPrimario, CampoBusca, Cartao,
                         Confirmar, EstadoVazio, Toast, abreviar)
from .clipboard import Clipboard
from .constants import MS_VERIFICACAO, SEGUNDOS_BLOQUEIO
from .dialogs import Editor, Gerar, Importar, Restaurar, TrocarSenha, alternar, campo_senha
from .errors import DadosInvalidos, ErroPassVault
from .storage import Armazenamento, configurar_log
from .vault import Cofre, Conta, normalizar


class Aplicacao:
    """Coordena telas, operações de conta e bloqueio por inatividade."""

    def __init__(self, raiz: tk.Tk, disco: Armazenamento) -> None:
        self.raiz = raiz
        self.disco = disco
        self.cofre = Cofre(disco)
        self.clip = Clipboard(raiz, self.status)
        self._atividade = time.monotonic()
        self._geracao = 0
        self._resumo = tk.StringVar(raiz)
        self._busca = tk.StringVar(raiz)
        self._busca.trace_add("write", lambda *_: self.atualizar() if self.cofre.aberto else None)
        self.config = Config.ler(disco.pasta)
        self.paines = None
        self.toast = None
        self._ordem = "service"
        self._inversa = False
        raiz.title("PassVault")
        if so.WINDOWS:
            raiz.tk.call("tk", "scaling", raiz.winfo_fpixels("1i") / 72)
        self.tema = Tema(raiz, self.config.tema)
        self.logo = tk.PhotoImage(file=str(so.resource_path("logo.png")))
        self.icone = tk.PhotoImage(file=str(so.resource_path("passvault.png")))
        if so.WINDOWS:
            raiz.iconbitmap(str(so.resource_path("passvault.ico")))
        else:
            raiz.iconphoto(True, self.icone)
        tela_w, tela_h = raiz.winfo_screenwidth(), raiz.winfo_screenheight()
        w, h = min(1040, tela_w), min(710, tela_h)
        x, y = (tela_w - w) // 2, max(0, (tela_h - h) // 2)
        if g := GEOMETRIA.fullmatch(self.config.geometria):
            w, h, x, y = map(int, g.groups())
            w, h = min(max(640, w), tela_w), min(max(480, h), tela_h)
            x, y = max(0, min(x, tela_w - w)), max(0, min(y, tela_h - h))
        raiz.geometry(f"{w}x{h}+{x}+{y}")
        raiz.minsize(min(780, tela_w), min(540, tela_h))
        raiz.report_callback_exception = self._erro
        raiz.protocol("WM_DELETE_WINDOW", self.sair)
        raiz.bind_all("<KeyPress>", self._interacao, add="+")
        raiz.bind_all("<Button>", self._interacao, add="+")
        raiz.bind_all("<Control-l>", self._atalho_bloqueio, add="+")
        self._timer = raiz.after(MS_VERIFICACAO, self._verificar)
        self._tela_acesso()

    def _erro(self, tipo: type[BaseException], erro: BaseException, traceback: object) -> None:
        if isinstance(erro, ErroPassVault):
            texto = str(erro)
        else:
            logging.getLogger("passvault").error("Falha de operação na interface.")
            texto = "Não foi possível concluir a operação. Verifique os dados e as permissões."
        pai = self.raiz.grab_current() or self.raiz
        messagebox.showerror("PassVault", texto, parent=pai)

    def confirmar(self, texto: str, pai: tk.Misc) -> bool:
        """Invalida confirmações pendentes quando a sessão muda."""
        geracao = self._geracao
        try:
            anterior = self.raiz.grab_current()
            modal = Confirmar(pai, texto)
            self.raiz.wait_window(modal)
            if anterior and anterior.winfo_exists():
                anterior.grab_set()
            resposta = modal.resultado
            return resposta and geracao == self._geracao and bool(pai.winfo_exists())
        except tk.TclError:
            return False

    def _interacao(self, evento: tk.Event | None = None) -> None:
        self._atividade = time.monotonic()

    def _verificar(self) -> None:
        if self.cofre.aberto and time.monotonic() - self._atividade >= SEGUNDOS_BLOQUEIO:
            self.bloquear()
        self._timer = self.raiz.after(MS_VERIFICACAO, self._verificar)

    def _atalho_bloqueio(self, evento: tk.Event) -> str:
        if self.cofre.aberto:
            self.bloquear()
        return "break"

    def _limpar_tela(self) -> None:
        if self.paines and self.paines.winfo_exists():
            self.config.posicao_sash = self.paines.sashpos(0)
        self.paines = None
        self._geracao += 1
        self.raiz.configure(menu="")
        for evento in ("<Control-n>", "<Control-e>", "<Control-f>", "<F5>", "<Escape>"):
            self.raiz.unbind(evento)
        for filho in self.raiz.winfo_children():
            filho.destroy()
        # O Tk cria diálogos nativos que não constam no cadastro de widgets do tkinter.
        for nome in self.raiz.tk.splitlist(self.raiz.tk.call("winfo", "children", ".")):
            self.raiz.tk.call("destroy", nome)
        self._resumo.set("")

    def status(self, mensagem: str) -> None:
        """Publica aviso temporário ao lado da contagem e do caminho."""
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()
        self.toast = Toast(self.raiz, mensagem)

    def mudar_tema(self, modo: str) -> None:
        self.escolha_tema.set(modo)
        self.config.tema = modo
        self.tema.aplicar(modo)
        self.config.salvar(self.disco.pasta)
        if hasattr(self, "botao_tema") and self.botao_tema.winfo_exists():
            self.botao_tema.nome = "sol" if self.tema.p == ESCURA else "lua"
            self.botao_tema.redesenhar()
            self.vazio.icone.configure(bg=self.tema.p.superficie)
            self.vazio.icone.itemconfigure("all", fill=self.tema.p.destaque)

    def _tela_acesso(self) -> None:
        self._limpar_tela()
        criar = not self.disco.cofre.exists()
        quadro = Cartao(self.raiz)
        quadro.place(relx=.5, rely=.5, anchor="center")
        ttk.Label(quadro, image=self.logo).pack(anchor="center")
        ttk.Label(quadro, text="PassVault", style="Titulo.TLabel").pack()
        ttk.Label(quadro, text="Seu cofre local e cifrado", style="Secundario.TLabel").pack(
            pady=(0, 12))
        titulo = "Criar cofre" if criar else "Desbloquear"
        ttk.Label(quadro, text="Senha mestra").pack(anchor="w")
        linha = ttk.Frame(quadro)
        linha.pack(fill="x")
        senha = campo_senha(linha)
        senha.configure(width=30)
        senha.pack(side="left", fill="x", expand=True)
        olho = ttk.Button(linha, text="Mostrar", command=lambda: alternar(senha, olho))
        olho.pack(side="left", padx=(4, 0))
        confirmacao = None
        barra = None
        if criar:
            ttk.Label(quadro, text="Confirmar senha mestra").pack(anchor="w", pady=(8, 0))
            confirmacao = campo_senha(quadro)
            confirmacao.pack(fill="x")
            barra = BarraForca(quadro, self.tema)
            barra.pack(fill="x", pady=4)
            ttk.Label(quadro, text="Não há recuperação da senha mestra.",
                      style="Aviso.TLabel").pack(anchor="w")
        aviso = ttk.Label(quadro, style="Erro.TLabel", wraplength=360)
        aviso.pack(anchor="w", pady=4)

        def interagir(evento=None) -> None:
            aviso.configure(text="Caps Lock ativado." if so.caps_lock() else "")
            if barra:
                valor = senha.get()
                barra.definir(min(len(valor) * 5, len(set(valor)) * 9))

        def entrar() -> None:
            try:
                if criar:
                    if senha.get() != confirmacao.get():
                        raise DadosInvalidos("As senhas não coincidem.")
                    self.cofre.criar(senha.get())
                    confirmacao.delete(0, "end")
                else:
                    self.cofre.desbloquear(senha.get())
            except ErroPassVault as exc:
                aviso.configure(text=str(exc))
                senha.focus_set()
                return
            senha.delete(0, "end")
            self.principal()

        BotaoPrimario(quadro, text=titulo, command=entrar).pack(fill="x", pady=4)
        if self.disco.anterior.exists() or self.disco.backups.exists():
            ttk.Button(quadro, text="Restaurar backup", command=lambda: Restaurar(self)).pack()
        for campo in (senha, confirmacao):
            if campo is not None:
                campo.bind("<Return>", lambda _: entrar())
                campo.bind("<KeyRelease>", lambda e: interagir() if e.keysym != "Return" else None)
        interagir()
        senha.focus_set()

    def _menu(self) -> None:
        menu = tk.Menu(self.raiz)
        arquivo, editar, ajuda = (tk.Menu(menu, tearoff=False) for _ in range(3))
        for submenu, nome in ((arquivo, "Arquivo"), (editar, "Editar"), (ajuda, "Ajuda")):
            menu.add_cascade(label=nome, menu=submenu)
        for nome, func in (("Backup", self.backup), ("Restaurar backup", lambda: Restaurar(self)),
                           ("Importar legado", lambda: Importar(self)),
                           ("Trocar senha mestra", lambda: TrocarSenha(self)), ("Sair", self.sair)):
            arquivo.add_command(label=nome, command=func)
        atalhos = ("Ctrl+N", "Ctrl+E", "Delete", "Ctrl+C", "")
        for (nome, func), atalho in zip(self._acoes_conta(), atalhos):
            editar.add_command(label=nome, command=func, accelerator=atalho)
        exibir = tk.Menu(menu, tearoff=False)
        menu.add_cascade(label="Exibir", menu=exibir)
        self.escolha_tema = tk.StringVar(self.raiz, value=self.config.tema)
        for modo in ("claro", "escuro", "sistema"):
            exibir.add_radiobutton(label="Tema " + modo, variable=self.escolha_tema, value=modo,
                                   command=lambda m=modo: self.mudar_tema(m))
        ajuda.add_command(label="Sobre", command=lambda: messagebox.showinfo(
            "Sobre", f"PassVault {__version__}\nGerenciador local de senhas.", parent=self.raiz))
        self.raiz.configure(menu=menu)

    def _acoes_conta(self) -> tuple[tuple[str, Callable], ...]:
        return (("Adicionar", lambda: Editor(self)), ("Editar", self.editar),
                ("Excluir", self.excluir), ("Copiar senha", self.copiar),
                ("Gerar senha", lambda: Gerar(self)))

    def principal(self) -> None:
        """Monta a interface após validar a chave."""
        self._limpar_tela()
        self._interacao()
        self._menu()
        corpo = ttk.Frame(self.raiz, padding=16, style="Fundo.TFrame")
        corpo.pack(fill="both", expand=True)
        topo = ttk.Frame(corpo, padding=(12, 6))
        topo.pack(fill="x")
        self.logo_pequeno = self.logo.subsample(2)
        ttk.Label(topo, image=self.logo_pequeno).pack(side="left", padx=(0, 8))
        ttk.Label(topo, text="PassVault", style="Subtitulo.TLabel").pack(side="left")
        for nome, texto, acao in (("bloquear", "Bloquear", self.bloquear),
                                  ("backup", "Backup", self.backup)):
            BotaoIcone(topo, self.tema, nome, texto, acao).pack(side="right", padx=3)
        self.botao_tema = BotaoIcone(topo, self.tema, "sol" if self.tema.p == ESCURA else "lua",
                                     "Tema", lambda: self.mudar_tema(
                                         "claro" if self.tema.p == ESCURA else "escuro"))
        self.botao_tema.pack(side="right", padx=3)
        busca = ttk.Frame(corpo, padding=8)
        busca.pack(fill="x", pady=8)
        campo = CampoBusca(busca, self._busca)
        campo.pack(side="left", fill="x", expand=True)
        entrada = campo.entrada
        BotaoPrimario(busca, text="Nova conta", command=lambda: Editor(self)).pack(side="right")
        paines = self.paines = ttk.PanedWindow(corpo, orient="horizontal")
        paines.pack(fill="both", expand=True)
        esquerda = ttk.Frame(paines)
        direita = Cartao(paines)
        paines.add(esquerda, weight=62)
        paines.add(direita, weight=38)
        def posicionar() -> None:
            if paines.winfo_exists():
                w = paines.winfo_width()
                paines.sashpos(0, max(w // 4, min(3*w // 4, self.config.posicao_sash or int(w*.62))))
        paines.after_idle(posicionar)
        self.tabela = ttk.Treeview(esquerda, columns=("service", "username", "tags"),
                                   show="headings", selectmode="browse")
        scroll = ttk.Scrollbar(esquerda, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tabela.pack(fill="both", expand=True)
        for campo, nome in (("service", "Serviço"), ("username", "Usuário"), ("tags", "Tags")):
            self.tabela.heading(campo, text=nome, command=lambda c=campo: self.ordenar(c))
            self.tabela.column(campo, width=150, minwidth=60)
        self.vazio = EstadoVazio(self.tabela, self.tema, lambda: Editor(self))
        self.tabela.bind("<<TreeviewSelect>>", lambda _: self.detalhar())
        self.tabela.bind("<Double-1>", self._duplo)
        self.tabela.bind("<Control-c>", lambda _: self._executar(self.copiar))
        self.tabela.bind("<Delete>", lambda _: self._executar(self.excluir))
        self.contexto = tk.Menu(self.tabela, tearoff=False)
        for nome, func in (("Editar", self.editar), ("Copiar senha", self.copiar),
                           ("Excluir", self.excluir)):
            self.contexto.add_command(label=nome, command=func)
        self.tabela.bind("<Button-3>", self._contexto)
        self.titulo_conta = ttk.Label(direita, style="Titulo.TLabel", width=1)
        self.titulo_conta.pack(fill="x")
        linha_user = ttk.Frame(direita)
        linha_user.pack(fill="x")
        self.usuario = ttk.Label(linha_user, width=1)
        self.usuario.pack(side="left", fill="x", expand=True)
        BotaoIcone(linha_user, self.tema, "copiar", "Usuário",
                   lambda: self.clip.copiar(c.username, "Usuário") if
                   (c := self.selecionada()) else None).pack(side="right")
        self.titulo_conta.bind("<Configure>", lambda _: self._cabecalho_conta())
        self.usuario.bind("<Configure>", lambda _: self._cabecalho_conta())
        ttk.Label(direita, text="Senha").pack(anchor="w", pady=(12, 0))
        seg = ttk.Frame(direita)
        seg.pack(fill="x", pady=(0, 6))
        self.segredo = campo_senha(seg)
        self.segredo.configure(state="readonly", width=12)
        self.segredo.pack(side="left", fill="x", expand=True)
        self.revelar = ttk.Button(seg, text="Mostrar", width=8, command=lambda: alternar(
            self.segredo, self.revelar))
        self.revelar.pack(side="left", padx=3)
        ttk.Button(seg, text="Copiar", width=7, command=self.copiar).pack(side="left")
        self.detalhes = tk.Text(direita, wrap="word", width=30, height=12, state="disabled",
                                padx=8, pady=8, exportselection=False, font="TkDefaultFont")
        ttk.Button(direita, text="Editar", command=self.editar).pack(side="bottom", anchor="e")
        rolagem = ttk.Scrollbar(direita, command=self.detalhes.yview)
        self.detalhes.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.detalhes.pack(fill="both", expand=True)
        self.detalhes.tag_configure("rotulo", font="TkHeadingFont", spacing1=6)
        rodape = ttk.Frame(corpo, padding=6)
        rodape.pack(side="bottom", fill="x", before=paines)
        ttk.Label(rodape, textvariable=self._resumo, style="Secundario.TLabel").pack(side="left")
        local = ttk.Label(rodape, style="Secundario.TLabel", anchor="e")
        local.pack(side="right", fill="x", expand=True)
        def elidir(evento) -> None:
            nome = str(self.disco.cofre)
            while nome and self.tema.pequena.measure("…" + nome) > evento.width:
                nome = nome[1:]
            local.configure(text=nome if nome == str(self.disco.cofre) else "…" + nome)
        local.bind("<Configure>", elidir)
        self.tema.colorir(self.raiz)
        for tecla, func in (("<Control-n>", lambda: Editor(self)), ("<Control-e>", self.editar),
                            ("<Control-f>", entrada.focus_set), ("<F5>", self.recarregar),
                            ("<Escape>", lambda: self._busca.set(""))):
            self.raiz.bind(tecla, lambda _, f=func: self._executar(f))
        self._busca.set("")
        entrada.focus_set()

    def _executar(self, func: Callable[[], object]) -> str:
        self._interacao()
        func()
        return "break"

    def _duplo(self, evento: tk.Event) -> None:
        if ident := self.tabela.identify_row(evento.y):
            self.tabela.selection_set(ident)
            self.editar()

    def _contexto(self, evento: tk.Event) -> None:
        if ident := self.tabela.identify_row(evento.y):
            self.tabela.selection_set(ident)
            try:
                self.contexto.tk_popup(evento.x_root, evento.y_root)
            finally:
                self.contexto.grab_release()

    def atualizar(self, selecionar: str | None = None) -> None:
        """Reaplica filtro e ordenação, preservando a seleção por UUID."""
        selecao = self.tabela.selection()
        ident = selecionar or (selecao[0] if selecao else "")
        contas = self.cofre.buscar(self._busca.get())

        def chave(c: Conta) -> str:
            valor = ", ".join(c.tags) if self._ordem == "tags" else getattr(c, self._ordem)
            return normalizar(valor)

        self.tabela.delete(*self.tabela.get_children())
        for i, c in enumerate(sorted(contas, key=chave, reverse=self._inversa)):
            self.tabela.insert("", "end", iid=c.id, tags=("alternada",) if i % 2 else (), values=(c.service, c.username,
                                                           ", ".join(c.tags)))
        if contas:
            self.vazio.place_forget()
            ident = ident if self.tabela.exists(ident) and ident else self.tabela.get_children()[0]
            self.tabela.selection_set(ident)
            self.tabela.see(ident)
        else:
            self.vazio.apresentar(bool(self.cofre.conteudo.contas))
        total = len(self.cofre.conteudo.contas)
        self._resumo.set(f"{len(contas)} de {total} contas")
        self.detalhar()

    def selecionar_salva(self, identificador: str) -> None:
        """Exibe a conta salva mesmo que a edição a retire do filtro atual."""
        if not any(c.id == identificador for c in self.cofre.buscar(self._busca.get())):
            self._busca.set("")
        self.atualizar(identificador)
        self.status("Conta salva.")

    def ordenar(self, campo: str) -> None:
        """Alterna a ordenação pelo cabeçalho."""
        self._inversa = not self._inversa if campo == self._ordem else False
        self._ordem = campo
        self.atualizar()

    def selecionada(self) -> Conta | None:
        """Obtém a conta selecionada pela identidade persistente."""
        selecao = self.tabela.selection()
        return self.cofre.obter(selecao[0]) if selecao else None

    def _cabecalho_conta(self) -> None:
        if self.cofre.aberto:
            conta = self.selecionada()
            for widget, valor, fonte in (
                    (self.titulo_conta, conta.service if conta else "", self.tema.titulo),
                    (self.usuario, conta.username if conta else "", font.nametofont("TkDefaultFont"))):
                widget.configure(text=abreviar(valor, max(1, widget.winfo_width() - 4), fonte))

    def detalhar(self) -> None:
        """Renderiza detalhes e redefine a máscara ao trocar de seleção."""
        if not self.cofre.aberto:
            return
        c = self.selecionada()
        self._cabecalho_conta()
        self.revelar.configure(text="Mostrar")
        self.segredo.configure(state="normal", show="•")
        self.segredo.delete(0, "end")
        self.segredo.insert(0, c.password if c else "")
        self.segredo.configure(state="readonly")
        self.detalhes.configure(state="normal")
        self.detalhes.delete("1.0", "end")
        if c:
            for nome, valor in (("Serviço", c.service), ("Usuário", c.username), ("URL", c.url),
                                ("Notas", c.notes), ("Tags", ", ".join(c.tags)),
                                ("Criação", self._data(c.created_at)),
                                ("Atualização", self._data(c.updated_at))):
                self.detalhes.insert("end", nome + "\n", "rotulo")
                self.detalhes.insert("end", (valor or "—") + "\n")
        self.detalhes.configure(state="disabled")

    @staticmethod
    def _data(valor: str) -> str:
        return datetime.fromisoformat(valor).astimezone().strftime("%d/%m/%Y %H:%M:%S")

    def editar(self) -> None:
        """Abre o editor da seleção."""
        if c := self.selecionada():
            Editor(self, c)

    def excluir(self) -> None:
        """Confirma a exclusão pelo nome visível e remove pelo UUID."""
        if (c := self.selecionada()) and self.confirmar(f"Excluir a conta de {c.service}?",
                                                       self.raiz):
            self.cofre.excluir(c.id)
            self.atualizar()

    def copiar(self) -> None:
        """Envia a senha selecionada ao clipboard temporário."""
        if c := self.selecionada():
            self.clip.copiar(c.password)

    def backup(self) -> None:
        """Cria uma cópia cifrada datada."""
        caminho = self.disco.criar_backup()
        self.status(f"Backup criado em {caminho}")

    def recarregar(self) -> None:
        """Revalida o arquivo atual e atualiza a lista."""
        self.cofre.recarregar()
        self.atualizar()
        self.status("Cofre recarregado.")

    def bloquear(self) -> None:
        """Encerra a sessão e fecha os diálogos abertos."""
        self.cofre.bloquear()
        self._busca.set("")
        self._tela_acesso()
        self.clip.limpar()

    def sair(self) -> None:
        """Limpa o material da sessão e encerra a janela."""
        self.cofre.bloquear()
        self.clip.limpar()
        self.raiz.after_cancel(self._timer)
        try:
            self.config.geometria = self.raiz.geometry()
            if self.paines and self.paines.winfo_exists():
                self.config.posicao_sash = self.paines.sashpos(0)
            self.config.salvar(self.disco.pasta)
        except ErroPassVault:
            logging.getLogger("passvault").warning("Falha ao salvar preferências.")
        finally:
            self.raiz.destroy()


def principal() -> int:
    """Inicia a aplicação e mantém o lock até o fechamento da interface."""
    disco = Armazenamento()
    try:
        raiz = tk.Tk()
    except tk.TclError:
        raise RuntimeError("Interface indisponível.") from None
    raiz.withdraw()
    app = None
    try:
        disco.adquirir()
        configurar_log()
        app = Aplicacao(raiz, disco)
        raiz.deiconify()
        raiz.mainloop()
    except ErroPassVault:
        raiz.destroy()
        raise
    finally:
        if app is not None:
            app.cofre.bloquear()
        disco.liberar()
    return 0

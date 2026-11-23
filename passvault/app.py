"""Janela principal e ciclo de vida da sessão desktop."""

import logging
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

from . import __version__
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
        self._mensagem = tk.StringVar(raiz)
        self._resumo = tk.StringVar(raiz)
        self._prazo_status: str | None = None
        self._busca = tk.StringVar(raiz)
        self._busca.trace_add("write", lambda *_: self.atualizar() if self.cofre.aberto else None)
        self._ordem = "service"
        self._inversa = False
        raiz.title("PassVault")
        raiz.geometry("1000x650")
        raiz.minsize(860, 560)
        ttk.Style(raiz).theme_use("clam")
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
            resposta = messagebox.askyesno("PassVault", texto, parent=pai)
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
        self._geracao += 1
        self.raiz.configure(menu="")
        for evento in ("<Control-n>", "<Control-e>", "<Control-f>", "<F5>", "<Escape>"):
            self.raiz.unbind(evento)
        for filho in self.raiz.winfo_children():
            filho.destroy()
        # O Tk cria diálogos nativos que não constam no cadastro de widgets do tkinter.
        for nome in self.raiz.tk.splitlist(self.raiz.tk.call("winfo", "children", ".")):
            self.raiz.tk.call("destroy", nome)
        if self._prazo_status is not None:
            self.raiz.after_cancel(self._prazo_status)
            self._prazo_status = None
        self._mensagem.set("")
        self._resumo.set("")

    def status(self, mensagem: str) -> None:
        """Publica aviso temporário ao lado da contagem e do caminho."""
        if self._prazo_status is not None:
            self.raiz.after_cancel(self._prazo_status)
        self._mensagem.set(mensagem)
        self._prazo_status = self.raiz.after(30000, self._apagar_status)

    def _apagar_status(self) -> None:
        self._mensagem.set("")
        self._prazo_status = None

    def _tela_acesso(self) -> None:
        self._limpar_tela()
        criar = not self.disco.cofre.exists()
        quadro = ttk.Frame(self.raiz, padding=24)
        quadro.place(relx=0.5, rely=0.48, anchor="center")
        titulo = "Criar cofre" if criar else "Desbloquear"
        ttk.Label(quadro, text=titulo, font="TkHeadingFont").pack(anchor="w", pady=(0, 12))
        ttk.Label(quadro, text="Senha mestra").pack(anchor="w")
        senha = campo_senha(quadro)
        senha.configure(width=44)
        senha.pack(fill="x")
        confirmar = None
        if criar:
            ttk.Label(quadro, text="Confirmar senha mestra").pack(anchor="w", pady=(8, 0))
            confirmar = campo_senha(quadro)
            confirmar.pack(fill="x")
            ttk.Label(quadro, text="Não há recuperação da senha mestra.").pack(anchor="w", pady=4)
            aviso = ttk.Label(quadro, text="Mínimo de 8 caracteres. Prefira 12 ou mais.")
            aviso.pack(anchor="w")
            senha.bind("<KeyRelease>", lambda _: aviso.configure(
                text="Prefira 12 caracteres ou mais." if len(senha.get()) < 12 else ""))

        def entrar() -> None:
            valor = senha.get()
            if criar and confirmar is not None:
                if valor != confirmar.get():
                    raise DadosInvalidos("As senhas não coincidem.")
                self.cofre.criar(valor)
                senha.delete(0, "end")
                confirmar.delete(0, "end")
            else:
                senha.delete(0, "end")
                self.cofre.desbloquear(valor)
            del valor
            self.principal()

        ttk.Button(quadro, text=titulo, command=entrar).pack(fill="x", pady=(12, 4))
        if self.disco.anterior.exists() or self.disco.backups.exists():
            ttk.Button(quadro, text="Restaurar backup", command=lambda: Restaurar(self)).pack()
        for widget in (senha, confirmar):
            if widget is not None:
                widget.bind("<Return>", lambda _: entrar())
        ttk.Label(self.raiz, textvariable=self._mensagem, padding=6).pack(side="bottom")
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
        for nome, func in self._acoes_conta():
            editar.add_command(label=nome, command=func)
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
        corpo = ttk.Frame(self.raiz, padding=10)
        corpo.pack(fill="both", expand=True)
        busca = ttk.Frame(corpo)
        busca.pack(fill="x")
        ttk.Label(busca, text="Buscar").pack(side="left", padx=(0, 8))
        entrada = ttk.Entry(busca, textvariable=self._busca)
        entrada.pack(side="left", fill="x", expand=True)
        barra = ttk.Frame(corpo)
        barra.pack(fill="x", pady=8)
        for nome, func in (*self._acoes_conta(), ("Backup", self.backup),
                           ("Bloquear", self.bloquear)):
            ttk.Button(barra, text=nome, command=func).pack(side="left", padx=(0, 4))
        paines = ttk.PanedWindow(corpo, orient="horizontal")
        paines.pack(fill="both", expand=True)
        esquerda = ttk.Frame(paines)
        direita = ttk.Frame(paines, padding=(12, 0, 0, 0))
        paines.add(esquerda, weight=3)
        paines.add(direita, weight=2)
        self.tabela = ttk.Treeview(esquerda, columns=("service", "username", "tags"),
                                   show="headings", selectmode="browse")
        scroll = ttk.Scrollbar(esquerda, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tabela.pack(fill="both", expand=True)
        for campo, nome in (("service", "Serviço"), ("username", "Usuário"), ("tags", "Tags")):
            self.tabela.heading(campo, text=nome, command=lambda c=campo: self.ordenar(c))
            self.tabela.column(campo, width=150, minwidth=60)
        self.vazio = ttk.Label(self.tabela, text="Nenhuma conta encontrada")
        self.tabela.bind("<<TreeviewSelect>>", lambda _: self.detalhar())
        self.tabela.bind("<Double-1>", self._duplo)
        self.tabela.bind("<Control-c>", lambda _: self._executar(self.copiar))
        self.tabela.bind("<Delete>", lambda _: self._executar(self.excluir))
        self.contexto = tk.Menu(self.tabela, tearoff=False)
        for nome, func in (("Editar", self.editar), ("Copiar senha", self.copiar),
                           ("Excluir", self.excluir)):
            self.contexto.add_command(label=nome, command=func)
        self.tabela.bind("<Button-3>", self._contexto)
        ttk.Label(direita, text="Detalhes da conta", font="TkHeadingFont").pack(anchor="w")
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
        rolagem = ttk.Scrollbar(direita, command=self.detalhes.yview)
        self.detalhes.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.detalhes.pack(fill="both", expand=True)
        self.detalhes.tag_configure("rotulo", font="TkHeadingFont", spacing1=6)
        ttk.Label(corpo, textvariable=self._mensagem, anchor="w").pack(fill="x", pady=(5, 0))
        ttk.Label(corpo, textvariable=self._resumo, anchor="w").pack(fill="x")
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
        for c in sorted(contas, key=chave, reverse=self._inversa):
            self.tabela.insert("", "end", iid=c.id, values=(c.service, c.username,
                                                           ", ".join(c.tags)))
        if contas:
            self.vazio.place_forget()
            ident = ident if self.tabela.exists(ident) and ident else self.tabela.get_children()[0]
            self.tabela.selection_set(ident)
            self.tabela.see(ident)
        else:
            self.vazio.place(relx=0.5, rely=0.5, anchor="center")
        total = len(self.cofre.conteudo.contas)
        self._resumo.set(f"{len(contas)} de {total} contas   ·   {self.disco.cofre}")
        self.detalhar()

    def selecionar_salva(self, identificador: str) -> None:
        """Exibe a conta salva mesmo que a edição a retire do filtro atual."""
        if not any(c.id == identificador for c in self.cofre.buscar(self._busca.get())):
            self._busca.set("")
        self.atualizar(identificador)

    def ordenar(self, campo: str) -> None:
        """Alterna a ordenação pelo cabeçalho."""
        self._inversa = not self._inversa if campo == self._ordem else False
        self._ordem = campo
        self.atualizar()

    def selecionada(self) -> Conta | None:
        """Obtém a conta selecionada pela identidade persistente."""
        selecao = self.tabela.selection()
        return self.cofre.obter(selecao[0]) if selecao else None

    def detalhar(self) -> None:
        """Renderiza detalhes e redefine a máscara ao trocar de seleção."""
        if not self.cofre.aberto:
            return
        c = self.selecionada()
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
        self.raiz.destroy()


def principal() -> int:
    """Inicia a aplicação e mantém o lock até o fechamento da interface."""
    disco = Armazenamento()
    try:
        raiz = tk.Tk()
    except tk.TclError:
        print("Não foi possível abrir a interface. Verifique a sessão gráfica e o DISPLAY.")
        return 1
    raiz.withdraw()
    app = None
    try:
        disco.adquirir()
        configurar_log()
        app = Aplicacao(raiz, disco)
        raiz.deiconify()
        raiz.mainloop()
    except ErroPassVault as erro:
        messagebox.showerror("PassVault", str(erro), parent=raiz)
        return 1
    finally:
        if app is not None:
            app.cofre.bloquear()
        disco.liberar()
    return 0

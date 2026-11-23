"""Formulários modais da interface em português."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Callable

from .plataforma import caminho_legado_padrao
from .ui.widgets import BarraForca, BotaoPrimario, centralizar
from .errors import DadosInvalidos, ErroPassVault
from .generator import Opcoes
from .migrate import Analise, analisar, importar
from .vault import Conta, validar_senha

if TYPE_CHECKING:
    from .app import Aplicacao


def campo_senha(pai: tk.Misc) -> ttk.Entry:
    """Cria campo mascarado sem exportação de seleção ou cópia desgerenciada."""
    entrada = ttk.Entry(pai, show="•", exportselection=False)
    for evento in ("<<Copy>>", "<<Cut>>", "<Button-2>"):
        entrada.bind(evento, lambda _: "break")
    return entrada


def alternar(entrada: ttk.Entry, botao: ttk.Button) -> None:
    """Alterna a máscara do campo e a legenda do botão."""
    mostrar = bool(entrada.cget("show"))
    entrada.configure(show="" if mostrar else "•")
    botao.configure(text="Ocultar" if mostrar else "Mostrar")


class Dialogo(tk.Toplevel):
    """Janela modal vinculada à sessão e ao diálogo de origem."""

    def __init__(self, app: "Aplicacao", titulo: str, pai: tk.Misc | None = None) -> None:
        super().__init__(pai or app.raiz)
        self.app = app
        self.title(titulo)
        self.transient(pai or app.raiz)
        self.resizable(True, False)
        self.corpo = ttk.Frame(self, padding=16)
        self.corpo.pack(fill="both", expand=True)
        self.corpo.columnconfigure(1, weight=1)
        self.linha = 0
        self.bind("<Escape>", lambda _: self.fechar())
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self.grab_set()
        self.after_idle(self.preparar)

    def preparar(self) -> None:
        self.app.tema.colorir(self)
        centralizar(self, self.master)

    def fechar(self) -> None:
        """Fecha e devolve a modalidade ao pai, se houver."""
        pai = self.master
        self.destroy()
        if isinstance(pai, Dialogo) and pai.winfo_exists():
            pai.grab_set()
            pai.focus_set()

    def rotulo(self, texto: str) -> None:
        """Inclui uma mensagem em toda a largura."""
        ttk.Label(self.corpo, text=texto, wraplength=460).grid(
            row=self.linha, column=0, columnspan=3, sticky="w", pady=5)
        self.linha += 1

    def campo(self, nome: str, valor: str = "", secreto: bool = False) -> ttk.Entry:
        """Adiciona uma entrada rotulada."""
        ttk.Label(self.corpo, text=nome).grid(row=self.linha, column=0, sticky="w", padx=(0, 10))
        entrada = campo_senha(self.corpo) if secreto else ttk.Entry(self.corpo)
        entrada.configure(width=40)
        entrada.insert(0, valor)
        entrada.grid(row=self.linha, column=1, sticky="ew", pady=4)
        if secreto:
            btn = ttk.Button(self.corpo, text="Mostrar")
            btn.configure(command=lambda: alternar(entrada, btn))
            btn.grid(row=self.linha, column=2, padx=(6, 0))
        self.linha += 1
        return entrada

    def acoes(self, *botoes: tuple[str, Callable[[], None]]) -> None:
        """Adiciona ações e cancelamento."""
        self.erro = ttk.Label(self.corpo, style="Erro.TLabel", wraplength=420)
        self.erro.grid(row=self.linha, column=0, columnspan=3, sticky="w")
        self.linha += 1
        self.botoes = {}
        barra = ttk.Frame(self.corpo)
        barra.grid(row=self.linha, column=0, columnspan=3, sticky="e", pady=(12, 0))
        self.linha += 1
        ttk.Button(barra, text="Cancelar", command=self.fechar).pack(side="left", padx=3)
        for nome, comando in botoes:
            def executar(acao=comando) -> None:
                try:
                    self.erro.configure(text="")
                    acao()
                except ErroPassVault as exc:
                    self.erro.configure(text=str(exc))
            botao = BotaoPrimario(barra, text=nome, command=executar)
            botao.pack(side="left", padx=3)
            self.botoes[nome] = botao


class Gerar(Dialogo):
    """Gera uma senha avulsa ou para o editor da conta."""

    def __init__(self, app: "Aplicacao", pai: tk.Misc | None = None,
                 destino: ttk.Entry | None = None) -> None:
        super().__init__(app, "Gerar senha", pai)
        self.destino = destino
        ttk.Label(self.corpo, text="Comprimento").grid(row=0, column=0, sticky="w")
        self.tamanho = ttk.Spinbox(self.corpo, from_=8, to=128, width=6)
        self.tamanho.set("24")
        self.tamanho.grid(row=0, column=1, sticky="w")
        self.linha += 1
        self.classes = []
        for i, nome in enumerate(("Maiúsculas", "Minúsculas", "Dígitos", "Símbolos",
                                  "Evitar caracteres ambíguos (Il1O0o)")):
            var = tk.BooleanVar(self, value=i < 4)
            self.classes.append(var)
            ttk.Checkbutton(self.corpo, text=nome, variable=var).grid(
                row=self.linha, column=0, columnspan=2, sticky="w")
            self.linha += 1
        self.resultado = self.campo("Senha gerada", secreto=True)
        self.resultado.configure(font=app.tema.mono)
        self.medidor = BarraForca(self.corpo, app.tema)
        self.medidor.grid(row=self.linha, column=0, columnspan=3, sticky="ew")
        self.linha += 1
        self.forca = ttk.Label(self.corpo)
        self.forca.grid(row=self.linha, column=0, columnspan=3, sticky="w")
        self.linha += 1
        self.acoes(("Gerar", self.gerar), ("Usar senha" if destino else "Copiar senha", self.usar))
        self.gerar()

    def gerar(self) -> None:
        """Atualiza a amostra e sua entropia."""
        try:
            tamanho = int(self.tamanho.get())
        except ValueError:
            raise DadosInvalidos("Comprimento inválido.") from None
        opc = Opcoes(tamanho, *(v.get() for v in self.classes))
        senha = opc.gerar()
        self.resultado.configure(state="normal")
        self.resultado.delete(0, "end")
        self.resultado.insert(0, senha)
        self.resultado.configure(state="readonly")
        self.medidor.definir(opc.entropia())
        self.forca.configure(text=f"Entropia da senha gerada: {opc.entropia():.0f} bits")

    def usar(self) -> None:
        """Entrega a amostra ao destino escolhido."""
        if self.destino is None:
            self.app.clip.copiar(self.resultado.get())
        else:
            self.destino.delete(0, "end")
            self.destino.insert(0, self.resultado.get())
        self.fechar()


class Editor(Dialogo):
    """Edição de uma conta, com gravação imediata ao salvar."""

    def __init__(self, app: "Aplicacao", conta: Conta | None = None) -> None:
        super().__init__(app, "Editar conta" if conta else "Adicionar conta")
        self.identificador = conta.id if conta else None
        base = self.corpo
        self.resizable(True, False)
        secoes = ttk.Frame(base)
        secoes.grid(row=0, column=0, columnspan=3, sticky="ew")
        secoes.columnconfigure((0, 1), weight=1)
        def secao(nome: str, coluna: int) -> None:
            self.corpo = ttk.Frame(secoes, padding=8)
            self.corpo.grid(row=0, column=coluna, sticky="nsew")
            self.corpo.columnconfigure(1, weight=1)
            self.linha = 0
            ttk.Label(self.corpo, text=nome, style="Subtitulo.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
            self.linha += 1
        secao("Básico", 0)
        self.servico = self.campo("Serviço *", conta.service if conta else "")
        self.usuario = self.campo("Usuário", conta.username if conta else "")
        self.senha = self.campo("Senha", conta.password if conta else "", True)
        for campo in (self.servico, self.usuario, self.senha):
            campo.configure(width=16)
        ttk.Button(self.corpo, text="Gerar senha", command=lambda: Gerar(
            app, self, self.senha)).grid(row=self.linha, column=1, sticky="w")
        secao("Detalhes", 1)
        self.url = self.campo("URL", conta.url if conta else "")
        self.tags = self.campo("Tags (vírgulas)", ", ".join(conta.tags) if conta else "")
        self.url.configure(width=18)
        self.tags.configure(width=18)
        ttk.Label(self.corpo, text="Notas").grid(row=self.linha, column=0, sticky="nw")
        self.notas = tk.Text(self.corpo, height=5, width=18, wrap="word", exportselection=False)
        self.notas.grid(row=self.linha, column=1, sticky="ew")
        self.notas.insert("1.0", conta.notes if conta else "")
        self.corpo, self.linha = base, 1
        self.acoes(("Salvar", self.salvar))
        self.nome = tk.StringVar(self, value=self.servico.get())
        self.servico.configure(textvariable=self.nome)
        def validar(*_) -> None:
            ok = bool(self.nome.get().strip())
            self.botoes["Salvar"].state(["!disabled" if ok else "disabled"])
            self.erro.configure(text="" if ok else "Informe o nome do serviço.")
        self.nome.trace_add("write", validar)
        validar()
        self.servico.focus_set()

    def salvar(self) -> None:
        """Valida, grava e seleciona a conta editada."""
        campos = dict(service=self.servico.get(), username=self.usuario.get(),
                      password=self.senha.get(), url=self.url.get(),
                      notes=self.notas.get("1.0", "end-1c"), tags=self.tags.get().split(","))
        identificador = self.identificador
        if identificador:
            self.app.cofre.editar(identificador, **campos)
        else:
            conta = Conta(**campos)
            self.app.cofre.adicionar(conta)
            identificador = conta.id
        self.fechar()
        self.app.selecionar_salva(identificador)


class TrocarSenha(Dialogo):
    """Reautenticação e troca da senha mestra."""

    def __init__(self, app: "Aplicacao") -> None:
        super().__init__(app, "Trocar senha mestra")
        self.atual = self.campo("Senha atual", secreto=True)
        self.nova = self.campo("Nova senha", secreto=True)
        self.confirmacao = self.campo("Confirmação", secreto=True)
        self.rotulo("Mínimo de 8 caracteres. Prefira 12 ou mais. Não há recuperação.")
        self.acoes(("Trocar", self.trocar))
        self.atual.focus_set()

    def trocar(self) -> None:
        """Confirma a substituição antes de recifrar o cofre."""
        validar_senha(self.nova.get())
        if self.nova.get() != self.confirmacao.get():
            raise DadosInvalidos("As senhas não coincidem.")
        if self.app.confirmar("Trocar a senha mestra? Backups anteriores mantêm a senha antiga.",
                              self):
            self.app.cofre.trocar_senha(self.atual.get(), self.nova.get())
            self.fechar()
            self.app.status("Senha mestra alterada.")


class Restaurar(Dialogo):
    """Lista cópias e autentica a selecionada antes da confirmação."""

    def __init__(self, app: "Aplicacao") -> None:
        copias = app.disco.listar()
        anterior = app.disco.anterior
        self.caminhos = [c.caminho for c in copias]
        opcoes = [f"{c.data:%d/%m/%Y %H:%M:%S}   ·   {c.tamanho} bytes" for c in copias]
        if anterior.is_file():
            self.caminhos.append(anterior)
            opcoes.append(f"Versão anterior (.bak)   ·   {anterior.stat().st_size} bytes")
        if not opcoes:
            raise DadosInvalidos("Nenhum backup disponível.")
        super().__init__(app, "Restaurar backup")
        self.rotulo("Selecione a cópia e informe a senha mestra usada quando ela foi criada.")
        self.lista = ttk.Combobox(self.corpo, values=opcoes, state="readonly", width=45)
        self.lista.grid(row=self.linha, column=0, columnspan=3, sticky="ew", pady=6)
        self.lista.current(0)
        self.linha += 1
        self.senha = self.campo("Senha do backup", secreto=True)
        self.acoes(("Validar e restaurar", self.restaurar))
        self.senha.focus_set()

    def restaurar(self) -> None:
        """Carrega o backup antes que a retenção possa alterar sua posição."""
        dados = self.app.disco.ler_backup(self.caminhos[self.lista.current()])
        if self.app.cofre.restaurar(dados, self.senha.get(), lambda: self.app.confirmar(
                "Backup autenticado. Salvar uma cópia do cofre atual e substituí-lo?", self)):
            self.fechar()
            self.app.clip.limpar()
            self.app.principal()
            self.app.status("Backup restaurado.")


class Importar(Dialogo):
    """Prévia sem gravação e confirmação de importação do legado."""

    def __init__(self, app: "Aplicacao") -> None:
        super().__init__(app, "Importar legado")
        self.analise: Analise | None = None
        self.origem = self.campo("Arquivo", app.config.ultimo_import or str(caminho_legado_padrao()))
        ttk.Button(self.corpo, text="Escolher…", command=self.escolher).grid(row=0, column=2)
        self.relatorio = ttk.Label(self.corpo, wraplength=460,
                                   text="Analise o arquivo para começar.")
        self.relatorio.grid(row=self.linha, column=0, columnspan=3, sticky="w", pady=8)
        self.linha += 1
        self.acoes(("Analisar", self.analisar), ("Importar", self.importar))
        self.caminho = tk.StringVar(self, value=self.origem.get())
        self.origem.configure(textvariable=self.caminho)
        self.caminho.trace_add("write", self.invalidar)
        self.invalidar()

    def invalidar(self, *_) -> None:
        self.analise = None
        self.botoes["Importar"].state(["disabled"])
        self.relatorio.configure(text="Analise o arquivo para começar.")

    def escolher(self) -> None:
        """Preenche a origem a partir do seletor."""
        nome = filedialog.askopenfilename(parent=self, title="Escolher arquivo legado")
        if nome and self.winfo_exists():
            self.origem.delete(0, "end")
            self.origem.insert(0, nome)
            self.analise = None
            self.relatorio.configure(text="Analise o arquivo para começar.")

    def analisar(self) -> None:
        """Exibe o resumo e a detecção de importação anterior."""
        self.invalidar()
        analise = analisar(Path(self.origem.get()))
        aviso = " Este arquivo já foi importado." if analise.repetida(self.app.cofre) else ""
        self.relatorio.configure(text=analise.resumo(self.app.cofre.buscar("")) + aviso)
        self.analise = analise
        self.botoes["Importar"].state(["!disabled"])

    def importar(self) -> None:
        """Preserva o original e informa contagens após a gravação."""
        a = self.analise
        if a is None or Path(self.origem.get()).expanduser().absolute() != a.origem:
            raise DadosInvalidos("Analise o arquivo selecionado antes de importar.")
        repetida = a.repetida(self.app.cofre)
        resumo = a.resumo(self.app.cofre.buscar(""))
        aviso = "Este arquivo já foi importado. Repetir a importação?" if repetida else (
            "Importar as contas e criar uma cópia do original com acesso restrito?")
        if not self.app.confirmar(aviso + "\n\n" + resumo, self):
            return
        copia = importar(a, self.app.cofre, permitir_repetida=repetida)
        self.app.config.ultimo_import = str(a.origem)
        self.fechar()
        self.app.atualizar()
        self.app.config.salvar(self.app.disco.pasta)
        self.app.status(f"Importadas: {len(a.contas)}.")
        messagebox.showinfo("Importação concluída",
                            f"Importadas: {len(a.contas)}. {resumo}\nBackup: {copia}\n"
                            "O original foi preservado. A exclusão é manual, após conferência.",
                            parent=self.app.raiz)

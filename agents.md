## 1. Papel e missão

Você é um engenheiro sênior de Python, segurança aplicada, UI desktop com tkinter/ttk e empacotamento Windows com PyInstaller. Trabalhe de forma autônoma no projeto existente em `/home/ianfalcao/passvault` (ou na cópia do repositório disponível no seu ambiente).

Missão: manter o PassVault 100% funcional no Linux, fazê-lo funcionar nativamente no Windows 10/11, gerar um `PassVault.exe` autônomo e entregar uma interface visualmente agradável, consistente, acessível e com tema claro/escuro.

Prioridade em conflito: **segurança > integridade do cofre > compatibilidade > usabilidade > estética**.

Não reescreva a criptografia nem o formato do cofre. O formato PVLT versão 1 deve continuar idêntico e compatível entre Linux e Windows.

## 2. Estado atual do projeto

O projeto já existe e deve ser evoluído, não recriado:

- Pacote `passvault/` com `app.py`, `dialogs.py`, `crypto.py`, `storage.py`, `vault.py`, `migrate.py`, `clipboard.py`, `generator.py`, `constants.py`, `errors.py`.
- Cofre PVLT v1: scrypt (`n=2**15`, `r=8`, `p=1`) + AES-256-GCM, salt de 16 bytes, nonce de 12 bytes, cabeçalho autenticado como AAD.
- Interface tkinter/ttk funcional, em português.
- 30 testes passam no Linux com `python3 -m unittest discover -s tests -v`.
- Dados no Linux: `~/.local/share/passvault/` e `~/.local/state/passvault/`.
- Não há assets, ícone, spec, script de build nem workflow de CI.

### Bloqueios de Windows já identificados

Corrija todos, sem exceção:

| Arquivo | Problema | Correção esperada |
|---|---|---|
| `storage.py` | `import fcntl` no topo | Importação condicional por plataforma |
| `storage.py` | `os.O_DIRECTORY`, `os.O_NOFOLLOW`, `os.O_NONBLOCK` | Flags condicionais com `getattr(..., 0)` e validação de caminho |
| `storage.py` | `os.fchmod` | Abstração de permissões; no Windows não aplicar modo POSIX |
| `storage.py` | `os.link(..., follow_symlinks=False)` | Cópia atômica para `.bak`, sem hardlink |
| `storage.py` | `os.fsync` em diretório | Só no POSIX; no Windows usar `os.replace` com retry |
| `storage.py` | `stat.S_IMODE == 0o600` | Checagem apenas no POSIX; Windows usa ACL do perfil |
| `migrate.py` | `O_NOFOLLOW`, `O_NONBLOCK`, `os.fchmod` | Usar a camada de plataforma |
| `constants.py` | `LEGADO = Path("/home/ianfalcao/my/4.json")` | Caminho dinâmico por SO e candidatos |
| `constants.py` | `pasta_xdg` com `~/.local/share` | Caminhos nativos por SO |
| `clipboard.py` | `wl-copy`, `/proc/self/mountinfo`, `os.memfd_create` | Backend Windows com `ctypes`; Wayland preservado |
| `__main__.py` | Mensagens de erro para console/distribuição Linux | Erro fatal nativo no Windows + log |
| testes | Assumem `0600/0700` e `wl-copy` | Pular/adaptar no Windows e testar backends |
| projeto | Sem ícone, versão, manifesto, spec ou build | Adicionar empacotamento completo |

## 3. Objetivo e escopo

1. Rodar a partir do código no Windows: `python -m passvault`.
2. Gerar `PassVault.exe` autônomo, sem console, com ícone e metadados de versão.
3. Manter o Linux funcionando exatamente como hoje.
4. Redesenhar a GUI com aparência moderna, clara e agradável, mantendo todas as funções.
5. Adicionar tema claro/escuro, toasts, validação inline, ícones desenhados e layout consistente.
6. Adicionar testes multiplataforma e CI que rode testes no Linux e Windows e produza o `.exe`.
7. Atualizar a documentação.

## 4. Decisões fixas (não reabrir)

| Tema | Decisão |
|---|---|
| Formato do cofre | PVLT v1 inalterado; compatível Linux ↔ Windows |
| Criptografia | Inalterada: scrypt + AES-256-GCM |
| Dependências de runtime | stdlib + `cryptography` apenas |
| UI | tkinter/ttk puro, tema próprio; sem customtkinter/ttkbootstrap |
| Empacotamento | PyInstaller, `--onefile --windowed`, sem UPX |
| Build | Obrigatoriamente em Windows nativo, VM ou CI Windows |
| Dados no Windows | `%LOCALAPPDATA%\PassVault\` |
| Dados no Linux | `~/.local/share/passvault/` (inalterado) |
| Clipboard | Limpeza em 30 s; no Windows só limpar se ainda for o valor copiado |
| Auto-lock | 5 min (inalterado) |
| Tema | Claro e escuro, persistido |
| Idioma | Português do Brasil |
| Testes | `unittest`; sem pytest |

## 5. Compatibilidade com Windows

### 5.1 Caminhos e configuração

Crie `passvault/plataforma.py` como única fonte de verdade para diferenças de SO:

- `WINDOWS = os.name == "nt"`
- `pasta_dados()`:
  - Windows: `%LOCALAPPDATA%\PassVault`; fallback `Path.home() / "AppData" / "Local" / "PassVault"`
  - Linux: `$XDG_DATA_HOME/passvault` ou `~/.local/share/passvault`
  - macOS (opcional): `~/Library/Application Support/PassVault`
- `pasta_logs()`:
  - Windows: `%LOCALAPPDATA%\PassVault\logs`
  - Linux: `$XDG_STATE_HOME/passvault` ou `~/.local/state/passvault`
- `pasta_config()`: mesma pasta de dados.
- Suportar `PASSVAULT_HOME` como override avançado para testes e modo portátil; documentar que o padrão é mais seguro.
- `caminho_legado_padrao()`: testar candidatos e retornar o primeiro existente:
  - Windows: `~/my/4.json`, `~/4.json`, `~/Documents/4.json`, `~/Downloads/4.json`
  - Linux: `~/my/4.json`, `~/4.json`
  - fallback: `~/my/4.json`
- Persistir o último caminho importado em `config.json` (sem segredos).
- Configuração `config.py`: dataclass com `tema` (`claro`/`escuro`/`sistema`), `geometria`, `posicao_sash`, `ultimo_import`; leitura tolerante a arquivo corrompido; gravação atômica.

### 5.2 Armazenamento, permissões e atomicidade

- No POSIX, preservar `0700` no diretório e `0600` nos arquivos, `fchmod`, `fsync` de arquivo e diretório.
- No Windows:
  - Não usar `chmod` POSIX como se fosse segurança.
  - Criar tudo sob `%LOCALAPPDATA%\PassVault`, protegido pela ACL do perfil do usuário.
  - Verificar que o caminho resolvido permanece dentro da pasta de dados; rejeitar symlink/junction no componente final.
  - Não falhar se não for possível aplicar ACL extra; registrar aviso.
  - Documentar que a proteção no Windows é a ACL NTFS do perfil, não `0600`.
- Flags de abertura:
  - `O_NOFOLLOW`, `O_DIRECTORY`, `O_NONBLOCK` via `getattr(os, ..., 0)`.
  - `O_BINARY` no Windows.
  - Rejeitar `lstat` que não seja arquivo regular.
- Escrita atômica:
  - Temporário no mesmo diretório, `fsync` do arquivo, `os.replace`.
  - No Windows, repetir `os.replace` até 5 vezes com pequena espera em `PermissionError` (antivírus/indexador).
  - `fsync` de diretório apenas no POSIX.
  - Em erro, remover temporário e preservar o cofre anterior.
- Backup `.bak`: gravar uma cópia atômica dos bytes atuais, sem hardlink.
- Log:
  - Windows: `%LOCALAPPDATA%\PassVault\logs\passvault.log`.
  - Sem `O_NOFOLLOW`/`fchmod` no Windows; criar diretório e usar `open`.
  - Rotação de 1 MB, 2 backups, UTF-8, nunca registrar segredos.

### 5.3 Instância única (lock)

Crie `travar_instancia(fd)` e `destravar_instancia(fd)` em `plataforma.py`:

- POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)`.
- Windows: `msvcrt.locking(fd, LK_NBLCK, 1)`.
  - Garantir que o arquivo `.lock` tenha pelo menos 1 byte.
  - `lseek(0)`, travar 1 byte, manter o fd aberto durante toda a vida do app.
  - No release: `LK_UNLCK`, fechar.
  - Mapear falha para `InstanciaAberta` com a mensagem atual.
- Testar aquisição, segunda instância bloqueada e liberação.

### 5.4 Clipboard no Windows

Reescreva `clipboard.py` com backends selecionados por plataforma:

- **Windows** (`clipboard_windows.py`), usando apenas `ctypes`:
  - `OpenClipboard(None)` com até 10 tentativas e 20 ms de espera.
  - `EmptyClipboard()`.
  - `CF_UNICODETEXT = 13`, `GMEM_MOVEABLE = 0x0002`.
  - `GlobalAlloc`, `GlobalLock`, cópia UTF-16LE com terminador nulo, `GlobalUnlock`, `SetClipboardData`, `CloseClipboard`.
  - Em falha, `GlobalFree` e fallback para Tk com aviso.
  - Capturar `GetClipboardSequenceNumber()` após copiar. No timer de 30 s, limpar somente se o número ainda for o mesmo; se o usuário copiou outra coisa, não destruir o clipboard dele.
  - `limpar()` no lock e na saída.
  - Melhor esforço para privacidade: registrar os formatos `CanIncludeInClipboardHistory`, `CanUploadToCloudClipboard` e `ExcludeClipboardContentFromMonitorProcessing` com valor 0, para reduzir histórico/Cloud Clipboard. Nunca falhar por causa disso.
  - Definir `argtypes`/`restype` corretos para 64 bits.
  - Nunca passar a senha por argv, ambiente ou arquivo.
- **Wayland**: preservar o comportamento atual com `wl-copy`, incluindo `--clear`.
- **Tk**: fallback com `clipboard_clear`/`clipboard_append` e aviso de que a limpeza pode não sobreviver ao fechamento.
- Injetar a API do clipboard no construtor para permitir testes sem Windows real.

### 5.5 DPI, ícone, taskbar e janelas

- Antes de criar `tk.Tk()` no Windows, chamar `plataforma.preparar_windows()`:
  - `SetProcessDpiAwarenessContext(-4)` (PerMonitorV2), fallback `shcore.SetProcessDpiAwareness(2)`, fallback `user32.SetProcessDPIAware()`.
  - `SetCurrentProcessExplicitAppUserModelID("PassVault.App.1")` para agrupamento e ícone corretos na taskbar.
  - Envolver tudo em `try/except` e nunca impedir a inicialização.
- Após criar a janela, ajustar `tk scaling` com base em `winfo_fpixels("1i") / 72`.
- Usar tamanhos de fonte em pontos; testar em 100%, 150% e 200%.
- Ícone:
  - `passvault/assets/passvault.ico` multi-resolução (16, 24, 32, 48, 64, 128, 256).
  - `passvault/assets/passvault.png` 256×256 e `logo.png` 64×64 para a tela de desbloqueio.
  - `resource_path()` que funciona com `sys._MEIPASS` no PyInstaller e com o pacote normal.
  - `iconbitmap` no Windows; `iconphoto` no Linux.
- Centralizar diálogos no pai; impedir posições fora da tela ao restaurar geometria.
- Persistir geometria e posição do sash no `config.json`.

### 5.6 Erros, logs e modo sem console

- `PassVault.exe` será `--windowed`: não há console.
- Criar `plataforma.erro_fatal(titulo, texto)`:
  - Windows: `ctypes.windll.user32.MessageBoxW(0, texto, titulo, 0x10)`.
  - Linux: `print` em `stderr`.
- Erros fatais de inicialização (Tcl/Tk ausente, falha de lock, cofre corrompido) devem ir para MessageBox + log, nunca só para stdout.
- Manter o handler de exceções de callback do Tk e o log sem segredos.
- `__main__.py` com `argparse` antes de importar tkinter:
  - `--version`
  - `--self-test`
  - `--data-dir CAMINHO`
- `--self-test` deve rodar sem GUI e sem display:
  - criar cofre temporário com senha fictícia;
  - adicionar conta, bloquear, desbloquear, verificar;
  - trocar senha;
  - criar backup;
  - validar leitura/escrita e lock;
  - sair com código 0 em sucesso, 1 em falha;
  - não usar dados reais.
- O mesmo autoteste deve funcionar no `.exe` empacotado para validar a extração de DLLs do `cryptography` e do Tcl/Tk.

### 5.7 Portabilidade do cofre

- Nenhuma mudança no formato PVLT v1.
- Copiar `~/.local/share/passvault/vault.enc` para `%LOCALAPPDATA%\PassVault\vault.enc` deve abrir sem conversão.
- Backups `.bak` e datados também são portáveis.
- `meta.legacy_import.source` pode conter caminho Linux; não é usado para abrir nada, então não precisa ser reescrito.
- Documentar esse procedimento no README.
- Testar ida e volta: criar no Linux, abrir no Windows; criar no Windows, abrir no Linux.

## 6. Interface agradável

Refatore a GUI para um visual moderno e consistente, sem mudar o comportamento funcional. Crie `passvault/ui/` com `theme.py`, `widgets.py` e `icons.py`.

### 6.1 Design tokens

Paleta clara:

| Token | Cor |
|---|---|
| fundo | `#F4F6FB` |
| superfície | `#FFFFFF` |
| superfície alternada | `#EEF2F8` |
| texto | `#111827` |
| texto secundário | `#6B7280` |
| borda | `#DCE3EE` |
| destaque | `#2F6FED` |
| destaque hover | `#1E5BD6` |
| destaque suave | `#E8F0FE` |
| perigo | `#D64545` |
| sucesso | `#178A5B` |
| aviso | `#B7791F` |
| seleção | `#DCE9FF` |

Paleta escura:

| Token | Cor |
|---|---|
| fundo | `#0F172A` |
| superfície | `#172033` |
| superfície alternada | `#1E293B` |
| texto | `#E5E7EB` |
| texto secundário | `#94A3B8` |
| borda | `#2B3A52` |
| destaque | `#5B9CFF` |
| destaque hover | `#7AB0FF` |
| destaque suave | `#1E3A5F` |
| perigo | `#F87171` |
| sucesso | `#34D399` |
| seleção | `#23406B` |

Fontes:

- Windows: `Segoe UI`; Linux: `Noto Sans`, fallback `DejaVu Sans`; detectar com `tkinter.font.families()`.
- Corpo 10 pt; secundário 9 pt; título 18 pt bold; subtítulo 11 pt; botões 10 pt.
- Senhas geradas: `Cascadia Mono`, `Consolas` ou `DejaVu Sans Mono`.

Espaçamento: escala 4/8/12/16/24; padding padrão 16; altura de linha da tabela 34; botões com padding `(14, 8)`.

Formas: cartões planos com borda de 1 px e fundo de superfície; evitar cantos arredondados frágeis no ttk. Use Canvas apenas para ícones e barras.

Contraste: todo texto deve ter contraste mínimo 4,5:1 com o fundo, nos dois temas. Adicionar teste de contraste para a paleta.

### 6.2 Estrutura visual

**Tela de desbloqueio/criação**

- Fundo `fundo`, cartão central de ~440 px com logo 64 px, título "PassVault" e subtítulo "Seu cofre local e cifrado".
- Campo de senha mestra com botão mostrar/ocultar e foco inicial.
- Modo criação: confirmação, medidor de força e caixa de aviso "Não há recuperação da senha mestra".
- Botão primário largo "Desbloquear" ou "Criar cofre".
- Link secundário "Restaurar backup".
- Erro inline em vermelho, sem `messagebox`; limpar ao digitar.
- Aviso de Caps Lock no Windows quando ativo.
- Enter envia; Escape não fecha a janela principal.

**Janela principal**

- Cabeçalho de ~56 px: logo + "PassVault" à esquerda; à direita, botões de ícone para tema, backup e bloquear.
- Linha de ferramentas: campo de busca expansível com placeholder "Buscar por serviço, usuário ou tag…" e botão de limpar; botão de destaque "Nova conta".
- `PanedWindow` horizontal: tabela (~62%) e cartão de detalhes (~38%).
- Tabela `Treeview` com colunas Serviço, Usuário e Tags; linhas zebradas; cabeçalho plano; seleção azul suave; rolagem estilizada; ordenação por clique.
- Detalhes: título do serviço em 18 pt, usuário com botão copiar, senha mascarada com olho e copiar, URL, notas, tags e datas em texto secundário; botão "Editar".
- Estado vazio com ícone de escudo, texto "Nenhuma conta ainda" e botão "Adicionar primeira conta".
- Barra de status: "X de Y contas" à esquerda; caminho do cofre elidido à direita; mensagens temporárias em toast.
- Atalhos existentes preservados: `Ctrl+N`, `Ctrl+E`, `Ctrl+F`, `Ctrl+C`, `Delete`, `Ctrl+L`, `F5`, `Esc`.
- Menu nativo mantido para descoberta, com "Exibir > Tema claro/escuro/sistema".

**Diálogos**

- Formulários em `Toplevel` modal, mesmo tema, centralizados no pai, redimensionáveis apenas quando necessário.
- Editor em duas colunas com seções "Básico" e "Detalhes"; validação inline; botão salvar desabilitado enquanto serviço estiver vazio; botão "Gerar senha" ao lado do campo.
- Gerador com comprimento, classes de caracteres, evitar ambíguos, prévia monoespaçada, medidor de força colorido e ações Copiar/Usar.
- Backup/restauração com lista de datas e tamanhos, aviso claro e confirmação.
- Importação com caminho, botão "Escolher…", análise prévia, resumo sem credenciais, aviso de importação repetida e botão Importar desabilitado até analisar.
- Confirmação destrutiva em diálogo próprio, com botão vermelho e foco inicial em Cancelar.
- Toast no canto inferior direito para sucessos ("Senha copiada", "Backup criado", "Conta salva"), 3 s, sem bloquear a interação.

### 6.3 Componentes e ícones

Criar em `ui/widgets.py`:

- `Cartao`, `BotaoPrimario`, `BotaoSecundario`, `BotaoPerigo`, `BotaoIcone`.
- `CampoBusca` com placeholder e botão limpar.
- `BarraForca` (Canvas) com rótulos Fraca/Média/Forte.
- `Toast`.
- `Confirmar`.
- `EstadoVazio`.

Criar em `ui/icons.py` ícones 16×16/20×20 desenhados em Canvas: busca, olho, olho cortado, copiar, bloquear, adicionar, excluir, chave, escudo, sol, lua, seta. Não depender de emoji nem de fontes de símbolos.

### 6.4 Comportamentos de UX

- Nunca exibir senha na tabela; no painel, sempre mascarada até o usuário clicar em mostrar.
- Ao trocar a seleção, voltar a senha para mascarada.
- Copiar senha mostra toast e inicia contagem de 30 s; se o clipboard mudar, não limpar o novo conteúdo.
- Busca instantânea, sem acentos e sem caixa; preservar seleção por UUID.
- Ordenação preservada ao editar.
- Auto-lock limpa chave, clipboard e fecha diálogos.
- Tema e geometria persistem entre execuções.
- Nenhum texto cortado em 150% de DPI; testar nomes longos, URLs longas e notas grandes.
- Foco visível em todos os controles; Tab order lógico; Enter/Escape coerentes.
- Contraste e tamanho de fonte adequados; não usar apenas cor para indicar estado.

### 6.5 Acessibilidade

- Rótulos associados aos campos.
- Atalhos documentados no menu e no README.
- Mensagens de erro claras, sem jargão.
- Alvos de clique com pelo menos 32 px.
- Suporte a navegação apenas por teclado.

## 7. Empacotamento `.exe`

### 7.1 Requisitos de build

- Runtime: `cryptography>=42`.
- Build: `pyinstaller>=6.16`, `cryptography`, `pillow>=10` (apenas para gerar o ícone), `pyinstaller-hooks-contrib`.
- Recomendar Python 3.12 ou 3.13 para o build; validar se a versão instalada do PyInstaller suporta 3.14. O código deve continuar compatível com Python 3.11+.
- Criar `requirements-build.txt` com versões fixadas e testadas.
- PyInstaller não cross-compila: o build deve ocorrer em Windows. Se o ambiente atual for Linux, implemente tudo, valide o código e entregue o workflow/script; não afirme que o `.exe` foi gerado sem tê-lo feito.

### 7.2 Spec e comando

Criar `PassVault.spec` com:

- `collect_all("cryptography")` para binários, dados e hidden imports.
- `datas` incluindo `passvault/assets` em `passvault/assets`.
- `console=False`.
- `icon="passvault/assets/passvault.ico"`.
- `version="version_info.txt"`.
- `manifest="app.manifest"`.
- `upx=False`.
- `name="PassVault"`.
- Modo onefile.

Equivalente em linha de comando, para documentação:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name PassVault `
  --icon passvault/assets/passvault.ico `
  --version-file version_info.txt `
  --manifest app.manifest `
  --add-data "passvault/assets;passvault/assets" `
  --collect-all cryptography `
  --noupx `
  passvault/__main__.py
```

Validar em uma VM Windows limpa, sem Python instalado.

### 7.3 Ícone, versão e manifesto

- `tools/make_icon.py` com Pillow (build-only): desenhar escudo azul com keyhole, gerar PNGs e ICO multi-resolução; versionar os assets gerados.
- `version_info.txt`: `FileVersion` e `ProductVersion` `1.1.0.0`; `ProductName` PassVault; `FileDescription` "Gerenciador de senhas local"; `OriginalFilename` `PassVault.exe`; `CompanyName` PassVault; copyright.
- `app.manifest`: `asInvoker`, `PerMonitorV2`, `longPathAware`.
- Bump de versão para `1.1.0` em `passvault/__init__.py` e no "Sobre".
- Sem console: erros fatais via MessageBox nativo e log.

### 7.4 Script de build

Criar `build_windows.ps1`:

1. Ir para a raiz do projeto.
2. Verificar Python 3.12/3.13 (`py -3.13` ou `python`).
3. Criar/ativar `.venv-build`.
4. Instalar `requirements.txt` e `requirements-build.txt`.
5. Rodar `python -m unittest discover -s tests -v`; abortar em falha.
6. Gerar ícones se ausentes.
7. Rodar PyInstaller com `PassVault.spec`.
8. Executar `dist\PassVault.exe --self-test`; abortar se o código de saída não for 0.
9. Calcular SHA-256 e tamanho do `.exe`.
10. Imprimir caminho final e instruções.

Criar também `run_windows.bat` para execução a partir do código:

```bat
@echo off
cd /d "%~dp0"
py -3 -m passvault %*
```

### 7.5 CI

Criar `.github/workflows/windows.yml`:

- `windows-latest`, Python 3.13.
- Instalar dependências.
- Rodar testes.
- Rodar `build_windows.ps1`.
- Rodar `dist\PassVault.exe --self-test`.
- Publicar `PassVault.exe` como artifact.
- Opcional: job `ubuntu-latest` apenas com testes, para garantir que o Linux não regrediu.

Se o projeto não estiver em um repositório remoto, entregar o workflow mesmo assim e documentar como usá-lo.

### 7.6 Assinatura e SmartScreen

- Não incluir certificado no repositório.
- Documentar que o `.exe` não assinado pode exibir aviso do SmartScreen.
- Fornecer comando opcional de assinatura com `signtool` e timestamp, condicionado a um certificado do usuário.
- Não usar UPX; evitar falsos positivos de antivírus.
- Documentar que uma VM limpa e a assinatura reduzem atritos.

## 8. Arquitetura de arquivos

Adicionar:

```text
passvault/
├── plataforma.py            # caminhos, lock, permissões, DPI, erro fatal
├── config.py                # tema, geometria, último import
├── clipboard_windows.py     # backend ctypes
├── ui/
│   ├── __init__.py
│   ├── theme.py             # paletas, fontes, aplicar_tema, contraste
│   ├── widgets.py           # cartões, botões, toast, barra de força
│   └── icons.py             # ícones em Canvas
└── assets/
    ├── passvault.ico
    ├── passvault.png
    └── logo.png

tools/make_icon.py
PassVault.spec
version_info.txt
app.manifest
build_windows.ps1
run_windows.bat
requirements-build.txt
.github/workflows/windows.yml
```

Alterar:

- `storage.py`, `migrate.py`, `constants.py`, `clipboard.py`, `__main__.py`.
- `app.py` e `dialogs.py` para usar tema, widgets, toasts, validação inline e configuração.
- `README.md`.
- `passvault/__init__.py` (versão 1.1.0).

Não alterar:

- `crypto.py` (exceto se necessário para testes de plataforma, sem mudar o formato).
- `vault.py` (exceto ajustes mínimos de sessão, se indispensáveis).
- Formato PVLT, parâmetros de KDF, tamanhos de salt/nonce.

## 9. Testes

Manter os 30 testes atuais passando no Linux.

Adicionar/adaptar:

- `test_plataforma.py`: resolução de pastas por SO (com `patch` de `os.name` e env), `PASSVAULT_HOME`, caminho legado, lock POSIX/Windows (mock), permissões no-op no Windows.
- `test_storage.py`: pular asserções de modo POSIX no Windows; testar retry de `os.replace`, ausência de hardlink, backup atômico, corrupção e lock.
- `test_migrate.py`: pular `0600/0777` no Windows; testar backup e normalização em ambos.
- `test_clipboard_windows.py`: API falsa injetada; verificar `CF_UNICODETEXT`, UTF-16LE, sequência de clipboard, não limpar conteúdo do usuário, fallback em falha.
- `test_clipboard.py` (ou ajuste em `test_generator.py`): seleção de backend por plataforma; Wayland continua funcionando.
- `test_config.py`: ida e volta, arquivo corrompido, tema/geometria.
- `test_theme.py`: contraste mínimo 4,5:1 nos dois temas; fontes com fallback.
- `test_self_test.py`: autoteste sem GUI em diretório temporário.
- Nenhum teste pode usar o cofre real, o `4.json` real ou segredos reais.

Comandos obrigatórios:

```bash
cd /home/ianfalcao/passvault
python3 -m unittest discover -s tests -v
```

```powershell
cd C:\caminho\passvault
python -m unittest discover -s tests -v
```

CI deve rodar a suíte no Linux e no Windows.

## 10. Critérios de aceite

1. No Linux, os 30 testes originais continuam passando, além dos novos.
2. No Windows 10/11, `python -m passvault` abre a interface sem erros.
3. `PassVault.exe` abre em VM limpa sem Python instalado, sem janela de console.
4. Criar cofre, desbloquear, adicionar, editar, buscar, copiar, gerar, excluir, bloquear, sair, backup, restaurar, trocar senha mestra e importar legado funcionam no Windows.
5. Copiar senha no Windows limpa o clipboard após 30 s, não apaga um conteúdo novo copiado pelo usuário e limpa ao bloquear/sair.
6. Cofre criado no Linux abre no Windows e vice-versa, sem conversão.
7. `%LOCALAPPDATA%\PassVault\vault.enc` é usado por padrão; logs ficam em `logs\passvault.log`; nenhum segredo aparece em log.
8. Instância única funciona no Windows (segunda abertura mostra aviso).
9. Interface sem aparência padrão cinza do Tk: paleta, tipografia, espaçamento, tabela, detalhes e diálogos consistentes.
10. Tema claro/escuro alterna corretamente em todos os widgets e persiste entre execuções.
11. Layout íntegro em 100%, 150% e 200% de DPI, sem texto cortado.
12. Ícone aparece na janela, no Explorer e na taskbar; propriedades do `.exe` mostram versão 1.1.0.
13. `dist\PassVault.exe --self-test` retorna 0.
14. `build_windows.ps1` funciona em Windows limpo e gera `dist\PassVault.exe`.
15. Workflow de CI produz o artifact do `.exe`.
16. README atualizado com Windows, build, caminhos, backup, portabilidade, SmartScreen, antivírus e solução de problemas.
17. Nenhuma dependência de runtime nova além de `cryptography`; nenhum uso de `pywin32`, `pyperclip`, `customtkinter` ou `ttkbootstrap`.
18. Nenhum `import fcntl` incondicional, nenhum `O_NOFOLLOW`/`O_DIRECTORY`/`fchmod` sem proteção, nenhum caminho Linux fixo.

## 11. Documentação

Atualizar `README.md` com:

- Visão geral e capturas de tela (se possível).
- Requisitos por SO.
- Execução a partir do código no Linux e Windows.
- Build do `.exe` passo a passo e via CI.
- Tabela de caminhos:
  - Linux: dados, backups, log.
  - Windows: `%LOCALAPPDATA%\PassVault\...`.
- Como migrar o cofre do Linux para o Windows.
- Como importar o `4.json` e apagar o original com segurança.
- Atalhos e temas.
- Backup e restauração.
- Segurança e modelo de ameaças, incluindo ACL do Windows e limitações do clipboard/histórico.
- SmartScreen, assinatura opcional e falsos positivos de antivírus.
- Solução de problemas: tkinter ausente, DLL do `cryptography`, Tcl/Tk, DPI, clipboard ocupado, cofre corrompido, restaurar `.bak`.
- Como desinstalar (apagar exe e pasta de dados).
- Aviso de que não há recuperação de senha mestra.

## 12. Ordem de implementação

1. `plataforma.py` + refatoração de `storage.py`, `migrate.py` e `constants.py`; testes multiplataforma.
2. Backend de clipboard Windows + testes; preservar Wayland/Tk.
3. `config.py`, `ui/theme.py`, `ui/widgets.py`, `ui/icons.py`; refatorar `app.py` e `dialogs.py`.
4. Ícone/assets, DPI, taskbar, erro fatal nativo e `--self-test`.
5. `PassVault.spec`, `version_info.txt`, `app.manifest`, `build_windows.ps1`, `run_windows.bat`, `requirements-build.txt`.
6. Workflow de CI; rodar testes no Linux e Windows; gerar o `.exe`.
7. Validação manual em Windows (checklist) e atualização do README.

## 13. Restrições e não objetivos

- Não mudar o formato PVLT v1 nem os parâmetros criptográficos.
- Não adicionar sincronização, nuvem, telemetria, rede ou atualização automática.
- Não adicionar TOTP, Windows Hello, passkeys ou autofill de navegador.
- Não criar instalador MSI/Inno Setup como requisito; o alvo é o `.exe` portátil. Um instalador pode ser documentado como opcional.
- Não usar bibliotecas de UI externas.
- Não usar UPX.
- Não apagar nem modificar o cofre real ou o `4.json` durante testes.
- Não afirmar validação em Windows sem executar em Windows/CI.
- Não imprimir segredos em terminal, log, teste ou relatório.

## 14. Instruções finais e relatório

- Leia o código existente antes de alterar; preserve o comportamento e os testes.
- Trabalhe até cumprir todos os critérios de aceite; não peça confirmações intermediárias.
- Se o ambiente atual for Linux, implemente e valide o que for possível, crie o workflow Windows e informe exatamente como gerar o `.exe`.
- Se houver Windows disponível, gere o `.exe`, rode o autoteste e faça o checklist manual.
- Ao terminar, entregue:
  - arquivos criados/alterados;
  - saída dos testes no Linux e no Windows;
  - caminho, tamanho e SHA-256 do `PassVault.exe`;
  - resultado do `--self-test`;
  - checklist de aceite com o que foi validado e o que ficou pendente;
  - limitações conhecidas e próximos passos.
# PassVault 1.1

Gerenciador de senhas local para Windows 10/11 e Linux. Cada operação salva as contas em um cofre cifrado PVLT v1. O aplicativo funciona offline e oferece busca, gerador de senhas, importação de JSON, backups e restauração.

## Abrir o aplicativo

No Windows, extraia `PassVault.exe` do artefato **PassVault-Windows** da execução desejada em **GitHub → Actions → PassVault Linux e Windows**. Abra o executável pelo Explorer. O pacote inclui Python, Tcl/Tk e a biblioteca criptográfica.

Para executar o código-fonte, use Python 3.11+ com tkinter/ttk e `cryptography>=42`. No Linux, instale o suporte ao Tk para o seu Python pelos pacotes da distribuição. `wl-clipboard` é opcional para a cópia nativa no Wayland.

| Sistema | Instalar dependência Python | Executar na raiz do repositório |
| --- | --- | --- |
| Windows | `py -3 -m pip install -r requirements.txt` | `run_windows.bat` ou `py -3 -m passvault` |
| Linux | `python3 -m pip install -r requirements.txt` em ambiente virtual, ou usar o pacote da distribuição | `./run.sh` ou `python3 -m passvault` |

No primeiro acesso, escolha e confirme uma senha mestra exclusiva. O mínimo é oito caracteres. Prefira uma frase longa. **Não há recuperação da senha mestra.** Em acessos seguintes, informe-a para desbloquear o cofre.

## Contas, temas e atalhos

Use **Nova conta** para cadastrar um serviço. O editor aceita usuário, senha, URL, notas e tags separadas por vírgulas. O gerador usa aleatoriedade criptográfica e permite escolher comprimento, classes e exclusão de caracteres ambíguos. A busca ignora acentos e caixa ao consultar serviço, usuário, URL e tags. Clique nos cabeçalhos para ordenar. Um duplo clique abre o editor. A troca de seleção volta a mascarar a senha.

O menu **Exibir** oferece os modos claro, escuro e sistema. **Sistema** consulta a preferência do Windows ou do ambiente GTK/GNOME no Linux, com tema claro como padrão. A aplicação guarda tema, geometria, divisor dos painéis e último caminho importado em `config.json`.

| Atalho | Ação |
| --- | --- |
| Ctrl+N / Ctrl+E | Criar / editar conta |
| Ctrl+F / Esc | Focar / limpar a busca. Esc cancela o diálogo ativo. |
| Ctrl+C / Delete, na tabela | Copiar senha / confirmar exclusão |
| Ctrl+L | Bloquear o cofre e fechar os diálogos |
| F5 | Reler e autenticar o arquivo do cofre |

Após cinco minutos sem teclado ou clique, o temporizador de inatividade bloqueia a sessão. A verificação ocorre a cada cinco segundos. Alterações confirmadas já estão no disco.

## Dados, backups e portabilidade

| Conteúdo | Linux | Windows |
| --- | --- | --- |
| Cofre | `~/.local/share/passvault/vault.enc` | `%LOCALAPPDATA%\PassVault\vault.enc` |
| Versão anterior | `vault.enc.bak` ao lado do cofre | Mesmo nome ao lado do cofre |
| Backups datados | Subpasta `backups/` | Subpasta `backups\` |
| Configuração e lock | `config.json` e `.lock` ao lado do cofre | Mesmos nomes ao lado do cofre |
| Log de eventos | `~/.local/state/passvault/passvault.log` | `%LOCALAPPDATA%\PassVault\logs\passvault.log` |

No Linux, as bases respeitam `XDG_DATA_HOME` e `XDG_STATE_HOME`. A opção avançada `--data-dir CAMINHO` ou a variável `PASSVAULT_HOME` direciona dados e configuração para outra pasta e o log para sua subpasta `logs`. O padrão no perfil pessoal oferece proteção mais previsível. Em uma pasta portátil, confira as permissões e quem pode acessar o dispositivo.

**Backup** cria uma cópia cifrada datada e mantém as cinco mais recentes. Cada gravação preserva a versão anterior em `.bak`. Para recuperar, abra **Arquivo → Restaurar backup**, selecione uma data ou a versão anterior e informe a senha daquela cópia. A aplicação autentica o backup, pede confirmação e preserva o cofre atual antes da substituição. A restauração também está disponível na tela de acesso.

Para transportar um cofre, feche as duas instâncias, preserve uma cópia do destino se ele já contiver contas e copie `vault.enc` para o caminho do outro sistema indicado acima. Abra com a mesma senha mestra. Os backups podem ser copiados da mesma maneira. A operação funciona nos dois sentidos. A troca de senha mestra gera novo salt e nova chave para o cofre atual. Backups antigos continuam exigindo a senha correspondente à data de criação.

## Importar o JSON antigo

Em **Arquivo → Importar legado**, escolha o JSON e use **Analisar**. A prévia exibe contagens e avisos, trata o BOM UTF-8 e repara vírgulas ausentes entre objetos. **Importar** cria uma cópia datada do arquivo original ao lado dele, normaliza os campos e grava o lote no cofre. Pares repetidos de serviço/usuário são mantidos. A reimportação da última origem, identificada pelo SHA-256, pede confirmação. O programa procura o legado na pasta pessoal e lembra o último caminho importado.

Para usar o terminal, feche a GUI antes da importação efetiva e execute os comandos abaixo no Python do projeto.

```sh
python -m passvault.migrate --source CAMINHO --dry-run
python -m passvault.migrate --source CAMINHO
```

**O JSON original e sua cópia datada contêm credenciais em claro.** Depois de conferir as contas e o backup cifrado, a exclusão desses arquivos, da lixeira e de outras cópias é manual. Em SSDs e sistemas com snapshots, excluir um arquivo não garante eliminação física de todas as versões. No Windows, a cópia do legado herda as ACLs do diretório de origem.

## Segurança

O formato PVLT v1 usa scrypt com N=32768, r=8, p=1 e AES-256-GCM. Cada gravação gera um nonce novo e autentica também o cabeçalho. A aplicação valida o custo do KDF e os limites do arquivo antes de decifrar. O cofre protege as credenciais armazenadas contra leitura sem a senha mestra. Uma senha fraca permite tentativas offline. Malware, keyloggers, dumps de memória e acesso à sessão desbloqueada estão fora dessa proteção. A sessão sobrescreve o buffer mutável da chave ao bloquear. Python e bibliotecas nativas podem manter outras cópias em memória.

No Linux os diretórios privados usam `0700` e os arquivos `0600`. No Windows, o isolamento depende da ACL NTFS herdada do perfil. O aplicativo rejeita vínculos nos destinos gerenciados. O armazenamento usa arquivo temporário cifrado, sincronização do arquivo e substituição atômica. O Windows faz novas tentativas se um indexador ou antivírus bloquear a troca brevemente. O log rotativo registra eventos sem credenciais.

A cópia de senha tem prazo de 30 segundos. O backend Win32 verifica o número de sequência antes de limpar e solicita a exclusão do histórico e da área de transferência em nuvem. A janela Tk fornece o identificador de proprietário para `OpenClipboard`. No Wayland a cópia usa a entrada padrão de `wl-copy`; Tk fornece o fallback. Gerenciadores externos podem conservar itens, e o encerramento abrupto interrompe os temporizadores. O bloqueio e a saída normal também limpam a cópia gerenciada.

## Gerar e conferir o executável

Em um Windows com Python 3.13 ou 3.12 x64, abra PowerShell na raiz e rode:

```powershell
.\build_windows.ps1
```

O script cria `.venv-build`, instala as versões de build fixadas, roda a suíte e empacota `PassVault.spec` com PyInstaller em modo onefile/windowed. O resultado fica em `dist\PassVault.exe`. O script aguarda o autoteste do processo gráfico e imprime tamanho e SHA-256. O arquivo inclui ícones, versão e manifesto DPI, usa privilégios do usuário e dispensa UPX. Pillow é usado somente na geração dos ícones.

Para conferir o autoteste e o hash separadamente:

```powershell
$p = Start-Process .\dist\PassVault.exe -ArgumentList '--self-test' -PassThru -Wait
$p.ExitCode
Get-FileHash .\dist\PassVault.exe -Algorithm SHA256
```

A definição do build fica em [PassVault.spec](PassVault.spec). Sua forma equivalente em linha de comando, a partir do ambiente de build, é:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name PassVault --paths . `
  --icon passvault/assets/passvault.ico --version-file version_info.txt `
  --manifest app.manifest --add-data "passvault/assets:passvault/assets" `
  --collect-all cryptography --noupx passvault/__main__.py
```

O workflow testa Windows e Linux, troca cofres fictícios entre os runners e publica o executável após o autoteste. Abra **Actions** no GitHub e escolha a execução correspondente ao commit. Os logs mostram a saída da suíte e o hash. A validação de distribuição consiste ainda em abrir o artefato em uma VM Windows limpa, sem Python, verificar ícone no Explorer/taskbar e propriedades, exercitar os fluxos de conta, bloqueio, clipboard, backup e importação, e conferir os temas e as escalas 100%, 150% e 200%.

Um executável sem assinatura pode gerar um aviso de reputação do SmartScreen. Confira a origem e o hash do artefato. Se houver detecção de antivírus, confira em VM limpa e envie o artefato ao fornecedor para análise. Para quem dispõe de certificado Authenticode no repositório pessoal de certificados e de um serviço de timestamp, a assinatura opcional usa o SDK do Windows:

```powershell
signtool sign /sha1 SEU_THUMBPRINT /fd SHA256 /tr URL_DO_SEU_SERVICO_DE_TIMESTAMP /td SHA256 dist\PassVault.exe
signtool verify /pa dist\PassVault.exe
```

Calcule novamente o hash após a assinatura. Mantenha o certificado e sua chave privada fora do repositório.

## Testar e solucionar problemas

```sh
python -m unittest discover -s tests -v
python -m passvault --self-test
python -m passvault --version
```

Os testes usam diretórios temporários e credenciais fictícias. O autoteste valida o carregamento de Tcl e cryptography, lock, criação, CRUD básico, desbloqueio, troca de senha e backup sem abrir uma janela.

| Sintoma | Procedimento |
| --- | --- |
| Falha ao iniciar Tk ou carregar DLL | Na execução por fonte, confira `python -m tkinter` e `python -c "import cryptography"` no mesmo ambiente. No executável, confira o hash e rode o autoteste. |
| DPI ou janela deslocada | Reinicie após mudar a escala. Com o aplicativo fechado, remova apenas `config.json` para restaurar a geometria e o tema padrão. |
| Clipboard ocupado | Tente copiar novamente após fechar o programa que o mantém aberto. Observe o aviso de fallback e verifique o histórico do sistema. |
| Cofre corrompido ou senha rejeitada | Confira o teclado e o Caps Lock. Na tela de acesso, restaure a cópia datada ou `.bak` com a senha daquela versão. |
| Outra instância aberta | Feche a janela anterior antes de iniciar a GUI ou a migração. A presença de `.lock` no disco é normal. |
| Falha de gravação | Confira espaço livre, ACLs/permissões e acesso à pasta do cofre. |

Para desinstalar o portátil, feche o PassVault e remova o executável. A pasta de dados é independente e sua exclusão remove também o cofre e os backups. Guarde primeiro uma cópia cifrada e a senha necessária para abri-la.

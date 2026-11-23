# PROMPT DE IMPLEMENTAÇÃO — PassVault

## 1. Papel

Você é um engenheiro de software sênior especializado em Python, segurança aplicada e interfaces desktop com tkinter. Implemente, teste e documente o projeto abaixo de ponta a ponta, trabalhando de forma autônoma. Não faça perguntas: se houver ambiguidade, siga este documento e registre a decisão no README.

Prioridade em caso de conflito: **segurança > integridade dos dados > usabilidade > conveniência**.

## 2. Contexto do usuário

O usuário guarda cerca de 40 senhas pessoais em um único arquivo JSON em claro. O arquivo atual é:

- Caminho: `/home/ianfalcao/my/4.json`
- Tamanho: ~5,3 KB, codificado em UTF-8 **com BOM**
- Permissões atuais: `0777` (qualquer usuário do sistema pode ler)
- Estrutura: `{"accounts": [ {...}, {...} ]}`
- Chaves encontradas nas contas: `service`, `email`, `username`, `id`, `user`, `password`, `pin`, `key`, `code`
- **O arquivo não é JSON válido**: faltam vírgulas entre objetos por volta das linhas 95–113. O reparo deve ser genérico, nunca baseado em números de linha fixos.
- O arquivo contém segredos reais: **nunca imprima seu conteúdo** em terminal, log, teste, commit ou mensagem.

Objetivo: substituir esse arquivo por um gerenciador de senhas desktop, com cofre cifrado em repouso, migrando os dados existentes com backup.

## 3. Ambiente verificado

- Linux, sessão Wayland (`DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`)
- Python 3.14.10
- `cryptography` 50.0.0 instalado no sistema
- `tkinter` disponível, Tcl/Tk 9.0, temas `clam`, `alt`, `default`, `classic`
- `wl-copy` e `wl-paste` disponíveis; `xclip` e `xsel` ausentes
- `pytest` ausente — use `unittest` da stdlib
- Diretório de trabalho: `/home/ianfalcao`

## 4. Objetivo e escopo

Criar o **PassVault**, aplicativo desktop em Python para gerenciar senhas pessoais:

- Interface gráfica com tkinter/ttk, em português do Brasil
- Cofre único cifrado com AES-256-GCM e chave derivada por scrypt
- Desbloqueio por senha mestra, sem armazená-la
- CRUD de contas, busca, gerador de senhas, cópia segura para clipboard
- Backup, restauração, troca de senha mestra e auto-lock
- Migração assistida do `4.json`, preservando o original e criando backup
- Testes automatizados com `unittest`
- Documentação completa em `README.md`

Local do projeto: `/home/ianfalcao/passvault`

## 5. Decisões fixas (não reabrir)

| Tema | Decisão |
|---|---|
| Interface | GUI tkinter/ttk, pt-BR |
| Cofre | `~/.local/share/passvault/vault.enc` (respeitar `XDG_DATA_HOME`) |
| Criptografia | scrypt + AES-256-GCM |
| Dependências | stdlib + `cryptography` apenas; nada de pip install |
| Testes | `unittest`, sem pytest |
| Migração | Importar e manter backup; nunca apagar o original automaticamente |
| Clipboard | Limpeza automática em 30 s |
| Auto-lock | 5 min de inatividade |
| TOTP/2FA | Fora do escopo desta versão |
| Layout | Pacote plano, executável com `python3 -m passvault` |

## 6. Requisitos funcionais

**FR-01 — Criar cofre.** No primeiro uso, tela de criação com senha mestra, confirmação e aviso explícito de que não há recuperação. Mínimo de 8 caracteres; aviso visual abaixo de 12. Criar diretório `0700`, arquivo `0600` e cofre vazio válido.

**FR-02 — Desbloquear.** Se o cofre existe, solicitar senha mestra. Senha errada ou arquivo corrompido exibem mensagem amigável e permitem tentar novamente. Não implementar bloqueio por tentativas (é local).

**FR-03 — Listar.** Tabela com `Serviço`, `Usuário` e `Tags`. Nunca exibir senhas na tabela. Ordenação por clique no cabeçalho (asc/desc).

**FR-04 — Buscar.** Campo de busca com filtro instantâneo, insensível a maiúsculas e acentos (normalização Unicode), sobre serviço, usuário, tags e URL. Não buscar dentro de senhas nem de notas.

**FR-05 — Adicionar.** Diálogo com serviço (obrigatório), usuário, senha (oculta, com botão mostrar), URL, notas e tags (separadas por vírgula). Botão para gerar senha. Salvar imediatamente no cofre.

**FR-06 — Editar.** Mesmo diálogo, pré-preenchido. Permitir alterar qualquer campo. Duplo clique na linha também abre a edição.

**FR-07 — Excluir.** Confirmação exibindo o nome do serviço. Remover pelo `id` interno, nunca pelo índice da tabela.

**FR-08 — Copiar senha.** Botão e atalho copiam a senha da conta selecionada. Preferir `wl-copy` via `subprocess` com a senha em `stdin` (nunca em argumentos de linha de comando). Limpar após 30 s com `wl-copy --clear`. Fallback: clipboard do tkinter com `after(30000, clipboard_clear)`, avisando na barra de status que a limpeza pode não sobreviver ao fechamento do app. Limpar também ao bloquear e ao sair.

**FR-09 — Gerador.** Comprimento 8–128 (padrão 24), maiúsculas, minúsculas, dígitos e símbolos; opção "evitar caracteres ambíguos" (`Il1O0o`); garantir ao menos um caractere de cada classe selecionada; usar `secrets`. Indicador simples de força por entropia.

**FR-10 — Revelar senha.** No painel de detalhes, senha mascarada com botão "Mostrar/Ocultar".

**FR-11 — Trocar senha mestra.** Solicitar senha atual, nova e confirmação. Verificar a atual, gerar novo salt, derivar nova chave e regravar o cofre atomicamente. Em caso de falha, o cofre antigo permanece intacto.

**FR-12 — Backup.** Botão que cria cópia cifrada datada em `~/.local/share/passvault/backups/vault-AAAAMMDD-HHMMSS.enc` com `0600`. Manter as 5 mais recentes. Além disso, antes de cada gravação, copiar o cofre anterior para `vault.enc.bak` com `0600`.

**FR-13 — Restaurar backup.** Listar backups disponíveis com data e tamanho, pedir confirmação, fazer backup do cofre atual e substituir pelo escolhido. Validar o backup com a senha mestra antes de confirmar a substituição.

**FR-14 — Importar legado.** Diálogo com caminho pré-preenchido `/home/ianfalcao/my/4.json`, botão "Analisar" que mostra contagem e avisos sem gravar nada, e botão "Importar" que:
- repara o JSON quebrado;
- normaliza os campos;
- grava no cofre;
- cria backup datado do original;
- ajusta a permissão do original para `0600`;
- mantém o original no lugar;
- exibe relatório de importados/ignorados/duplicados.

**FR-15 — Auto-lock.** Após 300 s sem teclado ou clique, apagar a chave da memória, limpar o clipboard e voltar à tela de desbloqueio. Verificar a inatividade a cada 5 s.

**FR-16 — Bloquear manualmente.** Botão e atalho fazem o mesmo que o auto-lock, imediatamente.

**FR-17 — Sair.** Ao fechar a janela, limpar chave e clipboard. Cada operação já grava o cofre, então não há alterações pendentes.

**FR-18 — Status.** Barra inferior com quantidade de contas, caminho do cofre e aviso quando o clipboard não pôde ser gerenciado com segurança.

**FR-19 — Atalhos.** `Ctrl+N` adicionar, `Ctrl+E` editar, `Ctrl+F` buscar, `Ctrl+C` copiar senha (apenas com foco na tabela), `Delete` excluir, `Ctrl+L` bloquear, `F5` recarregar, `Esc` limpar busca.

**FR-20 — Menu.** Arquivo (Backup, Restaurar backup, Importar legado, Trocar senha mestra, Sair), Editar (Adicionar, Editar, Excluir, Copiar senha, Gerar senha), Ajuda (Sobre).

## 7. Requisitos não funcionais

- 100% offline; nenhuma chamada de rede, telemetria ou analytics.
- Nenhum segredo em texto claro em disco, arquivo temporário, log, argv, ambiente, título de janela ou nome de arquivo.
- Escrita atômica e recuperável; nunca truncar o cofre em caso de erro.
- Desbloqueio em menos de 1,5 s em máquina típica; busca instantânea para até 1.000 contas.
- Mensagens de erro em português, sem traceback para o usuário.
- Código com type hints, docstrings curtas em português, sem estado global mutável.
- Sem `eval`, `pickle`, `yaml`, `os.system` ou `shell=True`.
- Testes não podem tocar no cofre real nem no `4.json` real: usar diretórios temporários e fixtures com dados falsos.

## 8. Arquitetura e arquivos

Criar exatamente esta estrutura:

```text
/home/ianfalcao/passvault/
├── passvault/
│   ├── __init__.py          # versão e metadados
│   ├── __main__.py          # ponto de entrada da GUI
│   ├── constants.py         # caminhos, tempos, limites, versão do formato
│   ├── errors.py            # exceções do domínio
│   ├── crypto.py            # scrypt, AES-GCM, serialização do cofre
│   ├── storage.py           # caminhos, permissões, escrita atômica, backup, lock
│   ├── vault.py             # modelo, CRUD, busca, sessão e troca de senha
│   ├── generator.py         # geração e força de senhas
│   ├── clipboard.py         # wl-copy com fallback tkinter
│   ├── migrate.py           # reparo do JSON legado e normalização
│   ├── app.py               # janela principal e fluxo de telas
│   └── dialogs.py           # diálogos modais
├── tests/
│   ├── fixtures/legacy_broken.json
│   ├── test_crypto.py
│   ├── test_storage.py
│   ├── test_vault.py
│   ├── test_generator.py
│   └── test_migrate.py
├── run.sh
├── requirements.txt
└── README.md
```

Responsabilidades:

- `crypto.py`: derivar chave, cifrar/decifrar bytes, montar/validar o formato binário. Não conhece GUI nem caminhos.
- `storage.py`: ler/gravar arquivo, permissões, backup, lock de instância, limites de tamanho. Não conhece GUI.
- `vault.py`: dados em memória, CRUD, busca, sessão desbloqueada, troca de senha. Não conhece GUI.
- `migrate.py`: reparo e normalização do legado, retornando dados prontos para `vault.py`.
- `app.py`/`dialogs.py`: apenas apresentação e orquestração.
- `clipboard.py` e `generator.py`: utilitários independentes e testáveis.

## 9. Especificação criptográfica

- KDF: `scrypt` do módulo `cryptography.hazmat.primitives.kdf.scrypt`
  - `n=2**15` (32768), `r=8`, `p=1`, `dklen=32`
  - `maxmem=64 * 1024 * 1024`
  - salt aleatório de 16 bytes via `secrets.token_bytes(16)`
- Cifra: `AESGCM` com chave de 32 bytes, nonce de 12 bytes via `secrets.token_bytes(12)`
- AAD: os bytes exatos do cabeçalho JSON, para autenticar os parâmetros do KDF
- Salt é gerado na criação do cofre e na troca de senha mestra; o nonce é novo em **toda** gravação
- A chave derivada fica apenas na sessão em memória; a senha mestra é descartada após derivar
- No lock, sobrescrever a chave com zeros (best effort) e descartar a referência
- Erros:
  - `InvalidTag` → `InvalidMasterPassword` com mensagem "Senha mestra incorreta ou cofre corrompido."
  - JSON inválido, magic errado, versão desconhecida, truncamento → `VaultCorrupted`
- Validar parâmetros do cabeçalho **antes** de derivar a chave, para impedir arquivo malicioso de consumir memória:
  - `n` entre `2**14` e `2**20` e potência de 2
  - `r` entre 1 e 32
  - `p` entre 1 e 16
  - `dklen == 32`
  - salt com exatamente 16 bytes; nonce com exatamente 12 bytes
  - cabeçalho com no máximo 4096 bytes; arquivo com no máximo 16 MiB

## 10. Formato do cofre

Arquivo binário, big-endian:

```text
[0..3]    magic "PVLT" (4 bytes ASCII)
[4]       versão do formato = 1 (uint8)
[5..8]    tamanho do cabeçalho (uint32 big-endian)
[9..]     cabeçalho JSON UTF-8 (tamanho informado)
[...]     ciphertext AES-GCM (inclui tag de 16 bytes no final)
```

Cabeçalho:

```json
{
  "v": 1,
  "kdf": "scrypt",
  "n": 32768,
  "r": 8,
  "p": 1,
  "dklen": 32,
  "salt": "<base64 de 16 bytes>",
  "nonce": "<base64 de 12 bytes>"
}
```

Conteúdo em claro (somente em memória), serializado de forma compacta:

```json
{
  "version": 1,
  "meta": {
    "created_at": "2026-11-23T00:00:00+00:00",
    "updated_at": "2026-11-23T00:00:00+00:00",
    "legacy_import": {
      "source": "/home/ianfalcao/my/4.json",
      "sha256": "<hash dos bytes originais>",
      "imported_at": "2026-11-23T00:00:00+00:00",
      "count": 40
    }
  },
  "entries": [
    {
      "id": "<uuid4>",
      "service": "Exemplo",
      "username": "usuario",
      "password": "segredo",
      "url": "",
      "notes": "",
      "tags": ["pessoal"],
      "extra": {},
      "created_at": "2026-11-23T00:00:00+00:00",
      "updated_at": "2026-11-23T00:00:00+00:00"
    }
  ]
}
```

Regras:

- `service` obrigatório e não vazio; os demais campos podem ser vazios
- `tags` é lista de strings, sem duplicatas case-insensitive
- `extra` preserva campos desconhecidos do legado
- Datas em ISO 8601 UTC com timezone
- `meta.legacy_import` é opcional e existe apenas após importação
- IDs são UUID4 e imutáveis

## 11. Armazenamento e integridade

Caminhos:

- Diretório: `$XDG_DATA_HOME/passvault` ou `~/.local/share/passvault`
- Cofre: `vault.enc`
- Backup anterior: `vault.enc.bak`
- Backups datados: `backups/vault-AAAAMMDD-HHMMSS.enc`
- Lock de instância: `.lock`
- Log: `$XDG_STATE_HOME/passvault/passvault.log` ou `~/.local/state/passvault/passvault.log`

Permissões:

- Diretório `0700`, cofre e backups `0600`
- Ao abrir, se o cofre tiver bits de grupo/outros, corrigir para `0600` e registrar aviso
- `umask` não pode ser a única proteção: usar `os.open`/`os.fchmod` explicitamente

Gravação atômica:

1. Criar temporário no mesmo diretório com `tempfile.mkstemp`, `fchmod(0o600)`
2. Escrever, `flush`, `os.fsync`
3. Fechar
4. Se o cofre existir, copiar para `vault.enc.bak` e ajustar permissão
5. `os.replace(temp, vault.enc)`
6. `fsync` no descritor do diretório
7. Em qualquer exceção, remover o temporário e não tocar no cofre

Instância única: adquirir `fcntl.flock(LOCK_EX | LOCK_NB)` no `.lock` ao iniciar. Se falhar, mostrar "O PassVault já está aberto em outra janela." e encerrar.

Log: `RotatingFileHandler` (1 MB, 2 backups), nível INFO. Nunca registrar senhas, conteúdo do cofre, chaves, salts ou nonces completos. Registrar apenas eventos: criação, desbloqueio, falha de desbloqueio, gravação, backup, importação, lock.

## 12. Interface gráfica

Janela principal: título "PassVault", 1000x650, mínimo 860x560, tema `clam`, fonte padrão do sistema.

Fluxo:

1. Adquirir lock de instância.
2. Se não existe cofre → diálogo "Criar cofre".
3. Se existe → diálogo "Desbloquear".
4. Só após sucesso montar a janela principal.

Layout:

- Barra superior com busca e botões: Adicionar, Editar, Excluir, Copiar senha, Gerar, Backup, Bloquear.
- `ttk.PanedWindow` horizontal: tabela à esquerda (~60%), detalhes à direita (~40%).
- Tabela `ttk.Treeview` com colunas Serviço, Usuário, Tags; seleção única; cabeçalhos ordenáveis; menu de contexto com Editar, Copiar senha, Excluir.
- Painel de detalhes com serviço, usuário, senha mascarada + Mostrar/Ocultar, URL, notas, tags, datas de criação/atualização e botão Copiar.
- Barra de status com contagem, caminho do cofre e mensagens temporárias.

Comportamentos:

- Busca com `trace_add("write", ...)` e normalização `unicodedata.normalize("NFKD", texto).casefold()`.
- Preservar seleção após editar; selecionar a conta recém-criada.
- Estado vazio com texto "Nenhuma conta encontrada".
- Confirmações com `messagebox.askyesno` para exclusão, troca de senha, restauração e importação.
- Senhas sempre com `show="•"`; nunca logar o conteúdo de `Entry`.
- Gerador abre diálogo modal e devolve a senha ao campo de origem.
- Auto-lock via `bind_all` em `<KeyPress>` e `<Button>`; timer com `after(5000, ...)`; ao bloquear, fechar diálogos abertos, limpar clipboard e voltar ao desbloqueio.
- Erros de domínio → `messagebox.showerror` com texto amigável; detalhe técnico apenas no log.

## 13. Migração do legado

Implementar `repair_json_text(texto: str) -> str` com um scanner que respeite strings e escapes:

- Percorrer caractere a caractere, rastreando `in_string`, `escape` e profundidade de `{`/`[`.
- Quando um `}` fora de string fecha um objeto dentro do array de nível 1 e o próximo caractere não branco é `{`, inserir uma vírgula.
- Não alterar conteúdo dentro de strings.
- Validar o resultado com `json.loads`; se falhar, levantar `LegacyParseError` com linha e coluna, sem gravar nada.
- Ler o arquivo com `encoding="utf-8-sig"` para remover o BOM.

Normalização de cada conta (apenas dicionários):

- `service`: `service` ou "Desconhecido"
- `username`: primeiro não vazio entre `username`, `email`, `user`, `id`
- `password`: primeiro não vazio entre `password`, `pin`, `key`, `code`
- `extra`: todos os outros campos, convertidos para string
- `tags`: `[]`; `notes`: `""`; `url`: `""`
- `id`: UUID4; datas: agora em UTC
- Duplicatas de serviço/usuário são permitidas e mantidas
- Contar importados e ignorados (entradas que não são dicionário)

Procedimento:

1. Calcular SHA-256 dos bytes originais.
2. Se `meta.legacy_import.sha256` for igual, avisar "este arquivo já foi importado" e só continuar com confirmação explícita do usuário.
3. Reparar, validar e normalizar em memória.
4. Criar backup `4.json.bak-AAAAMMDD-HHMMSS` com `0600` e ajustar o original para `0600`.
5. Gravar o cofre com os novos registros e atualizar `meta.legacy_import`.
6. Nunca apagar o original; informar que a exclusão é manual, após conferência.

Também disponibilizar execução sem GUI para diagnóstico e testes:

```bash
python3 -m passvault.migrate --source /home/ianfalcao/my/4.json --dry-run
python3 -m passvault.migrate --source /home/ianfalcao/my/4.json
```

Nesse modo, pedir a senha mestra com `getpass`, nunca por argumento. `--dry-run` não grava nada.

## 14. Testes automatizados

Criar `tests/fixtures/legacy_broken.json` com BOM, vírgulas ausentes e chaves variadas, usando **apenas dados falsos** (ex.: `SENHA-FAKE-123`). Cobrir:

`test_crypto.py`
- roundtrip cifra/decifra
- senha errada → `InvalidMasterPassword`
- cabeçalho adulterado → falha de autenticação
- ciphertext adulterado → falha de autenticação
- salt e nonce diferentes em gravações consecutivas
- parâmetros fora dos limites → `VaultCorrupted` sem derivar chave
- arquivo truncado, magic errado e versão desconhecida

`test_storage.py`
- permissões `0600` no cofre e `0700` no diretório
- escrita atômica preserva o cofre anterior em caso de erro simulado
- backup `.bak` criado antes da substituição
- temporário removido em caso de exceção
- cofre inexistente e cofre corrompido geram erros corretos
- lock de instância impede segunda abertura

`test_vault.py`
- criar, adicionar, editar, excluir e buscar
- busca insensível a acento e caixa
- tags sem duplicatas case-insensitive
- troca de senha mestra: senha antiga deixa de abrir, nova abre
- lock limpa a chave e impede operações
- serialização/desserialização preserva todos os campos

`test_generator.py`
- comprimento correto
- ao menos um caractere de cada classe selecionada
- exclusão de ambíguos
- comprimento inválido rejeitado

`test_migrate.py`
- reparo do JSON quebrado com BOM
- normalização de `email/username/id/user` e `password/pin/key/code`
- preservação de campos desconhecidos em `extra`
- contagem de importados e ignorados
- aborto sem gravar em JSON irrecuperável
- detecção de importação duplicada pelo SHA-256

Execução obrigatória:

```bash
cd /home/ianfalcao/passvault
python3 -m unittest discover -s tests -v
```

Todos os testes devem passar. Nenhum teste pode usar `/home/ianfalcao/my/4.json` nem o cofre real.

## 15. Critérios de aceite

1. `python3 -m unittest discover -s tests -v` termina com todos os testes OK.
2. `python3 -m passvault` abre a GUI no Wayland e permite criar, desbloquear, adicionar, editar, buscar, copiar, gerar, excluir, bloquear e sair.
3. `vault.enc` começa com `PVLT`, não é JSON legível e não contém uma senha fictícia usada nos testes (`grep -a` não encontra).
4. `stat -c %a ~/.local/share/passvault/vault.enc` retorna `600`; o diretório retorna `700`.
5. Senha mestra errada exibe mensagem amigável e não altera o arquivo.
6. Copiar senha coloca o valor no clipboard e, após 30 s, o clipboard não contém mais o segredo.
7. Auto-lock ocorre após 5 min e limpa chave e clipboard.
8. Troca de senha mestra mantém todas as contas e invalida a senha antiga.
9. Backup datado é criado e a restauração funciona.
10. A importação do `4.json` real importa todas as contas válidas, cria backup datado, mantém o original e corrige sua permissão para `600`.
11. Nenhum segredo aparece em log, terminal, argv, ambiente ou nome de arquivo.
12. `README.md` cobre instalação, uso, atalhos, backup/restauração, migração, segurança, testes e solução de problemas.

## 16. Documentação (`README.md`)

Incluir, em português:

- O que é o PassVault e o que ele não é
- Requisitos: Python 3.11+, `cryptography`, tkinter, `wl-clipboard` (opcional)
- Como executar (`./run.sh` e `python3 -m passvault`)
- Primeiro uso e criação do cofre
- Lista de atalhos
- Onde ficam cofre, backups e log
- Como fazer backup e restaurar
- Como migrar o `4.json`, o que é alterado e como apagar o original com segurança
- Formato do cofre em alto nível
- Modelo de ameaças: protege contra roubo de disco/backup/nuvem; não protege contra keylogger, malware, sessão comprometida ou senha mestra fraca
- Aviso de que não há recuperação de senha mestra
- Como rodar os testes
- Solução de problemas: tkinter ausente, clipboard no Wayland, cofre corrompido, restaurar `.bak`

## 17. Ordem de implementação

1. Scaffold, `constants.py`, `errors.py`, `crypto.py`, `storage.py`, `vault.py` e testes do núcleo.
2. `generator.py`, `clipboard.py` e testes.
3. `migrate.py` e testes com fixture.
4. GUI: criação, desbloqueio, lista, detalhes, CRUD e busca.
5. Diálogos restantes: gerador, backup, restauração, troca de senha, importação, auto-lock, atalhos.
6. Rodar testes completos, smoke test manual e só então executar a migração real do `4.json`, com backup e conferência da contagem.
7. Finalizar README e `run.sh`.

## 18. Estilo e restrições

- Type hints em todas as funções públicas; `dataclasses` para modelos.
- Exceções próprias em `errors.py`, sem `except:` nu.
- Nada de variáveis globais mutáveis; constantes em `constants.py`.
- Linhas de até 100 colunas; nomes e mensagens em português.
- `subprocess` sempre com lista de argumentos e sem `shell=True`.
- Não usar `print` para dados sensíveis; usar `logging`.
- Não adicionar dependências além de `cryptography`.
- Não criar instalador, serviço systemd, sincronização ou integração com navegador.

## 19. Não objetivos

- Sincronização entre dispositivos ou nuvem
- Extensão de navegador ou preenchimento automático
- TOTP/2FA, passkeys ou chaves de segurança
- Múltiplos cofres ou multiusuário
- Recuperação de senha mestra
- Suporte a Windows/macOS
- Auditoria de senhas vazadas ou integração com APIs externas

## 20. Instruções finais ao agente

- Trabalhe até concluir todos os critérios de aceite; não peça confirmações intermediárias.
- Nunca imprima, copie para teste ou registre em log os segredos reais do `4.json`.
- Não apague nem sobrescreva o `4.json`; apenas crie backup e ajuste a permissão durante a migração.
- Se a GUI não puder ser aberta no ambiente, valide toda a lógica pelos testes e registre no relatório o que ficou para verificação manual.
- Ao terminar, entregue um relatório com: arquivos criados, saída completa dos testes, contagem de contas migradas, caminho do backup gerado, checklist de aceite e limitações conhecidas.

---
title: O plugin é a única distribuição do PAR — CLI travado no uv.lock por launcher
date: 2026-10-02
status: approved
tags: [distribuicao, plugin, launcher, uv, mcp, hooks, preflight, superficies, release]
---

# O plugin é a única distribuição do PAR

## Resumo executivo

Hoje o PAR chega à pesquisadora por dois canais que andam separados: o plugin (skills, agents,
`.mcp.json`) e o CLI `prumo`, instalado à parte com `uv tool install git+…`. Os dois divergem
sem aviso. Em 2026-09-12 o CLI global 0.67.2 respondia a `prumo --version`, mas não tinha
`validate` nem `status`, e três skills ganharam contornos para isso. O detector de drift
gerado pela ADR-0019 nunca disparou.

Esta spec faz do plugin a **única** distribuição. Um lançador POSIX de 117 linhas,
`shims/prumo`, roda o código que já vem na raiz do plugin (`src/`). O ambiente é um venv que
o `uv` monta a partir do `uv.lock` daquela versão, em `~/.cache/prumo/`, e a chave do venv é
o conteúdo do lock e do próprio lançador. Três caminhos levam ao mesmo lançador:

- o servidor MCP, via `.mcp.json`;
- o Bash da sessão, porque um hook `SessionStart` põe `shims/` à frente do PATH;
- a forma `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"`, para máquinas em que a TI bloqueia hooks.

A identidade é a versão: um bloco gerado nas portas carimba `__version__`, e o preflight
compara com `prumo --version`. O único pré-requisito de runtime passa a ser o `uv`; nenhum
`uvx` roda na máquina da pesquisadora.

As decisões do dono que esta spec aplica são estas:

- **D1:** Windows (nativo e WSL) fica sem suporte, com mensagem fixa (o lançador detecta os dois)
  e regressão honesta ⚠ no CHANGELOG.
- **D3:** saem o `prumo-zettlr-export`, o `verify-refs --deep` e o servidor MCP do qmd.
- **D4:** a atualização automática vem por um arquivo estático do template.
- **D5:** os curingas Bash das portas ficam estreitos.

Junto entra a limpeza que o plugin único torna possível:

- o `init` não copia mais skills e agents;
- o `update` tira as cópias antigas para um backup, sem apagar nada;
- o pacote `integrations/` sai;
- o adeu entra no `uv.lock`.

Tudo isso sai num único evento breaking, a **0.71.0 MINOR ⚠**, junto com a parte 0.71.0 da
Spec B. O registro é a ADR-0038, que fica "proposta" até o spike S-canal e o job
`launcher-smoke` passarem. Os itens de Zotero e docx são da Spec B
(`2026-10-02-ponte-zotero-minima-design.md`, ADR-0037, que sai antes, na 0.70.3) e não se
repetem aqui.

## Contexto e problema

### Duas distribuições que divergem

- **Drift real.** O commit 5eb2c6b (2026-09-12) registra que o "CLI global 0.67.2 responde a
  `prumo --version`, mas não tem `validate` (nem `status`…)". Daí saíram três blocos de
  contorno: `skills/paper/modes/support.md:70-77`, `skills/review/modes/critique.md:110-112,120-122`
  e `skills/start/SKILL.md:35-38`.
- **O detector nunca disparou.** O `_PF_DRIFT` (`.github/scripts/gen_indexes.py:201-208`)
  compara versões usando `$CLAUDE_PLUGIN_ROOT` sem chaves, dentro de modos lidos com Read.
  Esses arquivos não recebem substituição, e a referência de plugins diz que as variáveis do
  plugin "aren't present in the environment of commands Claude runs through the Bash tool"
  (<https://code.claude.com/docs/en/plugins-reference>).
- **Um rename exigiu reinstalação.** O rename da 0.70.0 obrigou a reinstalar o CLI à parte
  (CHANGELOG 0.70.0).
- **Atualizar tem três passos.** Hoje são `/plugin marketplace update`,
  `uv tool upgrade prumo-assistant-for-researcher` e `/reload-plugins`. Quem esquece o segundo
  cai em drift silencioso: "No such command".
- **O MCP não acha o CLI recém-instalado.** O servidor depende do `prumo` global no PATH
  (`.mcp.json`: `"command": "prumo"`). No macOS, o app de janela lê o PATH do perfil do shell
  só ao abrir (<https://code.claude.com/docs/en/desktop>). Um CLI instalado no meio da sessão
  não aparece para o MCP até reiniciar o app.

### Nomes e servidores que nunca funcionaram para quem tem só o plugin

- **Prefixo das tools.** Um servidor de plugin expõe `mcp__plugin_<plugin>_<server>__<tool>`
  (<https://code.claude.com/docs/en/mcp>, §Plugin MCP tool names). Os `mcp__prumo__*` do
  reconcile nunca casaram para quem só tem o plugin. O dono nunca viu o problema por causa do
  `.mcp.json` de projeto deste repo: ele usa o mesmo comando do plugin, e a deduplicação por
  endpoint esconde o servidor do plugin. A correção do prefixo sai na 0.70.3 (Spec B). O
  comando novo desta spec acaba também com a deduplicação.
- **qmd.** O README do qmd (<https://github.com/tobi/qmd>) lista as tools MCP `query`, `get`,
  `multi_get`, `status` e `metadata`. Não existem `search` nem `embed`, e as skills citam
  `mcp__qmd__search` e `mcp__qmd__embed`. Para o consumidor, o prefixo seria de qualquer forma
  `mcp__plugin_par_qmd__*`. Quem não tem qmd vê ENOENT a cada sessão: a sessão que escreveu
  esta spec registrou "qmd (ENOENT): Executable not found in $PATH: qmd".

### `uvx` em runtime: pin que não pina e quebra offline

- **O pin não pina.** O `uvx adeu==1.29.0` (`review.py:763`) resolve hoje fastmcp 4.0.10 +
  mcp 2.2.0, combinação que o PAR nunca testou. O lock do PAR resolveria fastmcp 3.4.7 + mcp
  1.28.1.
- **Quebra offline.** Com o índice do uv envelhecido (12 min) e sem rede, o `uvx` falha
  (rc=2, "Request failed after 3 retries in 9.5s") mesmo com o ambiente inteiro em cache.
- **O `--deep` é inalcançável.** O `academic-refchecker` via `uvx` (`verify.py:431,480`) tem as
  mesmas dependências soltas (cffi, cryptography, idna, typing_extensions). Nenhuma skill nem
  tool chega a ele: o `mcp_server.py:217-221` o exclui, e as skills chamam `verify-refs` sem
  `--deep`.

### Cópias no projeto que sombreiam o plugin

- **Prompts congelados.** O `prumo init` copia skills e agents para `<pj>/.claude/`. Pela doc
  de subagents (<https://code.claude.com/docs/en/sub-agents>), `.claude/agents/` do projeto tem
  prioridade 3, e o `agents/` do plugin, prioridade 5. Um pj criado na 0.70.0 roda os prompts
  de reader, verifier e reviewer congelados e não recebe o `citation_checks` da 0.70.1.
- **O merge apagava customização.** O `init --merge` sobrescrevia cópias customizadas
  (`integrations/claude_code/installer.py:53,64`), ao contrário do "Merge — preserva seus
  arquivos" de `cli.py:284`.
- **Um pacote para uma cópia.** O pacote `integrations/` existe só para fazer essa cópia. Tem
  um adapter, uma ABC e uma exceção pública, `par.IntegrationError`.

### Permissões e atualização

- **Curingas largos demais.** `Bash(prumo paper *)` (`skills/paper/SKILL.md:10`) pré-aprova
  `prumo paper connect --create --yes`, que muda o Zotero. `Bash(prumo *)`
  (`skills/wiki/SKILL.md:11`) pré-aprova `prumo init --force` (rmtree, `cli.py:493-494`) e
  `prumo update --yes`.
- **Atualização automática desligada.** Marketplace de terceiro vem com atualização automática
  desligada: "third-party marketplaces default to `false`"
  (<https://code.claude.com/docs/en/settings-reference>, §extraKnownMarketplaces).

### Plataforma

- **Mac Intel.** A `cryptography` 49.0.0 entra via `mcp → pyjwt[crypto]` e não publica wheel
  para Mac Intel. Lá, o `uv sync --frozen` teria de compilar do sdist (Rust + OpenSSL).
- **Windows.** O código usa `symlink_to` (`paper/pdfs.py:115,121`), e o CI não testa Windows.
  Hooks em PowerShell não recebem `CLAUDE_ENV_FILE`, e as sessões WSL do Desktop não carregam
  plugins (<https://code.claude.com/docs/en/desktop-wsl>).

### Instalação de hoje

São 11 passos obrigatórios, em 4 métodos:

1. Adicionar o plugin pela conta.
2. Pedir `/par:start`.
3. Instalar o uv.
4. `uv tool install` do CLI.
5. Instalar Zotero e BBT.
6. Ligar o toggle da API local.
7. Rodar `prumo init`.
8. Abrir uma sessão no pj.
9. Pedir o `connect`.
10. Pedir o `sync`.
11. Instalar o pandoc.

Dois deles não estão documentados: o toggle e o pandoc. Há ainda uma anomalia: o canal da conta
(Customize → Plugins) não entrega o `par` à aba Code nesta máquina desde 2026-09-30. Os plugins
excluídos têm hooks ou MCP stdio, e a causa é desconhecida.

### O que o protótipo mediu

Medidas em macOS 27 arm64, uv 0.12.19, `/bin/sh` (bash 3.2 POSIX) e `/bin/dash`:

- **Caminho quente:** +6 ms (dash) e +13 ms (sh) sobre o Python direto (n=21).
- **`initialize` do MCP quente:** 0,40–0,48 s.
- **Frio com o cache do uv cheio:** 0,7–1,0 s.
- **Frio verdadeiro:** 3,2 s em rede rápida.
- **Corrida:** 40/40 partidas frias simultâneas com rc=0 e um único venv no fim.
- **Primeira preparação:**

  | Plataforma | Python 3.12 | Wheels com adeu | Total |
  |---|---|---|---|
  | macOS arm64 | 25,0 MB | 23–28 MB | ~50 MB |
  | Linux x86_64 | 34,3 MB | 28,8 MB | ~63 MB |

- **Lock com adeu:** vai de 54 para 99 pacotes, sem mudar nenhuma versão já pinada. O venv do
  lançador vai de 51 para 129 MB.

O lançador, com todas as correções da verificação adversarial, foi re-testado numa cópia nova do
repo em `$TMPDIR` durante a escrita desta spec. Passaram 28 de 28 checagens em `sh` e em `dash`:

- frio e quente;
- rebuild offline;
- corrida;
- Python pendurado;
- cwd sequestrador;
- MCP `initialize` com `serverInfo.version` = `__version__`;
- cache fixo;
- classificação 69/70/71/73/77/78/127/1;
- retry de TLS;
- 77 sob o Seatbelt real da sessão;
- hook idempotente.

A revisão da spec mudou depois três pontos do lançador: a detecção do WSL (saída 71), o teste
`-x` no uv (um uv inexistente ou um link pendurado vira 127, e não 69) e o texto da mensagem 71.
O texto final de §Componentes foi checado de novo numa cópia `git ls-files` em `$TMPDIR`, em
`sh` e em `dash`: frio (3,3 s, baixando o Python e as wheels em rede rápida) e quente (0,51 s)
em `prumo --version`; 71 com `WSL_DISTRO_NAME=Ubuntu`; 127 com `PRUMO_UV=/inexistente`; 1 sem
`src/`; 77 sob o Seatbelt da sessão. O ShellCheck 0.11.0 (`-s sh`, severidade padrão) sai limpo
no lançador e no hook. Das 28 checagens, só a classificação 71/127 passa pelas linhas mudadas, e
ela foi refeita acima; o `test_launcher` e o `launcher-smoke` repetem todas antes do corte.

## Decisões

### A1 · O plugin é a única distribuição; o CLI roda o código da raiz do plugin

**Decisão.** O `prumo` que a pesquisadora usa é sempre `${CLAUDE_PLUGIN_ROOT}/shims/prumo`, que
roda `${CLAUDE_PLUGIN_ROOT}/src/par`. Saem a instalação à parte (`uv tool install/upgrade`), o
console script `prumo-zettlr-export` (D3) e qualquer menção a PyPI. `uv tool install` e `uv run`
ficam só para desenvolvimento.

**Por quê.** O CLI passa a ter, por construção, a versão do plugin. O drift (5eb2c6b), o
"No such command" e o segundo passo de atualização deixam de existir. Para a pesquisadora,
atualizar o PAR é uma ação só.

**Alternativas rejeitadas.**

- PyPI/`uvx prumo==X.Y.Z` pinado: mais um artefato publicado por release, e o `uvx` falha
  offline com o índice envelhecido.
- `bin/` no topo do plugin: o chat e o Cowork recusam o plugin inteiro quando ele tem esse
  diretório (<https://code.claude.com/docs/en/plugins-reference>).
- MCPB: Python não embutido, e é um terceiro formato de empacotamento.
- MCP-first com ~35 tools: troca o Bash por contexto fixo por sessão.
- `command: uv` / `uv run --project` no `.mcp.json`: o MCP passa a depender do uv no PATH do
  app, e um uv recém-instalado não aparece sem reiniciar o app.

### A2 · Venv endereçado por conteúdo, em cache fixo `~/.cache/prumo`

**Decisão.** O venv mora em `$HOME/.cache/prumo/venv-3.12-<cksum(uv.lock + shims/prumo)>`. O
lançador o monta com `uv sync --frozen --no-install-project --compile-bytecode`.

- O cache é fixo: não se lê `XDG_CACHE_HOME`. `PRUMO_CACHE_DIR` e `PRUMO_UV` existem só para
  testes e CI.
- Um stamp vazio, `.prumo-ok`, marca o venv pronto.
- O caminho quente exige o stamp e `-x bin/python`.
- O `touch -c` a cada uso marca o venv como vivo, e o caminho frio apaga venvs sem uso há mais
  de 30 dias.

**Por quê.**

- **Releases sem mudança de dependência não têm espera.** Um bump só de versão reusa o venv
  (medido).
- **Nenhuma sessão viva é ressincronizada.** Vale também para raízes atualizadas no lugar
  (@synced, `--plugin-dir`), porque a chave é o conteúdo e não a raiz.
- **O cache tem de ser fixo.** No macOS, o app só herda o PATH do perfil do shell; "other
  variables you export there are not picked up" (<https://code.claude.com/docs/en/desktop>).
  Com um cache configurável pelo perfil, o MCP montaria um venv e o Bash outro. Com o sandbox
  ligado, o Bash ficaria frio para sempre, preso no 77.
- **A concorrência fica com o lock do próprio uv.** Foram 40/40 partidas frias simultâneas com
  um único venv no fim.

**Alternativas rejeitadas.**

- **Venv por raiz.** Raízes @synced vão para `.trash/` na hora, sem a carência de 14 dias.
- **Venv por versão.** Faz caminho frio a cada release, à toa.
- **`.python-version`.** É um arquivo a mais e mexeria no `.venv` 3.13 do dono. A constante
  `_py=3.12` no lançador basta.
- **Venv em `${CLAUDE_PLUGIN_DATA}`.** O diretório sobrevive a updates e o Claude Code o apaga
  ao desinstalar o plugin do último lugar, o que daria limpeza automática. Mas ele só existe
  como variável para hooks e servidores MCP; o Bash da sessão e os subagents não o veem. O hook
  teria de exportar `PRUMO_CACHE_DIR` para o env file, e a forma `sh` degradada (sem hook)
  montaria um segundo venv em outro lugar. Além disso, plugins synced e de marketplace têm
  diretórios de dados diferentes, o que daria dois venvs. O trade-off é registrado na ADR-0038,
  e a limpeza na desinstalação fica documentada (§Release e migração).

### A3 · Boot isolado e Python fixo

**Decisão.** O lançador termina em
`exec "$_venv/bin/python" -I -B -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from par.cli import app; app(prog_name="prumo")' "$_root/src" "$@"`.

- Não existe `src/par/__main__.py`, nem `PYTHONPATH`, nem `PRUMO_LAUNCHER_ROOT`.
- `_py=3.12` vale só no sync, via `UV_PYTHON` e `UV_PYTHON_PREFERENCE=only-managed`.

**Por quê.**

- **`-I`:** ignora o cwd, as variáveis `PYTHON*` e o site do usuário. Um `yaml.py` ou um `par/`
  no projeto não sequestra o CLI. O desenho antigo, com `PYTHONPATH`, imprimiu `HIJACKED yaml`.
- **`-B`:** não grava bytecode na raiz do plugin. As dependências já vêm compiladas do sync.
- **3.12:** a importação do servidor MCP leva 0,38 s em 3.12, contra 0,62 s em 3.11, e o
  adeu exige Python ≥ 3.12.

**Alternativas rejeitadas.**

- **`python -m par` com `PYTHONPATH`:** permite o sequestro pelo cwd, e a variável vazaria para
  os netos.
- **`PYTHONPYCACHEPREFIX`:** anula o `--compile-bytecode`, e sob o sandbox recompilaria as
  dependências a cada chamada.

### A4 · Falhas classificadas, uma mensagem por remédio

**Decisão.** Toda falha do lançador sai com uma linha que começa com `PAR:`, seguida do
comando de correção e de um `Detalhe:` (1ª e última linha do erro do uv).

| Saída | Causa |
|---|---|
| 127 | falta o uv (nenhum `uv` executável) |
| 69 | sem rede |
| 73 | sem espaço ou sem escrita |
| 77 | sandbox do Claude Code |
| 78 | uv antigo, ou configurado sem download de Python |
| 70 | venv sem Python |
| 71 | Windows ou WSL |
| 1 | plugin incompleto |

A classificação segue esta ordem:

1. Erros determinísticos de configuração viram 78: "Failed to parse `uv.lock`"/"uv version", e
   "downloads are set to", cujo remédio é `uv python install 3.12`.
2. `SANDBOX_RUNTIME=1` é o sinal primário de sandbox e vira 77, cujo 1º remédio é "repita fora
   do sandbox".
3. "Operation not permitted" e o pânico `dynamic_store` do uv 0.8 sob o Seatbelt também viram 77.
4. Disco e permissão viram 73, com remédio de espaço ou de dono da pasta.
5. O resto vira 69.

Num erro de certificado há uma 2ª tentativa com `UV_NATIVE_TLS=1 UV_SYSTEM_CERTS=1`, passadas
só àquela chamada do uv.

**Por quê.**

- **A string só não identifica o sandbox.** No Linux e no WSL2 o sandbox é bubblewrap com a raiz
  montada só para leitura, e `touch ~/x` "Fails with `Operation not permitted` on macOS, or
  `Read-only file system` on Linux and WSL2" (<https://code.claude.com/docs/en/sandboxing>). Pela
  string, o EROFS cairia em 73 com o remédio errado.
- **O Claude Code marca o sandbox.** Ele exporta `SANDBOX_RUNTIME=1` nos comandos que roda
  dentro do sandbox (observado nesta sessão, inclusive no macOS).
- **`UV_SYSTEM_CERTS` sozinha falha em uv antigo.** Ela só existe a partir do uv 0.11. Do 0.5.20
  ao 0.10.12, o uv conhece só `UV_NATIVE_TLS`, e o 0.12.19 aceita as duas.
- **Recusa de download.** Com `python-downloads = "manual"`, o próprio uv sugere
  `uv python install 3.12`. Com `"never"`, o `uv python install` recusa e pede `"manual"`
  (medido). A mensagem cobre os dois casos.
- **Hosts de download do Python.** O uv 0.12 baixa o Python de `releases.astral.sh`. Os uv
  antigos baixam de `github.com`, que redireciona para `objects.githubusercontent.com` e
  `release-assets.githubusercontent.com`. A mensagem 69 lista todos.
- **Sem piso numérico de uv no README.** Os uv até 0.5.19 falham ao ler o lock atual, e a
  partir do 0.5.20 funcionam. Mas qualquer `uv lock` futuro, feito com um uv novo, pode subir
  esse piso em silêncio. O 78 em runtime já diz o que fazer.

**Alternativas rejeitadas.**

- **Ler o cabeçalho `revision` do lock:** não discrimina; o que quebra os uv antigos é outro
  campo.
- **Um 2º sync offline primeiro:** com o cache completo, o `uv sync --frozen` já não faz
  nenhuma requisição (medido em 4 versões do uv).
- **Forçar `UV_SYSTEM_CERTS` sempre:** quebrava o TLS sob o Seatbelt.

### A5 · Três caminhos, um lançador

**Decisão.**

1. **MCP:** `.mcp.json` roda `/bin/sh ${CLAUDE_PLUGIN_ROOT}/shims/prumo mcp serve`. Não depende
   de PATH, de hook nem do bit de execução.
2. **Bash normal:** o hook `SessionStart` (forma exec: `"command": "/bin/sh"` com `args`) grava
   `export PATH='<raiz>/shims':"$PATH"` no `CLAUDE_ENV_FILE`. Assim `prumo …` casa com as regras
   `Bash(prumo …)` das portas.
3. **Bash degradado** (hooks bloqueados pela organização): a forma
   `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` do bloco runtime, com um prompt por comando.

**Por quê.**

- **O diálogo de permissão fica legível.** Ele mostra `prumo paper sync`, e não um caminho de
  120 caracteres. O "não perguntar de novo" continua valendo entre versões, e nenhum modo
  precisa ser editado.
- **A forma exec é a recomendada pela doc.** A documentação de hooks diz "Prefer exec form for
  any hook that references a path placeholder"
  (<https://code.claude.com/docs/en/hooks>, §Exec form and shell form). Os elementos de `args`
  passam sem shell, então apóstrofo, `$` e crase no caminho não quebram nada.
- **O PATH anexado serve ao MCP aberto pelo app.** O lançador anexa `~/.local/bin`,
  `/opt/homebrew/bin` e `/usr/local/bin` ao fim do PATH. Assim o MCP acha uv, pandoc e typst sem
  reiniciar o app, inclusive um uv instalado no meio da sessão.

**Alternativas rejeitadas.**

- **Gêmeos absolutos nas regras de `allowed-tools`:** dobram as portas para servir só às
  máquinas com hooks bloqueados.
- **Hook em forma shell:** depende de aspas em volta do placeholder. Fica como fallback se o
  S-canal mostrar que a forma exec não roda (§Spikes).

### A6 · Identidade por versão, carimbada por um único gerador

**Decisão.** O `gen_indexes.py` passa a gerar o bloco `<!-- prumo:runtime:begin/end -->`. Ele
lê `__version__` de `src/par/_version.py` e escreve o bloco em sete arquivos: as cinco portas
com modos, o `start` e `agents/reader.md`, o único agent com Bash. O preflight compara
`prumo --version` com a versão do bloco.

O `gen_indexes.py` é o **único escritor** do bloco, e o `RELEASING.md` é emendado assim:

- os passos 3 e 4 rodam o gerador com `uv run`;
- o passo 6 acrescenta `skills agents` ao `git add`.

O `sync_manifest_version.py` continua cuidando só dos manifests.

**Por quê.**

- **A versão não pode ser lida do ambiente.** Os modos são lidos com Read, sem substituição, e
  o Bash não tem `CLAUDE_PLUGIN_ROOT`. O bloco carimbado na porta é o único lugar onde o modelo
  lê a versão esperada sem chamada extra.
- **Opção escolhida: um escritor só.** A alternativa era carimbar com uma regex stdlib dentro do
  `sync_manifest_version.py`. Ela exigiria emendar o passo 6 do RELEASING do mesmo jeito,
  porque os sete arquivos recarimbados também precisam entrar no commit de release. Também
  criaria dois escritores para o mesmo bloco, contra a regra do repo "edite a fonte e rode o
  gerador". Com um escritor só, o `gen_indexes --check` do CI já pega qualquer esquecimento.
- **O `gen_indexes` precisa do `uv run`.** Ele importa `par.core.skills`, que importa `yaml`.
  Com `/usr/bin/python3` falha (reproduzido), e daí a emenda dos passos 3 e 4.

**Alternativas rejeitadas.**

- **Identidade pela raiz (`(plugin: <raiz>)` no `--version`):** a raiz muda com @synced e com
  symlink.
- **Preflight lendo o `plugin.json` a cada skill:** uma chamada a mais por preflight.
- **Carimbo stdlib no `sync_manifest_version.py`:** é a opção descartada acima.

### A7 · Preflight dos modos `cli` reescrito

**Decisão.**

- Sai o `_PF_DRIFT`.
- O `_PF_CLI` vira um item de superfície e versão (texto final em §Componentes). Ele reconhece a
  falta do uv pela linha `PAR: falta o uv`, nunca pelo exit 127.
- O preflight dos modos `cli` cai de 3 para 2 itens.
- Saem os três contornos de "No such command" e o bullet `uv tool` de cinco modos.

**Por quê.**

- **O 127 é ambíguo.** O Bash devolve 127 para `command not found` (hook não rodou), e o
  `sh /caminho/inexistente` do macOS também. O `dash` devolve 2. Pelo código, o modelo
  ofereceria instalar o uv quando o problema é outro. Toda mensagem do lançador começa com
  `PAR:`, e é por ela que o preflight decide.
- **Um CLI antigo instalado à parte faria o conselho girar em loop.** No modo degradado, um
  `prumo` antigo em `~/.local/bin` (o dono e o colega do piloto da F2 têm um) responde com outra
  versão. "Abra uma sessão nova" não resolve isso.
- **A forma do caminho separa os dois casos.** Todo `prumo` do plugin termina em `/shims/prumo`.
  Um `…/shims/prumo` de outra raiz é outra versão do plugin: o env file ainda aponta a raiz de
  antes de um update feito no meio da sessão, ou há duas linhas de hook (`--plugin-dir` junto
  com o marketplace). Ali o remédio é a sessão nova, e `uv tool uninstall` não faria nada.
  Qualquer outro caminho é o CLI antigo, e só para ele o preflight oferece, uma vez,
  `uv tool uninstall prumo-assistant-for-researcher`.
- **Quem não tem `prumo` cai na forma `sh` com a mesma classificação.** Com hooks bloqueados e
  sem uv, a forma `sh` sai com `PAR: falta o uv`. O preflight aplica a ela os mesmos casos da
  saída de `prumo --version`, e assim a pessoa vai ao `/par:start` em vez de ouvir "abra uma
  sessão nova" a cada sessão.

**Alternativa rejeitada.** Um código de saída próprio para "falta o uv". Seria mais um número
para o modelo decorar, e o prefixo textual já basta.

### A8 · Dependências: adeu no lock, nenhum `uvx` em runtime

**Decisão.**

- **adeu no lock.** Entra `"adeu==1.29.0; python_version >= '3.12'"` como dependência principal,
  sem extra. A chamada vira
  `[sys.executable, "-I", "-m", "adeu.cli", "extract", "--json", docx, "-o", "-"]`, com
  pré-checagem `importlib.util.find_spec("adeu")`.
- **Restrição para Mac Intel.** Entra
  `[tool.uv] constraint-dependencies = ["cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'"]`.
- **Sai o `--deep` (D3).** Com ele saem `REFCHECKER_PIN`, `_run_refchecker`,
  `_findings_from_report`, `_bib_subset_text` e `RefcheckerUnavailableError`.
- **Sai o motor do `uvx`.** Saem `core/uvx.py` e `tests/unit/core/test_uvx.py`, e a escada de
  erros (timeout e exit≠0) fica inline em `review.py`.

**Por quê.**

- **O adeu fica igual e passa a funcionar offline.** A saída é byte-idêntica à do `uvx` em
  3.12 e 3.13. O adeu fica travado com as dependências transitivas e funciona offline depois
  da 1ª preparação.
- **`-I`, pelo mesmo motivo de A3.** Sem isolamento, um diretório `adeu/` no cwd sequestra o
  `python -m adeu.cli` (verificado). O `-P` sozinho trata só o cwd: um `PYTHONPATH` ou
  `PYTHONHOME` exportado pela pesquisadora (comum com conda) ainda poria outro fastmcp ou outro
  mcp à frente dos travados no lock. O `-I` implica `-E -P -s`, e o `find_spec("adeu")` sob `-I`
  já foi medido como verdadeiro no venv do lançador.
- **O `--deep` é invisível para a pesquisadora.** Levá-lo ao lock custaria +50 MB de download e
  +128 MB de venv, e instalaria um pacote top-level chamado `backend`.
- **A linha da `cryptography`.** Com ela, o lock bifurca em 48.0.1 para Mac Intel e 49.0.0 nas
  demais plataformas. O dry-run com `--python-platform x86_64-apple-darwin` falha sem a linha e
  passa com ela.

**Alternativas rejeitadas.**

- Extras `[review]`/`[refs]`: exigiriam `--extra` no lançador, e `--all-extras` puxaria o `dev`.
- Manter o `uvx` com `--offline` primeiro.
- `pypandoc-binary`: a wheel arm64 traz um pandoc x86_64, que falha com "bad CPU type"; o bug
  upstream #447 está aberto.
- `typst` no lock: +30 MB, e nenhuma skill pede pdf.

### A9 · qmd só como CLI (D3)

**Decisão.**

- O servidor `qmd` sai do `.mcp.json`.
- As skills usam o CLI `qmd`, já pré-aprovado por `Bash(qmd *)`.
- Saem `mcp__qmd__embed`, `mcp__qmd__query` e `mcp__qmd__search` de `allowed-tools` e do corpo
  dos modos.
- O `_PF_QMD` passa a checar o CLI com `qmd --version`, que a regra `Bash(qmd *)` já cobre. Um
  `command -v qmd` não casa com nenhuma regra e pediria permissão no preflight, pelo menos uma
  vez por projeto.
- No `wiki ingest`, o próprio agente roda `qmd embed`, ou `prumo wiki index` na 1ª vez.
- `wiki ingest` e `wiki query` continuam com `requires: [qmd]`, sem `cli`. O trabalho deles
  (ler e escrever Markdown, responder do wiki) não precisa do CLI; o `prumo` aparece só em
  passos opcionais (`prumo wiki index` na 1ª indexação, `prumo wiki finding` ao arquivar uma
  resposta). Com `cli`, o preflight recusaria a consulta inteira numa máquina sem uv. Nesses
  passos, o modo usa `prumo` ou, se ele não existir, a forma `sh` do bloco PAR da porta; uma
  saída com linha `PAR:` é repassada, e o modo segue sem o passo opcional. Fica sem a checagem de
  versão do `_PF_CLI`; o resíduo aceito é um CLI antigo no modo degradado rodar `wiki finding`
  ou `wiki index`, que existem desde antes da 0.67.
- A instalação passa a ser `npm install -g @tobilu/qmd` (ou `bun install -g @tobilu/qmd`).

**Por quê.**

- Os nomes MCP nunca casaram para o consumidor, e dois deles não existem.
- O servidor dá ENOENT para quem não tem qmd.
- A ADR-0026:29 ("o `.mcp.json` do plugin continua sem qualquer MCP de terceiro") passa a ser
  verdadeira.
- A busca semântica funciona sem reiniciar a sessão.

**Alternativa rejeitada.** Um MCP de escopo de usuário recomendado pelo produto. O dono pode
registrar um por conta própria; o produto não depende disso.

### A10 · Sai o `prumo-zettlr-export`; o perfil do Zettlr usa uma cópia do filtro no projeto (D3)

**Decisão.**

- Saem o console script, `zettlr_export_entry` e o passo 5 do `project_guide.md`.
- O `prumo write zettlr-profile` copia `zotero_live_docx.lua` para
  `<pj>/docs/templates/zotero_live_docx.lua` e aponta o perfil para essa cópia.
- O `doctor` acusa três casos: cópia divergente, filtro fora do projeto e filtro inexistente.
  O remédio é `prumo write zettlr-profile`.
- O `docs/templates/prumo-docx.yaml`, que tem caminhos absolutos da máquina, entra no
  `.gitignore` do `pj_base` (projetos novos). Nos pj existentes, o próprio
  `prumo write zettlr-profile` acrescenta a linha ao `<pj>/.gitignore` quando ela falta: o
  `prumo update` só traz arquivos ausentes e só compara `.claude/rules/`, então nunca levaria a
  linha a um `.gitignore` que já existe.

**Por quê.**

- **O comando custom quebraria.** O Zettlr passa só o caminho do arquivo, e o comando precisa
  estar no PATH, "or be specified with an absolute path" (zettlr-docs, custom-commands). Com a
  raiz versionada, esse caminho absoluto muda a cada release.
- **O perfil importado fica na pasta de dados do Zettlr.** Por isso o caminho do filtro precisa
  ser estável. Com a cópia no projeto, a pesquisadora reimporta uma última vez e nunca mais.
- **O docx canônico continua disponível.** Basta pedir ao Claude: "exporta o docx canônico de
  <arquivo>".
- **O perfil não vai para o git de ninguém.** Ele traz caminhos desta máquina; commitado, quebra
  o export do coautor que o importar a partir do mesmo pj.
- **Isto substitui decisões anteriores.** A ADR-0034:17 lista o `prumo-zettlr-export` entre os
  nomes que permanecem, e a spec `2026-07-22-zettlr-front-design.md` faz do custom command a rota
  do docx canônico (l.30, §4 e o fluxo de exports). A ADR-0038 registra a substituição, e aquela
  spec ganha uma nota (§Componentes, Documentação).

**Alternativa rejeitada.** Um segundo shim só para o Zettlr: mais um caminho absoluto versionado
para o mesmo problema.

### A11 · `init` sem cópias; `update` move as cópias antigas para backup, sem flag

**Decisão.** O `prumo init` para de criar `.claude/skills` e `.claude/agents`.

O `prumo update` procura as cópias com nome do PAR. Os nomes de skill vêm de `registry.names()`
∪ `registry.legacy_map()`; os de agent, de `agents/*.md` do plugin. Ele **sempre** move essas
cópias para `<pj>/.prumo/legacy-copies/<AAAAMMDD-HHMMSS>/{skills,agents}/` e lista o que moveu.
Nada é apagado.

- Nomes fora dessa lista nunca são tocados.
- `--dry-run` só lista.
- A remoção **não** passa pelo `--yes`. O `--yes` continua significando só "sobrescrever
  arquivos divergentes do template" (ADR-0029).
- O `doctor` emite um único `[skill_obsoleta]`, que junta as invocações antigas e as cópias, com
  o remédio `prumo update`.

**Por quê.**

- **O `--yes` é a flag errada.** Reusá-lo para apagar cópias faria o `prumo update --yes`
  recomendado sobrescrever também rules e `CLAUDE.md` customizados. Como o agente roda o
  `update` sem TTY, a confirmação item a item nunca aconteceria.
- **Mover é reversível, e é o que honra "sem perda de dados".** As cópias sombreiam o plugin,
  então ficar com elas é pior que o drift. `.prumo/` já é ignorado pelo git do `pj_base` e
  pulado pelas varreduras de `skill_refs`.
- **Alguém pode ter customizado uma cópia.** O relatório diz como recriá-la com outro nome.

**Alternativas rejeitadas.**

- **Perguntar item a item:** sem TTY, nunca pergunta.
- **Apagar confiando no git:** nem todo pj é repo git, e as cópias podem não estar commitadas.
- **Manter `legacy_installed_dirs`:** só apontava o problema, e deixava a pessoa decidir sem dar
  o remédio.

### A12 · Sai o pacote `integrations/`; o Princípio III muda de texto

**Decisão.**

- Apagar `src/par/integrations/` e `tests/unit/integrations/`.
- Tirar `IntegrationError` de `par/__init__.py` (inclusive de `__all__`) e de `cli.py`.
- O `_entry` desaparece, e o bloco `__main__` chama `app()`.
- O Princípio III perde "via seu `BaseIntegration`" na emenda 1.2.3.
- O Princípio I fica intocado: "vira `integrations/<host>/installer.py`" descreve um host
  futuro e continua verdadeiro.

**Por quê.** Princípio VI. Uma ABC com um adapter cujo único trabalho era a cópia que A11
elimina é abstração sem uso, além de um loop morto no `doctor` e de uma flag sem destino. O
protótipo sem o pacote passou 1248 testes, com ruff e mypy limpos.

**Alternativa rejeitada.** Manter a base vazia "para o próximo host". O ROADMAP (bullet
"**Sem multi-host.**" em "Decisões deliberadas postergadas") já posterga o multi-host com
trigger, e o adapter nasce junto com o primeiro host novo.

### A13 · Atualização automática por arquivo estático do template (D4)

**Decisão.** Novo `templates/pj_base/.claude/settings.json`, sem código novo:

```json
{
  "extraKnownMarketplaces": {
    "prumo-assistant-for-researcher": {
      "source": { "source": "github", "repo": "raphaelfh/prumo-assistant-for-researcher" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "par@prumo-assistant-for-researcher": true }
}
```

- O `prumo init` o copia, porque o overlay leva o template inteiro.
- O `prumo update` o leva aos pj existentes como **arquivo ausente**, que entra direto.
- Um `.claude/settings.json` que já exista no pj nunca é tocado. A comparação de divergência do
  `update` só olha `.claude/rules/` (`scaffold.COMPARE_PREFIX`).

**Por quê.**

- **Atualização automática.** `autoUpdate` vence o default `false` de marketplace de terceiro
  (<https://code.claude.com/docs/en/settings-reference>).
- **Coautor.** Depois do diálogo de confiança da pasta, o Claude Code oferece o PAR ao coautor
  que abrir o pj.
- **Arquivo em vez de código.** Código só no `init` nunca chegaria aos pj que já existem, e o
  arquivo estático chega pelo `update`.

**Alternativa rejeitada.** Escrever o JSON no `init`, com merge num settings existente: é
código e testes de merge para um ganho que o template dá de graça.

### A14 · Curingas Bash estreitos, editados na fonte (D5)

**Decisão.** Os curingas largos (`Bash(prumo *)`, `Bash(prumo paper *)`) saem do
frontmatter dos modos. O gerador refaz as portas. Os modos ficam assim:

| Modo | `allowed-tools` |
|---|---|
| `paper/modes/extract.md` | `Read Write Edit Glob Grep Bash(prumo paper extract-prep *) Bash(prumo paper extract *) Bash(prumo paper sync-pdfs *) Bash(cat *) Agent` |
| `paper/modes/library.md` | `Read Write Edit Glob Grep Bash(prumo paper sync *) Bash(prumo paper sync-pdfs *) Bash(prumo paper graph *) Bash(prumo paper find *) Bash(prumo paper lint *) Bash(prumo paper set-primary *) Bash(prumo paper migrate-layout *) Bash(rg *)` |
| `wiki/modes/ingest.md` | `Read Write Edit Glob Grep WebFetch Bash(qmd *) Bash(prumo wiki *)` |
| `wiki/modes/query.md` | `Read Glob Grep Bash(qmd *) Bash(prumo wiki *) Bash(prumo paper find *) Bash(cat *)` |
| `wiki/modes/study.md` | `Read Write Edit Glob Grep Bash(qmd *) Bash(prumo wiki *) Bash(prumo paper find *) Bash(echo *) Bash(cat *)` |

**Por quê.**

- **Os comandos que mudam coisas voltam a pedir permissão.** `prumo paper connect` (muda o
  Zotero; ADR-0026:21 e :29, ADR-0028), `prumo init --force` (rmtree) e `prumo update --yes`.
  Isso cumpre a intenção de `MUTATING_TOOLS`.
- **O curinga casa só o subcomando certo.** Um ` *` no fim casa o comando sem argumentos, e o
  espaço impede que `sync *` case `sync-pdfs`
  (<https://code.claude.com/docs/en/permissions>).
- **O custo é aceito.** São prompts nos raros usos dos comandos que mudam coisas. Há também o
  `prumo --version` do preflight, que pede permissão uma vez por projeto nas portas que não o
  cobrem (já era assim em paper, protocol, write e review).

**Alternativa rejeitada.** Um lint `requires⇔allowed-tools`. Em runtime, só o frontmatter da
porta vale, e só no turno (<https://code.claude.com/docs/en/skills>). O teste útil é outro:
nenhuma regra pode casar com os comandos que mudam estado fora do fluxo da skill, que são
`prumo paper connect`, `prumo init --force` e `prumo update --yes` (§Testes). Regras que
continuam casando com comandos que mudam arquivos dentro do fluxo da própria skill, como
`Bash(prumo write *)` (casa `prumo write review apply`) e `Bash(git *)` da porta `write`, ficam
fora do D5 (§Fora de escopo).

### A15 · Superfícies declaradas com honestidade; Windows fora (D1)

**Decisão.**

- **Canal recomendado:** o app Claude na aba Code (Mac) ou o Claude Code no terminal (Mac ou
  Linux), com o plugin instalado pelo marketplace.
- **Cowork:** "não suportado/testado no Cowork; use a aba Code". Só o julgamento sobre texto
  colado é garantido.
- **Chat, SSH e WSL:** não suportados.
- **Windows (nativo e WSL):** não suportado, com mensagem fixa: exit 71 no lançador, frase no
  `/par:start` e no `_PF_CLI`. Entra no CHANGELOG como ⚠ regressão honesta, porque o onboarding
  citava "instaladores nativos (não validados)".
- **O lançador detecta o WSL.** O Claude Code aberto num terminal dentro do WSL carrega
  plugins e se apresenta como Linux (`uname -s` = `Linux`, sem `OS`). Sem a checagem, o venv
  montaria normalmente, e o Zotero do Windows, inalcançável pelo NAT do WSL2, apareceria como
  "Zotero fechado". O lançador sai com 71 quando `WSL_DISTRO_NAME` ou `WSL_INTEROP` existem, ou
  quando `/proc/sys/kernel/osrelease` contém `microsoft`. Como o WSL nunca ganha venv, a checagem
  roda em toda chamada, sempre no caminho frio. A frase "Windows ou WSL" do `_PF_CLI` e do
  `start` fica como reforço, sem depender de o modelo reconhecer o WSL.

**Por quê.**

- **Cowork.** Rodar comandos numa VM ou no host depende de configuração e de um rollout
  controlado por flag (`requireCoworkFullVmSandbox`, documentado com default `false`; "host loop"
  atrás de feature gate). Por isso esta spec **não** afirma que o Cowork roda numa VM.
- **Windows.** Não há nenhum usuário conhecido. Suportá-lo exigiria:
  - um 2º lançador;
  - regras `PowerShell(prumo *)` em todas as portas;
  - CI no Windows;
  - um fallback para os symlinks.

  Além disso, as sessões WSL do Desktop não carregam plugins.

**Alternativa rejeitada.** "Use o WSL". Os plugins não carregam nas sessões WSL do app, e o
Zotero do Windows não é alcançável pelo localhost do WSL2 em NAT.

### A16 · Zotero atrás do sandbox Bash: referência à Spec B

**Não é decisão desta spec.** O ramo do Zotero sob o sandbox do Claude Code é da Spec B
(`2026-10-02-ponte-zotero-minima-design.md`). Lá, `core/deps.in_claude_sandbox()` entra na 0.70.3
com o aviso E2 do export docx, e as variantes E11 (linha `zotero` do `doctor`) e E15
(`paper connect`) entram na 0.71.0. A sonda é `_bbt_probe()`, e as mensagens usam `{base}`
(`zotero_base()`, que respeita `PRUMO_ZOTERO_BASE`).

Esta spec usa o sinal `SANDBOX_RUNTIME=1` só no lançador (saída 77, A4) e não acrescenta código
nem mensagem ao acesso ao Zotero. O número A16 fica reservado para não renumerar A17.

### A17 · Desenvolvimento do repo

**Decisão.**

- O `.claude/settings.json` deste repo ganha `"disabledMcpjsonServers": ["prumo"]` e perde
  `enabledMcpjsonServers`.
- O loop de dev é `claude --plugin-dir .`, que carrega o plugin no lugar como `par@inline`. No
  Desktop, o equivalente é `/plugin marketplace add ./`.
- `uv run prumo` e `uv run pytest` não mudam.

**Por quê.**

- **O `.mcp.json` também é lido como config de projeto aqui.** O placeholder não resolvido ali
  só gera aviso: "the config still loads" (<https://code.claude.com/docs/en/mcp>). Com a rejeição
  explícita, nem o aviso aparece.
- **O `--plugin-dir` reflete a edição na hora.** Uma mudança em `src/` vale na chamada seguinte,
  porque o lançador lê `<raiz>/src` a cada execução.

**Alternativa rejeitada.** `${CLAUDE_PLUGIN_ROOT:-.}`. Não se sabe se a substituição do plugin
aceita `:-`. Se não aceitar, quebra todos os consumidores.

## Arquitetura

```
                        ${CLAUDE_PLUGIN_ROOT}  (~/.claude/plugins/cache/prumo-assistant-for-researcher/par/<versão>/)
                        ├── shims/prumo        ← único arquivo do diretório (100755)
                        ├── hooks/{hooks.json, session-start.sh}
                        ├── .mcp.json          ← só o servidor prumo
                        ├── src/par/…  uv.lock  skills/  agents/  templates/
                        │
  app/CLI ── MCP stdio ──► /bin/sh shims/prumo mcp serve ─┐
  SessionStart hook ─────► CLAUDE_ENV_FILE: PATH=<raiz>/shims:$PATH
  Bash: `prumo paper sync` (regra Bash(prumo paper sync *)) ─┤
  Bash degradado: sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo" … ──┤
                                                             ▼
         ~/.cache/prumo/venv-3.12-<cksum(uv.lock+shims/prumo)>/   ← uv sync --frozen (só no caminho frio)
                                                             │
                     exec python -I -B -c '…from par.cli import app…' <raiz>/src  "$@"
```

- **Runtime:** só o `uv`. O adeu vem do lock; o pandoc e o typst são binários externos (o
  pandoc é da Spec B).
- **Identidade:** `prumo --version` (que imprime `prumo X.Y.Z`) e `serverInfo.version` são ambos
  `__version__`, e o bloco runtime da porta carimba a mesma versão.
- **Atualização:** a raiz nova chega com a sessão nova. Se o lock não mudou, é o mesmo venv. Se
  mudou, monta um venv novo, offline quando o cache do uv já tem as wheels. Sessões antigas
  seguem no venv antigo.

| Peça | Valor para a pesquisadora |
|---|---|
| `shims/prumo` | O CLI tem sempre a versão do plugin. Acabam o `uv tool install/upgrade` e o "No such command", e funciona offline depois da 1ª vez. |
| Venv por conteúdo em `~/.cache/prumo` | Atualizar sem mudar dependência não tem espera, e uma sessão aberta nunca quebra no meio. |
| Hook `SessionStart` | O pedido de permissão mostra `prumo paper sync`, e o "não perguntar de novo" vale entre versões. |
| Bloco runtime gerado | Em máquina de hospital com hooks bloqueados, o PAR ainda funciona, com um prompt por comando. A versão esperada fica visível ao preflight. |
| PATH anexado no lançador | O MCP aberto pelo app acha uv, pandoc e typst sem reiniciar o app. |
| Mensagens `PAR:` classificadas | Cada falha diz o remédio certo: rede, disco, sandbox ou uv antigo. |
| adeu no lock | A revisão docx funciona offline e com as dependências testadas. |
| `settings.json` do template (D4) | O PAR se atualiza sozinho no projeto e é oferecido ao coautor. |
| Curingas estreitos (D5) | Nada que mude o Zotero ou apague o projeto roda sem a pesquisadora ver. |
| `update` com backup | Projetos antigos passam a usar os prompts atuais dos agents, sem perder customização. |

## Componentes

### `shims/prumo` (novo, 100755, 117 linhas, único arquivo de `shims/`)

Texto final. As linhas que a revisão mudou depois do 28/28 foram checadas de novo em `sh` e
`dash` (§Contexto, "O que o protótipo mediu"):

```sh
#!/bin/sh
# prumo: lançador do CLI do PAR (ADR-0038). Roda o código DESTA raiz do plugin
# num venv que o uv monta a partir do uv.lock. Nada é instalado no sistema.
#
# Caminho quente: dois testes de arquivo e exec do Python.
# Caminho frio (1ª vez de cada uv.lock ou deste arquivo): `uv sync` em
#   ~/.cache/prumo/venv-<python>-<cksum(uv.lock + este arquivo)>.
# A chave é o CONTEÚDO, não a versão nem a raiz. Update que não mexe no uv.lock
# reusa o venv sem esperar, e uma raiz atualizada no lugar (@synced,
# --plugin-dir) nunca ressincroniza um venv que outra sessão está usando.
# O cache é fixo de propósito: o MCP aberto pelo app só herda o PATH do perfil
# do shell, e um cache configurável separaria o venv do MCP do venv do Bash.
# PRUMO_CACHE_DIR e PRUMO_UV existem só para testes e CI. Chamar este arquivo
# por link simbólico não é suportado (a raiz sairia errada).
#
# Saídas: 127 sem uv · 69 sem rede · 73 sem espaço/escrita · 77 sandbox do
# Claude Code · 78 uv antigo ou sem permissão de baixar Python · 70 venv sem
# Python · 71 Windows ou WSL · 1 plugin incompleto. Toda mensagem começa com
# "PAR:" e traz o comando de correção.

_py=3.12   # Python do venv, o mesmo da matriz do CI. Mudar aqui muda o hash e cria venv novo.
_days=30   # o caminho frio apaga venvs sem uso há mais de N dias

_die() {
  _c=$1; shift
  printf 'PAR: %s\n' "$1" >&2; shift
  [ $# -eq 0 ] || printf '  %s\n' "$@" >&2
  exit "$_c"
}

case $0 in */*) _d=${0%/*} ;; *) _d=. ;; esac
_root=$(CDPATH='' cd -- "$_d/.." 2>/dev/null && pwd -P) || _root=
[ -f "$_root/uv.lock" ] && [ -f "$_root/src/par/cli.py" ] ||
  _die 1 "instalação do plugin incompleta${_root:+ em $_root} (ou o lançador foi chamado por um link simbólico, o que não é suportado)." \
    "Reinstale o plugin (no app: + → Plugins → Gerenciar plugins; no terminal: /plugin uninstall par e /plugin install par@prumo-assistant-for-researcher) e abra uma sessão nova."

# Anexado (não prefixado): o MCP aberto pelo app de janela também acha uv, pandoc e typst.
PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"; export PATH
_cache=${PRUMO_CACHE_DIR:-$HOME/.cache/prumo}
_key=$(cat "$_root/uv.lock" "$_root/shims/prumo" | cksum)
_venv=$_cache/venv-$_py-${_key%% *}

_windows() {
  _die 71 "ainda não funciona no Windows nem no WSL (o PAR só é testado em macOS e Linux)." \
    "Por enquanto, use /par:review critique colando trechos do seu texto."
}

_sync() { # "$@": VAR=valor extras, só para esta chamada do uv
  _err=$(env "$@" UV_PROJECT_ENVIRONMENT="$_venv" UV_PYTHON="$_py" UV_PYTHON_PREFERENCE=only-managed \
    "$_uv" sync --project "$_root" --frozen --no-install-project --compile-bytecode --quiet 2>&1 >/dev/null)
}

_sandbox() {
  _die 77 "o sandbox do Claude Code bloqueou a preparação do PAR (só acontece na 1ª vez de cada versão)." \
    "Repita este comando fora do sandbox (o Claude pede sua permissão) ou abra uma sessão nova: o servidor do PAR prepara tudo ao iniciar, fora do sandbox." \
    "Detalhe: $_t"
}

_fail() {
  _t=$(printf '%s\n' "$1" | awk 'NF { if (f == "") f = $0; l = $0 } END { print f; if (l != f) print "  ... " l }')
  case $1 in
    *"to parse"*uv.lock* | *"uv version"*)
      _die 78 "o seu uv é antigo demais para esta versão do PAR." \
        "Atualize e repita: uv self update (ou brew upgrade uv, se ele veio do Homebrew)" \
        "Detalhe: $_t" ;;
    *"downloads are set to"*)
      _die 78 "a configuração do seu uv não deixa baixar o Python $_py que o PAR usa." \
        "Instale-o uma vez e repita: uv python install $_py && prumo --version (se o uv recusar, troque python-downloads de \"never\" para \"manual\" no seu uv.toml)" \
        "Detalhe: $_t" ;;
  esac
  # O Claude Code marca os comandos que roda dentro do sandbox (macOS e Linux).
  [ "${SANDBOX_RUNTIME:-}" != 1 ] || _sandbox
  case $1 in
    *"Operation not permitted"* | *dynamic_store*) _sandbox ;;
    *"No space left"* | *"Disk quota"* | *"ermission denied"* | *"Read-only file system"*)
      _die 73 "não consegui gravar em $_cache (disco cheio ou pasta sem permissão)." \
        "Libere espaço ou corrija o dono da pasta (sudo chown -R \"\$USER\" ~/.cache) e rode: prumo --version" \
        "Detalhe: $_t" ;;
    *)
      _die 69 "preparar esta versão do PAR precisa de internet uma única vez (cerca de 60 MB)." \
        "Conecte-se e rode: prumo --version" \
        "Em rede de hospital ou universidade, peça liberação de pypi.org, files.pythonhosted.org, releases.astral.sh, github.com e dos domínios de download do GitHub (objects.githubusercontent.com, release-assets.githubusercontent.com)." \
        "Detalhe: $_t" ;;
  esac
}

_prepare() {
  [ "${OS:-}" != Windows_NT ] || _windows
  case $(uname -s 2>/dev/null) in MINGW* | MSYS* | CYGWIN*) _windows ;; esac
  # O WSL se apresenta como Linux; as variáveis e o kernel dele o denunciam.
  [ -z "${WSL_DISTRO_NAME:-}${WSL_INTEROP:-}" ] || _windows
  case $(cat /proc/sys/kernel/osrelease 2>/dev/null) in *[Mm]icrosoft*) _windows ;; esac
  _uv=${PRUMO_UV:-$(command -v uv 2>/dev/null)}
  [ -x "$_uv" ] || _die 127 "falta o uv (instalação única)." \
    "Peça /par:start ou rode: curl -LsSf https://astral.sh/uv/install.sh | sh"
  _err=$(mkdir -p "$_cache" 2>&1) || _fail "$_err"
  # Rede com inspeção de HTTPS (comum em hospital): 2ª tentativa com os certificados
  # do sistema. UV_NATIVE_TLS vale em todo uv suportado; UV_SYSTEM_CERTS, só no 0.11+.
  _sync || { case $_err in *ertificate* | *UnknownIssuer*) _sync UV_NATIVE_TLS=1 UV_SYSTEM_CERTS=1 ;; *) false ;; esac; } ||
    _fail "$_err"
  [ -x "$_venv/bin/python" ] || _die 70 "o ambiente $_venv ficou sem Python executável." \
    "Apague a pasta e repita: rm -rf \"$_venv\" && prumo --version"
  { true >"$_venv/.prumo-ok"; } 2>/dev/null
  touch -c "$_venv" 2>/dev/null
  find "$_cache" -maxdepth 1 -type d -name 'venv-*' -mtime +"$_days" -exec rm -rf {} + 2>/dev/null
  return 0
}

if [ -f "$_venv/.prumo-ok" ] && [ -x "$_venv/bin/python" ]; then
  touch -c "$_venv" 2>/dev/null # marca uso, para a poda nunca levar o venv de uma sessão viva
else
  _prepare
fi

# -I: ignora cwd, PYTHON* e site do usuário (um yaml.py no projeto não sequestra o CLI);
# -B: não grava bytecode na raiz do plugin. As dependências já vêm compiladas do sync.
exec "$_venv/bin/python" -I -B -c 'import sys; sys.path.insert(0, sys.argv.pop(1)); from par.cli import app; app(prog_name="prumo")' "$_root/src" "$@"
```

Resíduo aceito: uma variável `_xxx` exportada pelo usuário com o mesmo nome de uma interna é
sobrescrita, porque o POSIX sh não tem `local`.

### `hooks/hooks.json` e `hooks/session-start.sh` (novos)

`hooks/hooks.json`, só com `SessionStart`, sem matcher, em forma exec:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/bin/sh",
            "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

`hooks/session-start.sh` (100755, 10 linhas):

```sh
#!/bin/sh
# SessionStart do plugin PAR (ADR-0038): põe o lançador desta raiz (shims/prumo)
# à frente do PATH do Bash da sessão, para `prumo` sem caminho casar com as
# permissões Bash(prumo ...) das skills. Idempotente, silencioso (stdout de
# SessionStart vira contexto do modelo) e nunca falha a sessão.
[ -n "${CLAUDE_ENV_FILE:-}" ] && [ -f "${CLAUDE_PLUGIN_ROOT:-}/shims/prumo" ] || exit 0
_q=$(printf '%s' "$CLAUDE_PLUGIN_ROOT/shims" | sed "s/'/'\\\\''/g")
_line="export PATH='$_q':\"\$PATH\""
{ grep -qxF -- "$_line" "$CLAUDE_ENV_FILE" || printf '%s\n' "$_line" >>"$CLAUDE_ENV_FILE"; } 2>/dev/null
exit 0
```

Não se registra nenhum outro evento. O `validate_manifests.py` **não** ganha checagem de hooks:
o workflow dele só roda quando muda `.claude-plugin/**`, e o `test_plugin_layout.py` já cobre o
caso em todo PR.

### `.mcp.json`

```json
{
  "mcpServers": {
    "prumo": {
      "command": "/bin/sh",
      "args": ["${CLAUDE_PLUGIN_ROOT}/shims/prumo", "mcp", "serve"]
    }
  }
}
```

O servidor `qmd` sai (A9). As tools aparecem como `mcp__plugin_par_prumo__*` em todos os canais,
e a Spec B já renomeia os nomes no `reconcile.md` na 0.70.3.

### `.github/scripts/gen_indexes.py`

- **Sai** `_PF_DRIFT` (201-208).
- **`render_preflight`:** `cli` contribui 2 itens, `_PF_CLI` e `_PF_INIT`, não 3. A docstring
  passa a dizer "itens 1-2".
- **`_PF_CLI` reescrito.** No modo, ele aparece renderizado assim:

  ```markdown
  > 1. **Superfície e CLI:** este modo precisa do app Claude na aba Code (Mac) ou do Claude Code
  >    no terminal (Mac ou Linux). Se esta conversa for uma tarefa do Cowork, um chat, uma sessão
  >    SSH ou rodar no Windows ou no WSL, diga em uma frase que este modo não é suportado aqui e
  >    que a pessoa deve abrir o app Claude na aba Code (Mac) ou o Claude Code no terminal (Mac ou
  >    Linux), e pare. Senão, rode `prumo --version`; o esperado é
  >    `prumo <versão do bloco PAR da porta>`.
  >    (a) `prumo` não existe: rode a forma `sh … --version` do bloco PAR e aplique (b)–(d) à
  >    saída dela; avise uma vez que cada comando vai pedir permissão. Só se a saída não trouxer
  >    nem a versão nem uma linha `PAR:`, diga "abra uma sessão nova" e pare.
  >    (b) Outra versão: rode `command -v prumo`. Caminho terminado em `/shims/prumo`: é outra
  >    versão do plugin; diga "este `prumo` é de outra versão do plugin — abra uma sessão nova".
  >    Qualquer outro caminho (por exemplo `~/.local/bin/prumo`): é o CLI antigo, instalado à
  >    parte; ofereça UMA vez, com consentimento, `uv tool uninstall prumo-assistant-for-researcher`
  >    (se a pessoa usa o Zettlr, antes peça "regenera o perfil do Zettlr" e a reimportação do
  >    perfil, que ainda aponta para dentro desse CLI). Nos dois casos, use a forma `sh …` nesta
  >    sessão.
  >    (c) A saída contém `PAR: falta o uv`: roteie para `/par:start` (que instala o uv com
  >    consentimento) e pare.
  >    (d) Qualquer outra linha que comece com `PAR:`: repasse-a (ela traz o comando de correção).
  >    Se for a do sandbox (saída 77), ofereça repetir o mesmo comando fora do sandbox, pedindo
  >    permissão; nos outros casos, pare.
  >    Nunca simule a operação.
  ```

  A string `uv tool uninstall prumo-assistant-for-researcher` aparece uma única vez no item, e
  `uv tool install`/`uv tool upgrade` não aparecem.

- **`_PF_QMD` reescrito:** "**Busca semântica (qmd):** rode `qmd --version`; só `command not
  found` significa ausente. Se ausente, diga isso explicitamente ("busca semântica
  indisponível — resultados via leitura direta, mais lentos/parciais") e prossiga só no fallback
  documentado por esta skill; sem fallback, recuse a operação com o hint do `prumo doctor`." O
  `qmd --version` casa com `Bash(qmd *)`, que os três modos `qmd` já têm (A14), e não pede
  permissão. O `_PF_QMD_SEM_CLI` continua acrescentando o roteamento para `/par:start` nos dois
  modos só-`qmd` (`wiki/ingest` e `wiki/query`, A9).
- **Novo `render_runtime()`**, que lê `__version__` com `from par._version import __version__`
  (o `sys.path` já inclui `src`) e devolve:

  ```markdown
  **PAR 0.71.0** · raiz do plugin: `${CLAUDE_PLUGIN_ROOT}`
  - CLI: `prumo`. Se `prumo` não existir nesta sessão (hooks bloqueados pela organização), use `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"`: funciona igual, mas cada comando pede permissão.
  - Agents: `${CLAUDE_PLUGIN_ROOT}/agents/`.
  ```

  O `0.71.0` acima é o valor de `__version__` no corte.
- **`_targets()`** ganha sete alvos `runtime`, via `replace_block`:
  - `skills/{paper,protocol,review,wiki,write}/SKILL.md`;
  - `skills/start/SKILL.md`;
  - `agents/reader.md`.

  Os marcadores vazios entram uma vez no PR, logo abaixo do H1 nas portas e no `start`, e logo
  depois do frontmatter no `reader.md`. Daí em diante só o gerador escreve o miolo. Nas portas,
  o `${CLAUDE_PLUGIN_ROOT}` é substituído ao carregar (SKILL.md e corpo de agent). Os agents não
  estão no registry de skills, e por isso o `reader.md` entra como alvo explícito.
- **A docstring do módulo** passa a listar `src/par/_version.py → bloco prumo:runtime`.

Os blocos de preflight dos 12 modos `cli` são regerados, nunca editados à mão:

- `paper/{extract,library,support}`;
- `protocol/{cep,picot,sap}`;
- `review/reconcile`;
- `wiki/{lint,study}`;
- `write/{disclosure,manuscript,section}`.

Os blocos dos três modos `qmd` (`wiki/{ingest,query,study}`) também são regerados, pelo
`_PF_QMD` novo; `ingest` e `query` continuam só-`qmd` (A9).

### `pyproject.toml` e `uv.lock`

- `dependencies` ganha `"adeu==1.29.0; python_version >= '3.12'"`, com o comentário "backend
  de prosa do review ingest (ADR-0016)".
- Entra
  `[tool.uv] constraint-dependencies = ["cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'"]`.
- Sai `prumo-zettlr-export = "par.domains.write.cli:zettlr_export_entry"` de
  `[project.scripts]`.
- O `uv lock` é regenerado: 99 pacotes, sem mudar nenhuma versão existente.
- `requires-python = ">=3.11"`, `force-include` e `dynamic = ["version"]` não mudam.

### `src/par/domains/write/review.py`

- **Saem** `_ADEU_TOOL`, `_ADEU_INSTALL_HINT`, `_check_uvx_on_path` e o import de
  `par.core.uvx`.
- **Entra `_check_adeu_available()`.** Ela levanta `AdeuUnavailableError` quando
  `importlib.util.find_spec("adeu") is None`, com a mensagem:
  "o backend de prosa (adeu) não está instalado neste ambiente Python. Pelo plugin: abra uma
  sessão nova; se persistir, apague a pasta e prepare de novo: rm -rf ~/.cache/prumo &&
  prumo --version. Em desenvolvimento: uv sync --extra dev --python 3.12 (o adeu exige
  Python ≥ 3.12)."
- **`_run_adeu_extract`** chama `subprocess.run([sys.executable, "-I", "-m", "adeu.cli",
  "extract", "--json", str(docx_path), "-o", "-"], capture_output=True, text=True,
  timeout=120)`:
  - `TimeoutExpired` → `AdeuUnavailableError` "o adeu passou de 120 s lendo <docx>; repita:
    prumo write review ingest …";
  - exit≠0 → `AdeuUnavailableError` com a cauda do stderr e "confira se o arquivo abre no Word
    e repita o ingest".
  - O parse do JSON (campo `markdown`) não muda; a mensagem dele troca "`uvx adeu==1.29.0
    --version`" por "o formato do adeu 1.29.0 mudou? rode: prumo --version e reporte".
- **As docstrings e comentários** que citam `uvx adeu==1.29.0` passam a dizer "adeu 1.29.0,
  travado no uv.lock".

### `src/par/core/uvx.py`, `src/par/domains/paper/verify.py`, `src/par/domains/paper/cli.py`, `src/par/mcp_server.py` (D3)

- **Apagados:** `src/par/core/uvx.py` e `tests/unit/core/test_uvx.py`.
- **`verify.py`, o que sai:** `REFCHECKER_PIN`, `_REFCHECKER_HINT`, `_REFCHECKER_TOOL`,
  `RefcheckerUnavailableError` (usada só pelo caminho do refchecker), `_bib_subset_text`,
  `_run_refchecker`, `_findings_from_report`, o parâmetro `deep` de `verify_refs` e o ramo
  `if deep and deep_keys`. O comentário do campo `source` de `Finding` perde `"refchecker"`
  (fica `"crossref" | "pubmed" | "local"`).
- **`verify.py`, o JSON:** a chave `"deep"` do dict devolvido **fica, sempre `False`**
  (Princípio IV: o campo não é removido; a tool MCP `paper_verify_refs` o repassa).
- **`verify.py`, a mensagem `no-identifier`:** passa a ser "entrada sem DOI/PMID{extra} —
  verificação nativa impossível; adicione o DOI no Zotero, deixe o Better BibTeX regravar o .bib
  e rode: prumo paper verify-refs".
- **`verify.py`, a docstring do módulo:** perde a camada profunda.
- **`paper/cli.py`:** sai a opção `--deep`.
- **`mcp_server.py:217-221`:** a docstring perde a menção ao `--deep`.

### `src/par/cli.py`

- **`init`:**
  - saem `--integration/-i`, o passo 3 do wizard (escolha de integration), o loop de install, a
    chave `integrations` do payload JSON e o campo `integrations` de `WizardAnswers`;
  - o `.claude/settings.json` (D4) chega pelo overlay do template, sem código;
  - `_render_next_steps` passa a dizer "Abra uma sessão nova do Claude Code dentro de
    `<pj>` (no app: aba Code → escolher a pasta; no terminal: `cd <pj> && claude`) e peça
    `/par:start`".
- **`doctor`:**
  - sai o loop de `INTEGRATIONS`;
  - o `[skill_obsoleta]` junta invocações antigas e cópias (`plugin_copies`) numa issue só
    (texto em §Erros);
  - a 1ª linha da docstring, "Health-check do projeto: estrutura, skills instaladas,
    integrations OK?", vira "Health-check do projeto: estrutura, cópias antigas do PAR e
    dependências externas."
- **`update`:**
  - **antes** de `migrate_skill_names` (assim o backup guarda as cópias intactas, sem a
    reescrita de invocações), chama
    `moved = move_plugin_copies(pj_root, plugin_copies(pj_root, _plugin_skill_names(), _plugin_agent_files()), dest)`;
  - o destino é `dest = pj_root / ".prumo" / "legacy-copies" / <AAAAMMDD-HHMMSS>`;
  - sem `--dry-run`, isso roda sempre, sem depender de `--yes` nem de TTY; `--dry-run` só lista;
  - o payload ganha `plugin_copies: list[str]` e `legacy_backup: str | None`;
  - `_update_summary` emite **uma** linha (texto em §Erros);
  - `_confirm_diverged` não muda.
- **Helpers novos:**
  - `_plugin_skill_names()` devolve `registry.names()` ∪ as chaves de `legacy_map()`;
  - `_plugin_agent_files()` devolve os nomes de `agents/*.md` resolvidos por
    `find_resource("agents")`.
- **`IntegrationError`:** sai do import e do `_entry`. O bloco `if __name__ == "__main__":`
  chama `app()`.

### `src/par/core/skill_refs.py`

- **Sai** `legacy_installed_dirs`.
- **Entram duas funções:**
  - `plugin_copies(pj_root, skill_names, agent_files) -> list[str]` devolve
    `.claude/skills/<n>/` com `n` em `skill_names` e `.claude/agents/<f>` com `f` em
    `agent_files`, e nada mais;
  - `move_plugin_copies(pj_root, rels, dest) -> list[str]` faz `shutil.move` preservando a
    estrutura relativa abaixo de `.claude/`, apaga `.claude/skills` e `.claude/agents` se
    ficarem vazios e devolve `rels`.
- **Camadas:** `core/` recebe os nomes por parâmetro e nunca importa `domains/`.
- **`__all__`** é atualizado.

### `src/par/__init__.py`, `src/par/integrations/`, `tests/unit/integrations/`

- `IntegrationError` sai da classe, de `__all__` e da docstring da hierarquia.
- O pacote e os testes são apagados.

### `src/par/domains/write/zettlr.py` e `src/par/domains/write/cli.py`

- **Constante nova:** `FILTER_RELPATH = Path("docs") / "templates" / "zotero_live_docx.lua"`.
- **`generate_profile`** copia `_zotero_live_docx_filter()` para `pj_path / FILTER_RELPATH`
  (`shutil.copy2`) e escreve `"filters": ["citeproc", str((pj_path / FILTER_RELPATH).resolve())]`.
  Depois garante a linha `docs/templates/prumo-docx.yaml` no `<pj>/.gitignore`: acrescenta a
  linha (com o comentário do template) quando nenhuma linha do arquivo é igual a ela, e cria o
  arquivo se ele não existir. Rodar duas vezes deixa uma linha só.
- **`profile_issues`** acrescenta duas checagens à de filtro inexistente:
  - filtro diferente de `<pj>/docs/templates/zotero_live_docx.lua`;
  - cópia com bytes diferentes do filtro empacotado.

  O remédio é sempre "Regenere: `prumo write zettlr-profile`".
- **A docstring do módulo** troca "caminho absoluto do filtro no wheel instalado" por "cópia
  do filtro no projeto, caminho estável entre versões".
- **`write/cli.py`:** sai `zettlr_export_entry`. A mensagem de sucesso do `zettlr-profile`
  vira "Perfil Zettlr gerado: {out} (o filtro fica em docs/templates/zotero_live_docx.lua).
  Importe uma vez no Zettlr (Assets Manager → defaults files). Depois de atualizar o PAR, se o
  `prumo doctor` avisar do perfil, rode `prumo write zettlr-profile` de novo — o caminho não
  muda, então não precisa reimportar."

### Mensagens e textos em `src/`

- **`core/paths.py:25-28`:** "Recurso '{name}' não encontrado (nem empacotado nem na raiz do
  plugin). Reinstale o plugin (no app: + → Plugins → Gerenciar plugins; no terminal:
  /plugin uninstall par e /plugin install par@prumo-assistant-for-researcher) e abra uma sessão
  nova. Em desenvolvimento, rode a partir do repositório: uv run prumo …"
- **`core/deps.py`, item `qmd` da docstring do módulo:** "**qmd** — CLI de busca (BM25 +
  vector + rerank) que os modos `wiki query`, `wiki ingest` e `wiki study` usam. Binário no
  PATH."
- **`core/deps.py`, `hint` do `DepStatus` `qmd` em `check_external_deps`:** "Instale o qmd:
  `npm install -g @tobilu/qmd` (ou `bun install -g @tobilu/qmd`) e indexe o projeto:
  `prumo wiki index`."
- **`domains/wiki/index.py`, mensagem de `QmdNotFoundError` em `reindex`:** "qmd não está
  no PATH. Instale: npm install -g @tobilu/qmd (ou bun install -g @tobilu/qmd) e repita: prumo
  wiki index".

### `templates/pj_base/`

- **Novo** `.claude/settings.json`, com o texto de A13.
- **`.gitignore`** ganha a linha `docs/templates/prumo-docx.yaml`, com o comentário "perfil do
  Zettlr: caminhos absolutos desta máquina; regenere com `prumo write zettlr-profile`". Nos pj
  existentes, quem acrescenta a linha é o `zettlr-profile` (A10).
- **`README.md`, §Setup:** saem o bloco bash com `uv sync` e o `/plugin install`. Entra "Abra
  este projeto no app Claude, aba Code (ou `claude` no terminal), e peça `/par:start`".
- **`README.md`, §Evoluir o projeto:** vira "peça ao Claude", por exemplo "ativa o módulo
  clínico" (roda `prumo add clinical`).
- **`docs/project_guide.md`:**
  - o passo 4 ganha "peça 'gera o perfil do Zettlr' (roda `prumo write zettlr-profile`) e
    importe";
  - o passo 5 sai; o docx canônico fica "peça ao Claude: 'exporta o docx canônico de
    <arquivo>'";
  - o passo 7 vira "Atualizou o PAR e o `prumo doctor` avisou do perfil? Peça 'regenera o
    perfil do Zettlr'; não precisa reimportar".
- **`docs/README.md`:** o bloco "Operações wiki" passa a dizer que os `/par:wiki …` são pedidos
  ao Claude, e que `qmd query` é o uso opcional no terminal.
- **Testes de inventário do template**, como `tests/unit/test_pj_base_integration.py`, passam
  a incluir `.claude/settings.json` onde enumeram arquivos.

### `skills/` e `agents/` (fonte; as portas são regeradas)

- **`skills/start/SKILL.md`:** reescrito (texto em §Fluxo), com `requires: []` mantido e o
  bloco runtime.
- **Contornos de drift que saem:**
  - `paper/modes/support.md:70-77` sai inteiro;
  - `review/modes/critique.md:110-112` vira "**Sem validador** (`prumo` ausente, como no
    Cowork) —";
  - `review/modes/critique.md:120-122` sai. A validação à mão **fica**, porque o critique tem
    `requires: []`.
- **Bullet "O CLI `prumo` precisa estar no PATH… `uv tool install`":** sai de
  `paper/modes/extract.md:54-55`, `protocol/modes/picot.md:56-57`, `wiki/modes/query.md:45-46`,
  `wiki/modes/study.md:61-62` e `review/modes/reconcile.md:56-57`.
- **Fallback de agents** (`paper/modes/extract.md:71`, `paper/modes/support.md:63`,
  `review/modes/critique.md:90`): "(em `$CLAUDE_PLUGIN_ROOT/agents/` ou `.claude/agents/`)"
  vira "(na pasta da linha *Agents* do bloco PAR da porta)".
- **qmd só CLI:**
  - `wiki/modes/ingest.md:73,154-165,175,189`: "o agente roda `qmd embed` (na 1ª vez,
    `prumo wiki index`)", e sai "mostre ao usuário o comando";
  - `wiki/modes/query.md:38,57-59` e `wiki/modes/study.md:77,231`: `qmd query "<termo>"` pelo
    Bash;
  - `wiki/modes/query.md:38,43`: saem as referências ao monorepo do autor.
- **Passos opcionais com `prumo` nos modos só-`qmd`** (A9): `wiki/modes/ingest.md`, no passo de
  indexação, e `wiki/modes/query.md`, no arquivamento do finding (`prumo wiki finding`), ganham
  a frase "use `prumo`; se ele não existir nesta sessão, use a forma `sh` do bloco PAR da porta.
  Se a saída trouxer uma linha `PAR:`, repasse-a e siga sem este passo".
- **D5:** o `allowed-tools` dos cinco modos de A14.
- **`agents/reader.md`:** recebe o bloco runtime. "Nunca use Bash para outra coisa além de
  `prumo paper extract`" ganha "(ou da forma `sh` do bloco PAR acima)".
- **`skills/write/modes/style.md:312`:** "copiar a skill write para `.claude/skills/write/`"
  vira "copie para `.claude/skills/<um-nome-seu>/` — um nome do PAR seria tirado pelo
  `prumo update`".

### Documentação

- **`README.md`** (âncoras por seção, porque a Spec B mexe em §"Pré-requisitos externos" na
  0.70.3):
  - **§"Para pesquisadores (Desktop/Cowork, sem terminal)"** vira §"Para pesquisadores (app
    Claude, aba Code)", e o link `#para-pesquisadores-desktopcowork-sem-terminal` de
    §Instalação acompanha. A trilha:
    1. abrir o app Claude (plano pago) → aba Code;
    2. colar `/plugin install par --marketplace raphaelfh/prumo-assistant-for-researcher` →
       **Instalar para você** (o texto final depende do S-canal; o fallback é + → Plugins → Add
       plugin);
    3. abrir uma sessão nova e pedir `/par:start`.
  - **superfícies:** Cowork e chat ficam só com julgamento; Windows (inclusive WSL) sem suporte;
  - **atualização:** saem de §Instalação o bloco `uv tool install …` e o "Atualizar depois:
    `uv tool upgrade …`", e de §Releases o `/reload-plugins`. Fica "o PAR se atualiza sozinho nos
    projetos criados ou atualizados a partir da 0.71.0; senão, aceite a atualização em + →
    Plugins. Depois, abra uma sessão nova";
  - **dependências:** qmd como CLI em §MCP (sai o servidor) e na linha `qmd` de §"Pré-requisitos
    externos" (`npm install -g @tobilu/qmd`); `uv` sem piso numérico ("o PAR avisa se o seu for
    antigo e diz como atualizar");
  - **dev:** a nota de `PRUMO_ZOTERO_BASE` em §"Pré-requisitos externos" fica marcada como
    variável de dev, porque o MCP aberto pelo app não herda variáveis do perfil;
  - **§Desinstalar (nova):** `/plugin uninstall par`; `rm -rf ~/.cache/prumo`; e, só se nada
    mais os usa, `uv cache clean` e `uv python uninstall 3.12` (~70 MB).
- **`docs/onboarding-pesquisador.md`** (âncoras por seção, porque a Spec B reescreve parte da §4
  e da §6 antes):
  - o `title:` do frontmatter vira "Trilha do pesquisador — app Claude, aba Code" (é ele que o
    `gen_indexes` imprime no bloco `kb-index` de `docs/_index.md`), `cowork` sai das `tags`, e o
    H1 vira "Trilha do pesquisador (app Claude, aba Code)";
  - **introdução e §1 "Instalar o plugin, direto na conversa":** a trilha passa a ser a da aba
    Code; saem "sem instalar nada no terminal", "no Claude Desktop ou no Cowork" e o aviso de
    *research preview* do Desktop/Cowork;
  - **§2:** sai "Desktop, Cowork e Claude Code instalam a partir do mesmo `marketplace.json`";
  - **§3 "Quando você quiser ir além":** sai o passo "CLI do prumo: `uv tool install …`"; o qmd
    vira `npm install -g @tobilu/qmd`; sai "No Cowork, esses comandos rodam dentro da pasta do
    projeto…"; o aviso "No Windows, use o WSL — ou os instaladores nativos…" vira "Windows
    (inclusive WSL): ainda não suportado";
  - **§6 "Busca no seu wiki":** "exige `bun` + terminal" vira "o qmd é um CLI opcional
    (`npm install -g @tobilu/qmd`); na aba Code, o próprio Claude roda a busca";
  - **§6 "Conectores de literatura":** "No Cowork:" vira "No app Claude:", e sai a referência ao
    "aviso de Windows/WSL acima";
  - **§"Trilha dev":** "instalação do CLI via `uv`" vira "o CLI vem no plugin; `uv run prumo` e
    `claude --plugin-dir .` só para desenvolvimento";
  - **§"Kit do piloto":** a narrativa da F5 passa a dizer "reaberta e entregue na 0.71.0".
- **`docs/actions-by-context.md`:** apagado. Cita `integrations`, `sync-notes` e
  `.claude/rules/project_context.md`, e se apresenta como lista de comandos para digitar. O bloco
  `kb-index` de `docs/_index.md` é regerado. Saem também os três links escritos à mão para ele:
  - `docs/_index.md`, tabela "Por onde começar": a linha "Tenho um gatilho concreto, qual
    comando usar?";
  - `docs/_index.md`, "Como o vault está organizado": o item "`actions-by-context.md` — playbook
    de bolso por gatilho.";
  - `docs/Research Project Structure.md`, linha final "Ver também": fica só
    "[[journey|Canvas de jornada]]".
- **`docs/_index.md`, fora dos blocos gerados:** "Sou pesquisador sem terminal — como começo no
  Desktop/Cowork?" vira "Sou pesquisador — como começo pelo app Claude (aba Code)?", e
  "`onboarding-pesquisador.md` — trilha do pesquisador sem terminal (Desktop/Cowork) + kit do
  piloto da Fase 2." vira "… — trilha do pesquisador pelo app Claude (aba Code) + kit do piloto
  da Fase 2.".
- **`docs/Research Project Structure.md`:**
  - `.claude/skills/` (no diagrama do layout e na seção do diretório) vira "só skills próprias do
    projeto, com nome que não seja do PAR";
  - sai "preenchida por `prumo init` e atualizada por `prumo doctor`", que era falso.
- **`docs/positioning.md`,** linha "Mandar a bibliografia inteira a serviço externo": "Na
  checagem padrão, só DOI e PMID saem da máquina. O `--deep` envia só as entradas citadas na
  página" vira "Só DOI e PMID saem da máquina; não há camada profunda".
- **`docs/superpowers/specs/2026-07-22-zettlr-front-design.md`:** nota de uma linha no fim de §4
  ("CLI/entrypoint para o custom command"); a nota da Spec B fica abaixo da tabela de
  degradações. Texto: "> O custom command (`prumo-zettlr-export`) desta seção, da decisão 4 e do
  fluxo de exports foi substituído pela ADR-0038: o docx canônico é pedido ao Claude, e o perfil
  do Zettlr usa uma cópia do filtro no projeto."
- **`ARCHITECTURE.md`** (âncoras por texto, porque a Spec B tira linhas do diagrama antes):
  - box do core em §"Cinco domínios + core": sai `uvx` ("config · uvx · provenance*" vira
    "config · provenance*");
  - linha do `.mcp.json` em §"Layout do repositório": vira "servidor MCP `prumo` do plugin, via
    `shims/prumo`";
  - o mapa ganha `shims/` ("lançador do CLI, único arquivo") e `hooks/` ("SessionStart: PATH
    do lançador");
  - sai a linha de `integrations/`;
  - a nota de `agents/` ("`prumo init` copia p/ .claude/agents/") vira "lido da raiz do plugin;
    `init` não copia";
  - item 3 de §"Como contribuir" ("Host novo… subclasse `BaseIntegration`…"): "Host novo:
    adapter fino criado junto com o 1º host novo (trigger 3.0)";
  - sai a entrada "Integration" de §"Glossário rápido".
- **`RELEASING.md`:** §Release e migração.
- **`ROADMAP.md`, `docs/constitution.md`:** §ADRs e emendas.
- **`CLAUDE.md`:**
  - **§"Armadilhas deste repo":**
    - o bullet do `.mcp.json` vira "`.mcp.json` é só do plugin (o dev do repo o rejeita como
      servidor de projeto em `.claude/settings.json` e carrega o plugin com
      `claude --plugin-dir .`)";
    - o bullet "Plugin root = raiz do repo … não mover `skills/`, `.mcp.json`,
      `.claude-plugin/`" ganha `shims/` e `hooks/` na lista;
    - o bullet dos índices com blocos gerados ganha "o bloco `prumo:runtime` das 5 portas, do
      `start` e de `agents/reader.md`";
    - entram:
      - "`shims/` contém só `prumo` (100755); nunca crie `bin/` na raiz — chat e Cowork recusam
        o plugin inteiro";
      - "o venv do lançador é chaveado pelo conteúdo de `uv.lock` + `shims/prumo`: mudar
        qualquer um faz cada pesquisadora baixar o ambiente de novo (cerca de 60 MB, uma vez) —
        diga isso no CHANGELOG";
      - "o canal da conta (Customize → Plugins) copia a árvore git inteira: limite de 5.000
        arquivos e 200 MB".
- **`.claude/rules/release.md`:** depois da linha da fonte única de versão, entra "A versão no
  bloco `prumo:runtime` (portas, `start`, `agents/reader.md`) é escrita só pelo
  `gen_indexes.py` (RELEASING, passos 3, 4 e 6)."

### Dev do repo (`.claude/settings.json`)

- Sai `"enabledMcpjsonServers": ["qmd"]`, no mesmo PR que tira o qmd do `.mcp.json`.
- Entra `"disabledMcpjsonServers": ["prumo"]`, no mesmo PR que troca o comando do `prumo`.
- O hook `PreToolUse` do graphify fica como está.

### CI (`.github/workflows/ci.yml`)

- **`lint-and-test`:** novo passo `uv lock --check`. O `--frozen` na máquina da pesquisadora
  confia num lock em dia. A perna 3.11 continua, e lá o adeu não é instalado (marker ≥ 3.12).
- **Novo job `launcher-smoke`.** Matriz `os: [ubuntu-latest, macos-latest, macos-15-intel]`, com
  `PRUMO_CACHE_DIR=$RUNNER_TEMP/pc`. Passos:
  1. `shellcheck -s sh shims/prumo hooks/session-start.sh`, só no ubuntu, onde o shellcheck vem
     instalado. O ShellCheck 0.11.0 sai limpo nos dois arquivos com a severidade padrão
     (medido); a forma `[ teste ] && [ teste ] || _die …` não dispara o SC2015, que só vale
     quando o meio não é um teste.
  2. Copiar `git ls-files` para `$RUNNER_TEMP/root` e rodar `chmod -R a-w`.
  3. `sh $RUNNER_TEMP/root/shims/prumo --version` deve imprimir `prumo <__version__>`. No ubuntu,
     onde `/bin/sh` já é o `dash`, repetir com `bash --posix`; no macOS, onde `/bin/sh` é o bash
     3.2 em modo POSIX, repetir com `/bin/dash`, que o sistema traz.
  4. Apagar o venv e remontar com `UV_OFFLINE=1`.
  5. Handshake `initialize` por um script Python inline: `serverInfo.version == __version__`.
  6. `prumo init pj_smoke --yes` num diretório temporário. Deve criar `.claude/settings.json` e
     não criar `.claude/skills`.
  7. Rodar `hooks/session-start.sh` com `CLAUDE_ENV_FILE` temporário; `bash -c '. env; command -v prumo'`
     deve apontar o shim.
- **O leg `macos-15-intel` é o gate do Mac Intel.** Se o runner Intel não existir na hora da
  implementação, o README e a matriz declaram "Mac Intel: não suportado" antes do corte.

## Fluxo

### Instalação e início de sessão

1. **Instalação:** pela aba Code, no canal marketplace. A raiz fica em
   `~/.claude/plugins/cache/prumo-assistant-for-researcher/par/<versão>/`.
2. **Início de sessão:** o hook grava a linha do PATH no env file. Em paralelo, o Claude Code
   roda `/bin/sh <raiz>/shims/prumo mcp serve`. O MCP roda fora do sandbox: "MCP servers, and
   hooks run outside it" (<https://code.claude.com/docs/en/sandboxing>).
   - Na 1ª vez de cada lock, o caminho é frio: ~1 s com o cache do uv cheio, ~3 s em rede rápida,
     e proporcional à banda em rede lenta (cerca de 60 MB).
   - Depois disso, o caminho é quente: `initialize` em 0,40–0,48 s.
   - As tools aparecem como `mcp__plugin_par_prumo__*`.
3. **Skill:** a porta chega com o bloco runtime já substituído. O preflight checa a superfície
   e a versão. `prumo paper sync` casa com `Bash(prumo paper sync *)` e cai no shim e no venv.
4. **Subagent `reader`:** usa `prumo`, se herdar o env file, ou a forma `sh` do próprio bloco.
5. **Atualização:** a raiz nova chega com a sessão nova.
   - Se o lock não mudou, é o mesmo venv.
   - Se mudou, monta um venv novo, e a sessão antiga segue no antigo.
   - Um venv sem uso há 30 dias sai no próximo caminho frio.
6. **Sandbox do Bash ligado:** o MCP já preparou o venv, e o Bash só lê. Se o Bash chegar
   primeiro, sai com 77 e o remédio "repita fora do sandbox"; o preflight oferece a repetição.
   Comandos que falam com o Zotero recebem as mensagens E2, E11 e E15 da Spec B (A16).

### `/par:start` reescrito

O corpo abaixo dos blocos gerados (runtime, preflight puro) e acima do catálogo gerado fica
assim:

````markdown
Você é a porta de entrada E o instalador guiado. Primeiro descubra o estado:

1. **Superfície.** Se esta conversa for uma tarefa do Cowork, um chat do claude.ai, uma sessão
   SSH ou rodar no Windows ou no WSL, responda só com isto e pare:
   "Aqui o PAR só julga texto que você colar — por exemplo, `/par:review critique`. Bibliografia
   do Zotero, projeto no disco e exportação para Word não são suportados nem testados nesta
   superfície. Abra o app Claude na aba **Code** (Mac) ou o Claude Code no terminal (Mac ou
   Linux), escolha a pasta dos seus projetos e peça `/par:start` lá. No Windows (inclusive no
   WSL), o PAR ainda não funciona."
2. **CLI.** Rode `prumo --version`. O esperado é `prumo <versão do bloco PAR acima>`.
   - `prumo` não existe → rode a forma `sh … --version` do bloco PAR e aplique os casos abaixo
     à saída dela. Avise uma vez que os hooks do plugin não rodaram nesta sessão, então cada
     comando pedirá permissão. Só se a saída não trouxer nem a versão nem uma linha `PAR:`, diga
     "abra uma sessão nova" e pare.
   - A saída contém `PAR: falta o uv` → vá para **Instalar o uv**.
   - Outra versão → rode `command -v prumo`.
     - Caminho terminado em `/shims/prumo` (outra versão do plugin): diga "este `prumo` é de
       outra versão do plugin — abra uma sessão nova" e use a forma `sh` até lá.
     - Qualquer outro caminho (por exemplo `~/.local/bin/prumo`, o CLI antigo instalado à
       parte): ofereça UMA vez, com consentimento, `uv tool uninstall prumo-assistant-for-researcher`
       e use a forma `sh` nesta sessão. Se a pessoa usa o Zettlr, antes da remoção peça
       "regenera o perfil do Zettlr" dentro do projeto e a reimportação do perfil: o perfil
       antigo aponta para dentro desse CLI.
   - Linha `PAR:` do sandbox (saída 77) → ofereça repetir o mesmo comando fora do sandbox,
     pedindo permissão.
   - Qualquer outra linha `PAR:` → repasse-a (ela traz o comando de correção) e pare.
   - Versão certa, mas `type -a prumo` lista também um `prumo` que não termina em
     `/shims/prumo` → ofereça UMA vez a mesma remoção, com o mesmo cuidado do Zettlr (é o CLI
     antigo, que voltaria a aparecer se os hooks falhassem). Outros `…/shims/prumo` na lista são
     raízes antigas do plugin e não pedem nada.
3. **Ferramentas do PAR.** Se as ferramentas `mcp__plugin_par_prumo__*` não estiverem no seu
   inventário, diga: "As ferramentas do PAR não subiram nesta sessão (a 1ª preparação pode ter
   demorado). Abra uma sessão nova." Siga pelo CLI enquanto isso.
4. **Diagnóstico.** Rode `prumo doctor --json`.
   - Dentro de um `pj_*` → rode `prumo status --json`. Com `next` preenchido, ofereça em 1 linha
     a frase `next.say` (invocação `next.invocation`) e o motivo `next.why`. Sem `next`, ou se a
     pessoa quiser outra coisa, pergunte o que ela quer fazer e roteie (bibliografia → `paper`;
     wiki e estudo → `wiki`; PICOT, plano estatístico e CEP → `protocol`; escrita → `write`;
     revisão → `review`), usando o catálogo abaixo. Não execute a tarefa você mesmo.
   - Fora de um `pj_*` → siga a **Trilha guiada**.
   - Dependência externa ausente → mostre o `hint` do doctor (ele traz o comando).

## Instalar o uv (com consentimento — nunca rode sem um "sim")

Explique antes: o uv é o gerenciador de Python que o PAR usa para preparar o próprio ambiente
(instalação única). Se esta conversa for no Cowork, NÃO instale: lá o PAR não é suportado —
mande a pessoa para a aba Code.

`curl -LsSf https://astral.sh/uv/install.sh | sh`

Se falhar com `Operation not permitted` ou `Read-only file system` (sandbox do Claude Code),
peça para repetir fora do sandbox. Depois rode `prumo --version` de novo: não precisa reiniciar
nada (o PAR acha o uv em `~/.local/bin`). A primeira vez baixa cerca de 60 MB, uma vez só.

## Trilha guiada (um comando por vez, com consentimento)

1. **Projeto:** `prumo init pj_<nome>` na pasta que a pessoa indicar. O projeto já sai com a
   atualização automática do PAR ligada.
2. **Sessão no projeto:** "Abra uma sessão nova dentro de `pj_<nome>` (no app: aba Code →
   escolher a pasta; no terminal: `cd pj_<nome> && claude`) e peça `/par:start` de novo."
3. **Zotero:** Zotero 9 ou mais novo com o Better BibTeX ≥ 9.0.65 (`.xpi`), app aberto. Serve para conectar a coleção (uma vez) e manter o `.bib` atualizado; no export docx, vincula as citações se estiver aberto. Não bloqueia escrita nem julgamento, e não é preciso ligar "Allow other applications".
4. **Conectar a biblioteca:** com o Zotero aberto, `prumo paper connect "<coleção>"` liga o
   `.bib` do projeto à coleção. Se a coleção ainda não existir, `--create` cria e liga num
   passo — só quando a pessoa pedir a criação; nunca acrescente a flag por conta própria
   (ADR-0028).
5. **Sincronizar:** `prumo paper sync`.
6. **qmd (opcional, busca semântica):** `npm install -g @tobilu/qmd` (ou
   `bun install -g @tobilu/qmd`) e depois `prumo wiki index`. Não precisa reiniciar a sessão. Sem
   qmd, `wiki query` funciona por leitura direta.
7. **Primeiro resultado em minutos:** peça um trecho de draft e rode `/par:review critique` —
   funciona sem nada do stack.

Regras duras: nunca simule saída de comando que falhou; nunca crie scaffold à mão
(`prumo init` é o único caminho); nunca cite tooling do monorepo do autor; nunca ofereça
instalar o CLI à parte — ele vem no plugin.
````

O item 3 da trilha (Zotero) é final e é, palavra por palavra, o texto que a Spec B fixa para ele
(pisos Zotero ≥ 9 e Better BibTeX ≥ 9.0.65, sem o toggle da API local). Ele fica numa linha só,
como lá. Quem o grava no arquivo é o PR do `start` desta spec, que reescreve a trilha inteira.

### Antes e depois para a pesquisadora

**Instalação, hoje.** São 11 passos obrigatórios, em 4 métodos, e dois deles não estão
documentados (§Contexto).

**Instalação, depois.** São 8 passos:

1. Abrir o app Claude (plano pago) → aba **Code** → escolher a pasta dos projetos.
2. Colar e enviar `/plugin install par --marketplace raphaelfh/prumo-assistant-for-researcher` →
   **Instalar para você**. Depende do S-canal; o fallback é `+ → Plugins → Add plugin`.
3. Abrir uma sessão nova e pedir `/par:start`. Autorizar a instalação do uv só se faltar. O PAR
   se prepara sozinho (cerca de 60 MB, uma vez).
4. Autorizar `prumo init pj_<nome>`. A atualização automática já fica ligada.
5. Abrir uma sessão nova dentro de `pj_<nome>`.
6. Instalar o Zotero e o Better BibTeX ≥ 9.0.65 e abrir o Zotero, sem toggle (Spec B).
7. Pedir "Conecta minha coleção <nome>".
8. Pedir "Sincroniza a bibliografia".

O pandoc é da Spec B: quem usa Zettlr no Mac não tem nenhum passo, e os demais recebem a dica do
doctor uma vez.

**Atualização, hoje:** `/plugin update`, mais `uv tool upgrade`, mais `/reload-plugins`. Quem
esquece o 2º passo cai em drift silencioso.

**Atualização, depois:** nos pj com o `settings.json` do template, nada; nos outros, aceitar a
atualização. Depois, abrir uma sessão nova. Não há passo que possa ser esquecido.

**Primeira atualização para a 0.71.0, uma vez só:**

- em cada pj, pedir "atualiza o projeto";
- pedir "regenera o perfil do Zettlr" e reimportar o perfil uma última vez, antes de aceitar a
  remoção do CLI antigo;
- apagar o comando custom do Zettlr;
- atualizar o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins; Spec B).

## Erros

Cada situação tem uma mensagem e um remédio. Todas trazem o comando de correção.

| Situação | Detecta | Mensagem pt-BR |
|---|---|---|
| Sem uv (ou um `uv` que não é executável, como um link pendurado) | lançador, 127 | "PAR: falta o uv (instalação única). Peça /par:start ou rode: curl -LsSf https://astral.sh/uv/install.sh \| sh" |
| 1ª preparação sem rede, sem proxy liberado ou sem o host do Python | lançador, 69 | "PAR: preparar esta versão do PAR precisa de internet uma única vez (cerca de 60 MB). Conecte-se e rode: prumo --version. Em rede de hospital ou universidade, peça liberação de pypi.org, files.pythonhosted.org, releases.astral.sh, github.com e dos domínios de download do GitHub (objects.githubusercontent.com, release-assets.githubusercontent.com). Detalhe: …" |
| Disco cheio ou cache sem permissão (fora do sandbox) | lançador, 73 | "PAR: não consegui gravar em <cache> (disco cheio ou pasta sem permissão). Libere espaço ou corrija o dono da pasta (sudo chown -R "$USER" ~/.cache) e rode: prumo --version. Detalhe: …" |
| Sandbox do Claude Code: `SANDBOX_RUNTIME=1`, EPERM ou pânico `dynamic_store` | lançador, 77 | "PAR: o sandbox do Claude Code bloqueou a preparação do PAR (só acontece na 1ª vez de cada versão). Repita este comando fora do sandbox (o Claude pede sua permissão) ou abra uma sessão nova: o servidor do PAR prepara tudo ao iniciar, fora do sandbox. Detalhe: …" |
| uv antigo demais para o lock | lançador, 78 | "PAR: o seu uv é antigo demais para esta versão do PAR. Atualize e repita: uv self update (ou brew upgrade uv, se ele veio do Homebrew). Detalhe: …" |
| uv configurado sem download de Python | lançador, 78 | "PAR: a configuração do seu uv não deixa baixar o Python 3.12 que o PAR usa. Instale-o uma vez e repita: uv python install 3.12 && prumo --version (se o uv recusar, troque python-downloads de "never" para "manual" no seu uv.toml). Detalhe: …" |
| Venv sem Python depois do sync | lançador, 70 | "PAR: o ambiente <venv> ficou sem Python executável. Apague a pasta e repita: rm -rf "<venv>" && prumo --version" |
| Windows nativo ou WSL (`OS=Windows_NT`, MINGW/MSYS/CYGWIN, `WSL_DISTRO_NAME`/`WSL_INTEROP` ou `microsoft` no `osrelease`) | lançador, 71 | "PAR: ainda não funciona no Windows nem no WSL (o PAR só é testado em macOS e Linux). Por enquanto, use /par:review critique colando trechos do seu texto." |
| Raiz incompleta ou chamada por symlink | lançador, 1 | "PAR: instalação do plugin incompleta em <raiz> (ou o lançador foi chamado por um link simbólico, o que não é suportado). Reinstale o plugin (no app: + → Plugins → Gerenciar plugins; no terminal: /plugin uninstall par e /plugin install par@prumo-assistant-for-researcher) e abra uma sessão nova." |
| Hook não rodou | preflight e start | Usa a forma `sh`, aplica à saída dela os mesmos casos (inclusive `PAR: falta o uv` → `/par:start`) e avisa uma vez: "os hooks do plugin não rodaram nesta sessão; vou usar o caminho do plugin (cada comando pedirá permissão)." |
| `prumo` de outra versão do plugin (caminho terminado em `/shims/prumo`) | preflight e start | "Este `prumo` é de outra versão do plugin — abra uma sessão nova (no app: nova sessão na aba Code; no terminal: saia e rode `claude`)." |
| CLI antigo instalado à parte (caminho que não termina em `/shims/prumo`) | preflight e start, uma vez | "Há um `prumo` antigo instalado à parte em <caminho>, que o PAR não usa mais. Posso removê-lo com `uv tool uninstall prumo-assistant-for-researcher`? Se você usa o Zettlr, antes peça 'regenera o perfil do Zettlr' e reimporte o perfil: o perfil antigo aponta para dentro desse CLI." |
| Tools MCP ausentes | start | "As ferramentas do PAR não subiram nesta sessão (a 1ª preparação pode ter demorado). Abra uma sessão nova." |
| Cowork, chat, SSH, Windows ou WSL | `_PF_CLI` e start | Frase do `_PF_CLI`, ou mensagem fixa do start (§Fluxo). |
| Cópias antigas no pj | doctor | "[skill_obsoleta] cópias antigas das skills/agents do PAR em .claude/ (<lista>) sombreiam o plugin. Rode: prumo update — elas vão para .prumo/legacy-copies/<AAAAMMDD-HHMMSS>/, nada é apagado; se você customizou alguma, recrie-a em .claude/skills/<um-nome-seu>/." (com invocações antigas: "…; invocações antigas em <arquivos>, que o mesmo `prumo update` reescreve.") |
| `update` moveu cópias | update | "N cópia(s) antiga(s) do PAR saíram de .claude/ para .prumo/legacy-copies/<AAAAMMDD-HHMMSS>/ (nada foi apagado; o plugin passa a valer). Se você tinha customizado alguma, recrie-a com outro nome em .claude/skills/<um-nome-seu>/." |
| Zotero inalcançável sob o sandbox Bash | doctor, export docx, connect | Mensagens E2 (export, 0.70.3), E11 (doctor) e E15 (connect) da Spec B, que é a dona do ramo (A16). |
| adeu ausente | `write review ingest` | Texto de §Componentes, `review.py`. |
| Perfil do Zettlr fora do projeto, divergente ou apontando arquivo inexistente | doctor | "Perfil Zettlr aponta filtro fora do projeto: <caminho>. Regenere: `prumo write zettlr-profile`" · "A cópia do filtro em docs/templates/zotero_live_docx.lua está diferente da desta versão do PAR. Regenere: `prumo write zettlr-profile`" · (filtro inexistente: mensagem atual) |
| qmd ausente | doctor (`hint`) e `wiki index` | Textos de §Componentes, "Mensagens e textos". |

## Superfícies suportadas

| Superfície | Julgamento puro (`/par:review critique`) | Skills com CLI/Zotero | MCP do PAR | Status | Base |
|---|---|---|---|---|---|
| Claude Code no terminal, macOS arm64 | sim | sim | sim | suportado | medido: 28/28 no lab, em `sh` e `dash` |
| Claude Code no terminal, Linux | sim | sim | sim | suportado | job `launcher-smoke` (ubuntu: `sh`, que lá é o `dash`, e `bash --posix`) |
| Claude Code no terminal dentro do WSL | sim | não | não (o servidor sai com 71) | não suportado (D1) | lançador: 71 por `WSL_DISTRO_NAME`/`WSL_INTEROP`/`osrelease` |
| App Claude, aba Code (sessão local, macOS) | sim | sim | sim | **canal recomendado** | hook e MCP pela documentação; instalação em 1 comando pendente do S-canal |
| IDE (VS Code, JetBrains) | sim | sim | sim | suportado pela documentação, não testado | docs |
| Mac Intel | sim | sim, com `cryptography<49` | sim | suportado se o leg `macos-15-intel` passar; senão, declarado sem suporte | dry-run de resolução |
| Hooks bloqueados (`allowManagedHooksOnly`, `disableAllHooks`) | sim | degradado: forma `sh`, 1 prompt por comando | sim | degradado (a TI pode force-habilitar `par@prumo-assistant-for-researcher`) | settings-reference |
| Bash sandbox do Claude Code ligado | sim | **parcial**: o CLI funciona depois que o MCP prepara o venv (o 1º `prumo` no Bash pode sair com 77); comandos que falam com o Zotero não alcançam o Zotero do host e recebem as mensagens E2, E11 e E15 da Spec B | sim (fora do sandbox) | parcial | 77 medido no Seatbelt; sandboxing.md |
| Cowork (local ou remoto) | sim | não suportado/testado — use a aba Code | não usar | só julgamento | execução VM × host depende de configuração e rollout (S-cowork opcional) |
| Chat do claude.ai | sim | não | não | só julgamento | platform-support |
| Aba Code em sessão SSH | sim | não | não | não suportado: Bash e MCP rodam no host remoto, longe do Zotero local | desktop.md |
| Aba Code em sessão WSL | — | não | não | não suportado (plugins não carregam) | desktop-wsl.md |
| Windows nativo | sim | não | não | não suportado (D1) | lançador: 71 |
| `--bare` | — | — | — | fora de escopo (nenhum plugin carrega) | headless.md |

## Testes

### Arquivos novos

**`tests/unit/test_plugin_layout.py`**
- `shims/` contém só `prumo`, com modo `100755` em `git ls-files -s` (skip se não for checkout
  git); `hooks/session-start.sh` também tem `100755`.
- Não existe `bin/` na raiz.
- `hooks/hooks.json` faz parse; os eventos são exatamente {SessionStart}, com uma entrada sem
  `matcher`, `command == "/bin/sh"` e `args == ["${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"]`.
- `.mcp.json` é exatamente o dict de §Componentes, sem `qmd`.
- `templates/pj_base/.claude/settings.json` é exatamente o dict de A13.

**`tests/unit/test_launcher.py`** roda por subprocess em `/bin/sh` e em `dash` (se existir), com
`PRUMO_CACHE_DIR` temporário, `PRUMO_UV` apontando um uv falso (um script executável) e
`SANDBOX_RUNTIME`, `WSL_DISTRO_NAME` e `WSL_INTEROP` removidos do ambiente, salvo onde indicado.
No sucesso, o uv falso cria `bin/python` como wrapper de `sys.executable`.
- Caminho quente: com stamp e `bin/python`, `PRUMO_UV=/inexistente` funciona, ou seja, o uv não
  é chamado.
- O stamp é por existência; `bin/python` quebrado (symlink pendurado) dispara o rebuild.
- Classificação a partir do stderr do uv falso:

  | stderr do uv falso | Saída esperada |
  |---|---|
  | "Failed to parse `uv.lock`" | 78, "uv self update" |
  | "downloads are set to 'never'" | 78, "uv python install 3.12" |
  | "Read-only file system" com `SANDBOX_RUNTIME=1` | 77, "fora do sandbox" |
  | o mesmo sem `SANDBOX_RUNTIME` | 73, "chown" |
  | "Operation not permitted" | 77 |
  | "No space left" | 73 |
  | erro de rede | 69, com `release-assets.githubusercontent.com` |
  | erro de rede com `SANDBOX_RUNTIME=1` | 77 |
  | uv que sai 0 sem criar Python | 70 |

- Sem uv: `PRUMO_UV=/inexistente` sem stamp → 127, e o stderr começa com `PAR: falta o uv`. O
  teste usa `PRUMO_UV`, e não um `PATH` podado, porque o lançador anexa `/opt/homebrew/bin` e
  `/usr/local/bin` ao `PATH` e acharia o uv da máquina que roda os testes; o `-x` do lançador faz
  um `PRUMO_UV` inexistente valer como uv ausente.
- `OS=Windows_NT` → 71; `WSL_DISTRO_NAME=Ubuntu` → 71; `WSL_INTEROP=/run/WSL/1_interop` → 71. A
  mensagem cita "nem no WSL".
- Raiz sem `src/` → 1, e a mensagem cita o link simbólico.
- TLS: o uv falso que falha com "invalid peer certificate: UnknownIssuer" é chamado 2 vezes; a
  2ª chamada recebe `UV_NATIVE_TLS=1` e `UV_SYSTEM_CERTS=1`.
- Cache fixo: sem `PRUMO_CACHE_DIR`, com `HOME` e `XDG_CACHE_HOME` temporários, o venv nasce em
  `$HOME/.cache/prumo` e nada em `$XDG_CACHE_HOME`.
- Um cwd com `yaml.py`, `typer.py` e `par/` não sequestra.
- O ambiente do processo filho só difere no sufixo do PATH.
- Poda: um `venv-*` com `mtime` de 40 dias sai no caminho frio; o atual e um de 10 dias ficam.
- Hook: 2 execuções deixam 1 linha; uma raiz com `'`, `$` e crase resolve `command -v prumo` em
  bash e sh; sem `CLAUDE_ENV_FILE` sai com 0 e sem saída; com env file só de leitura sai com 0 e
  stderr vazio.

**`tests/unit/wiki/test_index.py`** (1 teste): com `shutil.which` mockado devolvendo `None`, a
mensagem de `QmdNotFoundError` traz `npm install -g @tobilu/qmd`.

### Arquivos alterados

**`tests/unit/test_cli_update.py`** (o espelho do `update` da raiz `cli.py`; os testes unitários
de `plugin_copies`/`move_plugin_copies` ficam em `tests/unit/core/test_skill_refs.py`):
- Cópias `.claude/skills/paper/` e `.claude/agents/reviewer.md` vão para
  `.prumo/legacy-copies/<stamp>/`.
- `minha-skill/` e `meu-agent.md` ficam.
- `--dry-run` só lista.
- Sem TTY e sem `--yes`, as cópias são movidas **e** um `.claude/rules/<x>.md` customizado fica
  byte-idêntico.
- `--yes` não muda o tratamento das cópias.
- O payload traz `plugin_copies` e `legacy_backup`.
- `.claude/settings.json` é acrescentado a um pj que não o tem, e um existente fica
  byte-idêntico.

**`tests/unit/test_cli_doctor.py`**
- Sai o loop de integrations.
- `test_doctor_aponta_invocacao_antiga_e_skill_instalada_velha` é reescrito: com
  `.claude/skills/paper/`, `.claude/agents/reviewer.md`, `minha-skill/` e uma invocação antiga
  no `README.md`, o doctor emite um único `[skill_obsoleta]` que cita as duas cópias, a
  invocação e `prumo update`, e não cita `minha-skill`.

**`tests/unit/test_gen_indexes.py`**
- `render_runtime()` traz `**PAR <__version__>**` e `${CLAUDE_PLUGIN_ROOT}` com chaves.
- Os 7 alvos têm o bloco.
- O `--check` acusa o bloco desatualizado quando `__version__` muda (monkeypatch).
- O preflight `cli` tem 2 itens e contém `PAR: falta o uv` e `/shims/prumo`.
- O preflight `cli` contém `uv tool uninstall prumo-assistant-for-researcher` exatamente uma vez
  e não contém `Drift CLI×plugin`, `uv tool install` nem `uv tool upgrade`.
- O caso (a) do `_PF_CLI` remete a "(b)–(d)", para a falta do uv na forma `sh` chegar ao
  `/par:start`.
- O caso (d) do `_PF_CLI` contém "fora do sandbox".
- O `_PF_QMD` contém `qmd --version` e não contém `command -v`.

**`tests/unit/core/test_skills.py`.** O helper `_bodies_calling` e o teste
`test_subcomando_recente_tem_fallback_de_subcomando_ausente` dão lugar a invariantes sobre
`skills/` e `agents/`:
- nenhum `uv tool install`, `uv tool upgrade` nem `No such command` (as instruções antigas de
  instalar e atualizar o CLI à parte; o `uv tool uninstall` do `start` e do `_PF_CLI` é
  permitido);
- nenhum `$CLAUDE_PLUGIN_ROOT` sem chaves;
- `paper_connect` fora de todo frontmatter;
- nenhum `mcp__qmd__`;
- D5: nenhuma regra `Bash(...)` de nenhum frontmatter (porta ou modo) casa com
  `prumo paper connect x --create --yes`, `prumo init x --force` ou `prumo update --yes`. O teste
  aplica a semântica documentada: o ` *` final casa o comando sem argumentos, e o espaço é
  fronteira.
- O invariante `mcp__prumo__` é da Spec B (0.70.3).

**`tests/unit/test_cli_init.py`**
- Sem `--integration`.
- `.claude/skills` e `.claude/agents` não existem depois do init.
- O payload JSON não tem `integrations`.
- `.claude/settings.json` é igual ao do template.

**`tests/unit/core/test_skill_refs.py`:** testes de `plugin_copies` e `move_plugin_copies`; os
2 de `legacy_installed_dirs` saem.

**`tests/unit/write/test_review_adeu.py` e `test_review_ingest.py`**
- O argv é `[sys.executable, "-I", "-m", "adeu.cli", "extract", …]`.
- `find_spec` é mockado, para a perna 3.11 do CI passar sem adeu.
- Timeout e exit≠0 viram `AdeuUnavailableError`.
- Os testes que travavam o texto `uvx adeu==1.29.0` são reescritos.

**`tests/unit/paper/test_verify.py`**
- Sai a classe `TestDeepLayer` inteira (os testes de `_bib_subset_text`,
  `_findings_from_report` e `_run_refchecker`, os que fazem patch em
  `par.core.uvx.subprocess.run`, `test_verify_refs_deep_mescla_warnings`,
  `test_verify_refs_sem_deep_nao_roda_subprocess` e
  `test_deep_com_escopo_so_duplicatas_nao_roda_subprocess`) e a constante `_REPORT_FIXTURE`.
- `report["deep"] is False`.
- A mensagem `no-identifier` não cita `--deep` (`test_sem_identificador_info` passa a afirmar o
  contrário do que afirma hoje).

**`tests/unit/paper/test_cli.py`:** `test_verify_refs_repassa_flags` deixa de passar `--deep`
(fica `--refresh`) e afirma que a opção não existe mais.

**`tests/unit/paper/test_errors.py`:** sai `verify.RefcheckerUnavailableError` de
`_PAPER_LEAVES`.

**`tests/unit/write/test_cli.py` e `tests/unit/write/test_export_docx_validation.py`:** saem os
testes do `zettlr_export_entry`: `test_zettlr_entry_calls_canonical_docx_export`,
`test_zettlr_entry_export_error_exits_cleanly`, `test_zettlr_entry_usage_error_exits_cleanly` e
`test_zettlr_export_entry_overwrites_on_second_run`.

**`tests/unit/write/test_zettlr_profile.py`**
- O Lua é copiado para `docs/templates/`.
- `filters` aponta para a cópia.
- `profile_issues` acusa a cópia divergente, o filtro fora do projeto e o filtro inexistente.
- O `.gitignore` do pj ganha `docs/templates/prumo-docx.yaml` quando falta, e duas execuções
  deixam uma linha só.

**`tests/unit/core/test_deps.py`:** as asserções do hint do qmd (hoje `bun install -g
@tobilu/qmd` e `github.com/tobi/qmd`) passam a `npm install -g @tobilu/qmd` e
`bun install -g @tobilu/qmd`, sem a URL do repositório. Os testes de `in_claude_sandbox()` e do
ramo de sandbox da linha `zotero` são da Spec B.

**`tests/unit/test_agents.py`:** `agents/reader.md` tem o bloco runtime.

### Arquivos apagados

- `tests/unit/integrations/`
- `tests/unit/core/test_uvx.py`

### CI

- `uv lock --check`.
- `launcher-smoke` (§Componentes).

## ADRs e emendas

### ADR-0038 (nova): "O plugin é a única distribuição: launcher roda o CLI desta raiz, travado no uv.lock"

Arquivo: `docs/adr/adr-0038-plugin-unica-distribuicao.md`.

- **Status e data.** Status "proposta"; passa a "aceito" quando o S-canal e o `launcher-smoke`
  (com o leg Intel, ou com o Mac Intel declarado sem suporte) estiverem verdes. Data do PR.
  Origem: esta spec.
- **Contexto.** O drift 0.67.2 (5eb2c6b), o `_PF_DRIFT` inerte, os nomes MCP que nunca casaram,
  o `uvx` sem pin real, as cópias que sombreiam o plugin e os curingas largos.
- **Decisão.** Registra A1–A15 e A17 (a A16 só aponta para a Spec B):
  - `shims/prumo`;
  - o hook de PATH em forma exec;
  - o `.mcp.json` via `/bin/sh`;
  - o venv por conteúdo em `~/.cache/prumo`;
  - a identidade por versão, com o bloco gerado e o `gen_indexes` como único escritor;
  - o `init` sem cópias e o `update` com backup;
  - o qmd só como CLI;
  - o adeu no lock e nenhum `uvx` em runtime;
  - D1, D3, D4 e D5;
  - a matriz de superfícies.
- **Trade-off do `CLAUDE_PLUGIN_DATA`.** A ADR registra o texto de A2, e a limpeza na
  desinstalação: `rm -rf ~/.cache/prumo`, mais `uv cache clean` e `uv python uninstall 3.12` se
  nada mais os usa.
- **Supersede em parte.**
  - ADR-0019: o item de drift, o "CLI ausente → instalar o CLI" e o item `qmd` (inventário de
    tools MCP da sessão → checagem do CLI `qmd`).
  - ADR-0017 e ADR-0026: "sem o CLI instalado, o servidor falha ao subir" passa a "sem uv".
  - ADR-0026:23: o prefixo `mcp__prumo__paper_find` passa ao nome real no plugin,
    `mcp__plugin_par_prumo__*`. A correção nas skills saiu na 0.70.3 (Spec B, B8); a ADR-0037
    não registra a emenda, e o registro fica nesta ADR.
  - ADR-0033:21: "`prumo init` o copia para `.claude/agents/`".
  - ADR-0032:25: "não é apagado pelo `update`" passa a "o `update` move para backup".
  - ADR-0018: a camada `--deep`.
  - ADR-0034:17: `prumo-zettlr-export` sai da lista de nomes que permanecem; fica só o CLI
    `prumo`.
  - Spec `2026-07-22-zettlr-front-design.md`: o custom command do Zettlr (decisão 4, §4 e o
    fluxo de exports) sai; o docx canônico é pedido ao Claude.
- **Complementa.** A ADR-0010 (raiz do plugin = raiz do repo): a raiz agora é também o runtime.
  A ADR-0026:29 passa a ser verdadeira com o qmd fora.
- **Alternativas rejeitadas.** As de A1–A15 e A17:
  - PyPI/uvx pinado;
  - `bin/`;
  - MCPB;
  - MCP-first;
  - `command: uv` / `uv run --project`;
  - venv em `CLAUDE_PLUGIN_DATA`;
  - venv por raiz ou por versão;
  - `.python-version`;
  - `python -m par` com `PYTHONPATH`;
  - `pypandoc-binary`;
  - typst no lock;
  - gêmeos absolutos;
  - lint `requires⇔allowed-tools`;
  - "use o WSL".

A ADR-0037 ("Ponte Zotero mínima", da Spec B) sai antes, na 0.70.3, e não é tocada aqui.

### Constitution 1.2.2 → 1.2.3 (PATCH)

Exige revisão humana (constitution, §Governança: "O agent-host … NÃO pode reescrever esta
constitution sem revisão humana"). A emenda entra no PR de docs da 0.71.0, que só faz merge com
aprovação explícita do dono.

- **Distribuição (linha 138):** "**Distribuição**: plugin do Claude Code (marketplace), que
  executa o próprio CLI `prumo` travado no `uv.lock` da versão instalada (pré-requisito: `uv`).
  `uv tool install`/`uv run` só para desenvolvimento."
- **Stack externa (linha 139):** "**Stack externa do projeto-cliente** (`pj_*`): Zotero + Better
  BibTeX (bibliografia), Zettlr (front do wiki Markdown), Pandoc ≥ 3.8.2 + Typst (opcional) +
  CSL (export), `qmd` opcional (CLI de busca BM25 + vector + rerank local, instalado pelo
  pesquisador)." O piso do pandoc vem da Spec B.
- **Princípio III (linha 82):** "O catálogo do plugin Claude Code é montado por
  `core/skills.py::load_skill_registry`; um host novo consumirá o mesmo arquivo (Princípio I)."
  Sai "via seu `BaseIntegration`".
- **Princípio I:** intocado.
- **Sync impact report** (a 1ª linha leva a data do merge, como nas emendas anteriores):
  "1.2.3 — emenda PATCH: distribuição pelo plugin com CLI
  travado no `uv.lock` (ADR-0038); stack externa com piso do Pandoc e qmd como CLI opcional;
  Princípio III sem a menção a `BaseIntegration`, que deixou de existir. Nenhuma norma alterada:
  os termos 'hooks plugáveis' e 'lockfile' do Princípio VI continuam designando o sistema de
  hooks interno e o lockfile de packs que o ROADMAP posterga; o hook `SessionStart` é config do
  agent-host e o `uv.lock` já existia." A linha "Versão atual" passa a 1.2.3.

### ROADMAP

- **Linha `| F5 |` da tabela "Status do programa zero-friction"** (coluna de status): "encerrada
  fechada na 0.63.0 (o trigger 'colega travado apesar da instalação guiada' não disparou);
  **reaberta na 0.71.0 por trigger novo**: drift CLI×plugin
  reincidente depois do preflight da F2 — CLI global 0.67.2 sem `validate`/`status` (5eb2c6b,
  2026-09-12; três contornos em skills, CHANGELOG 0.70.0 › Corrigido) — e o item de drift da
  ADR-0019 comprovadamente inerte; entregue na 0.71.0: o plugin executa o CLI travado no
  `uv.lock` ([ADR-0038](docs/adr/adr-0038-plugin-unica-distribuicao.md)); o `uv` segue
  pré-requisito, instalado pelo `/par:start`."
- **Bullet "**Sem multi-host.**" de "Decisões deliberadas postergadas":** "**Sem multi-host.** O
  plugin do Claude Code é o único host
  ([ADR-0038](docs/adr/adr-0038-plugin-unica-distribuicao.md)); o adapter fino nasce junto com
  o 1º host novo (trigger 3.0)."
- **"Decisões deliberadas postergadas", entrada nova:** "**Sem Windows** (nativo e WSL).
  Trigger: a 1ª pesquisadora real no Windows
  ([ADR-0038](docs/adr/adr-0038-plugin-unica-distribuicao.md))."

### Índices

Rodar `uv run python .github/scripts/gen_indexes.py`. Ele regera:

- `docs/adr/_index.md`, com a ADR-0038;
- `docs/_index.md`, com esta spec e sem `actions-by-context`;
- as portas;
- os preflights.

## Release e migração

### Sequência

A 0.70.3 PATCH é inteira da Spec B. A Spec A sai na **0.71.0 MINOR ⚠**, num corte único que
segue os 8 passos do `RELEASING.md`. São vários PRs em `main`, e o CHANGELOG acumula em
"Não publicado":

1. **Cortes do repo:** `integrations/`, cópias no pj (`init`/`update`/`doctor`), `_PF_DRIFT` e
   contornos, qmd só como CLI (com a saída do `enabledMcpjsonServers` no mesmo PR), D5 e
   `docs/actions-by-context.md`.
2. **Dependências:** adeu no lock, restrição de `cryptography`, `--deep` fora, `core/uvx.py`
   fora, `prumo-zettlr-export` fora, Lua do Zettlr no pj e `uv lock --check`.
3. **Parte 0.71.0 da Spec B:** aposentadoria, sonda, transporte do `connect` e as variantes de
   sandbox E11 e E15.
4. **Lançador:**
   - `shims/`, `hooks/` e `.mcp.json` (com `disabledMcpjsonServers` no mesmo PR);
   - bloco runtime, `_PF_CLI` e `start`;
   - D4;
   - testes e `launcher-smoke`.
5. **Docs:** README, onboarding, RELEASING, ARCHITECTURE, ROADMAP, CLAUDE.md, a ADR-0038 e a
   constitution 1.2.3 (com revisão humana).

O S-canal roda depois que o PR 4 entra em `main` e antes do bump de versão (§Spikes e gates
pré-corte). Se o S-canal ou o `launcher-smoke` atrasarem, a 0.71.0 espera: o evento breaking é
único por decisão do dono, e não há corte parcial.

### Notas do CHANGELOG (parte da Spec A; a Spec B traz as dela)

No formato do `CHANGELOG.md`: sem seção "Breaking"; cada item breaking leva o prefixo
`**⚠ Breaking — …**` dentro de "Alterado" ou "Removido", e as ADRs entram como link.

```markdown
### Alterado

- **⚠ Breaking — o CLI `prumo` vem dentro do plugin e roda exatamente a versão dele**, travado
  no `uv.lock` ([ADR-0038](docs/adr/adr-0038-plugin-unica-distribuicao.md); Princípios I, VII e
  VIII). Acabam a instalação à parte e o `uv tool upgrade`. O único pré-requisito é o `uv` (o
  `/par:start` instala). A 1ª chamada de cada versão que muda dependências prepara o ambiente
  (internet, cerca de 60 MB, uma vez).
- **⚠ Breaking — `prumo init` não copia mais skills e agents para `.claude/`.** `prumo update`
  move as cópias antigas para `.prumo/legacy-copies/<AAAAMMDD-HHMMSS>/`, sem apagar nada, porque
  elas sombreavam o plugin ([ADR-0038](docs/adr/adr-0038-plugin-unica-distribuicao.md) supersede
  em parte a [ADR-0032](docs/adr/adr-0032-superficie-por-dominio-e-modos.md) e a
  [ADR-0033](docs/adr/adr-0033-subagents-nomeados.md)).
- **⚠ Breaking — `prumo paper connect`, `prumo init` e `prumo update` deixam de ser
  pré-aprovados pelas skills** e pedem confirmação
  ([ADR-0026](docs/adr/adr-0026-mcp-prumo-dominio-paper.md)).
- **⚠ Breaking — o perfil do Zettlr passa a usar uma cópia do filtro em `docs/templates/`:**
  regenere o perfil e reimporte-o uma vez. O `prumo write zettlr-profile` acrescenta o perfil ao
  `.gitignore` do projeto, porque ele traz caminhos desta máquina.
- **⚠ Breaking — regressão honesta: Windows (nativo e WSL) declarado sem suporte**, com
  mensagem fixa. O onboarding citava instaladores nativos não validados.

### Removido

- **⚠ Breaking — `prumo init --integration/-i`**, a chave `integrations` do `prumo init --json`
  e a exceção pública `par.IntegrationError` (Princípio VI).
- **⚠ Breaking — o console script `prumo-zettlr-export`.** O docx canônico se pede ao Claude
  ("exporta o docx canônico de <arquivo>").
- **⚠ Breaking — `prumo paper verify-refs --deep`**, e com ele o parâmetro `deep` de
  `verify_refs` e a exceção `RefcheckerUnavailableError`. A chave `deep` do JSON continua,
  sempre `false` (Princípio IV).
- **⚠ Breaking — o servidor MCP `qmd` sai do plugin.** O qmd vira CLI opcional
  (`npm install -g @tobilu/qmd`).

### Adicionado

- `.claude/settings.json` no template: o PAR se atualiza sozinho no projeto e é oferecido aos
  coautores. `prumo update` o traz aos projetos existentes.
- Mensagem própria para o sandbox do Claude Code na preparação do ambiente (saída 77, com a
  oferta de repetir fora do sandbox).

### Corrigido

- O drift CLI×plugin (0.67.2 sem `validate`/`status`) deixa de ser possível; sai o
  `_PF_DRIFT`, que nunca disparava
  ([ADR-0019](docs/adr/adr-0019-preflight-uniforme-skills.md)).
- O adeu passa a ser travado com as dependências transitivas e funciona offline. Antes, o
  `uvx adeu==1.29.0` resolvia fastmcp 4.0.10 + mcp 2.2.0, nunca testados.
- Mac Intel: `cryptography` < 49 nessa plataforma, porque a 49 não publica wheel Intel.
- A mensagem de qmd ausente apontava um repositório errado.

### Documentação

- README e onboarding: trilha pela aba Code; Cowork e chat só com julgamento; desinstalação
  limpa.
- RELEASING: versão carimbada pelo `gen_indexes` (passos 3, 4 e 6); "abra uma sessão nova" no
  lugar de `/reload-plugins`.
```

Os bullets ⚠ da Spec B para a 0.71.0 entram nas mesmas seções ("Removido" para a aposentadoria;
"Alterado" para o doctor e o `connect`).

### `RELEASING.md` (muda só a documentação, sem bump)

- **Regra-mãe (linha 7):** "(atualizar o plugin + abrir uma sessão nova)".
- **Passo 3:**
  ```bash
  # edite _version.py manualmente, depois:
  uv run python .github/scripts/sync_manifest_version.py
  uv run python .github/scripts/gen_indexes.py   # carimba a versão no bloco runtime das portas, do start e do reader
  ```
- **Passo 4:** acrescenta `uv run python .github/scripts/gen_indexes.py --check`.
- **Passo 6:** `git add CHANGELOG.md CITATION.cff src/par/_version.py .claude-plugin/plugin.json .claude-plugin/marketplace.json skills agents`.
- **Passo 8 e §"Como consumidores aplicam":** "Atualize o plugin (automático nos projetos com o
  `settings.json` do template; senão, no app: + → Plugins → Gerenciar plugins; no terminal:
  `/plugin marketplace update prumo-assistant-for-researcher`) e abra uma sessão nova." Saem
  `/reload-plugins` e `uv tool upgrade`.
- **Nota nova no passo 2:** "Se o release muda `uv.lock` ou `shims/prumo`, o CHANGELOG avisa
  que a 1ª chamada desta versão prepara o ambiente de novo (internet, cerca de 60 MB, uma vez)."

### Migração de quem já usa

Lista única da 0.71.0, com os itens da Spec B (ADR-0037) no fim. A ordem importa: o perfil do
Zettlr é regenerado antes de remover o CLI antigo, porque o perfil importado hoje aponta para o
filtro dentro desse CLI.

1. **Atualize o PAR e abra uma sessão nova.** A 1ª chamada prepara o ambiente.
2. **Em cada `pj_*`:** peça "atualiza o projeto" (`prumo update`). As cópias de `.claude/skills`
   e `.claude/agents` com nome do PAR vão para `.prumo/legacy-copies/<AAAAMMDD-HHMMSS>/`, e entra
   `.claude/settings.json` se faltar.
3. **Zettlr:**
   - peça "regenera o perfil do Zettlr" (`prumo write zettlr-profile`) e reimporte
     `docs/templates/prumo-docx.yaml` uma última vez; o comando também acrescenta o perfil ao
     `.gitignore` do projeto;
   - apague o comando custom "prumo docx (canônico)" (Settings → Import/Export → Custom export
     commands);
   - o `doctor` acusa um perfil que ainda aponte o caminho do `uv tool`.
4. **CLI global antigo** (`uv tool install`, que o dono e o colega do piloto têm): o preflight e
   o `/par:start` oferecem uma vez `uv tool uninstall prumo-assistant-for-researcher`, ou rode
   você mesmo, depois do item 3. Enquanto ele existir, o hook garante que o `prumo` da sessão é o
   do plugin.
5. **qmd:** quem usava a busca semântica confere `qmd --version`; sem ele,
   `npm install -g @tobilu/qmd`. Não há o que registrar como MCP.
6. **Dono (dev):**
   - o `.claude/settings.json` do repo já traz `disabledMcpjsonServers`;
   - desenvolva com `claude --plugin-dir .`;
   - o qmd como MCP é opcional e fica fora do produto: `claude mcp add --scope user qmd -- qmd mcp`.
7. **Zotero (Spec B, ADR-0037):**
   - atualize o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins);
   - quem ligou "Allow other applications" só pelo PAR pode desligar, a menos que use o 54yyyu;
   - scripts com `prumo paper sync-all` passam a `prumo paper sync`;
   - nada a fazer nos arquivos: `_annotations.md` e `note__*.md` ficam.

## Spikes e gates pré-corte

Os gates bloqueiam o corte da 0.71.0 e a aceitação da ADR-0038, não o merge de cada PR. O
`/plugin install … --marketplace raphaelfh/prumo-assistant-for-researcher` instala o ramo padrão
do repositório, então o S-canal só exercita o lançador depois que o PR 4 (§Release e migração)
entra em `main`. Ele roda logo em seguida, antes do PR 5 e do bump de versão.

- **Pré-condição do S-canal.** O cache de plugins é por versão, e a versão ainda é a 0.70.3:
  antes do passo (1), o dono roda `/plugin uninstall par` e apaga
  `~/.claude/plugins/cache/prumo-assistant-for-researcher/par/`, senão a instalação reaproveita a
  cópia antiga.
- **Janela de exposição.** Entre o merge do PR 4 e o corte, uma instalação nova pelo marketplace
  recebe o lançador com o número 0.70.3. Quem já tem o plugin fica na cópia em cache até a versão
  mudar ("a manifest that pins `version` keeps every user on the cached copy until its author
  changes the string", <https://code.claude.com/docs/en/plugins/loading>). Os únicos usuários
  são o dono e o colega do piloto; a janela dura o S-canal mais o PR de docs.

| Gate | O que confirma | Bloqueia | Se falhar |
|---|---|---|---|
| **S-canal** (manual, máquina do dono, ~1 h) | Na aba Code do Desktop:<br>(1) `/plugin install par --marketplace raphaelfh/prumo-assistant-for-researcher` instala;<br>(2) numa sessão nova, o hook em forma exec rodou (`command -v prumo` → `<raiz>/shims/prumo`);<br>(3) aparecem `mcp__plugin_par_prumo__*`;<br>(4) `prumo --version` = bloco runtime;<br>(5) com o sandbox Bash ligado, o 1º `prumo` depois do MCP funciona;<br>(6) num pj com o `settings.json` do template, o auto-update aparece ligado em + → Plugins. | aceitação da ADR-0038 e o corte da 0.71.0 | (1) trilha pela interface (+ → Plugins → Add plugin), +1 passo no README;<br>(2) `hooks.json` em forma shell com o placeholder entre aspas duplas;<br>(6) instrução de ligar "Enable auto-update" no `/par:start`. |
| **`launcher-smoke` verde** (CI) | ubuntu (`sh`, que lá é o `dash`, e `bash --posix`), macos arm64 e macos-15-intel (`sh` e `/bin/dash`) | idem | Intel: declarar "Mac Intel: não suportado" no README e na matriz. Outros: corrigir antes do corte. |
| **S-cowork** (opcional) | Se o Cowork em "host loop" carrega hooks e MCP stdio de plugin synced | nada | A matriz continua "não suportado/testado". |
| **S-sync** (opcional) | Se a anomalia do canal da conta (plugins com hooks/MCP stdio excluídos do synced desde 30/09) tem causa conhecida | nada | O canal da conta continua sem recomendação para o PAR completo. |

## Riscos e premissas restantes

| # | Premissa ou risco | Estado | Degradação se falhar |
|---|---|---|---|
| R1 | `/plugin install <nome> --marketplace <repo>` funciona na aba Code | desconhecido (S-canal) | Trilha pela interface, com 1 passo a mais. |
| R2 | A forma exec de hook (`args`) roda na versão do Claude Code da pesquisadora | documentado, não observado (S-canal) | Forma shell com placeholder entre aspas. O caminho da raiz só varia no `$HOME`, que no macOS e no Linux não tem espaço nem aspas. |
| R3 | Subagents herdam o env file da sessão | incerto | O `reader` usa a forma `sh` do próprio bloco (1 prompt por comando). |
| R4 | A 1ª preparação (cerca de 60 MB) cabe no tempo-limite de inicialização de MCP em rede lenta | desconhecido: depende do default de `MCP_TIMEOUT`, que este trabalho não verificou; para referência, ~60 MB levam ~32 s a 15 Mbit/s | As tools faltam só naquela sessão. O `/par:start` aquece o venv pelo Bash e diz "abra uma sessão nova". |
| R5 | A 2ª tentativa com `UV_NATIVE_TLS=1 UV_SYSTEM_CERTS=1` resolve proxy com inspeção de HTTPS | não verificado em proxy real | Saída 69 com a lista de hosts; a TI libera ou instala a CA. |
| R6 | Linux real se comporta como o macOS medido | inferido | O `launcher-smoke` no ubuntu pega antes do release. |
| R7 | `cryptography<49` torna o Mac Intel instalável | só dry-run | Leg Intel; sem ele, declarar sem suporte. |
| R8 | `disabledMcpjsonServers: ["prumo"]` não atinge o servidor `plugin:par:prumo` | inferido | Afeta só o dev do repo: testar o MCP com `claude --plugin-dir <repo>` aberto em outra pasta. |
| R9 | Hooks bloqueados pela TI | verificado como possível | Forma `sh`, com 1 prompt por comando; o MCP fica intacto. |
| R10 | Outro hook sobrescreve o PATH com um export absoluto (receita do direnv) | possível | O preflight compara a versão e cai na forma `sh`. |
| R11 | Um adeu futuro exige fastmcp ≥ 4 (que exige mcp ≥ 2) | possível | O erro aparece no `uv lock` do dev, nunca na máquina da pesquisadora. |
| R12 | Uma mudança futura do uv altera `--no-install-project` ou o formato do lock | possível | O `launcher-smoke` pega. Um lock novo pode subir o piso do uv; a pesquisadora recebe o 78 com o comando. |
| R13 | Configuração do uv do usuário (`~/.config/uv/uv.toml` ou `uv.toml` num ancestral da raiz) altera o sync | medido: é honrada | `python-downloads` tem mensagem própria (78). Um mirror de índice configurado pela TI continua valendo de propósito. |
| R14 | Um MCP aberto há mais de 30 dias perde o venv para a poda de outra versão | aceito | O próprio Claude Code apaga raízes antigas em ~14 dias. |
| R15 | Lançador chamado por symlink | não suportado | A mensagem 1 diz isso; não existe superfície suportada que crie o symlink. |
| R16 | Um pj com `.claude/settings.json` próprio não recebe o D4 | certo (o `update` não o toca) | A pesquisadora liga "Enable auto-update" uma vez em + → Plugins; o onboarding diz como. |
| R17 | Cópia customizada movida para backup deixa de valer | certo, por desenho | O relatório do `update` diz como recriá-la com outro nome; nada é apagado. |
| R18 | `~/.cache/prumo` cresce com venvs antigos (~130 MB cada) | limitado pela poda de 30 dias | `rm -rf ~/.cache/prumo` é sempre seguro; o lançador reconstrói. |

## Fora de escopo

- **Windows** (D1): nenhum código de suporte, nenhum CI. Só a detecção no lançador (nativo e
  WSL) e a mensagem fixa.
- **Spec B:** tolerância do ingest a Refresh/Add Citation, ponte Zotero, docx, pandoc e piso do
  BBT (`2026-10-02-ponte-zotero-minima-design.md`).
- **Substituto do `--deep`:** não há busca por título e autor para entradas sem DOI/PMID.
- **Rodar o lançador sob bubblewrap no CI:** a classificação 77 já é coberta pelo teste
  unitário com `SANDBOX_RUNTIME=1`, e os runners ubuntu podem restringir user namespaces.
- **Resolver symlink em `$0`:** nenhuma superfície suportada o usa.
- **Detectar um servidor `prumo` configurado à mão** (e pedir `claude mcp remove prumo --scope
  user`): nenhum README, onboarding ou template mandou criá-lo. As tools `mcp__prumo__*` que o
  dono vê vêm do `.mcp.json` de projeto deste repo, caso coberto por A17.
- **`--no-config` no `uv sync`:** ignoraria mirrors legítimos configurados pela TI.
- **Publicação no PyPI, MCPB e bundle offline:** se um dia houver bundle com pandoc, entra a
  obrigação GPL (texto e oferta de fonte).
- **Canal da conta como caminho do PAR completo;** "Cowork degradado".
- **qmd como MCP do produto;** typst e pandoc no lock.
- **Limpeza automática na desinstalação** (`CLAUDE_PLUGIN_DATA`; trade-off em A2).
- **Curingas largos fora do D5:** `Bash(prumo write *)` (portas `write` e `protocol`; casa
  `prumo write review apply`) e `Bash(git *)` (porta `write`) continuam. Mudam arquivos dentro do
  fluxo da própria skill, ao contrário dos três comandos que o D5 tira.

## Quando reavaliar

- **Windows:** com a 1ª pesquisadora real no Windows (D1). Escopo: 2º lançador, regras
  PowerShell, CI Windows e fallback de symlink.
- **Limpeza automática:** se o Claude Code passar a expor `CLAUDE_PLUGIN_DATA` ao Bash e aos
  subagents, ou se uma pesquisadora reclamar do `~/.cache/prumo` órfão. Aí mover o cache para
  `CLAUDE_PLUGIN_DATA` vira troca de uma linha mais o export no hook.
- **Partida a frio:** com o 1º relato de tools ausentes por partida lenta em rede de hospital.
  Opções: aquecer o venv no próprio hook, que roda antes do MCP, ou baixar o tamanho
  (dependências opcionais).
- **Canal da conta:** quando o S-sync explicar a anomalia, ou a Anthropic corrigi-la. Aí avaliar
  recomendar o canal da conta também para a aba Code.
- **Cowork:** quando o S-cowork mostrar hooks e MCP stdio carregando no host. Aí revisar a matriz.
- **Forma exec do hook:** se o S-canal mostrar que ela não roda, troca para a forma shell com
  aspas.
- **`--deep`:** quando uma pesquisadora pedir checagem por título e autor de entradas sem
  identificador.
- **Comando no Zettlr:** quando uma pesquisadora pedir, mais de uma vez, o docx canônico de
  dentro do Zettlr.
- **qmd como MCP:** quando o qmd for necessário numa superfície sem Bash.
- **Python do venv:** quando a matriz do CI sair do 3.12. Muda `_py`, e com isso o hash e o venv.
- **Proxy de hospital:** com o 1º relato real de proxy que o retry de TLS não resolve.
- **Curingas `Bash(prumo write *)` e `Bash(git *)`:** com o 1º relato de um comando desses
  mudando arquivos sem a pesquisadora ver. Aí estreitá-los como o D5.

# ADR-0038 — O plugin é a única distribuição: launcher roda o CLI desta raiz, travado no uv.lock

- Status: aceito
- Data: 2026-10-06
- Origem: [[2026-10-02-plugin-distribuicao-unica-design]]; supersede em parte a ADR-0017, a ADR-0018, a ADR-0019, a ADR-0026, a ADR-0032, a ADR-0033 e a ADR-0034; complementa a ADR-0010

## Contexto

O CLI e o plugin eram distribuídos em separado e divergiam: o CLI global 0.67.2 não tinha `validate` nem `status` sob um plugin mais novo (5eb2c6b), e o item de drift do preflight da ADR-0019 (`_PF_DRIFT`) se mostrou inerte, porque o Bash da sessão não vê `CLAUDE_PLUGIN_ROOT`. Os nomes MCP que as skills citavam (`mcp__prumo__*`, `mcp__qmd__*`) nunca casaram para quem tem só o plugin. O `uvx` em runtime não pinava de verdade e quebrava offline. O `prumo init` copiava skills e agents para o projeto, e essas cópias sombreavam o plugin. Os curingas `Bash(prumo *)` pré-aprovavam mais do que cada modo usa.

## Decisão

1. **Lançador** (A1, A3). O `prumo` da pesquisadora é sempre `${CLAUDE_PLUGIN_ROOT}/shims/prumo` (único arquivo de `shims/`; `bin/` na raiz faz o chat e o Cowork recusarem o plugin). Ele roda `src/par` desta raiz com `python -I -B -c …`, Python 3.12 fixo. `uv tool install`/`uv run` ficam só para desenvolvimento; sai o console script `prumo-zettlr-export`.
2. **Venv por conteúdo** (A2) em `~/.cache/prumo/venv-3.12-<cksum(uv.lock + shims/prumo)>`, montado com `uv sync --frozen --no-install-project`. Release sem mudança de dependência reusa o venv; venvs sem uso há 30 dias são apagados no caminho frio.
3. **Falhas classificadas** (A4): toda falha sai com uma linha `PAR:` e o remédio (127 falta o uv, 69 rede, 73 disco, 77 sandbox, 78 uv antigo ou sem download de Python, 70 venv sem Python, 71 Windows/WSL, 1 plugin incompleto).
4. **Três caminhos, um lançador** (A5): o `.mcp.json` roda `/bin/sh ${CLAUDE_PLUGIN_ROOT}/shims/prumo mcp serve`; o hook `SessionStart` (forma exec) põe `<raiz>/shims` no PATH via `CLAUDE_ENV_FILE`; com hooks bloqueados, a forma `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` do bloco runtime.
5. **Identidade por versão** (A6, A7): o `gen_indexes.py` é o único escritor do bloco `prumo:runtime` (portas, `start`, `agents/reader.md`), carimbado com `__version__`; o preflight dos modos `cli` compara `prumo --version` com ele e decide pela linha `PAR:`, nunca pelo exit 127.
6. **Dependências** (A8): adeu no lock, nenhum `uvx` em runtime; sai `verify-refs --deep` (D3); `cryptography<49` no Mac Intel.
7. **qmd só como CLI** (A9, D3): o servidor `qmd` sai do `.mcp.json`; as skills usam `Bash(qmd *)`.
8. **Zettlr** (A10, D3): `prumo write zettlr-profile` copia o filtro para `<pj>/docs/templates/` e aponta o perfil para a cópia; o `doctor` acusa cópia divergente ou ausente.
9. **Projeto sem cópias** (A11): `init` não cria `.claude/skills` nem `.claude/agents`; `update` move as cópias antigas para backup.
10. **Sai `integrations/`** (A12); o catálogo é montado por `core/skills.py::load_skill_registry`.
11. **Atualização automática** (A13, D4) pelo `templates/pj_base/.claude/settings.json` estático; **curingas Bash estreitos** (A14, D5) por modo.
12. **Superfícies** (A15, D1): app Claude na aba Code (Mac) e Claude Code no terminal (Mac ou Linux). Windows, WSL, chat, Cowork e SSH: não suportados, ditos em uma frase pelo preflight.
13. **Desenvolvimento do repo** (A17): o dev rejeita o `.mcp.json` como servidor de projeto e carrega o plugin com `claude --plugin-dir .`.

A16 (Zotero atrás do sandbox Bash) fica na ADR-0037.

**Trade-off do `CLAUDE_PLUGIN_DATA`.** Ele daria limpeza automática ao desinstalar, mas só existe para hooks e servidores MCP; o Bash da sessão não o vê, e plugin synced e de marketplace teriam venvs diferentes. O cache fica em `~/.cache/prumo`, e a desinstalação limpa é documentada: `rm -rf ~/.cache/prumo`, e `uv cache clean` e `uv python uninstall 3.12` se nada mais os usa.

**Supersede em parte.**
- ADR-0019: o item de drift, "CLI ausente → instalar o CLI" e o item `qmd` (inventário de tools MCP → checagem do CLI `qmd`).
- ADR-0017 e ADR-0026: "sem o CLI instalado, o servidor falha ao subir" passa a "sem uv".
- ADR-0026:23: o prefixo `mcp__prumo__*` passa ao nome real no plugin, `mcp__plugin_par_prumo__*` (corrigido nas skills na 0.70.3).
- ADR-0033:21: "`prumo init` o copia para `.claude/agents/`" sai.
- ADR-0032:25: "não é apagado pelo `update`" passa a "o `update` move para backup".
- ADR-0018: sai a camada `--deep`.
- ADR-0034:17: `prumo-zettlr-export` sai da lista de nomes; fica só o CLI `prumo`.
- Spec `2026-07-22-zettlr-front-design.md`: sai o custom command do Zettlr; o docx canônico é pedido ao Claude.

**Complementa.** A ADR-0010: a raiz do plugin, que já é a raiz do repo, passa a ser também o runtime. A ADR-0026:29 ("sem MCP de terceiro no `.mcp.json`") passa a ser verdadeira.

## Alternativas rejeitadas

PyPI/`uvx` pinado; `bin/`; MCPB; MCP-first; `command: uv` / `uv run --project` no `.mcp.json`; venv em `CLAUDE_PLUGIN_DATA`; venv por raiz ou por versão; `.python-version`; `python -m par` com `PYTHONPATH`; `pypandoc-binary`; typst no lock; gêmeos absolutos nas regras de `allowed-tools`; lint `requires⇔allowed-tools`; "use o WSL". Os motivos estão na spec de origem, uma por decisão.

## Consequências

Atualizar o PAR é uma ação só: a versão nova do plugin traz o CLI da mesma versão, e o drift deixa de existir por construção. O único pré-requisito é o `uv`, que o `/par:start` instala com consentimento. Mudar `uv.lock` ou `shims/prumo` faz cada pesquisadora baixar o ambiente de novo (cerca de 60 MB, uma vez). Quem tem o CLI antigo instalado à parte recebe, uma vez, a oferta de `uv tool uninstall`. Gates: `launcher-smoke` verde no CI (ubuntu, macOS arm64 e macOS Intel); o S-canal (instalação pelo marketplace na aba Code) é confirmado pelo dono depois do corte, com os remédios da spec se algum passo falhar.

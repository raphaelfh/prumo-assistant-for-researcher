# ADR-0040 — Antigravity e ChatGPT (Codex) por manifesto nativo na mesma raiz

- Status: proposto
- Data: 2026-11-08
- Origem: pedido do mantenedor (usar o PAR também no Antigravity e no ChatGPT); dispara a fase 3.0 do ROADMAP ("colega adotar host diferente"); complementa a ADR-0010 e a ADR-0038

## Contexto

O Antigravity e o Codex (no app ChatGPT e no terminal) passaram a ler plugins com o mesmo formato de skill do Claude (`skills/<nome>/SKILL.md`, só `name` e `description` obrigatórios) e servidor MCP stdio. Cada um quer o próprio manifesto: o Antigravity lê `.antigravity-plugin/plugin.json` (precedência sobre `plugin.json` na raiz, pensada para repo que também traz `.claude-plugin/`) e `mcp_config.json`; o Codex lê `.codex-plugin/plugin.json`, o catálogo `.agents/plugins/marketplace.json` e o MCP que o manifesto nomeia. A constitution previa `integrations/<host>/installer.py`, que a ADR-0038 removeu.

Medido no Codex 0.163 (app ChatGPT 155, 2026-11-08), instalando deste checkout num `CODEX_HOME` isolado: as skills aparecem como `par:start`, `par:paper`…; o `${PLUGIN_ROOT}` dos docs **não** é expandido no `mcp.json` nem exportado ao servidor, mas `"cwd": "."` resolve para a raiz do plugin; o servidor sobe e expõe `mcp__prumo__*`; sem `hooks` no manifesto o Codex lê o `hooks/hooks.json` do Claude e avisa da chave `modules`; o sandbox marca `CODEX_SANDBOX=seatbelt` e bloqueia rede e escrita fora do workspace.

## Decisão

1. **Uma raiz, três manifestos.** `.claude-plugin/` (como está), `.antigravity-plugin/plugin.json` + `mcp_config.json` (`${PLUGIN_ROOT}/shims/prumo`, como documentado) e `.codex-plugin/plugin.json` + `mcp.json` (`./shims/prumo` com `cwd: "."`) + `.agents/plugins/marketplace.json` (fonte `./`). Nenhuma lógica nova: as mesmas `skills/`, o mesmo lançador, o mesmo servidor (Princípio I). O manifesto do Codex declara `"hooks": {"hooks": {}}` para não ler o arquivo do Claude.
2. **Versão e coerência geradas.** `sync_manifest_version.py` escreve a versão nos dois manifestos novos; `validate_manifests.py` exige `name`, `version` e `description` iguais aos do Claude e o servidor `prumo` pelo lançador nos três MCPs (Princípio VII).
3. **Texto host-neutro nos blocos gerados.** O bloco `prumo:runtime` diz como achar a raiz quando `${CLAUDE_PLUGIN_ROOT}` não é trocado (a pasta acima de `skills/` ou `agents/`), o nome das tools em cada host e a invocação (`/par:x`, `$par:x`, `/x`); o preflight aceita os três hosts. Sem subagent no host, a skill segue o agent ela mesma (o fallback que os modos já tinham).
4. **Projeto lido por todos.** O `pj_base` passa a gerar `AGENTS.md` com as instruções, e o `CLAUDE.md` só o importa (`@AGENTS.md`). Projetos antigos ganham o `AGENTS.md` no próximo `prumo update` (arquivo ausente, ADR-0029).
5. **Lançador.** `CODEX_SANDBOX` conta como sandbox (saída 77), e a mensagem fala em "sandbox do agente".
6. **Superfícies** (revisa a ADR-0038, item 12): Claude Code (app e terminal), Antigravity e Codex (app ChatGPT e terminal), no Mac e no Linux. Chat web, Cowork, SSH, Windows e WSL seguem fora.

## Alternativas rejeitadas

`integrations/<host>/installer.py` copiando skills para o projeto (é a cópia que a ADR-0038 tirou); `plugin.json` portátil único na raiz (o Antigravity rejeita chave desconhecida e o MCP de cada host tem formato próprio de qualquer jeito); `${PLUGIN_ROOT}` no MCP do Codex (não expande na versão medida); converter os agents em skills (o fallback em texto já cobre, sem segunda fonte).

## Consequências

Mudar `shims/prumo` refaz o venv de cada pesquisadora (cerca de 60 MB, uma vez).

Medido no Antigravity 2.29.1 (2026-11-08), instalando do GitHub como usuário novo: o app não traz o CLI `agy`, e o caminho que funciona sem terminal é o agente clonar o repo em `~/.gemini/config/plugins/<pasta>`; o `${PLUGIN_ROOT}` expande, o `cwd` é a raiz do plugin, as 6 skills carregam e o servidor fica `READY` com as 10 tools, nomeado `<pasta>_prumo` (o prefixo é a pasta, não o `name` do manifesto). Plugin sem agents nesta versão: as skills seguem o agent elas mesmas. O `hooks/hooks.json` e o `AGENTS.md` da raiz são ignorados (o Antigravity só lê `hooks.json` e `rules/` na raiz do plugin). Não medido: a instalação por `owner/repo` no Codex e o piloto com pesquisadora nos dois hosts novos. Os mods (ADR-0039) e o hook `SessionStart` continuam só do Claude; fora dele, a forma `sh` do lançador é o caminho normal.

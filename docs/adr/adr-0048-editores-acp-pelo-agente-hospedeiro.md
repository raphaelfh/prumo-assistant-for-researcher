# ADR-0048 — Zed e JetBrains pelo agente que roda via ACP, sem integração por editor

- Status: proposto
- Data: 2026-11-19
- Origem: pedido do mantenedor (rodar o PAR no Zed e nos IDEs JetBrains); trigger da fase 3.0 do ROADMAP ("colega adotar host diferente"); complementa a ADR-0040

## Contexto

O Zed e os IDEs JetBrains não têm sistema de plugin para agente. O Zed tem um agente nativo que lê Skills de `~/.agents/skills/` ou `<projeto>/.agents/skills/` (pastas planas, sem namespace), MCP em `context_servers` no `settings.json` (sem `cwd` nem expansão de variável documentados) e um único arquivo de regras por projeto (o primeiro de uma lista em que `AGENTS.md` vem antes de `CLAUDE.md`). Skills, MCP e regras são três mecanismos separados, e não há manifesto que os junte. O JetBrains AI Assistant não tem nada parecido para terceiros.

Os dois editores falam o ACP (Agent Client Protocol, criado pela Zed com a JetBrains): rodam no chat do editor um agente externo instalado pelo registro ACP. Entre esses agentes estão o Claude Agent, que usa o Claude Agent SDK (o runtime do Claude Code), e o Codex, os dois hosts em que o PAR já roda. O Zed avisa que as Skills dele não valem para agente externo; o agente lê a própria configuração nativa. O JetBrains documenta só o repasse dos servidores MCP configurados no IDE para o agente ("Pass custom MCP servers").

Ainda não medido: se o adaptador ACP do Claude (`agentclientprotocol/claude-agent-acp`) carrega os plugins instalados em `~/.claude`. No código lido, o adaptador resolve o `settings.json` do usuário pelo SDK (onde fica `enabledPlugins`), e só isso; nada nele carrega plugin. Por padrão, o SDK carrega as skills de `~/.claude/skills/`. Também não foi medido se o adaptador do Codex carrega os plugins do Codex.

## Decisão

1. **O PAR chega aos editores ACP pelo agente, não pelo editor.** No Zed e no JetBrains, a superfície suportada é o Claude Agent (ou o Codex) rodando via ACP, com o PAR instalado nesse agente como já é hoje. Não há manifesto, extensão nem instalador por editor. O que já serve para Claude Code e Codex vale aqui: as mesmas `skills/`, o mesmo lançador e o mesmo servidor `prumo` (Princípio I).
2. **A medição vem antes de qualquer código.** Instalar o Claude Agent pelo registro ACP no Zed e no JetBrains, abrir um `pj_exemplo` e registrar se `/par:start` e as tools `mcp__plugin_par_prumo__*` aparecem. O mesmo vale para o Codex. O resultado vai para a seção "Medição" desta ADR antes de ela ser aceita.
3. **Se o agente carregar o plugin**, a entrega é só texto: o README ganha a linha dos editores ACP; o bloco `prumo:runtime` (`gen_indexes.py`) e a skill `start` passam a citar o Zed e o JetBrains como "Claude Code/Codex dentro do editor". Lançador e manifestos ficam como estão.
4. **Se não carregar**, o caminho é o que os dois editores já expõem ao agente, sem tocar no editor:
   - MCP: o servidor `prumo` é registrado no IDE (`context_servers` no Zed, MCP personalizado no JetBrains) com o caminho absoluto do lançador (`/bin/sh <raiz>/shims/prumo mcp serve`) e repassado ao agente pelo ACP. O lançador já acha a raiz por `$0`.
   - Skills: o README orienta como pôr as skills do PAR onde o SDK as encontra (`~/.claude/skills/`). Isso só é feito se a medição mostrar que não duplica o plugin no Claude Code comum.
   Nesse caso, a forma exata vira emenda desta ADR, com a medição que a justifica.
5. **O agente nativo do Zed fica fora.** Fora do Claude e do Codex, nenhum agente roda o PAR no Zed. O Antigravity não usa ACP e segue pela ADR-0040.

## Alternativas rejeitadas

- **Instalador para o agente nativo do Zed** (`prumo zed install`, com skills geradas com prefixo `par-*` em `~/.agents/skills/` e a raiz absoluta gravada): seria uma segunda variante das skills, com nomes diferentes dos outros hosts, mais um trecho a editar no `settings.json` (JSONC) do usuário, e mesmo assim sem subagents nem hooks. É superfície nova para um público que o Claude Agent no próprio Zed já atende.
- **Extensão Zed com `context_servers` no `extension.toml`**: o Zed planeja descontinuar extensões MCP em favor do registro MCP oficial, e esse tipo de extensão não leva skills.
- **Publicar o PAR como agente próprio no registro ACP**: exigiria um agente nosso (modelo, loop, tools), o oposto de ser plugin de um agente existente.

## Consequências

- Zed e JetBrains entram como superfícies sem custo de manutenção por editor. O que quebrar ali quebra no adaptador ACP do agente, fora do nosso alcance; o README diz isso.
- A pesquisadora precisa de uma assinatura ou chave do agente (Claude ou Codex), como nos outros hosts; o JetBrains não exige a assinatura do JetBrains AI para agentes ACP.
- A ADR-0040, item 6 (superfícies), ganha "Zed e JetBrains, via Claude Agent ou Codex pelo ACP", condicionado à medição do item 2.
- Mods (ADR-0039) e o hook `SessionStart` podem não rodar no editor. A forma `sh` do lançador continua sendo o caminho normal, como no Antigravity e no Codex.

## Medição

Pendente (item 2).

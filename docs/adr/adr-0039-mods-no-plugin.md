# ADR-0039 — Mods de Claude Code no plugin: módulo TypeScript em `hooks/mods/`

- Status: proposto
- Data: 2026-11-01
- Origem: pedido do mantenedor (painel de revisão e PICOT no system prompt); complementa a ADR-0038 e a ADR-0017

## Contexto

O Claude Code passou a carregar "mods": um módulo TypeScript que o `hooks/hooks.json` de um plugin nomeia em `modules`, com acesso a painéis, ao system prompt (`prompt.compose`) e aos servidores MCP do próprio plugin (`$.mcp.connect`), sem gastar turno do modelo. Duas lacunas do PAR cabem nisso: a pesquisadora não vê o estado da revisão do manuscrito sem perguntar ao Claude, e a PICOT fechada em `.claude/picot.toml` só chega ao modelo quando uma skill a lê.

## Decisão

1. **Um módulo, no próprio plugin.** `hooks/hooks.json` mantém o hook `SessionStart` de shell e ganha `"modules": ["./mods/register.ts"]`; o código vive em `hooks/mods/`, o contrato de `$.state` em `types/index.d.ts` (nomeado em `plugin.json` como `types`) e os testes do kit em `tests/mods/` (`claude plugin test .`).
2. **PICOT vigente** (`hooks/mods/picot.ts`). Um hook `prompt.compose` anexa a seção `par:picot` (escopo `session`) com o TOML de `.claude/picot.toml` do cwd, lido a cada composição; sem arquivo, não há seção. O texto lembra que mudanças passam por `/par:protocol picot` (Princípio de fonte única da PICOT).
3. **Painel "Revisão do manuscrito"** (`hooks/mods/review.tsx`). Lê `reviews/*/events.yaml` para achar cada `page` e chama `review_status` e `review_worklist` do servidor `prumo` (só leitura, ADR-0017). Abre sozinho quando o projeto tem `reviews/`, e pelo comando `/revisao`; atualiza ao fim de cada turno e no botão. Os botões só preenchem o prompt (`/par:review reconcile --page …` ou uma pergunta sobre a marca): nenhuma decisão de revisão é tomada pelo painel.
4. **Nada de Python novo.** O mod não chama o CLI; depende só do servidor MCP que o plugin já sobe.

## Consequências

- Exige Claude Code com suporte a mods (2.1.286 ou mais, conforme a documentação de mods); versões anteriores ignoram `modules` ou recusam o hook. A API está em early access e muda entre releases: `claude plugin validate .` e `claude plugin test .` precisam rodar a cada bump do Claude Code.
- O canal da conta (Customize → Plugins), o chat e o Cowork não estão testados com `modules`; continuam fora das superfícies suportadas (ADR-0038, item 12).
- A seção da PICOT consome tokens do system prompt em toda requisição (uma PICOT típica tem 1 a 2 KB; o texto é cortado em 8 000 caracteres).

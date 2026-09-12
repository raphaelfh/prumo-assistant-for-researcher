---
name: disclosure
description: "Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt ou en)."
argument-hint: "[--lang pt|en]"
allowed-tools: Read Bash(prumo write disclosure *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1k tokens
  requires: [cli]
  phrases:
    - "gera a declaração de uso de IA"
    - "disclosure de IA pro periódico"
---

# write disclosure — declaração de uso de IA

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

1. Rode `prumo write disclosure --lang <pt|en> --json` na raiz do `pj_*`. O idioma segue o pedido da pessoa; sem pedido, use o idioma do manuscrito.
2. Mostre o parágrafo (`statement_pt` ou `statement_en`) e a tabela de `tools`: ferramenta, modelo, tarefa, contagem e se houve revisão humana.
3. Se `tools` vier vazio, diga que nenhum artefato do projeto registra uso de IA. Não invente uso.
4. Nunca edite o parágrafo para acrescentar ferramenta que o comando não listou. Correção de proveniência se faz no artefato, não na declaração.

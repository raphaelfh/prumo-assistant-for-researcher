# ADR-0035 — Proveniência só no `_meta` embutido; trace JSONL adiado

- Status: aceito
- Data: 2026-09-12
- Origem: [[2026-09-12-proveniencia-ligada-design]]

## Contexto

O Princípio V pede duas coisas: bloco `_meta` em todo artefato gerado e eventos de execução em `.prumo/traces/YYYY-MM-DD.jsonl`. `core/provenance.py` tinha as duas peças, mas `TraceWriter` nunca teve chamada. O `_meta` estava ligado só no `paper extract`. Nenhum comando, skill ou relatório lê trace, e gravar payload de LLM em disco abre a questão de confidencialidade que o achado "Safe outputs" do ROADMAP ainda não fechou.

## Decisão

A proveniência do prumo mora no artefato. Todo produtor de artefato gerado por agent ou pelo CLI carimba `_meta` via `build_meta`: no frontmatter YAML quando é Markdown (chave machine-owned, corpo humano preservado, ADR-0009) e na chave `_meta` quando é JSON. `write disclosure` lê esse bloco primeiro.

`TraceWriter` e `is_trace_disabled` saem do código. O trace JSONL fica adiado, com gatilho: um consumidor concreto de eventos de execução (auditoria de IRB que peça a sequência de tool calls, ou reprodução de run que o `_meta` não cubra), decidido junto da fronteira de Safe outputs.

## Consequências

A cláusula de trace do Princípio V fica sem implementação até o gatilho. A constitution não muda sem emenda formal, e esta ADR registra o desvio e o gatilho.

Artefato novo gerado pelo prumo precisa carimbar `_meta`, com teste. O `generator` solto no frontmatter de finding deixa de existir: vira `_meta.skill`, e o disclosure não o lê mais (nenhum `pj_*` o tinha). O fallback legado `extracted_model`/`extracted_at` continua, porque 126 `_meta.md` extraídos antes do carimbo dependem dele.

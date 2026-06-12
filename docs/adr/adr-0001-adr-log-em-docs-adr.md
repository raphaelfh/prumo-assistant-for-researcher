# ADR-0001 — ADR log do repo em `docs/adr/`; produto continua gerando `docs/decisions/`

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D2)

## Contexto
As decisões do repo viviam em 5 lugares (ARCHITECTURE, constitution, ROADMAP, specs, canvas) sem canônico. O produto (`domains/protocol/adr.py` + `templates/pj_base`) gera ADRs em `docs/decisions/` nos projetos `pj_*` — o default do MADR 4.0 também é `decisions/`, enquanto `adr/` é a convenção do adr-tools e a mais reconhecível.

## Decisão
O repo mantém seu próprio log em `docs/adr/` (formato MADR 4.0 minimal, arquivos `adr-NNNN-slug.md`, numeração sequencial). O produto fica inalterado: consumidores continuam recebendo `docs/decisions/`.

## Consequências
Divergência nominal repo×produto, aceita por YAGNI. Trigger de revisão: na próxima mudança em `domains/protocol/adr.py`, decidir se o produto migra para `docs/adr/` (exigiria fallback para projetos existentes). Índice em `docs/adr/_index.md` é gerado por `gen_indexes.py`.

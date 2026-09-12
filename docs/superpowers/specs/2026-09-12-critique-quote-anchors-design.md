---
type: spec
date: 2026-09-12
status: implemented
---

# Achados do `review critique` ancorados em trecho literal e com fontes listadas

## Problema

No A/B de 2026-09-12 (prumo `review critique` × ARS), os dois chegaram a "major revision", mas o ARS ancorava cada achado num trecho literal de até 25 palavras, conferido por script contra o manuscrito. Os achados do prumo só nomeiam a seção, e os melhores vieram de arquivos que o `reviewer` escolheu ler (protocol.md, extracts) sem que o relatório dissesse isso.

## Decisão

1. **Schema, forward-only (Princípio IV).** `PeerReviewReport/v1` ganha `quote: str | None` em `ReviewWeakness` e `UnsupportedClaim` e `sources_read: list[str]` no topo, ambos opcionais. Relatórios antigos continuam válidos.
2. **Checagem determinística (Princípio II) em `contracts.py`, depois do Pydantic.** Um validador Pydantic não lê arquivo; `contracts.py` já é o consumidor determinístico de `prumo validate` e vive no topo do pacote. Para cada `quote` presente: no máximo 25 palavras e substring do texto de `draft_path` com espaços normalizados (`" ".join(s.split())`). Todas as falhas saem numa só `PrumoError`, cada uma nomeando o campo, a seção e o trecho. Se nenhum `quote` existe, o arquivo nem é lido. Se existe e `draft_path` é ilegível, o erro sai uma vez só. `draft_path` relativo resolve contra o cwd.
3. **Instruções mínimas.** `agents/reviewer.md` pede `quote` por fraqueza/claim e `sources_read`. O modo `critique` renderiza o trecho junto do achado e `sources_read` uma vez no fim. `agents/` é fonte única (vai no wheel; `prumo init` copia para `.claude/agents/`, ADR-0033) — não há cópia a manter.

## Alternativas rejeitadas

- **Limite de palavras como `field_validator` no schema.** Funcionaria sem arquivo, mas a mensagem do Pydantic não nomeia a seção; manter as duas regras juntas dá uma mensagem só e um lugar só.
- **Checagem no domínio `write`.** Exigiria função nova e re-export em `api.py` para um único chamador; `contracts.py` já é esse chamador.
- **Flag `--draft` no `validate`.** O caminho já está no payload; flag nova seria conceito a mais (Princípio VIII).
- **`quote` obrigatório.** Quebraria relatórios existentes e o fallback manual sem CLI.

## Aceite

- `quote` literal (inclusive com quebra de linha diferente) valida.
- `quote` parafraseado falha nomeando seção e trecho.
- `quote` com mais de 25 palavras falha.
- Sem `quote` e sem `sources_read` continua válido, sem ler o draft.
- `draft_path` ilegível com dois `quote`s gera uma mensagem só.
- `skills/review/examples/sample_report.json` atualizado valida via `validate_contract` com o draft presente.

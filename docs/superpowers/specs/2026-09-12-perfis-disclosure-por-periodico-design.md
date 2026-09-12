# Perfis de disclosure de IA por periódico — design

**Data:** 2026-09-12 · **ROADMAP:** 2.3 (recorte: só a declaração de IA)

## Problema

`prumo write disclosure` gera um parágrafo genérico. Cada periódico pede elementos
diferentes (versão, fabricante, datas, prompts, motivo) e em lugares diferentes
(Métodos, Agradecimentos, carta, contributorship). A pessoa descobre isso lendo a
política na hora da submissão, e o texto gerado não diz o que falta.

## Decisão

- Arquivo de dados versionado `src/par/domains/write/venue_policies.toml`
  (`VenueDisclosure/v1`), dentro do pacote: sai no wheel por `packages`, sem
  force-include nem `core/paths.py`. Campos por perfil: `name`, `source_url`,
  `accessed`, `required`, `placement`, `prohibited`, `authorship`. Texto parafraseado
  e conferido na página primária do periódico; nada copiado do ARS (CC BY-NC).
- `required` usa vocabulário fechado: preenchido pela proveniência (`tool`, `model`,
  `task`, `dates`, `human_review`) ou pedido à pessoa (`manufacturer`, `prompts`,
  `rationale`). Chave desconhecida ou perfil sem `source_url`/`accessed` falha no load.
- Mesma op e mesmo modo: `--venue <chave>` opcional. Sem ele, saída idêntica à de hoje.
  Com perfil: parágrafo + datas quando exigidas + "Complete antes de submeter: …" +
  local declarado uma vez. `AIDisclosure.venue` (campo novo, forward-only) leva o perfil.
- Periódico sem perfil: texto genérico + uma linha mandando conferir a política.
- Perfis enviados: ICMJE, JAMA, BMJ. NEJM e The Lancet ficaram
  de fora: páginas primárias bloqueadas (403) na verificação de 2026-09-12. Entram
  quando alguém conferir a página e preencher `accessed`.

## Alternativas rejeitadas

- Geração por LLM do texto por periódico: viola II e não é reproduzível.
- Pack `venue-clinical` completo (template, checklist, estilo): VI; a dor atual é só a
  declaração.
- Perfis adivinhados a partir de resumos secundários: política errada é pior que o
  fallback honesto.
- Comando novo `prumo write venue`: mais um conceito para a pessoa (VIII).

## Aceitação

- Um teste por perfil a partir de proveniência fixa (elementos, datas, local).
- Fallback de periódico desconhecido.
- Teste que falha quando o perfil não tem `source_url` ou `accessed`.

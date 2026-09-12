---
type: spec
date: 2026-09-12
status: implemented
---

# Passe advogado do diabo no `review critique`

## Problema

No A/B de 2026-09-12 (prumo `review critique` × ARS academic-paper-reviewer), só uma cadeira do ARS justificou o custo: a do advogado do diabo, que ataca o argumento central. Três cadeiras do ARS apontaram que a conclusão do draft piloto ("attitudes were conclusão central") se apoia num item de teto, enquanto uma parcela grande das respostas a outro item a contradiz. O `reviewer` do prumo, que procura em largura (forças, método, checklist), não pegou.

## Decisão

1. **Segunda chamada do `reviewer` existente, sem agent novo.** `agents/reviewer.md` ganha a entrada opcional `pass: adversarial`. Nesse passe, o reviewer ignora forças e checklist, lê resumo e conclusão frase a frase contra os números dos resultados e ataca só o argumento central: conclusão contradita pelos dados, generalização além da amostra, evidência seletiva, non sequitur, explicação rival ausente e o teste do "e daí?". Devolve no máximo 5 achados, só com `critical_weaknesses` e `claims_without_evidence`, com `quote`.
2. **Opt-in, em paralelo.** O padrão continua com uma chamada do `reviewer`. O passe roda só quando o pesquisador pede ("seja o advogado do diabo", "seja duro", "revisa antes de submeter", frases no frontmatter do modo), nunca com `--section`.
3. **Junção no thread principal, sem schema novo.** Os achados adversariais são acrescentados às listas existentes quando não repetem por sentido (mesma afirmação na mesma seção), não por igualdade de `quote`. A recomendação é reavaliada se a conclusão cair, e o relatório juntado passa por `prumo validate PeerReviewReport/v1`, que confere os `quote`s.

## Alternativas rejeitadas

- **`agents/devils_advocate.md` novo (ADR-0039).** Mesmo custo de chamada, mais um arquivo empacotado, mais um tipo de agent e uma ADR, sem ganho de resultado. A persona só muda o foco, e uma instrução curta faz isso.
- **Marcador `origin` nos achados.** Forward-only seria possível, mas o pesquisador não usa essa informação para decidir nada (Princípios VI e VIII).
- **Passo adversarial dentro da chamada única.** Mais barato, mas é exatamente o contexto que perdeu o achado. A busca em largura dilui o ataque ao argumento.
- **Ligado por padrão.** Na medição, o passe base já pegou o defeito-alvo, e o adversarial acrescentou um achado por cerca de 84 mil tokens. Não passa no critério "mesmo resultado com menos tokens".
- **Flag nova.** Seria conceito a mais (Princípio VIII). Frases de pedido bastam.
- **Painel de personas ou sintetizador (ARS).** Doze chamadas e cerca de 28 mil palavras para o mesmo veredito.

## Aceite

- `agents/reviewer.md` documenta `pass: adversarial` e o formato parcial de saída.
- Por padrão, `critique.md` faz uma chamada. Com pedido explícito, faz duas em paralelo (nunca com `--section`), deduplica por sentido e valida o relatório juntado.
- No draft piloto, o passe adversarial aponta a conclusão central contra o item que a contradiz, e o relatório juntado é aceito por `prumo validate PeerReviewReport/v1`.

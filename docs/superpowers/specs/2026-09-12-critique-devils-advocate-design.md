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
2. **Padrão, em paralelo.** O modo `critique` despacha os dois passes na mesma mensagem, só com caminhos. Pula o passe com `--section`, porque uma seção sozinha não expõe o argumento. Com `--critical-only` o passe continua, já que só produz achados críticos.
3. **Junção no thread principal, sem schema novo.** Os achados adversariais são acrescentados às listas existentes quando não repetem achado da mesma seção com a mesma ideia. A recomendação é reavaliada se a conclusão cair, e o relatório juntado passa por `prumo validate PeerReviewReport/v1`, que confere os `quote`s.

## Alternativas rejeitadas

- **`agents/devils_advocate.md` novo (ADR-0039).** Mesmo custo de chamada, mais um arquivo empacotado, mais um tipo de agent e uma ADR, sem ganho de resultado. A persona só muda o foco, e uma instrução curta faz isso.
- **Marcador `origin` nos achados.** Forward-only seria possível, mas o pesquisador não usa essa informação para decidir nada (Princípios VI e VIII).
- **Passo adversarial dentro da chamada única.** Mais barato, mas é exatamente o contexto que perdeu o achado. A busca em largura dilui o ataque ao argumento.
- **Opt-in por flag nova.** O defeito que o passe pega é o que muda a recomendação, e uma flag seria conceito a mais. Hoje `--section` já basta como desligamento.
- **Painel de personas ou sintetizador (ARS).** Doze chamadas e cerca de 28 mil palavras para o mesmo veredito.

## Aceite

- `agents/reviewer.md` documenta `pass: adversarial` e o formato parcial de saída.
- `critique.md` despacha os dois passes em paralelo, pula com `--section`, junta sem duplicar e valida o relatório juntado.
- No draft piloto, o passe adversarial aponta a conclusão central contra o item que a contradiz, e o relatório juntado é aceito por `prumo validate PeerReviewReport/v1`.

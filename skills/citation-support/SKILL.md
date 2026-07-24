---
name: citation-support
description: "Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated) usando os extracts do acervo — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título)."
when_to_use: |
  Quando o usuário pedir para checar se as citações de uma página/manuscrito
  sustentam as frases que as citam ("as referências batem com o que eu
  afirmo?"), ou depois de um `prumo paper verify-refs` limpo, como camada
  semântica. NÃO é para verificar existência/retração (isso é o CLI
  determinístico) nem para editar a página (proposta de prosa é o fluxo
  review-reconcile/apply).
argument-hint: "--page <page.md>"
allowed-tools: Read Glob Grep Bash(prumo paper verify-refs *)
prumo:
  version: 1.0.0
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~3-8k tokens (depende do nº de citações na página)
  inputs:
    page: required
---

# citation-support — a citação sustenta a frase?

Ataca o residual que nenhuma camada determinística alcança: **referência real
que não sustenta a afirmação** (buraco semântico da autoria original — spec da
ponte, §Camada de verificação de referências, item 4).

Regra de ouro: **este protocolo SINALIZA e para.** Nunca edita a página, nunca
propõe marca, nunca bloqueia export/apply. Se algo precisar mudar no texto, o
caminho é humano (ou o fluxo review-reconcile → `prumo write review apply`).

## Protocolo

1. **Base determinística primeiro**: rode
   `prumo paper verify-refs <pj> --page <page.md> --json`.
   - `retracted`/`doi-not-found` (errors): reporte no topo — classificação
     semântica de citação retratada/inexistente é irrelevante até o humano
     resolver o erro.
2. **Inventário**: extraia da página cada par (frase → citekeys marcadas
   `[[@key]]`/`[@key]`). Frase = sentença completa que contém a(s) marca(s).
3. **Evidência do acervo**: para cada citekey, leia
   `references/notes/<citekey>/_extract.md` (e `_meta.md` para
   título/autores/DOI). Sem extract → classifique como **Sem-extract** (não
   invente conteúdo do paper; sugira `/prumo-assist:paper-extract <citekey>`).
4. **Classifique cada par** (3 vias do spec):
   - **Fully supported** — o extract afirma o que a frase atribui.
   - **Partially supported** — direção certa, mas a frase generaliza/omite
     condição (população, magnitude, desenho do estudo).
   - **Unsubstantiated** — o extract não contém (ou contradiz) a afirmação.
   Cada veredito vem com 1 linha de justificativa + trecho literal do extract
   (ou "extract silencioso sobre isso").
5. **Relatório final** (tabela): frase (recorte) | citekey | veredito |
   justificativa. Feche com a lista de ações sugeridas AO HUMANO
   (ex.: "reescrever a frase X", "trocar a citação Y", "rodar extract de Z")
   — sem executar nenhuma.

## Limites duros

- NUNCA edite página, bib, notas ou worklist — nem "só uma vírgula".
- NUNCA conclua veredito sem extract lido; na dúvida entre Partially e
  Unsubstantiated, escolha Unsubstantiated e diga por quê (falso-negativo é
  mais barato que falso-conforto — mesmo racional fail-closed do repo).
- Citação retratada NUNCA vira "Fully supported" — erro determinístico
  primeiro, sempre.

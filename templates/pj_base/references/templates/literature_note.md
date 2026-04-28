---
# CSL-JSON subset (compatível com Pandoc, BibLib, Zotero Integration)
id: <citekey>
type: article-journal           # article-journal | paper-conference | manuscript | chapter | review
title: ""
author:
  - { family: "", given: "" }
issued: { date-parts: [[YYYY]] }
DOI: ""
container-title: ""
URL: ""

# Curadoria deste projeto
pdf: "../pdfs/<citekey>.pdf"
tags: []
role: supporting                # primary | supporting | background | replaced
status: unread                  # unread | reading | read | skimmed
rating: null                    # 1-5
added: YYYY-MM-DD
tldr: ""
cites: []
extracted_at: null              # ISO date; null = nunca extraído
extracted_model: null           # string, ex.: "claude-opus-4-7"
extracted_template_hash: null   # sha256[:12] do paper_extraction.md usado
---

> [!tldr]
> _(uma frase: o que o paper fez e resultado principal)_

## Problema

_(pergunta clínica/técnica, gap na literatura)_

## Método

_(dataset, n, modalidades, arquitetura, backbone, treino, hiperparâmetros, baselines)_

## Resultados

_(métricas principais com IC; referenciar figuras/tabelas como `Fig. 3 (p.7)`, `Table 2 (p.5)`)_

> [!quote] "trecho exato" (p. XX)

## Limitações

> [!warning]
> _(o que o paper assume, o que não testou, reproducibilidade)_

## Relevância para este projeto

_(por que entrou no acervo; o que reaproveitar — split, métrica, backbone, baseline)_

## Referências citadas

_(wikilinks para outras notas do acervo)_

- [[@citekey_outro]]

## Notas

_(observações, dúvidas abertas, ideias)_

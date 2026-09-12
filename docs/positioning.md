---
title: Posicionamento e claims do prumo-assist
tags: [positioning, claims]
---

# Posicionamento e claims

## O que o prumo é

O prumo-assist é um plugin Claude Code com um CLI Python (`prumo`) que dá ao pesquisador clínico um projeto `pj_*` versionável: bibliografia espelhada do Zotero, wiki Markdown, protocolo (PICOT) e escrita via Pandoc. Todo passo repetível roda no CLI, sem LLM ([ADR-0004](adr/adr-0004-pacote-livre-de-llm.md)). O LLM entra só onde há julgamento, e o resultado dele é rascunho ou sinal que o pesquisador decide. O prumo não escreve o paper por você, não substitui revisor, estatístico nem comitê de ética, e não é um serviço: tudo fica na máquina e no projeto. O mapa do código está em [ARCHITECTURE](../ARCHITECTURE.md).

## Mecanismos recusados

| Mecanismo | Por que não |
|---|---|
| Redação ponta a ponta sem o pesquisador | LLM só onde há julgamento humano ([[constitution#II · Determinístico antes de agêntico]]). Os modos de escrita entregam rascunho com `[REF FALTANTE]` nas lacunas, e a autoria continua sendo do pesquisador. |
| LLM julgar se a citação sustenta a frase sem ler a fonte | Um resumo gerado por LLM errado vira confirmação falsa. O `verifier` lê o PDF, e o `_extract.md` nunca é evidência ([ADR-0033](adr/adr-0033-subagents-nomeados.md)). |
| Mandar a bibliografia inteira a serviço externo | Na checagem padrão, só DOI e PMID saem da máquina. O `--deep` envia só as entradas citadas na página ([ADR-0018](adr/adr-0018-verificacao-referencias-apis-publicas.md)). |
| Simular decisão de CEP ou parecer ético | O modo `protocol cep` redige a submissão. Decidir sobre ela é do comitê, e simular o parecer seria superfície sem gatilho real ([[constitution#VI · YAGNI militante]]). |
| Memória oculta entre projetos | Trace e proveniência são locais e por projeto ([[constitution#V · Provenance em todo output]]). Cada `pj_*` carrega o próprio estado ([ADR-0022](adr/adr-0022-layout-por-escopo.md)). |
| Lint heurístico de afirmação sem citação | Testado em 2026-09-12 sobre os 11 drafts de `writing/` dos `pj_*`: 139 alertas, quase todos falsos (itens numerados, placeholders de template, frases com citação DOI/PMID em linha, reafirmação dos próprios resultados). As afirmações sem suporte que importaram no A/B não têm número nem quantificador e escapam da regra. Ruído ensina a ignorar o lint ([[constitution#VI · YAGNI militante]], [[constitution#VIII · Simplicidade é o default]]). |
| Painel de revisores multi-persona | No A/B de 2026-09-12, o painel do ARS e o `review critique` deram o mesmo veredito. O painel custou 12 chamadas e ~28,5 mil palavras, contra 1 chamada e ~2,9 mil. Ele achou lacunas reais (proveniência do instrumento, contexto regulatório), que viram checagens candidatas, não painel. Todo agent novo precisa de critério próprio ([ADR-0033](adr/adr-0033-subagents-nomeados.md)) e custa conceitos ao pesquisador ([[constitution#VIII · Simplicidade é o default]]). |

## Capacidades e claim máximo

Nível = `prumo.determinism` no frontmatter do modo. Evidência = o que existe hoje no repo. Claim máximo = o máximo que se pode afirmar sem exagerar.

### paper

| Modo | Nível | Evidência | Claim máximo |
|---|---|---|---|
| `library` | deterministic | `tests/unit/paper/test_sync.py`, `test_find.py`, `test_graph.py`, `test_connect.py`; ADR-0007, ADR-0020 | Espelha `.bib`, anotações e grafo de citação do Zotero/BBT no acervo. Não avalia a qualidade dos papers. |
| `extract` | agentic | `tests/unit/paper/test_callout.py`, `tests/unit/test_agents.py`; ADR-0033 | Callout estruturado validado em `PaperCallout/v1`, com proveniência. O conteúdo é leitura do LLM e pode errar. |
| `support` | hybrid | `tests/unit/paper/test_verify.py`, `tests/unit/test_contracts.py`; ADR-0018, ADR-0033 | Existência, retração e título são checados de forma determinística. Suporte da frase é sinal do LLM lendo o PDF, nunca veredito nem bloqueio. |

### wiki

| Modo | Nível | Evidência | Claim máximo |
|---|---|---|---|
| `ingest` | agentic | ADR-0022, ADR-0025 | Cria a nota da fonte e registra no índice e no log. O resumo é do LLM. |
| `lint` | hybrid | `tests/unit/wiki/test_lint.py`, `test_stats_check.py` | Órfãs, citekeys quebradas e links mortos são detectados por código, e porcentagens, IC de Wilson e valores q relatados são recalculados (`stat_mismatch`). Contradição e claim desatualizado são sugestões do LLM. |
| `query` | agentic | sem avaliação automatizada | Responde citando páginas e citekeys do wiki. A cobertura depende do índice qmd. Não é revisão sistemática. |
| `study` | agentic | `tests/unit/wiki/test_study.py` (só o log) | Sessão guiada ancorada nas fontes, com log. Efeito de aprendizagem não medido. |

### protocol

| Modo | Nível | Evidência | Claim máximo |
|---|---|---|---|
| `picot` | hybrid | `tests/unit/protocol/test_picot_io.py`, `test_diff.py`, `test_adr.py`, `test_drift.py` | Versiona e propaga a PICOT com diff e ADR, e o `diff` aponta drift do manuscrito contra protocolo e PICOT (janela, `n`, testes, pré-especificação). A pergunta é do pesquisador. |
| `sap` | agentic | `tests/unit/test_guidelines_present.py` (só nomeia guidelines) | Rascunho do plano de análise que referencia TRIPOD+AI, TRIPOD-LLM e CONSORT 2025. Conformidade e tamanho amostral exigem estatístico. |
| `cep` | agentic | `tests/unit/write/test_compose_refs.py` | Rascunho da submissão à Plataforma Brasil. Não prevê nem substitui o parecer do CEP. |

### write

| Modo | Nível | Evidência | Claim máximo |
|---|---|---|---|
| `manuscript`, `section` | agentic | `tests/unit/write/test_compose_*.py` | Rascunho a partir das entradas do projeto, com citekeys do acervo e `[REF FALTANTE]` nas lacunas. A verificação é do pesquisador. |
| `style` | agentic | diff de citações obrigatório no próprio modo | Reformata a prosa. O diff confere que nenhuma citação entrou ou saiu. A preservação do sentido não é verificada por máquina. |
| `disclosure` | deterministic | `tests/unit/write/test_disclosure.py`, `test_disclosure_venues.py` | Declaração derivada do `_meta` gravado, no formato de ICMJE, JAMA ou BMJ quando pedido, com a política conferida na fonte e datada. Não cobre uso de IA fora do prumo, e a política do periódico pode ter mudado desde `accessed`. |

### review

| Modo | Nível | Evidência | Claim máximo |
|---|---|---|---|
| `critique` | agentic | `tests/unit/test_contracts.py` (`PeerReviewReport/v1`, `quote` conferido); A/B de 2026-09-12 | Segunda leitura num contexto que não viu a redação, com trecho literal conferido e fontes lidas; passe adversarial só a pedido. Não substitui peer review. |
| `reconcile` | hybrid | `tests/unit/test_mcp_server.py`, `tests/unit/write/test_review_apply.py`; ADR-0016, ADR-0017 | Propõe marcas pendentes. As guardas recusam tocar citação, e a decisão é humana. |

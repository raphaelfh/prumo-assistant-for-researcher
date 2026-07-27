# ADR-0016 — CriticMarkup como representação de revisão + conservação de citações contada no OOXML

- Status: aceito
- Data: 2026-07-23
- Origem: spec "Round-trip de revisão docx ↔ CriticMarkup" (2026-07-05, aprovado); decisão (b) da Fase 0 — adeu achata campos, citação 100% OOXML próprio

## Contexto
O spec da ponte docx↔CriticMarkup (docs/superpowers/specs/2026-07-05, aprovado 2026-07-23) exige round-trip de revisão de coautores Word-cêntricos com zero erro silencioso de citação. A Fase 0 decidiu o backend (b): o adeu 1.29.0 achata campos de citação para texto de exibição em todas as saídas, então a leitura/conservação de citações é 100% OOXML próprio. Nota de numeração: o ADR-0015 (pré-1.0-patch-para-releasável) já existe em `main`, à frente do ponto de fork desta branch — a numeração 0016 segue a sequência real do repositório.

## Decisão
A camada de revisão vive inline na fonte `.md` como as cinco marcas CriticMarkup planas — `{++inserção++}`, `{--deleção--}`, `{~~velho~>novo~~}`, `{==destaque==}` e `{>>comentário<<}` — implementadas em `core/criticmarkup.py` (parse/emit/accept/reject/apply; marcas aninhadas são erro, nunca achatamento). O normalizador Obsidian→Pandoc (`core/obsidian.py`) virou motor de edits de passada única que emite, junto do texto, um span-map lossless norm↔source (`normalize_markdown_with_map`) — nunca se inverte a normalização, inverte-se o mapa. O export docx emite sidecars versionáveis em `reviews/<slug>/` (`citemap.json` + `span-map.json`, schemas Pydantic v1) com pareamento hard-fail entre as citações do texto normalizado e os campos `ADDIN ZOTERO_ITEM` lidos do OOXML do próprio docx gerado (invariantes I2/I8; `CiteMapMismatchError`). Cada campo carrega `prumoOcc` (contador por ocorrência, independente do `citationID`) e `prumoFingerprint` por chave (cadeia de prioridade: `doi:<valor>` quando o `.bib` tem DOI; senão `sha256:` de `itemID|uri` do BBT; senão `bib:` sha256 do entry cru). Os campos de citação são travados em content controls (`<w:lock w:val="sdtContentLocked"/>`, invariante I4) com guarda pós-build (`MissingFieldLockError`). A gramática de citekey é única (I7): `core/citations.py` (lançado em 0.62.1) é o único lugar do pacote que reconhece citekeys em texto — export, compose, wiki lint e paper graph consomem suas funções, e o tokenizador divergente que descartava chaves compostas foi eliminado.

## Consequências
O agente e o humano revisam sobre a mesma fonte plain-text em Git, com aceite/rejeição determinístico por marca; toda contagem de citação deriva do OOXML, nunca de texto exibido ou saída de conversor (precedente do padrão máquina-possui-região: ADR-0009). Custos: payload maior por campo no docx, sidecars adicionais por export, e dependência do shape OOXML dos campos Zotero — mitigada pelas guardas hard-fail que transformam qualquer drift silencioso em erro barulhento.

## Nota de correção (2026-07-26)

A afirmação "o tokenizador divergente que descartava chaves compostas foi
eliminado" era incompleta quando esta ADR foi aceita. O escopo declarado do
I7 cobria apenas `domains/write/compose.py`; `domains/capture/route.py:18`
manteve um segundo reconhecedor (`^@?([a-z][\w-]*\d{4}[\w-]*)$`) que rejeitava
10 de 173 citekeys de um acervo real (5%) — chave sem 4 dígitos, com inicial
maiúscula, com `.` ou `+`. Fechado no plano 2026-07-26 (Task 3): `route.py`
passa a derivar de `core.citations.CITEKEY_BODY`. A decisão desta ADR não
muda; só o registro de que o invariante ainda não estava fechado.

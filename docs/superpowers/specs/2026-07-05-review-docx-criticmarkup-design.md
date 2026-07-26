---
title: Round-trip de revisão docx ↔ CriticMarkup com garantia de integridade de citações (write review)
date: 2026-07-05
status: approved
tags: [write, review, criticmarkup, citations, zotero, docx, roundtrip, integrity, conservation, mcp, agents]
---

# Round-trip de revisão docx ↔ CriticMarkup com garantia de integridade de citações

## Resumo executivo

Coautores de manuscritos clínicos revisam no Microsoft Word (comentários + tracked changes) e o `.docx` é o formato exigido. Hoje o prumo exporta docx com campos Zotero vivos ([export.py](../../../src/prumo_assist/domains/write/export.py)) e extrai comentários de forma unidirecional ([comments.py](../../../src/prumo_assist/domains/write/comments.py)) — mas nada volta para a fonte `.md`, e nenhuma garantia protege as citações no caminho de volta.

Esta spec define o **round-trip completo**: o docx revisado volta, as mudanças dos coautores são extraídas e **transplantadas como CriticMarkup para a fonte Obsidian-flavored em Git**, um humano revisa o diff e aceita/rejeita, e a fonte limpa segue. O centro de gravidade é a **garantia de integridade de citações**: *zero erro silencioso/mecânico* — nenhuma citação pode ser removida, duplicada, movida, re-chaveada, truncada ou repontada sem (a) reprodução idêntica, (b) hard-fail antes de qualquer transplante, ou (c) decisão humana explícita registrada em Git. O *must* inegociável: **toda citação origina do Zotero** — nada nascido de texto livre, palpite de agente ou digitação de coautor vira citação.

Princípio reitor, validado em dois red-teams adversariais e uma pesquisa externa: **código garante, agente propõe, humano decide.** A conservação de citações é contada dos campos OOXML do docx que volta — nunca de markdown, texto exibido, saída de pandoc/adeu ou leitura de LLM.

Decidido após 7 workflows de investigação nesta sessão (2026-07-04/05): mapa do código (`citation-mapping-sota`), superfícies colaborativas (`collab-surface-sota`), landscape local-first (`notion-like-editors-trends`), build-vs-use (`build-vs-use-oss`), refinamento adversarial do design (`adversarial-refine-design`, 18 falhas reais adjudicadas), red-team de integridade de citação (`redteam-citation-integrity`, 15 buracos silenciosos fechados), verificação do Claude for Word + Zotero-origin (`redteam-zotero-origin`) e deep-research externo sobre integridade de referências (173 claims verificados).

## Contexto e problema

### A dor

O dono descreveu (2026-07-04): *"como organizar citações e manter mapeado para poder editar como humano e com agentes de forma dinâmica sem precisar ficar regerando o docx"*, com refinamento posterior: *"o must é sair do Zotero para evitar erro de citação errada"*. O diagnóstico separou dois loops:

- **Loop interno (autor):** falta preview vivo — **superado** (emenda 2026-07-23): resolvido fora deste repo via front Zettlr com Pandoc puro (ADR-0015 externo, 2026-07-22). Nenhum entregável de preview neste programa.
- **Loop externo (coautores):** comentam + tracked-changes no Word; o docx volta e hoje é beco sem saída. **Esta spec resolve o loop externo.**

### O que já existe no prumo (grounding verificado no código)

- Fonte de verdade: Markdown Obsidian-flavored com `[[@citekey]]`, normalizado por [core/obsidian.py](../../../src/prumo_assist/core/obsidian.py) (`normalize_markdown`: transformação lossy many-to-one, sem bookkeeping de posição — fato central para o design do transplante).
- Export docx: `--citeproc` + [zotero_live_docx.lua](../../../src/prumo_assist/_filters/zotero_live_docx.lua) embrulha cada citação em campo `ADDIN ZOTERO_ITEM CSL_CITATION`. **Bug conhecido a corrigir:** `item.id` só carrega o citekey quando o lookup BBT popula (`lua:94`); `citationID` é contador `%08d` por export.
- Validações existentes reusáveis: `scan_citekeys` (só markdown), `_assert_no_missing_citekeys`, `_docx_zotero_field_counts`, `wiki/lint` (citekey quebrado), `[REF FALTANTE]` em [compose.py](../../../src/prumo_assist/domains/write/compose.py).
- **Defeito a remover (I7):** regex de citekey divergente em `compose.py` (`_extract_citekeys_used`) trunca chaves compostas (`smith2020:aha-guideline` → `smith2020`).
- Comentários: `extract_from_docx` lê `w:ins`/`w:del`/`comments.xml` (só `w:t`, cego a campos e a deleções com track-changes desligado) → vira fallback/insumo, não o caminho principal.

### Evidência empírica (por que o rigor não é paranoia)

Deep-research verificado (2026-07-05), números-âncora:

- ChatGPT-3.5 em conteúdo médico: **47% das referências fabricadas**, 46% autênticas-mas-imprecisas, só 7% corretas. GPT-4o: 19,9% fabricadas; **~65% fabricadas-ou-erradas** no total. 13 LLMs: fabricação de **14% a 95%**.
- *Wrong-but-real* domina: entre autênticas, 93% PMID errado, 64% volume errado, 60% ano errado. **DOI não basta:** 64% dos DOIs de citações fabricadas resolvem para artigo real — errado.
- Referências erradas em papers publicados: **11–41%** mesmo sem IA.
- Tracked changes **e merge de documentos multi-autor corrompem field codes do Zotero** (relatos documentados nos fóruns Zotero).
- Pandoc **descarta silenciosamente** comentário sobre inserção rastreada (jgm/pandoc#9833); round-trip docx→json→docx corrompe o arquivo. Nunca confiar no round-trip: **re-ler o OOXML**.
- Claude for Word lê só **conteúdo** (nunca field codes; payload Zotero mora em propriedade `data` escondida do campo ADDIN); custom connectors são cloud-only (localhost inacessível); `word-mcp` é Windows-only. **Nenhum LLM-leitor pode ser fonte de verdade de citação.**

## Decisões travadas com o dono

1. **Superfície dos coautores = Word puro** (docx exigido; comentam + tracked-changes). Superfícies alternativas (MyST Editor self-host, Obsidian+Commentator, HackMD) avaliadas e adiadas — CriticMarkup é o substrato agnóstico que serve a todas depois.
2. **CriticMarkup é o invariante; editor é commodity.** A representação de revisão vive no `.md`, versiona em Git, agente lê/aplica.
3. **Must Zotero-origin:** citação só nasce/muda por item Zotero real selecionado por humano. Agente **nunca** cunha citekey.
4. **Garantia = zero erro silencioso** (não zero absoluto): erro mecânico é eliminado fail-closed; julgamento científico é escalado com metadados completos, nunca decidido pelo sistema.
5. **Build-vs-use por camada:** `adeu` usar-direto via `uvx` (extração docx↔CriticMarkup); `core/criticmarkup.py` nosso (~150 linhas; pancritic é GPLv3); transplante nosso (nenhum OSS faz); editor futuro = referenciar plugins Obsidian, não adotar app.
6. **Claude for Word fora do caminho crítico** (conforto opcional para triagem/resumo); leitor de citação = o próprio prumo parseando OOXML (cross-platform, macOS ok).
7. **Camada de verificação de referências** incorporada como fase própria (RefChecker, Retraction Watch, resolução DOI/PMID, classificação citação-suporte).
8. **MVP = página única** (`export()`); multi-página (`compose()`) fica para spec futura.

## Alternativas avaliadas e descartadas

| Alternativa | Por que caiu (fato verificado) |
|---|---|
| Fidus Writer | melhor UX turnkey, mas verdade em DB — agente não co-edita a fonte |
| Tiptap Tracked Changes | canônico é ProseMirror/Yjs; markdown é export lossy; features pagas |
| HackMD | comentários/sugestões ficam fora do Git; SaaS |
| tolaria | files-first/agent-native exemplar, mas **zero camada de revisão** e sem plugin system |
| MyST Editor (antmicro) | única opção plain-text com review completo, mas exige hospedar editor+servidor; adiada, não descartada |
| Claude for Word como leitor/escritor | não vê field codes; sem write-back local; word-mcp Windows-only |
| redoc (R) | faz o transplante exato mas é R-only — referência conceitual |
| pancritic | escopo certo (accept/reject) mas GPLv3 e sem ingest docx — portar lógica, não depender |
| Obsidian + Commentator | encaixe ideal futuro, mas beta com risco documentado de perda de dados |

## Arquitetura

### Componentes e papéis

- **Zotero / Better BibTeX** — origem única de toda referência (`references/_references.bib` + BBT JSON-RPC em `127.0.0.1:23119`). Keys sempre pinadas (Zotero 9+ — par suportado detectado por `prumo doctor` desde a Fase 1 do zero-friction; emenda 2026-07-23).
- **prumo (guardião + leitor)** — a única coisa que escreve citação na fonte; parseia OOXML diretamente; impõe as invariantes I1–I8 em código determinístico.
- **Agente reconciliador** — resolve o resíduo ambíguo propondo eventos estruturados; invocado via prumo-MCP local (stdio, Claude Code/Desktop — Fase 3). Propõe; nunca cunha.
- **Fonte `.md` em Git** — verdade do manuscrito; CriticMarkup como camada de revisão inline; sidecars versionados.
- **Coautores** — Word puro, zero dependência instalada.

### Fluxo end-to-end

```
0. autor escreve [[@citekey]] na fonte .md          (nascimento Zotero-origin)
1. prumo write export --docx                        (campos travados + citemap + span-map @ SHA)
2. coautores revisam no Word                        (keep / deletar-campo / comentar / pedir em prosa)
   → reviewed.docx volta
3. prumo write review ingest reviewed.docx
   3a. preflight: backend pinado no PATH; fonte inalterada desde o SHA do export
   3b. extração de marcas (adeu; peer pandoc --track-changes=all)
   3c. GUARDA A: mudança estrutural (tabela/nota/equação) → HARD-FAIL nomeando regiões
   3d. GUARDA C: sobrevivência dos campos ZOTERO_ITEM → HARD-FAIL se achatados
   3e. conservação: S_depois (contado do OOXML) == S_antes (citemap) + ΔE → HARD-FAIL se não fecha
   3f. detecção mover/reescrever (pareia del/ins por similaridade de tokens)
   3g. classificação: prosa-pura-âncora-única → transplante determinístico via span-map;
       citação/seam/move/cluster → evento estruturado p/ reconciliador
   3h. escreve CriticMarkup na cópia de revisão (branch) + review-comments.yaml
4. portão humano: diff no branch; toda citação tocada exibe metadados Zotero completos;
   add/replace exige seleção de item no Zotero (atestação em Git)
5. prumo write review apply: GUARDA B (mark-count: toda marca pousou → senão HARD-FAIL);
   accept/reject por marca/autor/em massa → fonte limpa; bibliografia regenerada; commit
```

## O substrato CriticMarkup

### `core/criticmarkup.py` (novo, ~150 linhas)

Parse/emit/accept/reject das 5 marcas: `{++ins++}`, `{--del--}`, `{~~a~>b~~}`, `{==destaque==}`, `{>>comentário<<}`. Nível-formato, sem import de domínio (layering). Regras do refinamento adversarial:

- **Coalescing guardado:** del+ins adjacentes só viram `{~~a~>b~~}` quando ambos os lados são prosa pura, contíguos, sem âncora imóvel entre eles. Caso contrário, `{--del--}` + `{++ins++}` separados (sempre rejeitáveis limpo). Nenhuma substituição pode atravessar átomo de citação/wikilink/callout.
- **Marcas planas, nunca sobrepostas:** clusters de sobreposição são resolvidos ANTES (evento único para o reconciliador); o parser só vê marcas planas — cluster não-serializável é erro, não achatamento lossy.

### Comentários: âncora inline + sidecar versionado

`{>>...<<}` puro não tem autor/data/range/thread. Decisão: âncoras inline `{>>cid:ID<<}` pareadas ao redor do span mapeado + `review-comments.yaml` (Git) com `{id, author, date, text, reply_of, range}`. Filtros por autor/data operam no sidecar. Threads (w15 `paraId`) ficam como interino documentado: comentários ponto-ancorados, não-encadeados, no MVP.

## Export instrumentado

1. **span-map:** `normalize_markdown` passa a emitir, junto do texto normalizado, um mapa lossless de fragmentos `(source_start, source_end, norm_start, norm_end, kind)` com âncoras de largura-zero para construções que colapsam (header de callout, block-id, alias descartado). Sidecar JSON. **Não se inverte a função** — inverte-se o mapa.
2. **Fix do lua:** `item.id` SEMPRE carrega o citekey (id numérico do Zotero migra para `zoteroItemID`); o payload do campo ganha `occ_id` imutável por ocorrência + fingerprint por chave (`DOI` ou `sha256(itemID|libraryID|URI)`).
3. **`citemap.json` (S_antes):** `citationID → {citekeys[], occ_id, fingerprint, formattedCitation, norm_offset_range}` + hash dos bytes exatos de `_references.bib` + SHA do commit do export + hash de conteúdo do docx gerado (I8).
4. **Campos travados:** content controls read-only — coautor não redigita citação; só deleta o campo inteiro (evento drop limpo) ou comenta.
5. **Sidecars versionados** em `reviews/<slug>/` no projeto consumidor (não `build/`, que é descartável): citemap, span-map, review-comments.yaml, eventos e atestações. Schemas Pydantic versionados em `domains/write/schemas/` (forward-only).

## Invariantes de integridade de citação (I1–I8)

Endurecidas por red-team (24 ataques, 15 buracos silenciosos fechados):

- **I1 — ATOM:** citação é token opaco chaveado por citekey; nunca texto editável, nunca fuzzy-match. Edição que encosta em átomo vai INTEIRA ao reconciliador como evento (keep/drop/replace/add-request/comment). Prosa em forma de citação NUNCA é auto-promovida a átomo.
- **I2 — CONSERVAÇÃO (fail-closed):** `S_depois` deriva SÓ do OOXML do docx que volta (decodificar cada `w:instrText` com `ADDIN ZOTERO_ITEM CSL_CITATION` → multiconjunto de ocorrências). Nunca de markdown, `w:t`, pandoc/adeu ou resumo de LLM. `S_depois == S_antes + ΔE`, onde ΔE nasce só de eventos humanos aprovados (nunca retro-resolvido do diff). Vale também para tupla completa (locator, prefix, suffix, suppress-author). Campo ausente do XML = chave ausente → qualquer delete (mesmo com track-changes OFF), achatamento ou truncamento dispara o gate.
- **I2b — OCC-ID + integridade de campo:** `occ_id` imutável por ocorrência; conjunto observado == S_antes + adds − drops aprovados. `occ_id` duplicado (paste-clone) ou fldChar desbalanceado (campo colapsado) → HARD-FAIL.
- **I2c — MOVE acoplado:** deleção-de-átomo pareada com inserção da mesma chave no mesmo round = UM evento MOVE atômico (aprovar só uma perna é impossível). Campo com run tocado por `w:del`/`w:ins` = CITATION-TOUCHED → decisão humana obrigatória; instrText nunca auto-confiado.
- **I3 — EXISTÊNCIA + identidade:** toda chave resolve no BBT E no `.bib` local; fingerprint recomputado no ingest deve bater com o do export; hash do `.bib` deve bater. BBT offline + hash divergente → HARD-FAIL (nunca degrada para lookup em bib velho). Agente nunca cunha chave.
- **I3b — VÍNCULO SEMÂNTICO atestado:** citekey entra para `[REF FALTANTE]`/replace/add SÓ por seleção humana de item específico, com metadados completos exibidos (título/journal/ano/DOI — nunca só "(Autor, Ano)"), registrada como atestação em Git.
- **I4 — READ-ONLY:** campo travado por content control; coautor não redigita — só comenta ou deleta o campo inteiro.
- **I5 — BIB REGENERADA:** lista de referências é função pura de (chaves usadas × bib × CSL); nunca editada ou transplantada.
- **I6 — PROVENIÊNCIA:** todo evento de citação (quem/o quê/quando), resolução de placeholder e atestação em Git; revisável e reversível.
- **I7 — GRAMÁTICA ÚNICA:** um único regex de citekey (`_CITEKEY_RE` de export.py) em todo o código; deletar o tokenizador divergente de compose.py.
- **I8 — LINKAGE docx↔citemap:** citemap amarrado ao docx por hash de conteúdo; docx que volta sem os fingerprints da sessão contra citemap não-vazio → HARD-FAIL (documento trocado/campos removidos).

### Guardas hard-fail (perda silenciosa → erro barulhento)

- **Guarda A (estrutural):** mudança rastreada/comentário dentro de `w:tbl`, `footnotes.xml` ou `m:oMath` → HARD-FAIL nomeando cada região com instrução de correção (mensagem pt-BR, comando embutido). Nunca prossegue parcial.
- **Guarda B (mark-count):** toda marca extraída TEM que pousar na fonte; marca perdida → HARD-FAIL (backstop inclusive para contêineres exóticos que a Guarda A não reconheça).
- **Guarda C (sobrevivência de campo):** reusa `_docx_zotero_field_counts`; docx com citações que perdeu campos `ZOTERO_ITEM` na extração → HARD-FAIL.

## Ingest e transplante

- **Extração:** `adeu` (Python/MIT, PyPI, bidirecional docx↔CriticMarkup) como backend **pinado e golden-testado**, invocado via `uvx adeu==<versão>` (ambiente isolado — prumo é ≥3.11, adeu pede ≥3.12; não importar o SDK). Peer: `pandoc --track-changes=all` (só prosa, nunca citações). Fixture-ouro no CI trava drift de versão. **Condicional à Fase 0** (spike: adeu preserva `instrText`? — se achatar, extração de citação é 100% OOXML próprio via `zipfile`/`python-docx`).
- **Transplante determinístico (auto-apply):** só quando a marca (i) inverte para offset único dentro de UM fragmento `kind=identity` E (ii) tem zero sobreposição/adjacência com átomo (citação/wikilink/callout/embed/block-id), linha deletada ou seam. Inserções ancoradas por token sobrevivente dos DOIS lados, no mesmo bloco estrutural.
- **Mover vs reescrever:** pareamento del/ins por `difflib.SequenceMatcher`; alta similaridade = MOVE (reloca o span-fonte verbatim, com `[[@key]]`/wikilink intactos, aplicando só o diff interno); baixa/ambígua = reconciliador.
- **Reconciliador (Fase 3):** recebe eventos tipados (clusters, citation-touched, seams, moves ambíguos) e propõe colocações que o humano revê como diff. Invocação via prumo-MCP local. **Modo degradado sem agente:** eventos ambíguos viram checklist para resolução manual — o pipeline nunca depende do agente para ser correto, só para ser conveniente.
- **Deriva de fonte:** sidecar carimbado com SHA do export; fonte editada entre export e ingest → offsets derivados são roteados ao reconciliador, nunca confiados.
- **Idempotência/multi-coautor:** MVP processa um `reviewed.docx` por rodada, sequencialmente; re-ingest do mesmo docx é detectado pelo hash (I8). Merge simultâneo de múltiplos docx revisados fica fora do MVP.

## Camada de verificação de referências (Fase 4)

Determinística-primeiro, LLM só sinaliza:

1. **RefChecker** (`pip academic-refchecker`): valida cada referência contra Semantic Scholar, OpenAlex, CrossRef, DBLP, ACL; filtros determinísticos (não-verificada, author-overlap <60%, conflito de identificador, URL falha) antes de qualquer LLM.
2. **Retraction Watch via Zotero** (nativo, já disponível): aviso ao citar item retratado.
3. **Resolução determinística DOI/PMID/arXiv** por API + cache local de retratações.
4. **Classificação citação-suporte** (LLM, 3 vias: Fully/Partially/Unsubstantiated): sinaliza o residual "referência real que não sustenta a frase" — único mecanismo que ataca o buraco semântico da autoria original. Sinaliza; nunca bloqueia sozinho.

## CLI (fachadas finas, `cli_run`, saída via `Console`)

- `prumo write export --docx` — existente; passa a emitir sidecars e campos instrumentados.
- `prumo write review ingest <reviewed.docx>` — extração + guardas + transplante + cópia de revisão em branch.
- `prumo write review apply [--accept-all | --by-author <a> | --mark <id> --accept/--reject]` — aplica, recheca mark-count, regenera bib.
- `prumo write preview` — **superado** (emenda 2026-07-23): loop interno resolvido via front Zettlr (ADR-0015 externo); sem plano próprio.

## Fases e fronteiras de release

| Fase | Entrega | Fronteira |
|---|---|---|
| **0 — spike** | valida se adeu preserva `instrText`; fix do lua (`item.id`=citekey); decide backend de extração | sem release |
| **1 — substrato** | `core/criticmarkup.py`; span-map no normalize; citemap/occ_id/fingerprint no export; campos travados; I7 (regex único) | MINOR (export ganha sidecars) |
| **2 — ponte docx (MVP)** | `review ingest` + guardas A/B/C + conservação + transplante determinístico + portão humano + `review apply` | MINOR (comandos novos) |
| **3 — agente** | prumo-MCP local (stdio) + reconciliador para o resíduo | MINOR |
| **4 — verificação** | RefChecker + retração + DOI + citação-suporte | MINOR |
| ~~paralelo~~ | ~~`prumo write preview`~~ — superado (Zettlr/ADR-0015 externo; emenda 2026-07-23) | — |

Cada fase segue brainstorm → spec (esta) → plan → TDD; plano implementado arquiva com `status: implemented`.

## Riscos residuais (registro honesto)

| Risco | Sev. | Mitigação |
|---|---|---|
| Link errado-mas-real da autoria original (chave real, estudo errado para a frase) | alta | irredutível por design; portão exibe metadados completos; classificador citação-suporte (F4) sinaliza; promessa é "nenhum erro NOVO silencioso" |
| adeu achatar campo `ZOTERO_ITEM` na extração | alta | Fase 0 decide; extração de citação pode ser 100% OOXML próprio; Guarda C pega em runtime |
| Reconciliador errar sob fadiga humana (carimbar sem ler) | alta→média | propostas sempre rejeitáveis limpo; volume do portão minimizado (só átomo tocado/ambíguo); atestação atribuível e reversível em Git |
| Contêiner exótico escapar da Guarda A | alta→média | Guarda B (mark-count) é backstop independente de reconhecimento de contêiner |
| Fonte editada entre export e ingest (drift de offsets) | média | SHA no sidecar; offsets derivados → reconciliador; disciplina documentada |
| Duas citações idênticas da mesma chave, drop na ocorrência errada | média | occ_id distingue; ambiguidade residual vira proposta com as duas candidatas |
| Grupo multi-chave `[@a; @b]` com strike parcial | baixa | grupo inteiro → reconciliador com todas as chaves candidatas; sem sub-atribuição por sub-span no MVP |
| Zotero offline + re-key ao vivo com `.bib` inalterado | média | hash do `.bib` pega drift do arquivo; re-validação plena quando BBT online; documentado |
| Wikilink com alias editado degrada para prosa | baixa | aceito; visível no diff; re-wikificação é preocupação da wiki, não do transplante |

## Fora de escopo (specs futuras)

- Round-trip **multi-página** (`compose()` — exige proveniência "de qual arquivo veio este span").
- Renderização de CriticMarkup no preview/export.
- Superfícies de editor vivo (MyST Editor self-host; Obsidian+Commentator quando maduro) — o substrato CriticMarkup já as serve.
- Merge simultâneo de múltiplos docx revisados.
- Threads de comentário (w15 `paraId`) — interino: ponto-ancorado, não-encadeado.

## Perguntas abertas (resolvidas na Fase 0 / plan)

1. adeu preserva `instrText` através da extração com tracked-changes? (decide o backend de citação)
2. Como partir uma marca que cruza fronteira prosa↔citação no limite do campo, mostrando ao humano como unidade única?
3. Forma exata do travamento visível ao coautor: content control vs bookmark — qual sobrevive melhor ao round-trip sem ser editável?
4. Localização final dos sidecars (`reviews/<slug>/`) confirma com o layout dos projetos `pj_*`?

## Estratégia de testes

- Espelha o layout (`tests/unit/write/test_review.py`, `tests/unit/core/test_criticmarkup.py`); dependências externas mockadas nos seams (adeu/pandoc via subprocess seam; BBT via `PRUMO_ZOTERO_BASE`).
- **Cada hard-fail é um teste que prova que dispara:** fixtures docx com (a) citação+nota+tabela+equação (Guarda A), (b) deleção de frase com citação com track-changes OFF (I2), (c) paste-clone de campo (I2b), (d) fldChar desbalanceado (I2b), (e) move de parágrafo com citação (I2c), (f) strike parcial em grupo multi-chave, (g) comentário sobre inserção (#9833), (h) docx trocado (I8).
- Fixture-ouro do adeu no CI (trava drift de versão do backend pinado).
- Conservação testada como propriedade: para todo script de edição das fixtures, `S_depois == S_antes + ΔE` ou o run falha.

## Critérios de sucesso

1. Um `reviewed.docx` real de coautor entra e sai como CriticMarkup na fonte com **zero perda silenciosa de citação** (provado pelas fixtures).
2. Toda marca extraída pousa na fonte ou o run falha nomeando-a.
3. Nenhum caminho de código permite citekey não-resolvido no Zotero entrar na fonte.
4. O portão humano exibe metadados Zotero completos para toda citação tocada.
5. `uv run pytest`, `ruff`, `mypy --strict` verdes; mensagens de erro em pt-BR com comando de correção embutido.

## Governança

- **ADR novo** (decisão estrutural, MADR minimal, próximo número livre): "CriticMarkup como representação de revisão + conservação de citações contada no OOXML" — escrito na Fase 1, referenciando ADR-0009 (blocos delimitados) como precedente do padrão máquina-possui-região.
- Layering respeitado: `core/criticmarkup.py` sem imports de domínio; `write/review.py` importa core; schemas versionados forward-only em `domains/write/schemas/`.
- Versionamento conforme RELEASING.md: fases 1–4 são MINOR (invocável novo); esta spec em `docs/` não bumpa versão.
- **Revisão do dono:** 2026-07-23 — aprovado com 2 emendas editoriais (preview superado via Zettlr/ADR-0015 externo; Zotero 8→9+). Abre o gate da Fase 3 do guarda-chuva zero-friction ([[2026-07-22-zero-friction-onboarding-design]]).

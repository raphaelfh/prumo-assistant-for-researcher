# ADR-0016 — CriticMarkup como representação de revisão + conservação de citações contada no OOXML

- Status: aceito
- Data: 2026-07-23
- Origem: spec "Round-trip de revisão docx ↔ CriticMarkup" (2026-07-05, aprovado); decisão (b) da Fase 0 — adeu achata campos, citação 100% OOXML próprio

## Contexto

O spec da ponte docx ↔ CriticMarkup (2026-07-05) define o round-trip completo de revisão: coautores revisam no Word, o docx volta com comentários e tracked-changes, e as mudanças são extraídas para a fonte Markdown como **CriticMarkup** — permitindo que um humano revise o diff em Git e aceite/rejeita via agente.

O requisito inegociável é a **garantia de integridade de citações**: zero erro silencioso/mecânico. Toda citação deve ser contada a partir do OOXML do docx que volta (campos `ADDIN ZOTERO_ITEM` capturados em export), nunca de Markdown puro ou saída de Pandoc. Decisão crítica adotada no red-team adversarial (2026-07-05): **código garante, agente propõe, humano decide.**

## Decisão

A Fase 1 do substrato estabelece:

1. **CriticMarkup como invariante de revisão:** as 5 marcas de revisão (`{++...++}`, `{--...--}`, `{>>...<<}`, `{~~...~>...~}`, `{%%...%%}`) vivem em texto plano na fonte `.md` versiona em Git. Implementação em `core/criticmarkup.py` (~180 linhas): parsing canônico, operações accept/reject/apply determinísticas, tipagem estrita.

2. **Normalização lossless com span-map:** `normalize_markdown_with_map` produz um `span-map.json` sidecar que indexa cada caractere da prosa normalizada de volta à posição no original — permitindo que alterações no docx sejam transpostas com precisão pixel-perfect ao `.md`, sem perda de posição de citação.

3. **Citemap no export como contrato:** ao exportar `.docx`, o `export.py` gera um `citemap.json` sidecar registrando (posição no docx, citekey, fingerprint do item Zotero, occ_id). Esse mapa é a verdade de "quantas citações havia antes" — hard-fail I2/I8 se o docx que volta tiver contagem diferente.

4. **Campos de citação travados (`sdtContentLocked`, I4):** cada campo Zotero no docx sai com `sdtContentLocked=1`, impingindo o travamento nativo do Word — coautores veem `[[@key]]` mas não podem editá-lo diretamente (edição requer untrack/aceitar no prumo).

5. **Gramática única de citekey (I7):** regex `CITEKEY_BODY` unificada em `core/obsidian.py` e reusada em `core/criticmarkup.py`. Chaves compostas (`[[@smith2020:aha-guideline]]`) agora resolvem corretamente — o bug anterior de truncagem em `compose.py` (`_extract_citekeys_used`) é eliminado.

## Consequências

**Positivas:**
- Sidecars (`reviews/<slug>/{citemap,span-map}.json`) são versionáveis e verificáveis em Git — cada review é auditável.
- Precisão de pareamento del/ins preservada ao transpor para Markdown.
- Nenhuma citação pode ser removida, repontada ou reescrita sem registro explícito em CriticMarkup + metadados Zotero visíveis no diff.

**Custos:**
- Payload do docx aumenta com os sidecars (~50–500 bytes por citação; review de ~50 citações = ~25 KB);
- Dependência crítica do shape do OOXML (se Pandoc/adeu mudarem formato de field codes, precisará revisão);
- Sidecars precisam ser distribuídos junto do docx revisado (conveção: `reviews/<slug>/`);
- CriticMarkup não é markdown puro — ferramentas que não conhecem a gramática verão `{++...++}` como literal.

**Precedente:**
- [ADR-0009](adr-0009-blocos-delimitados.md) formalizou o padrão "máquina-possui-região" em comentários HTML. Esta decisão estende o princípio: CriticMarkup é a região machine-owned da revisão, marcada em texto plano em vez de comentário HTML — permitindo que a máquina reescreva apenas dentro da marca de revisão, e o humano dirija aceitar/rejeitar via `core/criticmarkup.py:apply()`.

---
title: Zero-friction onboarding — superfície Desktop/Cowork, export confiável e colapso da cadeia de instalação
date: 2026-07-22
status: approved
tags: [friction, onboarding, distribution, desktop, cowork, docx, doctor, mcpb, zotero, golden-path]
---

# Zero-friction onboarding — do terminal do dev ao colega pesquisador sem terminal

## Resumo executivo

O prumo-assist funciona hoje para quem vive no terminal. Para a persona-alvo deste ciclo — **colega pesquisador próximo, plano Claude pago, sem terminal** — a cadeia de uso exige ~7 passos e 4 gerenciadores de pacote distintos, o que mata a adoção antes do primeiro output. Este spec é um **guarda-chuva faseado** (padrão D3 do spec researcher-pipeline: uma spec, um plano por fase) que reduz essa cadeia ao mínimo viável, em 6 fases gated por trigger YAGNI.

A fricção tem **duas pontas com soluções distintas**: o **pesquisador** (instala o stack; alvo: primeiro output em ≤15 min sem terminal) e o **coautor** (nunca instala nada; a interface dele é o docx — coberta pela ponte docx↔CriticMarkup, absorvida aqui como Fase 3).

Fundamento: duas rodadas de deep research com verificação adversarial (3 verificadores independentes por claim), snapshot de 2026-07-22 — 48 claims confirmados, 2 refutados (ver "Fundamentos de pesquisa"). O achado central: a Anthropic tirou plugins/skills/MCP do terminal — o `marketplace.json` que o prumo já publica sincroniza **in-app** no claude.ai, no Claude Desktop e no Claude Cowork, por URL de repositório GitHub, sem CLI. A superfície que maximiza alcance ao pesquisador não-programador é **Desktop/Cowork**, não o terminal nem um app próprio.

Sequência: **validar → confiar → alcançar → coautor → colapsar** — spike empírico primeiro (fase mais barata falsifica premissas), depois confiabilidade do export docx (nunca prometer simplicidade entregando arquivo corrompido intermitente), depois o golden path, depois a ponte do coautor, e por fim colapso de dependências e empacotamento do CLI, ambos gated por dor real observada.

## Contexto e problema

### A cadeia de instalação hoje (7 passos, 4 gerenciadores)

1. Claude Code no terminal;
2. `/plugin marketplace add raphaelfh/prumo-assist` + `/plugin install`;
3. CLI via `uv tool install git+https://github.com/raphaelfh/prumo-assist` (requer uv);
4. qmd via `bun install -g @tobilu/qmd` (requer bun);
5. Zotero 9 + Better BibTeX rodando (API local em `127.0.0.1:23119`);
6. Obsidian (opcional, wiki);
7. estrutura `pj_*` scaffoldada.

Cada passo usa um mecanismo diferente (plugin marketplace, uv, bun, XPI do Zotero). A pesquisa anterior (rodada 1) já havia verificado que a barreira principal de pesquisadores a workflows Claude+MCP é exatamente essa: configurar excede o conforto técnico da maioria — e que há demanda por plugins pré-empacotados.

### As duas pontas da fricção

- **Pesquisador (dono do projeto):** é o único que precisa do stack. Alvo deste spec.
- **Coautor clínico:** Word-cêntrico, nunca instala nada. A interface dele é o docx com citações vivas + comentários/tracked changes — o round-trip é o programa do spec [2026-07-05-review-docx-criticmarkup-design.md](2026-07-05-review-docx-criticmarkup-design.md), absorvido aqui como Fase 3.

### Fundamentos de pesquisa (verificados 2026-07-22, 3 votos adversariais por claim)

Claims confirmados que sustentam as decisões (fontes primárias):

- **Plugins fora do terminal:** instalam-se e usam-se no chat do claude.ai, na aba Chat do Claude Desktop e no Cowork; marketplace sincroniza de URL GitHub in-app ("Add from a repository") — [support.claude.com art. 13837440](https://support.claude.com/en/articles/13837440-use-plugins-in-claude). Exige plano pago; hooks/sub-agents só no Cowork; research preview.
- **MCP local em plugin roda na máquina do usuário** (alcança o Zotero em localhost) — mesma fonte. Cowork tem acesso folder-scoped (o diretório `pj_*` funciona como pasta designada).
- **Agent Skills é padrão aberto multi-host** (18/12/2025, [agentskills.io](https://agentskills.io), 40+ hosts) — mas no claude.ai as skills rodam em sandbox **sem** filesystem/binários locais: a lógica dependente de CLI/Zotero/qmd exige Desktop/Cowork.
- **MCPB** (`.mcpb`, ex-`.dxt`) dá instalação one-click de MCP local no Claude Desktop; o Desktop **embute Node.js e não embute Python**; o spec MCPB recomenda Node — [anthropic.com/engineering/desktop-extensions](https://www.anthropic.com/engineering/desktop-extensions), [modelcontextprotocol/mcpb](https://github.com/modelcontextprotocol/mcpb).
- **Pipeline docx vivo tem defeito documentado pelos próprios docs do BBT:** o Word às vezes acusa o arquivo como corrompido; re-rodar o pandoc sem mudanças conserta — [retorque.re/zotero-better-bibtex/exporting/pandoc](https://retorque.re/zotero-better-bibtex/exporting/pandoc/). Primeira abertura exige passo manual no Word (document preferences do Zotero), senão um popup por citação.
- **Zotero+BBT vivos e acelerando:** Zotero em ciclo de release de ~6–10 semanas (9.0.6 em jul/2026); BBT v9.0.47 em 20/07/2026, múltiplos releases por semana. Riscos: bus-factor 1 no BBT (>99,5% dos commits de um mantenedor, doação-funded) e churn (BBT derruba Zotero antigo; Zotero 7 morto).
- **Typst segue PDF-first sem rota docx** (0.14→0.15, jun/2026); **Quarto manuscripts** cobre docx mas web-first e com citações **estáticas**. Nenhum substitui o pipeline de citações vivas.
- **Ponte Zotero de fricção quase zero já provada por terceiros:** [cookjohn/zotero-mcp](https://github.com/cookjohn/zotero-mcp) embute o servidor MCP dentro do Zotero via `.xpi` one-click (Tools → Add-ons).
- **Marketplaces curados por domínio existem** (Knowledge Work, [Life Sciences](https://github.com/anthropics/life-sciences), Financial, Legal) — gated, sem rota de self-publish comprovada.

Claims **REFUTADOS (0-3)** — não afirmar em docs nem em decisões:

1. ~~`zotero.lua` é feature oficialmente suportada do BBT~~ — é *documentado*, não *garantido*. Consequência: tratar como dependência vigiada; validação+retry no export são obrigatórios (D2).
2. ~~Bundles MCPB Python têm limitação dura específica com dependências compiladas (pydantic)~~ — o detalhe não se sustentou; permanece verdadeira apenas a assimetria geral Node/Python.

## Decisões travadas

- **D0 — Superfície-alvo = Claude Desktop/Cowork.** O golden path do pesquisador não-programador usa o **mesmo** `marketplace.json` atual, sincronizado in-app por URL. O terminal (Claude Code) continua sendo a trilha dev, documentada em paralelo. Isto **não** é multi-host: Desktop/Cowork/claude.ai são o mesmo sistema de plugin Claude — o deferral "sem multi-host" do ADR-0011 permanece intacto (Cursor/Codex/Gemini seguem fora, trigger inalterado).
- **D1 — Modo degradado fail-closed + instalação guiada.** Com dependência ausente (CLI `prumo`, Zotero, qmd): operações **exatas** (citekey, contagem, export, hash) recusam com mensagem contendo o comando de correção — nunca simuladas pelo agente (Princípio II literal). A skill oferece **instalar na hora, com consentimento explícito**, dentro da conversa (o Cowork executa comandos na pasta designada). Skills de **julgamento puro** (peer-review, scientific-writing) funcionam sem CLI — é o gancho de time-to-first-value. O contrato de preflight é uniforme entre skills e vira ADR no plan da Fase 2.
- **D2 — docx-first via Pandoc, mantido e endurecido.** Verificado: nenhuma alternativa cobre citações vivas (Typst sem docx; Quarto estático). Como `zotero.lua` não é garantido (refutado) e o defeito de corrupção intermitente é documentado, o export ganha **validação estrutural + retry automático + hard-fail** (Fase 1) — estendendo a checagem de campos que já existe (`_docx_zotero_field_counts`, `domains/write/export.py`).
- **D3 — Zotero+BBT mantidos com gestão de risco explícita.** `doctor` passa a detectar versão do Zotero/BBT e o par suportado (pin Zotero 9+), com comando de correção na mensagem (regra da casa). Bus-factor 1 do BBT registrado como risco. O campo nativo de citation key do Zotero 8+ fica **monitorado** como rota futura de desacoplamento (pergunta aberta; nenhum trabalho agora — Princípio VI).
- **D4 — Guarda-chuva com fases gated por trigger.** Cada fase vira um plano próprio em `docs/superpowers/plans/`; Fases 4–5 só começam quando o trigger citado disparar (padrão de deferral do ADR-0011). Promover fase sem trigger é violação do Princípio VI.
- **D5 — Ponte docx↔CriticMarkup absorvida como Fase 3.** O design detalhado (invariantes I1–I8, guardas hard-fail, span-map, fases próprias 0–4) é o spec 2026-07-05 — **referenciado, não duplicado**. Este guarda-chuva só posiciona a ponte na sequência e no orçamento de fricção do coautor.
- **D6 — Preview fora do escopo.** O preview vivo foi resolvido fora deste repo (front Zettlr, Pandoc puro, decisão de 2026-07-22 registrada no índice de memória do dono como ADR-0015 externo). Este spec não inclui trabalho de preview. Guarda: se a decisão externa tocar o export do prumo (ex.: flags do Pandoc), reconciliar no plan da Fase 1.
- **D7 — Fora do escopo deste spec:** submissão ao marketplace comunitário da Anthropic e publicação no JOSS (ações de distribuição sem engenharia — vivem no ROADMAP; JOSS elegível ~22/10/2026, 6 meses do primeiro commit público); multi-host real; qualquer superfície SaaS/hospedada; marketplace Life Sciences (gated — vira pergunta aberta, não fase).

## Fases e fronteiras de release

| Fase | Entrega | Release | Trigger de início |
|---|---|---|---|
| 0 | Spike de validação empírica no Desktop/Cowork | não-releasável | imediato |
| 1 | Confiabilidade do export docx + doctor de versões | PATCH | imediato (independe da 0) |
| 2 | Golden path Desktop/Cowork + modo degradado | MINOR | Fase 0 concluída |
| 3 | Ponte docx↔CriticMarkup (sub-programa) | conforme spec da ponte | revisão do dono no spec 2026-07-05 |
| 4 | Colapso de dependências (qmd→MCPB; Zotero→`.xpi`) | MINOR | bloqueio real no piloto da Fase 2 |
| 5 | Empacotamento do CLI Python | a definir no plan | colega travado apesar da instalação guiada; ou modo `uv` do MCPB amadurecer |

### Fase 0 — Spike de validação empírica (sem código)

Com a conta do dono (plano pago), no Claude Desktop e no Cowork: adicionar o marketplace `raphaelfh/prumo-assist` in-app por URL; inventariar **o que carrega e o que quebra** — quais skills aparecem, o que acontece ao invocar skill dependente de CLI/Zotero/qmd sem nada instalado, se o MCP `qmd` declarado em `.mcp.json` tenta subir, como o Cowork se comporta com uma pasta `pj_*` real. Capturar telas/transcrições para os docs da Fase 2. **Saída:** evidência registrada no próprio plano da Fase 0 (seção de verificação, lifecycle da casa), consumida pelo plan da Fase 2. A fase é manual por natureza (exige conta paga e UI) — o resultado é evidência registrada, não teste automatizado.

### Fase 1 — Confiabilidade do export docx + doctor de versões (PATCH)

1. **Validação estrutural do docx gerado:** abrir o zip, validar `[Content_Types].xml` e partes obrigatórias, e conferir contagem de campos `ADDIN ZOTERO_ITEM` (estende `_docx_zotero_field_counts`).
2. **Retry automático:** em falha de validação, re-executar o pandoc uma vez (o defeito documentado é intermitente e determinístico no re-run); persistindo, **hard-fail** com mensagem e comando de correção — nunca entregar arquivo suspeito silenciosamente.
3. **Guia de primeira abertura no Word:** instrução pós-export (document preferences do Zotero antes de refresh) na saída do comando e na doc — senão o coautor enfrenta um popup por citação.
4. **`doctor` detecta churn:** versão do Zotero (API local) e do BBT, contra o par suportado (Zotero 9+); mensagem de dependência desatualizada inclui o comando/link de correção (`core/deps.py`, seams `_binary_on_path`/`_port_open`/`check_external_deps` já existentes).

### Fase 2 — Golden path Desktop/Cowork + modo degradado (MINOR)

1. **Preflight uniforme nas skills:** contrato único de checagem de dependências no início de cada skill que toca operação exata; ausência → recusa fail-closed + oferta de instalação guiada consentida (D1). Registrado em ADR.
2. **Instalação guiada:** a skill `start` conduz a instalação dentro da conversa no Cowork — uv, CLI, deps — cada comando com consentimento explícito; o preflight das demais skills roteia para ela. No chat puro (sem execução), orienta com a doc.
3. **Docs em duas trilhas:** "pesquisador (Desktop/Cowork, sem terminal)" e "dev (Claude Code)", com material da Fase 0. README ganha a trilha nova sem perder a atual.
4. **Piloto com 1 colega real:** medir o critério ≤15 min até primeiro output (ex.: peer-review de um draft — julgamento puro, roda sem stack). O resultado calibra os triggers das Fases 4–5.

### Fase 3 — Ponte docx↔CriticMarkup (sub-programa)

Executa o programa do spec [2026-07-05-review-docx-criticmarkup-design.md](2026-07-05-review-docx-criticmarkup-design.md) (fases 0–4 próprias, invariantes I1–I8, guardas hard-fail). É a fricção do coautor: ele permanece no Word, sem instalar nada. Gate: revisão do dono naquele spec. A Fase 1 daqui é pré-requisito técnico natural (a ponte consome o export endurecido).

### Fase 4 — Colapso de dependências (gated)

> **Emenda (2026-07-25, aprovada pelo dono — escopo A):** o trigger DISPAROU
> no piloto real da Fase 2 com AMBAS as dores: (1) conectar a coleção do
> Zotero ao projeto (o fio "Keep updated"→`_references.bib`); (2) qmd
> inutilizável sem terminal. O grounding verificado (workflow 13 agentes,
> 2026-07-25) REESCREVE os itens originais:
>
> 1. **Zotero → `prumo paper connect <coleção>`** (substitui "camada via
>    .xpi"): o JSON-RPC do BBT expõe `autoexport.add(collection, translator,
>    path)` (provado ao vivo) e `user.groups(true)` para validação — o prumo
>    cria o fio coleção→bib programaticamente com guardas anti-fantasma
>    (validar existência + fuzzy-match; desambiguar multi-library; typo NUNCA
>    cria coleção no Zotero). Zero dependência nova. Decisão estrutural
>    (mutação controlada no Zotero do usuário) → ADR.
> 2. **qmd → MCPB REFUTADO na prática** (14 binários nativos por plataforma,
>    ~2 GB GGUF no 1º uso, Homebrew SQLite no macOS; ninguém publicou qmd
>    como .mcpb): o fallback lexical documentado (mesmo mecanismo nativo do
>    Cowork) vira o caminho NORMAL da persona para o wiki; qmd permanece
>    opcional-avançado.
> 3. **Docs:** conectores de literatura via marketplace oficial
>    `anthropics/life-sciences` (PubMed em MCP remoto da Anthropic, sem auth,
>    in-app sem terminal — recomendar, não construir); ponte
>    cookjohn/zotero-mcp (.xpi, semantic search do acervo) mencionada com
>    rótulo "não validado neste piloto"; Zettlr recomendado como editor.

Itens originais (superados pela emenda, mantidos como registro):

1. ~~**qmd → bundle MCPB Node:** o runtime Node embutido no Desktop elimina `bun install -g`. Não-trivial (binários nativos de node-llama-cpp, modelos GGUF, Node ≥22) — dimensionar no plan. Adoção de MCPB é decisão estrutural → ADR.~~
2. ~~**Camada Zotero via `.xpi`:** adotar/integrar o padrão cookjohn/zotero-mcp (MCP embutido no Zotero, one-click) ou empacotar `.xpi` próprio com o que o prumo precisa — avaliação no plan.~~

**Trigger:** bloqueio real observado no piloto da Fase 2 (colega ativo precisando de busca semântica sem terminal; ou config Zotero/BBT como ponto de abandono). Sem dor observada, a fase não começa. **[DISPARADO em 2026-07-25 — ver emenda acima.]**

### Fase 5 — Empacotamento do CLI Python (gated, decisão adiada)

O elo estruturalmente duro: o Desktop não embute Python. Alternativas mapeadas — (a) PyApp/binário single-file; (b) modo `server.type="uv"` do MCPB (experimental hoje); (c) migração progressiva de cola fina para Node. **Nenhuma decisão agora** (Princípio VI): decidir no plan quando o trigger disparar (colega travado *apesar* da instalação guiada da Fase 2) ou a pergunta aberta do MCPB resolver.

## Critérios de sucesso

1. Colega com plano Pro, sem terminal, chega ao **primeiro output em ≤15 min** a partir do link do marketplace (medido no piloto da Fase 2).
2. O export docx **nunca entrega arquivo corrompido silenciosamente**: valida → retry → hard-fail com mensagem acionável (fixture-testado).
3. `doctor` aponta par Zotero/BBT fora do suportado com o comando de correção embutido na mensagem.
4. Em modo degradado, **nenhuma operação exata é simulada** por agente — recusa verificável + oferta de instalação (testado no contrato de preflight).
5. Coautor continua sem instalar nada (invariante das Fases 3+).

## Estratégia de testes

Padrão da casa (`tests/unit/<dominio>/`, deps externas mockadas nos seams): cada hard-fail novo vira teste com fixture — docx são, docx corrompido (zip inválido / `[Content_Types].xml` quebrado), docx sem campos ADDIN; retry testado com pandoc mockado falhando 1x e 2x; doctor testado com versões Zotero/BBT simuladas nos seams (`_port_open`, resposta da API local). Preflight de skills: teste de contrato por skill afetada (recusa + mensagem). Fase 0 e piloto da Fase 2 são evidência manual registrada, não CI.

## Riscos registrados

- **Superfícies em research preview**, exigem plano pago; admins Enterprise podem bloquear plugins/MCP local. Mitigação: trilha dev/terminal permanece de primeira classe.
- **Bus-factor 1 do BBT** e churn de versões do Zotero (ciclo 6–10 semanas). Mitigação: doctor de versões (Fase 1) + pergunta aberta do citekey nativo.
- **Snapshot temporal:** toda a pesquisa é de 22/07/2026 num ecossistema rápido. Guarda: **reverificar as fontes primárias citadas no início de cada plan** antes de implementar.
- **Evidência de UX de clínicos é indireta** (a sub-questão não gerou claims verificados). Mitigação: Fase 0 e piloto da Fase 2 geram evidência própria antes das fases caras.
- **Interação com a decisão externa do Zettlr front** (D6): se o export mudar por fora, reconciliar no plan da Fase 1 antes de endurecer.

## Fora de escopo (specs/ações futuras)

Submissão ao marketplace comunitário e JOSS (ações de ROADMAP; JOSS ~out/2026); multi-host real (Cursor/Codex/Gemini — deferral ADR-0011); SaaS/hospedagem; app desktop próprio; marketplace Life Sciences (gated — acompanhar); reescrita do CLI em Node (só entraria via Fase 5, com trigger).

## Perguntas abertas (resolvidas nas fases indicadas)

1. O marketplace self-hosted sincroniza in-app hoje, com quais limitações? → **Fase 0**.
2. O que exatamente a decisão externa do Zettlr front (ADR-0015 externo) muda nas premissas do export? → **plan da Fase 1**.
3. O modo `server.type="uv"` do MCPB amadurece a ponto de one-click Python sem Python pré-instalado? → **monitorar; gate da Fase 5**.
4. O citation key nativo do Zotero 8+ cobre o caso do prumo a ponto de reduzir a dependência do BBT? → **monitorar; sem fase associada (Princípio VI)**.
5. Existe rota de terceiros para o marketplace Life Sciences? → **monitorar; fora de escopo**.

## Governança

- Fases 1 (PATCH) e 2/4 (MINOR) seguem RELEASING.md; Fase 0 e docs são não-releaseáveis; versão só em `src/prumo_assist/_version.py` + sync (Princípio VII).
- Decisões estruturais nas fases geram ADR próprio: contrato de preflight/modo degradado (Fase 2), adoção de MCPB (Fase 4), empacotamento do CLI (Fase 5).
- Cada fase → plano em `docs/superpowers/plans/`, executado com TDD; plano implementado recebe `status: implemented` + `verified` + `release` e move para `archive/` (lifecycle da casa).
- Este spec segue `status: draft` até revisão do dono; mudanças pós-aprovação = nova revisão datada.

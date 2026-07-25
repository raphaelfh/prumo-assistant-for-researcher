# Fase 0 — Spike de validação empírica no Desktop/Cowork — Runbook manual

> **Execução:** MANUAL, pelo dono (exige conta Claude paga e a UI do Claude Desktop/Cowork — nenhum agente consegue executar isto). Sem código. ~15–25 min. O resultado alimenta diretamente o plano da Fase 2 (golden path + modo degradado) do spec [[2026-07-22-zero-friction-onboarding-design]].

**Goal:** Responder empiricamente: o `marketplace.json` atual do prumo-assist sincroniza in-app nas superfícies Claude (web/Desktop/Cowork)? O que carrega e o que quebra sem o CLI/Zotero/qmd instalados? Como as falhas aparecem para um usuário não-programador?

**Por que primeiro:** é a fase mais barata do programa e falsifica premissas antes de qualquer código da Fase 2 (se a sincronização in-app não funcionar como documentado em mai/2026, o golden path muda de forma). Sensibilidade temporal: as superfícies estão em research preview — se a UI divergir do roteiro, registre a discrepância como achado (não como erro seu).

**Pré-flight automatizado (2026-07-23, controller):** `validate_manifests.py` ✓ (`plugin.json`, `marketplace.json`, coerência cruzada) e `sync_manifest_version.py --check` ✓ (v0.62.0) — o spike não falhará por manifesto inválido.

**Tentativa de execução agentiva (2026-07-23):** o dono autorizou executar o spike via Claude in Chrome (sessão logada), mas a extensão **bloqueia `claude.ai` e `claude.com` por política de permissões de site** ("This site is blocked by your site permissions") — anti-recursão. Caminhos: (a) execução manual pelo dono (este runbook), ou (b) o dono liberar os domínios nas permissões da extensão e pedir a retomada agentiva. Registrado como evidência: superfícies Claude não são automatizáveis por agente-no-Chrome na configuração default.

**Pré-requisitos:** plano Claude pago (Pro/Max); Claude Desktop instalado (aba Chat) e acesso ao Cowork; um diretório `pj_*` real disponível para o passo 6. Para maximizar o sinal do modo degradado, execute os passos 3–5 numa máquina/contexto SEM `prumo` CLI no PATH — ou anote que a sua máquina tem o stack completo e o degradado ficará sub-testado (aceitável; o piloto da Fase 2 cobre).

---

## Roteiro (marque e anote em cada item)

- [ ] **1. Adicionar o marketplace por URL, in-app.** No chat do claude.ai (web) OU no Claude Desktop: fluxo de plugins → "Add from a repository" → `raphaelfh/prumo-assist` (ou URL git completa). Registrar: onde o fluxo fica na UI atual, se a sincronização funciona, mensagens de erro, e o que o catálogo mostra do plugin (nome, versão, nº de skills).
- [ ] **2. Instalar o plugin e inventariar as skills visíveis.** Registrar: quantas das 14 skills aparecem, como aparecem (prefixo `/prumo-assist:`?), e se hooks/sub-agents aparecem desabilitados fora do Cowork (esperado, segundo a doc de mai/2026).
- [ ] **3. Testar uma skill de julgamento puro SEM stack.** Colar um trecho de draft qualquer e invocar `/prumo-assist:peer-review`. Registrar: roda? pede algo do CLI indevidamente? qualidade subjetiva ok? (Esta é a hipótese do gancho de time-to-first-value da Fase 2 — D1.)
- [ ] **4. Testar uma skill dependente do CLI e capturar a falha.** Invocar `/prumo-assist:paper-manager` (listar bibliografia) ou `/prumo-assist:wiki-query` sem `prumo`/Zotero/qmd disponíveis. Registrar A MENSAGEM EXATA que o usuário vê — é a linha de base que o preflight fail-closed da Fase 2 vai substituir.
- [ ] **5. Observar o MCP `qmd` declarado.** O plugin distribui `.mcp.json` com o servidor `qmd`. Registrar: a superfície tenta subir o servidor? Que erro aparece sem o binário? O erro é compreensível para um clínico?
- [ ] **6. Cowork com pasta `pj_*` real.** Designar a pasta de um projeto real; repetir os passos 3–4; testar se o agente consegue EXECUTAR um comando simples na pasta com consentimento (ex.: pedir para rodar `ls`/criar um arquivo de teste). Registrar: o modelo de permissão/consentimento como aparece — isso valida (ou não) a premissa da instalação guiada da Fase 2 (D1: "o Cowork executa comandos").
- [ ] **7. (Opcional) Upload direto de arquivo de plugin** (fluxo "recebido de um colega"): exportar/enviar o plugin como arquivo e instalar via upload. Registrar viabilidade.
- [ ] **8. Capturar screenshots** dos passos 1, 2, 4 e 6 (material bruto da doc em duas trilhas da Fase 2).

## Registro de evidência (preencher ao executar)

| Passo | Funcionou? | Mensagem/observação | Screenshot |
|---|---|---|---|
| 1 marketplace in-app | (pendente detalhes) | Instalação claramente funcionou (skills rodando na sessão do dono); falta registrar ONDE fica o fluxo na UI e o que o catálogo mostra (nome/versão/nº) | pendente |
| 2 skills visíveis | PARCIAL | Corroboração indireta: a sessão Claude Code do dono também carregou o plugin com **14 skills** (= estado do `main` v0.62.1; `review-reconcile` e `citation-support` só existem no branch do PR #11 — re-sync pós-merge é teste natural) | pendente |
| 3 julgamento sem stack | PARCIAL | `wiki-ingest` identificou o paper via web (Khalil 2022, DOI 10.1016/j.jclinepi.2021.12.005), RECUSOU ingest direto de paper (regra Zotero-fonte-de-verdade obedecida) e roteou p/ paper-manager; `peer-review` com trecho de draft ainda não testado | pendente |
| 4 falha sem CLI (baseline) | **SIM — capturada** | `write-paper section=intro` ABORTOU fail-closed com razões precisas: sem scaffold `pj_*` (pasta `teste` vazia), CLI `prumo` indisponível p/ `write prep`, sem `.claude/picot.toml` (regra de abort da skill), sem `references/_references.bib` (tudo viraria `[REF FALTANTE]`). Nada foi simulado. **ACHADO-CHAVE p/ Fase 2:** a remediação sugerida foi "`make new-project` no monorepo do prumo" — contexto do DONO, não da persona (colega não tem monorepo; pós-PR#12 o comando certo é `prumo init`). O preflight uniforme da Fase 2 precisa de comando de correção por CONTEXTO | transcrição colada |
| 5 MCP qmd | | | |
| 6 Cowork + execução | PARCIAL | "Add folder" conectou a pasta `teste`; o agente LEU a pasta (detectou vazia, sem `docs/`/`references/`) e EXECUTOU comando no fluxo do write-paper (CLI ausente → falha limpa). Falta: repetir com `pj_*` REAL + registrar o modelo de consentimento numa ação de escrita | pendente |
| 7 upload de arquivo | | | |

**Evidência recebida (2026-07-24, transcrição colada pelo dono — parcial):** fluxo real Desktop/Cowork com `teste` (pasta vazia). Validações: fail-closed do D1 funcionou na prática (abort com razões, zero simulação); roteamento paper→Zotero obedecido; agente lê pasta conectada e executa comandos. Alerta metodológico registrado: a sessão Cowork OFERECEU "criar o scaffold mínimo do wiki" na mão — oferta RECUSÁVEL por contaminar o spike (agente simulando trabalho do CLI, exatamente o que o fail-closed proíbe).

## Critérios de saída

1. Pergunta aberta nº 1 do spec respondida ("o marketplace self-hosted sincroniza in-app hoje, com quais limitações?").
2. Baseline do modo degradado registrada (mensagens exatas dos passos 4–5).
3. Premissa da instalação guiada validada ou refutada (passo 6).
4. Material de docs coletado (passo 8).

Ao concluir: preencher a tabela acima neste arquivo, adicionar frontmatter `status: implemented` + `verified: <data>` e mover para `archive/` (lifecycle da casa). O plano da Fase 2 nasce citando este registro.

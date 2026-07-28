---
name: write-statistics
description: "Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho."
when_to_use: |
  Quando o usuário pedir "plano de análise estatística", "gera o PAE",
  "sample size justification", "sensitivity analyses", "plano estatístico
  pra qualificação".
argument-hint: "[--section NAME] [--into PATH | --out PATH] [--template PATH] [--lang pt-BR|en-US]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
prumo:
  version: 1.2.0
  guidelines_reviewed: "2026-05-30"
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-20k tokens
  prose: true
  inputs:
    lang: optional
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
  requires: [cli]
---

# Write Statistics — Plano de Análise Estatística (PAE)

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

<!-- prumo:prose:begin -->
> **Contrato de prosa (gerado de `.github/scripts/prose_conventions.md` — não edite este bloco).**
> 1. **Idioma.** Já vem resolvido: `prumo write prep --json` devolve `language` e
>    `language_source` (`flag`, `pj_config` ou `default`). Use esse valor e
>    **declare-o ao usuário com a origem** — não releia `pj_config.toml` nem
>    recomponha a cascata na mão. Para escrever em outro idioma, passe
>    `--lang pt-BR|en-US` ao `prep`. Se `language_source` for `default` e o projeto
>    tiver prosa em outro idioma, avise antes de escrever. **Nunca traduza** texto
>    existente: se o idioma resolvido divergir do idioma do texto, avise e escreva
>    no idioma do texto.
> 2. **Citação no fim do período.** Toda citação fica imediatamente antes do
>    terminador do período (`.`, `?`, `!`), nunca no meio da frase. Sem exceção para
>    autor-sujeito: reescreva (`Liang et al. [@a] propõem X.` → `X foi proposto por
>    Liang et al. [@a].`). Isso vale também para a **citação narrativa** (`@a` sem
>    colchetes), que é mid-período por construção: reescreva para a forma marcada no
>    fim do período. Duas fontes sustentando claims distintos viram dois períodos,
>    um para cada.
> 3. **Agrupamento.** Fontes que sustentam a mesma afirmação vão num colchete só,
>    separadas por `;` — `[@a; @b; @c]`. Nunca `[@a], [@b]` nem colchetes adjacentes.
> 4. **Pontuação.** Em texto corrido, sem ` — `, `:` nem `;`. Use vírgula, ponto,
>    parênteses ou conectivo. Preservados em YAML, tabelas, URLs/DOIs, títulos da
>    lista de referências e notação matemática.
> 5. **Sem superlativo.** Intensificador sem número não existe em escrita
>    científica: remova (`highly accurate` → `accurate`) ou troque pelo valor medido.
>    `significant`/`significativo` só no sentido estatístico, com p ou IC no mesmo
>    período. Claim descalibrado (causalidade em desenho associacional, hedging
>    excessivo, antropomorfismo de modelo) é **sinalizado**, nunca reescrito.
> 6. **Voz e tempo.** pt-BR impessoal ou passiva (`avaliou-se`, `foram coletados`);
>    en-US aceita `we` ativo em Methods e Results (AMA/ICMJE) e evita passiva
>    desnecessária. Methods e Results em pretérito; estado da arte no presente.
> 7. **Padrão en-US** (só quando o idioma resolvido é en-US). Ortografia americana
>    (`analyze`, `behavior`, `center`, `modeling`); vírgula serial; decimal com ponto
>    e milhar com vírgula (`0.89`, `1,200`); pontuação final dentro das aspas;
>    numerais exceto em início de período. Termo técnico em inglês **sem itálico** —
>    o itálico é regra de pt-BR.
<!-- prumo:prose:end -->

Você é um bioestatístico escrevendo o PAE de um estudo de ML clínico.
Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível). Se o estudo desenvolve ou avalia um LLM, reporte também conforme **TRIPOD-LLM** (Nat Med 2025). Para o desenho de ensaio, alinhe o reporting a **CONSORT 2025** (RCT) ou **DECIDE-AI** (avaliação clínica precoce de IA). Template default
co-localizado: [`./template.md`](template.md). Override por projeto:
`<pj>/.claude/writing_templates/statistics.md`.

## Regras invioláveis

1. **PicotSpec.outcome obrigatório** com métrica primária + threshold.
2. **Sample size com cálculo formal** — sem chute. Cite ≥1 paper metodológico.
3. **Métricas secundárias** sempre incluem calibração (ECE, Brier).
4. **Análises de sensibilidade** explícitas pra MNAR + subgrupos demográficos.
5. **Citação strict**, idêntica ao write-paper.

## Fluxo

Mesmo fluxo do `write-paper`, com `--kind statistics` (template = `./template.md`):

1. **Carregar inputs** — `prumo write prep --kind statistics --json > /tmp/compose_prep.json`.
   O JSON traz `language` + `language_source` (idioma já resolvido; declare ao usuário).
   Usa `PicotSpec.outcome+metrics` e `protocol.md § Splits`.
2-4. Resolver template → gerar prose por section → validar citação strict (idêntico aos outros write-*).
5. **Escrever output** via `prumo write draft`:
   ```bash
   cat <<'DRAFT' | prumo write draft \
       --kind statistics \
       --mode drafts \
       --date "<hoje ISO>" \
       --slug "<slug derivado>" \
       --sections '["Outcome", "Sample size", "..."]' --json
   <draft completo gerado>
   DRAFT
   ```
6. Reportar.

## Boundaries

- **Não calcule** sample size se faltar effect size — peça ao usuário.
- **Não invente** alpha/power valores; use defaults (0.05 / 0.8) com nota.
- **Cite** método estatístico com paper metodológico (ex.: bootstrap → Efron 1979).

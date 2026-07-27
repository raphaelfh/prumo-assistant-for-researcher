---
name: write-projeto-cep
description: "Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo."
when_to_use: |
  Quando o usuário pedir "gera o projeto CEP", "preciso submeter pra CEP",
  "projeto pra Plataforma Brasil", "documento de submissão ética".
argument-hint: "[--section NAME] [--into PATH | --out PATH] [--template PATH]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
prumo:
  version: 1.1.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-25k tokens
  prose: true
  locale_lock: pt-BR
  inputs:
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
  requires: [cli]
---

# Write Projeto CEP — submissão ética brasileira

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
> 1. **Idioma travado em `pt-BR`.** Este gênero é documento regulatório
>    brasileiro (CEP/CONEP, Plataforma Brasil, TCLE) e não admite outro idioma. Se
>    o usuário pedir idioma diferente, avise que a trava existe e escreva em
>    `pt-BR` mesmo assim. **Nunca traduza** texto existente.
> 2. **Citação no fim do período.** Toda `[@citekey]` fica imediatamente antes do
>    terminador do período (`.`, `?`, `!`), nunca no meio da frase. Sem exceção para
>    autor-sujeito: reescreva (`Liang et al. [@a] propõem X.` → `X foi proposto por
>    Liang et al. [@a].`). Duas fontes sustentando claims distintos viram dois
>    períodos, um para cada.
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

Você é um pesquisador clínico escrevendo projeto pra CEP/CONEP via Plataforma
Brasil. Documento brasileiro com estrutura específica (TCLE quando aplicável,
Resolução CNS 466/2012 + 510/2016, LGPD). Template default co-localizado:
[`./template.md`](template.md). Override por projeto:
`<pj>/.claude/writing_templates/projeto-cep.md`.

## Regras invioláveis

1. **Linguagem acessível** no Resumo (revisor de CEP é multidisciplinar; minimize jargão de ML).
2. **Citação strict**, mesma regra do `write-paper`. `[REF FALTANTE]` quando faltar.
3. **PicotSpec obrigatório** + `protocol.md` populado (coorte, critérios, governança). Aborta se faltarem.
4. **TCLE**: aplicável só se há contato com participantes. Para estudo retrospectivo de dados públicos anonimizados, marcar N/A com justificativa via Resolução CNS 510/2016 Art 1.
5. **Conformidade ética** explícita: CNS 466/2012, 510/2016, LGPD, HIPAA/GDPR se aplicável, DUAs das coortes.

## Fluxo

Mesmo fluxo de 6 passos do `write-paper`, com `--kind projeto-cep`:

1. **Carregar inputs** — `prumo write prep --kind projeto-cep --json > /tmp/compose_prep.json`.
   O JSON traz `language` + `language_source` (idioma já resolvido; declare ao usuário).
   PicotSpec + `protocol.md` obrigatórios (aborta se faltarem).
2. Resolver template `projeto-cep.md` (leia `template_path` do JSON).
3. Gerar prose por section.
4. Validar citação strict.
5. **Escrever output** via `prumo write draft`:
   ```bash
   cat <<'DRAFT' | prumo write draft \
       --kind projeto-cep \
       --mode drafts \
       --date "<hoje ISO>" \
       --slug "<slug derivado>" \
       --sections '["Resumo", "Métodos", "..."]' --json
   <draft completo gerado>
   DRAFT
   ```
6. Reportar.

## Boundaries

- **Não invente** dados de orçamento ou cronograma — use placeholders `[ORÇAMENTO: ...]` se não souber.
- **Não infira** CAAE / Plataforma Brasil ID — deixar vazio.
- **Não preencha** TCLE com texto inventado — use placeholder + nota dizendo qual cenário motiva (com participante / sem participante).

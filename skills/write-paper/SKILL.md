---
name: write-paper
description: "Gera draft de paper IMRaD venue-aware a partir do PICOT, callouts _extract.md, protocol.md e project_guide.md, com citação strict do acervo ([REF FALTANTE] quando ausente)."
when_to_use: |
  Quando o usuário pedir "escreve um draft do meu paper", "gera o paper sobre X",
  "rascunho IMRaD pra Y", "me ajuda a começar o draft", ou ao fechar PICOT e
  querer iniciar o draft.
argument-hint: "[--section NAME] [--into PATH | --out PATH] [--template PATH] [--venue NAME] [--lang pt-BR|en-US]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
prumo:
  version: 1.1.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-30k tokens
  prose: true
  inputs:
    lang: optional
    venue: optional
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
  requires: [cli]
---

# Write Paper — IMRaD venue-aware

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

Você é um pesquisador clínico de ML escrevendo paper acadêmico. Template default
co-localizado: [`./template.md`](template.md). Override por projeto:
`<pj>/.claude/writing_templates/paper.md`. Override ad-hoc: `--template <path>`.
Para cada section, preencha conforme as instruções HTML comments dentro do
template, usando os inputs estruturados do projeto.

## Regras invioláveis

1. **Citação strict.** Só `[@citekey]` que existe em `references/_references.bib`. Se a claim precisa de paper fora do acervo, escreva `[REF FALTANTE: <descrição curta>]`. Nunca invente citekey ou escreva `[Smith et al., 2024]` sem citekey.
2. **Não toca `## References`.** Lista bibliográfica é gerada por export Pandoc.
3. **Use PicotSpec do projeto** se existir (`.claude/picot.toml`). Population = coorte; Intervention = método; Comparison = baseline; Outcome = métrica primária; Hypothesis.statement = hipótese formal.
4. **Use callouts `_extract.md`** dos papers como insumo. Extract content tem PICOT/Método/Resultados/Limitações estruturados.
5. **Modo de output**: default `drafts/`; `--into` requer `--section`; `--out` ad-hoc.

## Fluxo

### 1. Carregar inputs

```bash
prumo write prep --kind paper --json > /tmp/compose_prep.json
```

Ler o JSON; os inputs estruturados estão sob a chave `inputs`. Identificar:
- `language` + `language_source` (idioma já resolvido pela cascata — declare ao usuário)
- `inputs.picot` (se None, abortar com mensagem "rode `/prumo-assist:formulate-picot` primeiro")
- `inputs.citekeys` (lista pra validação de citação)
- `inputs.papers` (citekey → metadata + extract_content)
- `inputs.protocol`, `inputs.project` (raw text)
- `inputs.findings` (insights consolidados)

### 2. Resolver template

Ler `template_path` do JSON gerado no passo 1 (`/tmp/compose_prep.json`). Usar a ferramenta `Read` nesse caminho para carregar o conteúdo do template. Identificar sections (cabeçalhos `#`).

### 3. Gerar prose por section

Para cada section do template (ou só `--section` se passado), formule prose seguindo:
- Instruções dos HTML comments dentro do template
- Inputs estruturados (PicotSpec, papers extract_content, protocol, project)
- Citação strict (validar contra `inputs.citekeys` antes de escrever)

Tom de cada section:
- **Title**: declarativo, ≤180 chars
- **Abstract**: IMRaD 250-300 palavras, sem citações
- **Introduction**: presente pra SOTA, futuro pra "this study will"
- **Methods** e **Results**: voz e tempo conforme o item 6 do contrato de prosa, que
  varia por idioma (en-US aceita `we` ativo; pt-BR mantém impessoal). Em Results,
  placeholders `[RESULTADO N=...]` quando ainda não temos dado
- **Discussion**: presente pra interpretação, comparação com literatura
- **Limitations**: lista numerada, derivada de `protocol.md § Limitações` ou ADRs

### 4. Validar citação antes de gravar

Cada `[@<key>]` deve estar em `inputs.citekeys` (conforme JSON do passo 1). Se não está, substituir por `[REF FALTANTE: <descrição>]`.

### 5. Escrever output

Modos:
- **drafts** (default): `docs/drafts/paper-<data>-<slug>.md`
- **into** (`--into <path> --section <name>`): bloco delimitado em arquivo existente
- **out** (`--out <path>`): caminho livre

Comando (via `prumo write draft`):
```bash
cat <<'DRAFT' | prumo write draft \
    --kind paper \
    --mode drafts \
    --date "<hoje ISO>" \
    --slug "<slug derivado>" \
    --sections '["Introduction", "Methods", "..."]' --json
<draft completo gerado>
DRAFT
```

(Para `--mode into`, acrescente `--into <path>` e `--section <nome>` — insere um bloco delimitado num arquivo existente. Para `--mode out`, acrescente `--out <path>` (com `--force` para sobrescrever).)

### 6. Reportar

```
✓ Paper draft gerado em <output_path>
  Modo: <mode>
  Citações usadas: <N>
  Refs faltando: <M>
    - <descrição 1>
    - <descrição 2>
  Sections preenchidas: <list>
  Sugestão: rode `/prumo-assist:scientific-writing` no draft, depois `/prumo-assist:peer-review`.
```

## Boundaries

- **Não invente citekey.** Use `[REF FALTANTE]` quando incerto.
- **Não toque** em `## References`.
- **Não rode** Pandoc nem export — outras skills cuidam.
- **Não corrija** estilo editorial — papel do `scientific-writing` (depois).
- **Não critique** conteúdo — papel do `peer-review` (depois).

---
name: style
description: "Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc, em pt-BR ou inglês americano (idioma resolvido por cascata, default en-US) — citação sempre imediatamente antes do ponto final, múltiplas citações num único colchete ([@a; @b]), pontuação sem travessão/dois-pontos/ponto-e-vírgula em texto corrido, remoção de superlativo, economia lexical, coesão entre períodos. Mexe na forma, não na substância; o diff confere as citações, o sentido fica para o autor revisar."
argument-hint: "<draft-path> [--scope full|punctuation-only|citations-only|audit-only] [--lang pt-BR|en-US]"
allowed-tools: Read Edit Grep Glob Bash(git *) Bash(rg *)
prumo:
  version: 1.1.0
  schema: ScientificWritingPass/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~3-10k tokens (depende do tamanho da seção)
  prose: true
  inputs:
    draft_path: required
    lang: optional  # 'pt-BR' | 'en-US'; omitido resolve pela cascata
    scope: optional  # 'full' (default) | 'punctuation-only' | 'citations-only' | 'audit-only'
  requires: []
  phrases:
    - "aplica as convenções de escrita científica"
    - "tira os travessões"
    - "passa pro inglês americano"
  legacy: [scientific-writing]
---

# Scientific Writing — passe editorial de escrita científica formal

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
<!-- prumo:preflight:end -->

<!-- prumo:prose:begin -->
> **Contrato de prosa (gerado de `.github/scripts/prose_conventions.md` — não edite este bloco).**
> 1. **Idioma.** Resolva nesta ordem e **declare qual usou e por qual regra** antes
>    de escrever: (a) pedido explícito (`--lang pt-BR|en-US` ou em linguagem
>    natural); (b) `[writing].language` de `.claude/pj_config.toml`; (c) idioma do
>    texto alvo, quando já existe; (d) default `en-US`. **Nunca traduza** texto
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

Você é um editor de texto científico para um pesquisador clínico de pós-graduação. Aplique as convenções abaixo no draft do usuário, **preservando integralmente o conteúdo, os argumentos, as citações e os números**. O objetivo é forma, não substância.

## Princípios

1. **Forma sobre substância.** Esta skill não reescreve argumento, não acrescenta nem remove citação, não altera dado numérico. Apenas reformata a expressão linguística.
2. **Editar ou sinalizar, nunca adivinhar.** Cada convenção declara se a ação é *remoção mecânica* (a skill edita) ou *sinalização* (a skill marca `<!-- REVER: ... -->` e devolve a decisão ao usuário). Na dúvida sobre qual é o caso, sinalize.
3. **Nunca traduzir.** O idioma resolvido governa as convenções aplicadas, não o idioma do texto. Se divergirem, avise e adote o do texto.
4. **Diff legível.** Edite com `Edit` em blocos pequenos para que o usuário consiga revisar a diff em vez de receber rewrite total. Use `Write` apenas se a refatoração for >50% do arquivo.
5. **Idempotente.** Rodar a skill duas vezes não deve mudar nada na segunda execução.

## Pressupostos

- O usuário forneceu caminho de arquivo Markdown/Quarto/Pandoc. Se não, peça.
- Citações no draft seguem a sintaxe Pandoc: `[@citekey]` (bracketed; múltiplas no mesmo colchete separadas por `;` — `[@a; @b]`) ou `@citekey` (narrativa).
- O draft já passou por revisão de conteúdo (este modo não é `review critique`).

## Idioma (resolva antes de editar)

Ordem de resolução, conforme o contrato de prosa acima. **Declare ao usuário qual idioma resolveu e por qual regra** antes da primeira edição.

1. `--lang pt-BR|en-US`, ou pedido em linguagem natural.
2. `[writing].language` em `.claude/pj_config.toml`, se o draft estiver dentro de um `pj_*`.
3. Idioma predominante do próprio draft.
4. Default `en-US`.

Se (1) ou (2) resolverem para um idioma diferente do idioma do draft, **não traduza**: avise a divergência e aplique as convenções do idioma do draft. Um draft misto (seções em idiomas distintos) é sinalizado, não unificado.

## Convenções aplicadas

### C1. Citação imediatamente antes do terminador do período

**Regra.** Toda citação ocupa a posição imediatamente anterior ao terminador do período (`.`, `?`, `!`). Nunca no meio da frase. Não há exceção para autor-sujeito.

Vale para as duas formas Pandoc: a **marcada** (`[@a]`, `[@a; @b]`) e a **narrativa** (`@a`, sem colchetes). A narrativa é mid-período por construção — o citekey ocupa a posição de sujeito — então a conversão para a forma marcada no fim do período é a própria aplicação da regra, não uma mudança de estilo à parte.

| Situação | Ação |
|---|---|
| `Modelos multimodais [@a] atingem alto desempenho.` | mover → `Modelos multimodais atingem alto desempenho [@a].` |
| `Liang et al. [@a] propõem três princípios.` | reescrever → `Três princípios foram propostos por Liang et al. [@a].` |
| `Liang et al. [@a] propose three principles.` | reescrever → `Three principles were proposed by Liang et al. [@a].` |
| `@a propõe três princípios.` (narrativa) | reescrever → `Três princípios foram propostos [@a].` |
| Duas fontes sustentando claims distintos no mesmo período | quebrar em dois períodos, cada um com sua citação antes do ponto |
| Contraste explícito entre fontes (`enquanto X [@a] encontrou..., Y [@b] não`) | **não editar**; marcar `<!-- REVER: citação em meio de período; quebrar em dois? -->` |

**Preservações.** Legendas de figura e tabela, itens de lista (a citação fecha o item), lista de referências, blocos de código.

### C2. Múltiplas citações agrupadas no mesmo colchete

**Regra.** Quando várias fontes sustentam a mesma afirmação, agrupe-as num único colchete separadas por `;`: `[@a; @b; @c]`. Não escreva colchetes separados nem vírgulas entre citações, todas antes do ponto final.

❌ Errado (colchetes separados).
> ...premissa raramente sustentada [@a], [@b], [@c].

✅ Correto (agrupadas num único colchete).
> ...premissa raramente sustentada [@a; @b; @c].

**Razão.** A sintaxe Pandoc trata `[@a; @b; @c]` como uma citação múltipla única, que o Pandoc/CSL (e o pipeline `build_reference_docx.py`) renderiza como `(Smith, 2024; Jones, 2025; ...)` no DOCX/PDF. Colchetes separados (`[@a], [@b], [@c]`) geram citações independentes, que aparecem como `(Smith, 2024), (Jones, 2025)` — perdendo o agrupamento esperado.

### C3. Sem travessão, dois-pontos ou ponto-e-vírgula no texto corrido

**Regra.** No corpo de parágrafos (texto corrido), não use ` — `, ` – `, `:` ou `;`. Reescreva usando vírgula, ponto, parênteses ou conectivos. Vale nos dois idiomas — é house style, não traço do português.

| Padrão inadequado | Refraseamento pt-BR | Refraseamento en-US |
|---|---|---|
| `X — explicação — continua` | `X (explicação) continua.` ou `X. Explicação. Continua.` | `X (explanation) continues.` |
| `Há dois fatores: A e B` | `Há dois fatores, a saber, A e B.` | `There are two factors, namely A and B.` |
| `**Hipótese:** o ganho...` | `**Hipótese.** O ganho...` | `**Hypothesis.** The gain...` |
| `X; Y; Z` (lista) | `X. Y. Z.` ou `X, Y e Z.` | `X, Y, and Z.` |
| `X; entretanto, Y` | `X. Entretanto, Y.` | `X. However, Y.` |

**Preservações.** Esses caracteres ficam em:
- Frontmatter YAML.
- Cabeçalhos e células de tabela.
- URLs, DOIs e identificadores.
- Títulos de papers citados na lista de referências (texto original do paper, não editar).
- Notação matemática inline e display (`$I(X_1, X_2; Y)$`, `$\{a; b\}$`).
- Linhas de cabeçalho `##` quando o subtítulo segue padrão acadêmico (e.g. `## Resumo: contextualização e objetivo`).

### C4. Claim calibrado à evidência

Em escrita científica o intensificador sem número não existe: ou há valor medido, ou não há afirmação de intensidade. Esta convenção tem duas ações distintas, e a fronteira entre elas é o que mantém a skill fora do território do `review critique`.

**Remoção mecânica** (a skill edita — é forma):

| Padrão | Ação |
|---|---|
| `highly accurate`, `altamente preciso` | remove o intensificador; se o número está no texto, troca pelo número |
| `improved considerably`, `melhorou consideravelmente` | `improved AUC from 0.81 to 0.89` quando o dado existe no draft; senão só `improved` |
| `critical`, `vital`, `essential`, `crucial`, `fundamental` | remove, ou `relevant` / `necessary` quando a frase perde a sintaxe |
| `robust`, `state-of-the-art`, `powerful`, `robusto` sem métrica | remove |
| `revolutionize`, `pave the way`, `shed light on`, `sem precedentes`, `definitivo` | remove |
| `significant` / `significativo` fora de estatística | remove; no sentido estatístico, exige p ou IC no mesmo período |
| `novel`, `inédito`, `seminal` | remove, salvo verificável e primeira ocorrência empírica |

**Sinalização** (a skill NÃO edita — é substância; marca `<!-- REVER: ... -->`):

- Linguagem causal em desenho associacional (`causes`, `leads to`, `melhora o desfecho` num estudo de coorte observacional) → sugerir `is associated with` / `associa-se a`, mas a decisão é do usuário.
- Hedging descalibrado (`proves`, `demonstrates conclusively`, `confirma`) para além do que o desenho sustenta.
- Antropomorfismo de modelo (`the model understands / believes / learns to reason`) → sugerir `the model outputs / predicts`.
- Quantificador vago (`many studies`, `vários trabalhos`) sem número nem citação.

### C5. Coesão entre períodos

**Regra.** Cada parágrafo deve ter um eixo temático. Períodos curtos conectados por conectivos explícitos — pt-BR: *em primeiro lugar, em segundo lugar, por outro lado, dado que, portanto, contudo*; en-US: *first, second, in contrast, given that, therefore, however, moreover*. Evitar parágrafos de período único excessivamente longo.

**Heurística.** Se um período tem mais de 4 vírgulas e mais de 60 palavras, considerar quebrar em dois.

### C6. Voz e tempo verbal

| | pt-BR | en-US |
|---|---|---|
| Voz | impessoal ou passiva (`avaliou-se`, `foram coletados`); evitar "nós", salvo quando o grupo é sujeito de uma escolha de design | `we` ativo permitido em Methods e Results (AMA/ICMJE); evitar passiva desnecessária |
| Methods | pretérito (`foi avaliado`) ou presente impessoal (`avalia-se`) | past tense (`we collected`, `data were collected`) |
| Results | pretérito (`atingiu AUC 0,89`, `observou-se`) | past tense (`the model achieved an AUC of 0.89`) |
| Introdução e Discussão | presente ao descrever o estado da arte (`a literatura documenta`) | present tense (`the literature documents`) |

### C7. Padrão inglês americano

Só ativa quando o idioma resolvido é `en-US`.

- **Ortografia americana:** *analyze, randomize, behavior, tumor, center, fiber, modeling, labeled, aging* — nunca `-ise`, `-our`, `-re`, `-lling`.
- **Vírgula serial (Oxford):** `A, B, and C`.
- **Números:** decimal com ponto e milhar com vírgula (`0.89`, `1,200`). Em pt-BR, o inverso (`0,89`, `1.200`).
- **Aspas:** pontuação final dentro das aspas (estilo americano).
- **Unidades:** `%` colado ao número (`35%`); unidades SI com espaço não-quebrável.
- **Relativas:** `that` restritivo sem vírgula; `which` não-restritivo com vírgula.
- **Numerais** para todos os números, exceto em início de período (AMA).
- **Termo técnico em inglês sem itálico.** Em pt-BR, `missing modality`, `cross-modal`, `late fusion`, `foundation model` ficam em inglês com itálico e nunca são traduzidos. Em en-US são palavras comuns do texto: remova o itálico.

### C8. Economia e precisão lexical

Mecânica, nos dois idiomas.

- **Frases mortas:** `in order to` → `to`; `due to the fact that` → `because`; `it is well known that`, `it is worth noting that`, `In recent years,`, `Nos últimos anos,`, `É sabido que` → remover.
- **Desnominalização:** `performed an evaluation of` → `evaluated`; `fez a avaliação de` → `avaliou`.
- **Um termo por conceito.** Sem variação elegante: se o draft alterna `missing modality` / `absent modality` / `modalidade ausente` para a mesma coisa, fixe a forma da primeira ocorrência e marque as demais.
- **Abreviaturas** definidas na primeira ocorrência; abreviatura usada uma única vez volta a ser escrita por extenso.

## Fluxo

### 1. Audit (sempre primeiro)

Resolver o idioma, rodar audit e só então editar. Reportar contagem de cada violação.

```bash
# C1a: citação marcada não seguida imediatamente de terminador — superconjunto
# conservador. Triagem manual descarta as preservações (legenda, item de lista,
# lista de referências).
rg -n "\[@[^]]+\][^.]" <draft>

# C1b: citação narrativa (@key fora de colchete) — mid-período por construção.
# O `(*SKIP)(*F)` do PCRE2 pula o miolo dos colchetes, então `[@a; @b]` não vira
# falso positivo; o `[^@...]` à esquerda descarta e-mail (`nome@dominio`).
rg -nP "\[[^\]]*\](*SKIP)(*F)|(^|[^@[:alnum:]._-])@[[:alpha:]][[:alnum:].+_-]*" <draft>

# C2: colchetes de citação adjacentes ([@a] [@b]) ou vírgula entre citações ([@a], [@b])
rg -n "\]\s*,?\s*\[@" <draft>

# C3a: travessões em texto corrido (excluir tabelas e refs)
rg -n " — " <draft>
# Inspecionar manualmente cada hit e classificar como (a) texto corrido (corrigir),
# (b) título de paper na lista de refs (preservar), (c) tabela (caso a caso).

# C3b: ponto-e-vírgula
rg -n "; " <draft>
# Filtrar matches em notação matemática $I(X_1, X_2; Y)$ e em citações [@a; @b].

# C3c: dois-pontos em texto corrido (exclui URLs, DOIs, headings, listas com label)
rg -n ":" <draft>
# Inspeção manual obrigatória.

# C4 + C8: superlativos, hype e frases mortas nos dois idiomas
rg -n -iE "highly|extremely|dramatically|drastically|radically|crucial|vital|essential|robust|novel|unprecedented|seminal|state-of-the-art|revolutioniz|pave the way|in order to|it is (well known|worth noting)|altamente|particularmente|extremamente|drasticamente|fundamental|inédito|sem precedentes|nos últimos anos" <draft>

# C4 (sinalização): causalidade, hedging forte e antropomorfismo
rg -n -iE "causes|caused by|leads to|proves|demonstrates conclusively|the model (understands|believes|thinks|learns to reason)|comprova|confirma que" <draft>
```

Apresentar contagem por convenção e os 5 primeiros exemplos de cada antes de editar.

### 2. Plano de edição

Mostrar lista de mudanças propostas ao usuário em formato compacto antes de aplicar, separando **o que será editado** do **o que será apenas sinalizado**. Para drafts longos (>500 linhas), aplicar por seção (`##`) e confirmar a cada bloco.

### 3. Aplicação

Edit por bloco. Após cada bloco, rodar audit local naquele bloco para confirmar que (a) violações sumiram, (b) nenhuma citação foi perdida, (c) nenhuma palavra-chave do conteúdo foi alterada.

### 4. Diff de citação (validação obrigatória)

Antes de marcar como concluído, contar o conjunto de citekeys antes e depois. **Devem ser iguais.**

```bash
# Conjunto de citekeys antes (do snapshot ou do git HEAD)
git show HEAD:<draft> | rg -o "@[a-z][a-z0-9.+_-]+" | sort -u > /tmp/cites_before
rg -o "@[a-z][a-z0-9.+_-]+" <draft> | sort -u > /tmp/cites_after
diff /tmp/cites_before /tmp/cites_after
```

Se houver diferença, **abortar e reportar** ao usuário antes de prosseguir.

### 5. Snapshot

Sugerir ao usuário criar snapshot versionado em `docs/qualification/versions/<data>-vN-escrita-cientifica.md` (ou equivalente do projeto) e atualizar README/index com o pointer.

## Escopo controlado por `inputs.scope`

- `full` (default). Aplica C1 a C8.
- `punctuation-only`. Apenas C3.
- `citations-only`. Apenas C1 e C2.
- `audit-only`. Reporta violações sem editar nada.

## Anti-padrões da skill

- ❌ Não traduzir o draft. O idioma resolvido escolhe as convenções, nunca converte o texto.
- ❌ Não reescrever introdução inteira porque parece "fraca". Isso é peer-review (use `/par:review critique`).
- ❌ Não acrescentar citação que não está no draft, mesmo se obviamente faltante. Apenas marcar `<!-- REVER: faltam refs sobre X -->`.
- ❌ Não reescrever claim causal, hedging ou antropomorfismo por conta própria — isso é substância, e a ação é sinalizar.
- ❌ Não traduzir termo técnico estabelecido (`missing modality`, `cross-modal`, `late fusion`, `foundation model`, `gated product-of-experts`). Em pt-BR ficam em inglês com itálico; em en-US, sem itálico.
- ❌ Não converter Markdown em outro formato. Manter Markdown puro.
- ❌ Não tocar em frontmatter YAML, lista de referências (`## Referências`) nem em blocos de código.

## Saída esperada

Após o passe, reportar ao usuário:

1. **Idioma resolvido** e a regra que o resolveu (flag, `pj_config.toml`, idioma do draft ou default).
2. **Removidos** — contagem antes/depois por convenção (C1 a C8).
3. **Sinalizados** — lista dos `<!-- REVER -->` deixados, com número de linha e motivo.
4. **Conjunto de citekeys** — deve ser idêntico antes e depois.
5. Sugestão de próximo passo (snapshot, `review critique`, export para DOCX).

## Integração com outras skills

- **Antes desta skill.** `/par:review critique` para revisão de conteúdo. Esta skill assume que o conteúdo já está estável.
- **Depois desta skill.** Pipeline de export `build_reference_docx.py` (ou equivalente) consome o draft com convenções aplicadas e gera DOCX/PDF com citações fundidas em campo único pelo normalizador.
- **Em paralelo.** `/par:wiki lint` se o draft é parte de um wiki ingerido.

## Notas de manutenção

- O **contrato de prosa** estampado no topo desta skill vem de `.github/scripts/prose_conventions.md` e é machine-owned: edite a fonte e rode `uv run python .github/scripts/gen_indexes.py`. O detalhamento C1–C8 vive aqui e deve ser mantido coerente com aquele resumo (ADR-0021).
- As listas lexicais de C4, C5 e C8 vivem aqui e não em arquivo externo. Adicionar termos quando recorrentes em revisões.
- A tabela de preservação em C3 deve ser mantida em sincronia com o normalizador de export. Se o normalizador mudar (e.g. passar a aceitar `[@a, @b]` como multi-cite), atualizar C2 conforme.
- Em projetos `pj_*` que usam o template do PAR, considerar copiar a skill `write` para `.claude/skills/<um-nome-seu>/` — um nome do PAR seria tirado pelo `prumo update` — se o usuário quiser uma variante customizada por projeto (por exemplo, manter superlativos específicos da área).

---
title: Contrato de prosa — idioma configurável (default en-US) e citação no fim do período
date: 2026-07-26
status: approved
tags: [scientific-writing, skills, idioma, citacao, gen-indexes, machine-owned-block]
---

# Contrato de prosa — idioma configurável e citação no fim do período

## Resumo executivo

Duas convenções de escrita científica do prumo estão erradas hoje. O idioma é implicitamente pt-BR e não há como escolher outro, o que exclui o alvo real do pesquisador (submissão a periódico anglo). E a regra de posição de citação, embora exista (C1), tem exceção aberta para autor-sujeito e uma heurística de audit que erra muito — o resultado é citação no meio de frase sobrevivendo ao passe editorial.

A correção introduz um **contrato de prosa** único: um bloco Markdown machine-owned (`<!-- prumo:prose:begin/end -->`) estampado por `gen_indexes.py` nas seis skills que produzem ou fiscalizam prosa, a partir de uma fonte única em `.github/scripts/prose_conventions.md`. O idioma passa a ser resolvido por cascata explícita com default `en-US` e trava por gênero (CEP/CONEP é sempre pt-BR). A regra de citação vira estrita, sem exceção. E a convenção de superlativo deixa de "atenuar" para **remover** — em escrita científica o intensificador sem número não existe.

Precedente direto: ADR-0009 (blocos delimitados machine-owned) e ADR-0019 (bloco de preflight gerado a partir do frontmatter). Este spec reusa exatamente o mesmo mecanismo, com um campo novo de manifesto.

## Contexto e problema

### P1 — idioma implícito e não configurável

`skills/scientific-writing/SKILL.md` assume pt-BR em toda parte sem jamais dizer isso: a tabela de superlativos da C4 é lexical pt-BR, os conectivos da C5 são pt-BR, o exemplo da C6 usa decimal com vírgula (`AUC 0,89`), e o anti-padrão manda manter termo técnico inglês em itálico — regra que só faz sentido escrevendo em português. As quatro skills `write-*` geram prosa sem nenhuma declaração de idioma. Não há chave de configuração, flag nem detecção.

O pesquisador-alvo escreve **paper em inglês** e **CEP/qualificação em português**, no mesmo `pj_*`, com o mesmo acervo. Hoje o plugin serve bem só o segundo caso.

Existe precedente de configuração de idioma no repo: `[paper_extract].language` em `pj_config.toml`, validado em `core/config.py` contra `{pt-BR, en, es}`. É config de **callout de extração**, não de prosa — contratos distintos que não devem se misturar.

### P2 — citação no meio do período

A C1 atual diz "antes do ponto final" mas abre exceção para autor como sujeito gramatical (`Liang et al. [@a] propõem três princípios.`), e o audit usa

```bash
Grep "\[@[^\]]+\][^.]*[a-záéíóúâêôãõç]\." <draft>
```

que só pega citação seguida de texto minúsculo acentuado antes de um ponto — perde citação seguida de maiúscula, de número, de vírgula, de parêntese, e qualquer coisa em inglês sem acento. Na prática a violação atravessa o passe.

### P3 — superlativo atenuado em vez de removido

A C4 atual manda substituir `crítica/vital/essencial` por `relevante/necessária` e `robusto` por `consistente`. Isso troca um intensificador por outro mais discreto, mas mantém a estrutura retórica que a escrita científica moderna não usa: adjetivo de força sem número. O padrão correto é remover o intensificador ou substituí-lo pelo valor medido.

### Restrições duras

- **ADR-0019:** `scientific-writing` e `peer-review` são julgamento puro (`requires: []`) e rodam em qualquer superfície Claude, sem CLI. Nenhuma solução pode introduzir dependência de CLI nessas duas.
- **Armadilha do repo:** blocos gerados nunca são editados à mão; edita-se a fonte e roda-se o gerador (`gen_indexes.py`, com `--check` no CI).
- **`skills/` e `templates/`** são force-included no wheel (`pyproject.toml`) e resolvidos por `core/paths.py:find_resource` — mover qualquer um exige atualizar os dois lados.
- **Escrita forward-only:** campo de schema/manifesto nunca é removido nem renomeado.

## Decisões

| # | Decisão | Alternativas descartadas |
|---|---|---|
| D1 | Convenção compartilhada como **bloco estampado** `prumo:prose`, fonte única em `.github/scripts/prose_conventions.md` | (a) ponteiro + `prumo write conventions --lang` resolvendo a cascata em código: quebraria `requires: []` de `scientific-writing`/`peer-review`, regredindo ADR-0019; (b) cada skill referenciando `/prumo-assist:scientific-writing`: convenção duplicada à mão em 6 arquivos |
| D2 | **Dois níveis de detalhe.** O bloco estampado é o contrato compacto (7 itens); o detalhamento completo (C1–C8, tabelas por idioma, greps de audit, fluxo) vive só em `scientific-writing/SKILL.md` | Estampar tudo em todas: infla 6 arquivos com material que só a skill fiscalizadora executa |
| D3 | **Cascata de idioma** com default `en-US` e trava por gênero | Default pt-BR (status quo, não serve o caso paper); perguntar sempre (interação a mais em todo uso) |
| D4 | **C1 estrita, sem exceção** de autor-sujeito; contraste entre fontes no mesmo período é sinalizado, não editado | Manter narrative citation; só sinalizar sem nunca mover |
| D5 | **Superlativo removido, não atenuado**; claim descalibrado (causalidade, hedging, antropomorfismo) é sinalizado com `<!-- REVER -->`, nunca reescrito | Reescrever hedging automaticamente: cruza a fronteira forma/substância e invade o peer-review |
| D6 | Templates **sem variante por locale** | `template.<lang>.md`: o esqueleto de `write-paper` já é en-US e os comentários são instrução ao modelo, não saída |

## Arquitetura

### Fonte única e estampagem

```text
.github/scripts/prose_conventions.md  ← fonte canônica (3 fragmentos delimitados)
        │
        ├── prose:lang-free   ─┐
        ├── prose:lang-locked ─┤ render_prose(manifest) escolhe 1 dos 2 + core
        └── prose:core        ─┘
                │
      .github/scripts/gen_indexes.py  ← render_prose() + stamp_block()
                │
                ▼
   <!-- prumo:prose:begin --> … <!-- prumo:prose:end -->
   estampado em 6 SKILL.md, logo após o bloco de preflight
```

`SkillManifest` (`core/skills.py`) ganha dois campos:

```yaml
prumo:
  prose: true            # opta pelo bloco estampado
  locale_lock: pt-BR     # opcional; só write-projeto-cep
```

- `prose` deve ser booleano; qualquer outro tipo levanta `ManifestError`.
- `locale_lock` deve estar em `WRITING_LANGUAGES` (importado de `core/config.py` — fonte única do vocabulário de idioma de escrita) e só é aceito quando `prose: true`; caso contrário, `ManifestError`.
- Ambos entram na lista de chaves conhecidas do parser (hoje `extra_keys` captura desconhecidas para forward-compat).

Skills que optam: `scientific-writing`, `write-paper`, `write-scientific`, `write-statistics`, `write-projeto-cep` (locked pt-BR), `peer-review`.

A estampagem é genérica: `stamp_block(text, tag, body, *, where, after)` serve preflight e prosa — `after` é como a ordem entre blocos é declarada (o de prosa passa o fim do preflight para nascer embaixo dele), com fallback no H1 e abort sem âncora. `render_skill_blocks(manifest)` devolve `(tag, body, after)` por bloco, e corpo vazio significa "este bloco não deve existir", que `strip_block` remove — assim uma skill que deixa de declarar `prose:` não fica com bloco órfão que o `--check` chamaria de "em dia". Em `main()`, os blocos compõem sobre o mesmo texto antes do único `_sync`.

O enforcement é `gen_indexes.py --check` no CI, que já roda.

### Cascata de idioma

Avaliada nesta ordem, e a skill **declara em voz alta** qual idioma resolveu e por qual regra:

1. **Trava de gênero** (`prumo.locale_lock`). `write-projeto-cep` é `pt-BR`: CEP/CONEP, Plataforma Brasil e TCLE são artefatos regulatórios brasileiros. Pedido explícito em outro idioma recebe aviso e a skill escreve em pt-BR mesmo assim.
2. **Pedido explícito.** `--lang pt-BR|en-US` ou linguagem natural ("escreve em inglês").
3. **`[writing].language`** de `.claude/pj_config.toml` do projeto.
4. **Idioma do texto alvo**, quando já existe (draft do passe editorial, `--seed`, `--into`).
5. **Default `en-US`.**

**Onde cada degrau roda.** Os degraus 1, 2, 3 e 5 são determinísticos e vivem em `compose.resolve_language`, exposto por `prumo write prep --json` como `language` + `language_source` — as quatro `write-*` (todas `requires: [cli]`) consomem o valor pronto em vez de recompor a cascata em prosa, o que de quebra fecha o buraco de `[writing].language` só ser validado no caminho de extração de paper. A trava de gênero sai do próprio `skills/write-<kind>/SKILL.md` via `parse_skill_file`, não de um mapa novo em `compose.py`. O degrau 4 fica com a skill nos dois casos: depende de ler prosa, não de consultar índice. `scientific-writing` e `peer-review` mantêm a cascata em prosa porque não têm CLI para consultar (ADR-0019), e o gerador emite variantes distintas do item de idioma conforme o manifesto (`lang-locked` > `lang-cli` > `lang-free`).

**Regra de segurança transversal:** nenhuma skill de prosa traduz. Se o idioma resolvido divergir do idioma do texto existente, a skill avisa e adota o do texto. É o que impede o default novo de converter draft pt-BR em passe editorial.

### Configuração

`core/config.py`:

```python
WRITING_LANGUAGES = frozenset({"pt-BR", "en-US"})

DEFAULTS = {
    ...,
    "writing": {"language": "en-US"},
}
```

Validação em `_validate`, com mensagem citando os válidos, no mesmo molde de `paper_extract.language`. Deliberadamente **separada** de `VALID_LANGUAGES` (`{pt-BR, en, es}`, do callout de extração): são dois contratos, e fundi-los amarraria a evolução de um ao outro.

`templates/pj_base/.claude/pj_config.toml` ganha a seção documentada. `templates/pj_base/CLAUDE.md` passa a distinguir idioma de **interação** (pt-BR) de idioma de **escrita científica** (config, default en-US) — hoje a linha única "Idioma: **pt-BR**" ficaria contraditória.

## O contrato de prosa (corpo do bloco)

Sete itens, versão compacta:

1. **Idioma** — a cascata acima, mais a proibição de traduzir.
2. **Citação no fim do período** — `[@citekey]` imediatamente antes do terminador (`.`, `?`, `!`). Sem exceção de autor-sujeito. Duas fontes para claims distintos = dois períodos.
3. **Agrupamento** — mesmo colchete separado por `;` (`[@a; @b; @c]`); nunca `[@a], [@b]`.
4. **Pontuação** — sem ` — `, `:` ou `;` em texto corrido, nos dois idiomas.
5. **Sem superlativo** — intensificador sem número é removido; `significant` só com p ou IC no mesmo período.
6. **Voz** — pt-BR impessoal/passiva; en-US aceita `we` ativo em Methods/Results (AMA/ICMJE). Methods e Results em pretérito, estado da arte no presente.
7. **en-US** — ortografia americana, vírgula serial, decimal com ponto e milhar com vírgula, pontuação dentro das aspas, numerais exceto em início de período, termo técnico inglês sem itálico.

## Convenções completas (`scientific-writing/SKILL.md`)

### C1 — citação sempre antes do terminador (estrita)

| Situação | Ação |
|---|---|
| `Modelos combinados [@a] atingem alto desempenho.` | mover → `... alto desempenho [@a].` |
| `Liang et al. [@a] propõem três princípios.` | reescrever → `Três princípios foram propostos por Liang et al. [@a].` |
| Duas fontes, claims distintos, mesmo período | quebrar em dois períodos |
| Contraste explícito (`enquanto X [@a] encontrou…, Y [@b] não`) | **não editar**; marcar `<!-- REVER: citação em meio de período; quebrar em dois? -->` |

A regra cobre também a **citação narrativa** (`@a`, sem colchetes), que o repo reconhece como forma Pandoc de primeira classe: é mid-período por construção, já que o citekey ocupa a posição de sujeito, então convertê-la para a forma marcada no fim do período é a própria aplicação de C1. O audit ganha um segundo grep, em PCRE2, que pula o miolo dos colchetes com `(*SKIP)(*F)` para não acusar o `@b` de `[@a; @b]` e descarta e-mail pela classe à esquerda.

Preservações: legendas de figura/tabela, itens de lista (a citação fecha o item), lista de referências, blocos de código.

Audit novo — superconjunto conservador, triagem manual descarta preservações:

```bash
rg -n "\[@[^]]+\][^.]" <draft>
```

### C2 — agrupamento

Inalterada: `[@a; @b; @c]` num colchete, antes do ponto. Razão (Pandoc/CSL renderiza como citação múltipla única) mantida.

### C3 — pontuação

Inalterada em regra, com coluna en-US na tabela de refraseamento (`There are two factors: A and B` → `There are two factors, namely A and B.`). É house style, não traço do português — vale nos dois idiomas.

### C4 — claim calibrado à evidência (reescrita)

**Remoção mecânica** (a skill edita — é forma):

| Padrão | Ação |
|---|---|
| `highly accurate`, `altamente preciso` | remove o intensificador; se o número está no texto, troca pelo número |
| `improved considerably` | `improved AUC from 0.81 to 0.89` quando o dado existe; senão `improved` |
| `critical / vital / essential / crucial / fundamental` | remove, ou `relevant` / `necessary` |
| `robust`, `state-of-the-art`, `powerful` sem métrica | remove |
| `revolutionize`, `pave the way`, `shed light on`, `sem precedentes`, `definitivo` | remove |
| `significant` fora de estatística | remove; em estatística, exige p ou IC no mesmo período |
| `novel / inédito / seminal` | remove, salvo verificável e primeira ocorrência empírica |

**Sinalização** (a skill NÃO edita — é substância; marca `<!-- REVER -->`):

- Linguagem causal em desenho associacional (`causes`, `leads to`, `melhora o desfecho` em coorte observacional).
- Hedging descalibrado (`proves`, `demonstrates conclusively`, `confirma`) para além do que o desenho sustenta.
- Antropomorfismo de modelo (`the model understands / believes / learns to reason`).
- Quantificador vago (`many studies`, `vários trabalhos`) sem número nem citação.

### C5 — coesão

Conectivos por idioma (en-US: *first, second, in contrast, given that, therefore, however, moreover*). Heurística de quebra (>4 vírgulas e >60 palavras) inalterada.

### C6 — voz e tempo, por idioma

| | pt-BR | en-US |
|---|---|---|
| Voz | impessoal/passiva (`avaliou-se`, `foram coletados`); evitar "nós" | `we` ativo permitido em Methods/Results (AMA/ICMJE); evitar passiva desnecessária |
| Methods | pretérito ou presente impessoal | past tense |
| Results | pretérito | past tense |
| Intro/Discussão | presente para estado da arte | present tense para estado da arte |

### C7 — padrão en-US (novo, só quando o idioma resolvido é en-US)

Ortografia americana (*analyze, randomize, behavior, tumor, center, fiber, modeling, labeled, aging*); vírgula serial; decimal com ponto e milhar com vírgula; pontuação final dentro das aspas; `%` colado ao número e unidades SI com espaço não-quebrável; `that` restritivo sem vírgula e `which` não-restritivo com vírgula; numerais para todos os números exceto início de período (AMA); **termo técnico inglês sem itálico** — o itálico é regra de pt-BR, e o anti-padrão atual passa a ser condicionado ao idioma.

### C8 — economia e precisão lexical (novo, mecânico, os dois idiomas)

- Frases mortas: `in order to` → `to`; `due to the fact that` → `because`; `it is well known that`, `it is worth noting that`, `In recent years,`, `Nos últimos anos,`, `É sabido que` → remover.
- Desnominalização: `performed an evaluation of` → `evaluated`; `fez a avaliação de` → `avaliou`.
- Um termo por conceito, sem variação elegante — fixa a primeira ocorrência e marca as demais.
- Abreviatura definida na primeira ocorrência; sem abreviatura usada uma única vez.

Audit novo:

```bash
rg -n -iE "highly|extremely|dramatically|drastically|radically|crucial|vital|essential|robust|novel|unprecedented|seminal|state-of-the-art|revolutioniz|pave the way|in order to|it is (well known|worth noting)|altamente|extremamente|drasticamente|fundamental|inédito|sem precedentes|nos últimos anos" <draft>
```

### Saída esperada

O relatório final separa **removidos** (contagem por convenção) de **sinalizados** (lista com número de linha), para o usuário distinguir de relance o que a skill mexeu do que devolveu para decisão dele. Mais o diff de citekeys (idêntico antes/depois, hard-fail) e o idioma resolvido com a regra que o resolveu.

## Mudanças por arquivo

| Arquivo | Mudança |
|---|---|
| `.github/scripts/prose_conventions.md` | **novo** — fonte do bloco, 3 fragmentos delimitados |
| `.github/scripts/gen_indexes.py` | `render_prose()`, `stamp_block()`/`strip_block()` genéricos (absorvem `stamp_preflight`), `render_skill_blocks()` no loop de skills |
| `src/prumo_assist/core/skills.py` | campos `prose: bool` e `locale_lock: str \| None` + validação |
| `src/prumo_assist/core/config.py` | `WRITING_LANGUAGES`, `DEFAULTS["writing"]`, validação |
| `skills/scientific-writing/SKILL.md` | C1 estrita, C4 reescrita, C7 e C8 novos, C3/C5/C6 por idioma, audit novo, `prose: true`, `--lang` |
| `skills/write-{paper,scientific,statistics}/SKILL.md` | `prose: true`, `inputs.lang`, `--lang` no argument-hint |
| `skills/write-projeto-cep/SKILL.md` | `prose: true`, `locale_lock: pt-BR` |
| `skills/peer-review/SKILL.md` | `prose: true` (avalia contra o contrato; não reescreve) |
| `templates/pj_base/.claude/pj_config.toml` | seção `[writing]` documentada |
| `templates/pj_base/CLAUDE.md` | separa idioma de interação de idioma de escrita |
| `src/prumo_assist/domains/write/compose.py` | `resolve_language()`, `locale_lock()`, `WritePrep.language`/`language_source` |
| `src/prumo_assist/domains/write/cli.py` | `prep --lang` + `language`/`language_source` no JSON; corrige `list-templates` para a chain real (adjacente) |
| `docs/adr/adr-0021-idioma-de-escrita-cascata-e-default.md` | registra a decisão de idioma |
| `README.md`, `skills/start/SKILL.md`, `docs/adr/_index.md` | regenerados |

## Testes

- `tests/unit/core/test_config.py` — default `writing.language == "en-US"`; override válido; valor inválido levanta `ConfigError` citando os válidos; `[writing]` ausente em config legado cai no default.
- `tests/unit/core/test_skills.py` — `prose` booleano parseado; tipo errado levanta; `locale_lock` válido parseado; valor fora de `WRITING_LANGUAGES` levanta; `locale_lock` sem `prose: true` levanta; skill sem os campos mantém defaults (`False`, `None`).
- `tests/unit/test_gen_indexes.py` — `render_prose` produz variante livre vs travada (com o locale interpolado); `stamp_block` insere após a âncora, cai no H1 sem ela, é idempotente e falha sem âncora nenhuma; `strip_block` remove bloco órfão e é no-op quando não há bloco; toda skill com `prose: true` carrega o bloco no `SKILL.md` e nenhuma outra carrega (guarda de repo, no molde de `test_guidelines_present.py`).
- `tests/unit/write/` — `list-templates` reporta o caminho que `resolve_template` de fato usa.

## Riscos e migração

**Projetos `pj_*` existentes não têm `[writing]`** e caem no default `en-US`. O passo 4 da cascata (detecção) cobre o caso comum — passe editorial sobre draft pt-BR continua pt-BR, e a regra de não-tradução é hard. O caso descoberto é geração do zero em projeto antigo sem a chave, que sairá em inglês. Mitigações: `pj_base` nasce com a chave explícita; a skill sempre declara o idioma resolvido antes de escrever; CHANGELOG marca a mudança de comportamento.

**Divergência entre bloco e detalhamento.** O bloco compacto e o C1–C8 completo podem divergir com o tempo. O `--check` do CI garante bloco↔fonte, não bloco↔`scientific-writing`. Aceito: `scientific-writing` é a skill que fiscaliza, e a nota de manutenção dela passa a apontar `.github/scripts/prose_conventions.md` como fonte do contrato.

## Release

Bump **MINOR** (0.64.0): pré-1.0 reserva MINOR para breaking, e mudar o idioma default de saída é mudança de comportamento observável pelo consumidor — entra no CHANGELOG com "⚠ Breaking". Reorganização de docs não conta, mas skills e config contam.

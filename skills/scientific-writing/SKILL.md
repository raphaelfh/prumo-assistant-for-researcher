---
name: scientific-writing
description: "Aplica convenções editoriais de escrita científica em drafts Markdown/Quarto/Pandoc — pontuação (sem travessão / dois-pontos / ponto-e-vírgula em texto corrido), posição de citação (antes do ponto), agrupamento de múltiplas citações num único colchete separadas por ponto-e-vírgula ([@a; @b]), atenuação de superlativos, coesão entre períodos. Preserva conteúdo (forma, não substância)."
when_to_use: |
  Quando o usuário pedir "aplica as convenções", "reescreva no padrão científico",
  "limpa a pontuação", "arruma as citações", "tira os travessões", "padroniza
  pra banca", ou ao final de redigir uma seção antes de submeter ao peer-review.
  NÃO é peer review nem normalizador de export.
argument-hint: "<draft-path> [--scope full|punctuation-only|citations-only|audit-only]"
allowed-tools: Read Edit Grep Glob Bash(git *) Bash(rg *)
prumo:
  version: 1.0.0
  schema: ScientificWritingPass/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~3-10k tokens (depende do tamanho da seção)
  inputs:
    draft_path: required
    scope: optional  # 'full' (default) | 'punctuation-only' | 'citations-only' | 'audit-only'
  requires: []
---

# Scientific Writing — passe editorial de escrita científica formal

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
<!-- prumo:preflight:end -->

Você é um editor de texto científico para um pesquisador clínico de pós-graduação. Aplique as convenções abaixo no draft do usuário, **preservando integralmente o conteúdo, os argumentos, as citações e os números**. O objetivo é forma, não substância.

## Princípios

1. **Forma sobre substância.** Esta skill não reescreve argumento, não acrescenta nem remove citação, não altera dado numérico. Apenas reformata a expressão linguística.
2. **Conservadora por default.** Quando uma frase é ambígua, prefira deixar como está e marcar com comentário inline `<!-- REVER: ... -->` em vez de adivinhar.
3. **Diff legível.** Edite com `Edit` em blocos pequenos para que o usuário consiga revisar a diff em vez de receber rewrite total. Use `Write` apenas se a refatoração for >50% do arquivo.
4. **Idempotente.** Rodar a skill duas vezes não deve mudar nada na segunda execução.

## Pressupostos

- O usuário forneceu caminho de arquivo Markdown/Quarto/Pandoc. Se não, peça.
- Citações no draft seguem a sintaxe Pandoc: `[@citekey]` (bracketed; múltiplas no mesmo colchete separadas por `;` — `[@a; @b]`). Legado `[[@citekey|alias]]` é aceito na leitura/export, mas não escreva novo.
- O draft já passou por revisão de conteúdo (esta skill não é peer-review).

## Convenções aplicadas

### C1. Citações ao final do período

**Regra.** Toda citação `[@citekey]` deve aparecer **antes do ponto final** do período em que sustenta uma afirmação. Não em meio de frase.

❌ Errado.
> Modelos combinados [@smith2025review] atingem alto desempenho quando todas as modalidades estão presentes.

✅ Correto.
> Modelos combinados atingem alto desempenho quando todas as modalidades estão presentes [@smith2025review].

**Exceção.** Quando a citação é sujeito gramatical, mantenha posição.
> Liang et al. [@liang2024foundations] propõem três princípios.

### C2. Múltiplas citações agrupadas no mesmo colchete

**Regra.** Quando várias fontes sustentam a mesma afirmação, agrupe-as num único colchete separadas por `;`: `[@a; @b; @c]`. Não escreva colchetes separados nem vírgulas entre citações, todas antes do ponto final.

❌ Errado (colchetes separados).
> ...premissa raramente sustentada [@a], [@b], [@c].

✅ Correto (agrupadas num único colchete).
> ...premissa raramente sustentada [@a; @b; @c].

**Razão.** A sintaxe Pandoc trata `[@a; @b; @c]` como uma citação múltipla única, que o Pandoc/CSL (e o pipeline `build_reference_docx.py`) renderiza como `(Smith, 2024; Jones, 2025; ...)` no DOCX/PDF. Colchetes separados (`[@a], [@b], [@c]`) geram citações independentes, que aparecem como `(Smith, 2024), (Jones, 2025)` — perdendo o agrupamento esperado.

### C3. Sem travessão, dois-pontos ou ponto-e-vírgula no texto corrido

**Regra.** No corpo de parágrafos (texto corrido), não use ` — `, ` – `, `:` ou `;`. Reescreva usando vírgula, ponto, parênteses ou conectivos.

| Padrão inadequado | Refraseamento sugerido |
|---|---|
| `X — explicação — continua` | `X (explicação) continua.` ou `X. Explicação. Continua.` |
| `Há dois fatores: A e B` | `Há dois fatores, a saber, A e B.` ou `Há dois fatores. O primeiro é A. O segundo é B.` |
| `**Hipótese:** o ganho...` | `**Hipótese.** O ganho...` |
| `X; Y; Z` (lista) | `X. Y. Z.` ou `X, Y e Z.` |
| `X; entretanto, Y` | `X. Entretanto, Y.` |

**Preservações.** Esses caracteres ficam em:
- Frontmatter YAML.
- Cabeçalhos e células de tabela.
- URLs, DOIs e identificadores.
- Títulos de papers citados na lista de referências (texto original do paper, não editar).
- Notação matemática inline e display (`$I(X_1, X_2; Y)$`, `$\{a; b\}$`).
- Linhas de cabeçalho `##` quando o subtítulo segue padrão acadêmico (e.g. `## Resumo: contextualização e objetivo`).

### C4. Atenuação de superlativos

**Regra.** Substitua intensificadores não suportados por evidência empírica. Manter "significativo" apenas no sentido estatístico (com p-valor associado).

| Substitua | Por |
|---|---|
| altamente, particularmente, extremamente, drasticamente, radicalmente | (remover) ou "consideravelmente" se quantificado |
| crítica, vital, essencial, fundamental | "relevante", "necessária" |
| robusto (sem métrica) | "consistente", remover |
| seminal | "de referência" |
| inédito | manter apenas se for o caso e a primeira ocorrência empírica em revisão da literatura |
| sem precedentes, definitivo | (remover) |

### C5. Coesão entre períodos

**Regra.** Cada parágrafo deve ter um eixo temático. Períodos curtos conectados por conectivos explícitos (em primeiro lugar, em segundo lugar, por outro lado, dado que, portanto, contudo). Evitar parágrafos de período único excessivamente longo.

**Heurística.** Se um período tem mais de 4 vírgulas e mais de 60 palavras, considerar quebrar em dois.

### C6. Voz e tempo verbal

- **Métodos** em pretérito (foi avaliado, foram coletados) ou presente (avalia-se, coleta-se).
- **Resultados** em pretérito (atingiu AUC 0,89, observou-se).
- **Discussão e introdução** em presente quando descreve o estado da arte (a literatura documenta, modelos atingem).
- Evitar "nós" no texto formal (preferir voz passiva ou impessoal). Manter "nós" apenas quando o grupo de pesquisa é o sujeito de uma escolha de design.

## Fluxo

### 1. Audit (sempre primeiro)

Rodar audit antes de aplicar mudança. Reportar contagem de cada violação.

```bash
# C1: citações no meio do período (heurística — citação seguida de palavra e depois ponto)
Grep "\[@[^\]]+\][^.]*[a-záéíóúâêôãõç]\." <draft>

# C2: colchetes de citação adjacentes ([@a] [@b]) ou vírgula entre citações ([@a], [@b]) — deveriam estar agrupados num único colchete ([@a; @b])
Grep "\]\s*,?\s*\[@" <draft>

# C3a: travessões em texto corrido (excluir tabelas e refs)
Grep " — " <draft>
# Inspecionar manualmente cada hit e classificar como (a) texto corrido (corrigir),
# (b) título de paper na lista de refs (preservar), (c) tabela (caso a caso).

# C3b: ponto-e-vírgula
Grep "; " <draft>
# Filtrar matches em notação matemática $I(X_1, X_2; Y)$.

# C3c: dois-pontos em texto corrido (exclui URLs, DOIs, headings, listas com label)
Grep ":" <draft>
# Inspeção manual obrigatória.

# C4: superlativos comuns
Grep -iE "altamente|particularmente|extremamente|drasticamente|radicalmente|seminal|sem precedentes|definitivo" <draft>
```

Apresentar contagem por convenção e os 5 primeiros exemplos de cada antes de editar.

### 2. Plano de edição

Mostrar lista de mudanças propostas ao usuário em formato compacto antes de aplicar. Para drafts longos (>500 linhas), aplicar por seção (`##`) e confirmar a cada bloco.

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

- `full` (default). Aplica C1 a C6.
- `punctuation-only`. Apenas C3.
- `citations-only`. Apenas C1 e C2.
- `audit-only`. Reporta violações sem editar nada.

## Anti-padrões da skill

- ❌ Não reescrever introdução inteira porque parece "fraca". Isso é peer-review (use `/prumo-assist:peer-review`).
- ❌ Não acrescentar citação que não está no draft, mesmo se obviamente faltante. Apenas marcar `<!-- REVER: faltam refs sobre X -->`.
- ❌ Não traduzir termo técnico estabelecido (`missing data`, `cross-modal`, `late fusion`, `foundation model`, `gated product-of-experts` ficam em inglês com itálico).
- ❌ Não converter Markdown em outro formato. Manter Markdown puro.
- ❌ Não tocar em frontmatter YAML, lista de referências (`## Referências`) nem em blocos de código.

## Saída esperada

Após o passe, reportar ao usuário:

1. Contagem antes/depois de cada convenção (C1 a C5).
2. Conjunto de citekeys (deve ser idêntico antes e depois).
3. Lista de marcadores `<!-- REVER -->` deixados para inspeção humana.
4. Sugestão de próximo passo (snapshot, peer-review, export para DOCX).

## Integração com outras skills

- **Antes desta skill.** `/prumo-assist:peer-review` para revisão de conteúdo. Esta skill assume que o conteúdo já está estável.
- **Depois desta skill.** Pipeline de export `build_reference_docx.py` (ou equivalente) consome o draft com convenções aplicadas e gera DOCX/PDF com citações fundidas em campo único pelo normalizador.
- **Em paralelo.** `/prumo-assist:wiki-lint` se o draft é parte de um wiki ingerido.

## Notas de manutenção

- A lista de superlativos em C4 vive aqui e não em arquivo externo. Adicionar termos quando recorrentes em revisões.
- A tabela de preservação em C3 deve ser mantida em sincronia com o normalizador de export. Se o normalizador mudar (e.g. passar a aceitar `[@a, @b]` como multi-cite), atualizar C2 conforme.
- Em projetos `pj_*` que usam o template do prumo-assist, considerar copiar este SKILL.md para `.claude/skills/scientific-writing/` se o usuário quiser uma variante customizada por projeto (por exemplo, manter superlativos específicos da área).

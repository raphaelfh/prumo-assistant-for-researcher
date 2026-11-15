---
title: Painel "Projeto" — as etapas do estudo num mod fino sobre o `prumo status`
date: 2026-11-14
status: approved
tags: [mods, status, painel, mcp, etapas, adr-0039, adr-0017, adr-0029]
---

# Painel "Projeto": as etapas do estudo num mod fino sobre o `prumo status`

## Problema

O mod do PAR (ADR-0039) tem duas peças. A seção da pergunta do estudo no system prompt
(`hooks/mods/picot.ts`) funciona e fica como está. O painel "Revisão do manuscrito"
(`hooks/mods/review.tsx`) tem quatro defeitos:

1. **Lógica duplicada (Princípio I).** O painel conta marcas CriticMarkup com regex própria e
   lê `page` do `events.yaml` com outra regex. O Python já faz as duas coisas com
   `core/criticmarkup.parse` e `ReviewEventsFile` em `src/par/status.py`. Quando o formato
   mudar, painel e CLI vão discordar.
2. **Só aparece no fim.** Abre apenas com `reviews/` no disco. Quem mais precisa de guia
   (bibliografia vazia, pergunta aberta) não vê nada.
3. **Custo por turno.** A cada `turn.complete`: um `connect` e duas chamadas MCP por página,
   mesmo sem mudança.
4. **Ruído.** Até 30 botões por página; a decisão que importa é uma: o próximo passo.

O `prumo status` já sabe onde o estudo está e qual a próxima frase (`_next`), mas ninguém o
vê sem perguntar, e a cadeia fixa de `_next` não conhece protocolo nem entrega.

Defeito achado de passagem: `_drafts` exclui só `protocol.md`, então os esqueletos que o
módulo `protocol` copia para `writing/` (`projeto-cep.md`,
`statistical_analysis_plan_skeleton.md`) contam como draft, e um escopo com o módulo nunca
recebe a sugestão de `write manuscript`.

## Decisão

Uma fonte de cálculo (Python) e um painel que só desenha.

### 1. Etapas em `src/par/status.py`

Uma tupla de etapas, cada uma uma função pura `(pj_root, sinais já lidos) -> Stage | None`
(`None` = a etapa não se aplica a este projeto). Sem registro, sem plugin de etapa, sem
arquivo de configuração (Princípios VI e VIII).

```python
@dataclass(frozen=True)
class Stage:
    id: str            # "question", "library", ... (identificador estável, inglês)
    title: str         # rótulo pt-BR
    state: str         # "done" | "current" | "attention" | "todo"
    summary: str       # uma linha, pt-BR
    next: NextStep | None  # só a etapa "current" e as "attention" trazem
    scope: str | None = None
```

| id | Título | Aparece quando | `done` quando | `summary` |
|---|---|---|---|---|
| `question` | Pergunta | sempre | `read_question` valida | tipo do estudo e framework, ou o erro de validação |
| `library` | Bibliografia | sempre | `.bib` existe e não é placeholder | `N entradas · sync AAAA-MM-DD` |
| `reading` | Leitura | sempre | nenhum extract pendente | `X sem extract · Y sem PDF · Z desatualizados` |
| `protocol` | Protocolo | `writing/protocol.md` existe no escopo (âncora do `_module.toml`) | SAP e projeto CEP diferem do esqueleto do scaffold (`protocol.md` fica de fora: é documento vivo, e o bloco da pergunta já o altera) | quais ainda são esqueleto |
| `writing` | Escrita | sempre, uma por escopo | o escopo tem draft | `N draft(s)` |
| `review` | Revisão | o escopo tem `reviews/studies__<slug>__*` | zero eventos ambíguos | `E eventos ambíguos · M marcas aguardando apply` |
| `delivery` | Entrega | o escopo tem draft | existe docx exportado pela regra de nome default de `write/export.py` | caminho e data do último docx |

Regras:

- **Uma regra para "agora".** A etapa `current` é exatamente a que `_next` escolhe; `_next`
  passa a ser "a primeira etapa não `done`, na ordem da tupla", e a ordem da tupla é a ordem
  da tabela. CLI, skill `start` e painel concordam por construção.
- **`attention`** = etapa anterior à `current` com pendência que não bloqueia (hoje: extract
  desatualizado). Traz `next` próprio. Etapas depois da `current` são `todo`.
- **"Diferente do esqueleto"** compara o arquivo com o template empacotado
  (`templates/modules/protocol/...`, resolvido por `core/paths.py`). Sem heurística de
  conteúdo.
- **Esqueletos não são draft.** `_NOT_DRAFTS` passa a ser derivado dos arquivos de
  `writing/` dos módulos (`templates/modules/*/docs/studies/__scope__/writing/*`), não uma
  lista à mão.
- **Ordem `question` antes de `library`.** Em pesquisa em saúde a pergunta orienta a busca;
  hoje `_next` sugere a bibliografia primeiro. Muda o primeiro passo sugerido a projeto novo
  (ver Consequências).

### 2. Schema: `ProjectStatus/v1` ganha `stages`

Campo novo `stages: list[Stage]` no JSON de `status_to_dict`. Só acrescenta (Princípio IV);
`next` continua igual a `stages[current].next`. `render_status` passa a imprimir as etapas
(uma linha cada, com ✓ ● ! ○) antes da frase do próximo passo.

### 3. Ferramenta MCP `project_status(pj_path)`

Só leitura, em `src/par/mcp_server.py`, no padrão dos `paper_*` (ADR-0017): devolve
`status_to_dict(project_status(Path(pj_path), registry=...))`. Fora de um `pj_*`, devolve o
erro de `PjRootNotFoundError` com o comando de correção.

### 4. Mod: `hooks/mods/project.tsx` substitui `review.tsx`

- Comando `/projeto`; painel `par-projeto`, título "Projeto". Abre sozinho no
  `session.start` quando o cwd está num `pj_*` (a ferramenta não devolve erro).
- Estado num `atom` (`shape: 'project-1'`) com o JSON da ferramenta, sem transformação.
- Desenho: uma linha por etapa (`✓ Pergunta  coorte · PICOT`). Só a `current` vem aberta,
  com o `summary` e **um** botão que faz `$.prompt.fill` com `next.say`. Etapas `attention`
  têm um botão secundário igual. Tocar numa etapa `done` abre o `summary` dela; nada mais.
- `$.ui.status("Etapa 3/6 · Leitura")` mantém a etapa visível com o painel fechado.
- Atualiza no `session.start`, no `turn.complete` e no botão "Atualizar": **uma** chamada
  MCP por atualização.
- Servidor fora do ar: uma linha vermelha com "rode `/par:start`" (como hoje).
- Saem: `pendingMarks`, `pageOf`, `MARK_RE`, os botões por marca e o comando `/revisao`.
  A lista de marcas de uma página continua a um prompt de distância: o botão da etapa
  `review` diz a frase do `review reconcile`, que já mostra as marcas.
- `types/index.d.ts`: `ReviewSnapshot`/`ReviewPage`/`ReviewMark` dão lugar a
  `ProjectSnapshot` (o JSON de `ProjectStatus/v1` mais `error?`).

### 5. ADR

ADR nova (MADR minimal) que substitui o item 3 da ADR-0039: o painel de revisão vira o painel
de etapas do projeto, e a lógica de etapas mora só no Python.

## Fora de escopo

- Guardar progresso em arquivo: tudo é derivado do disco a cada leitura (ADR-0029).
- Configuração de etapas por projeto (`.claude/stages.toml` ou afim): só com caso real.
- Etapas para os módulos `code`, `data`, `ml`, `notebooks`: sem sinal de "feito" definido.
- Datas, prazos, Gantt, editar pelo painel. O painel sugere; quem age é a skill.
- Wiki como etapa: é transversal, não uma fase do estudo.

## Alternativas rejeitadas

- **Manter `review.tsx` e somar um painel de etapas**: dois painéis, duas fontes de verdade.
- **Etapas calculadas no TypeScript lendo o disco**: repete o defeito 1 em escala maior.
- **Chamar o CLI (`prumo status --json`) do mod**: o mod deixaria de depender só do servidor
  MCP que o plugin já sobe (ADR-0039, item 4).
- **Etapas declaradas em cada `_module.toml`**: flexível demais para 7 etapas; a tupla em
  Python é mais curta e testável. Rever se surgir o quarto módulo com etapa.

## Testes

- `tests/unit/test_status.py`, com projetos `pj_exemplo` sintéticos montados em `tmp_path`:
  - projeto recém-criado: `question` é `current`, demais `todo`;
  - pergunta fechada e `.bib` placeholder: `library` é `current`;
  - extract desatualizado com escopo sem draft: `reading` é `attention`, `writing` é `current`;
  - sem o módulo `protocol`: não há etapa `protocol`;
  - esqueletos do `protocol` em `writing/` não contam como draft;
  - `next` do JSON é igual ao `next` da etapa `current`;
  - JSON antigo continua com `library`, `extracts`, `question`, `picot`, `scopes`, `next`.
- `tests/unit/test_mcp_server.py`: `project_status` dentro e fora de um `pj_*`.
- `tests/mods/mods.test.tsx` (`claude plugin test .`): o painel desenha uma linha por etapa,
  um botão na `current` que preenche `next.say`, e a mensagem de servidor indisponível.

## Aceitação

- `prumo status` e o painel mostram a mesma etapa atual no mesmo projeto.
- Num projeto piloto com revisão ingerida, a etapa `review` mostra as mesmas contagens que o
  painel antigo.
- `hooks/mods/` fica menor do que hoje.
- `claude plugin validate .` e `claude plugin test .` passam.

## Consequências

- Release PATCH (ADR-0015): invocável novo (`/projeto`), `/revisao` some. O CHANGELOG diz que
  `/revisao` virou `/projeto`. `uv.lock` não muda: sem novo download do ambiente.
- A sugestão inicial do `prumo status` e da skill `start` para projeto novo passa de "conecte
  a coleção do Zotero" para "feche a pergunta do estudo".
- O bloco `prumo:runtime` e os índices não mudam de forma; rodar
  `uv run python .github/scripts/gen_indexes.py` só pela spec e pela ADR novas.

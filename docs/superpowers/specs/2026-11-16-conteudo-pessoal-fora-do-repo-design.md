---
title: Conteúdo pessoal fora do repo — base de conhecimento na pasta do usuário
date: 2026-11-16
status: approved
tags: [pasta-do-usuario, base-de-conhecimento, templates, guias, paths, adr-0045, adr-0002, adr-0038]
---

# Conteúdo pessoal fora do repo: a pasta do usuário

## Problema

O mantenedor quer usar com o PAR templates próprios (manuscrito, projeto CEP, SAP, seção) e
diretórios de teoria e referência (guias de método, notas de estilo, checklists pessoais) que
orientem as skills. O repo é público (`.claude/rules/privacy.md`): esse conteúdo não pode entrar
nele, nem como fixture.

O que existe hoje:

- **Templates de escrita** já têm cadeia de resolução em `domains/write/compose.py`:
  `--template` > `<pj>/.claude/writing_templates/<kind>.md` > `skills/<skill>/templates/<modo>.md`.
  O override é por projeto: um template pessoal usado em cinco `pj_*` vive em cinco cópias.
- **Guias** (teoria, referência) não têm lugar. As skills leem só o que está em `skills/` ou no `pj_*`.
- `core/paths.py` acha só recursos empacotados (ADR-0002, ADR-0038). Não há nível do usuário.
- `core/config.py` já cita `~/.config/prumo/` como o nível do usuário de uma cascata futura.

## Opções avaliadas

| Opção | Veredito |
|---|---|
| **Pasta do usuário lida em tempo de execução** | **Escolhida.** Um degrau a mais numa cadeia que já existe |
| Copiar o conteúdo pessoal para cada `pj_*` no `init`/`update` | Dá reprodutibilidade de graça, mas duplica a teoria em todo projeto e exige merge de várias fontes no `update`. Quem quer congelar um template copia o arquivo para o projeto |
| Só conteúdo por projeto (o que há hoje) | Não resolve o reuso; é o problema |
| Plugin privado que estende o PAR | A doc oficial do Claude Code (consultada em 2026-11-16) descreve `dependencies` entre plugins, mas nenhum mecanismo para um plugin estender as skills de outro, nem variável que aponte para a raiz de outro plugin. Serve para skills próprias, não para dados que os modos do PAR leiam |
| Variável de ambiente ou campo de caminho (`userConfig`) | O pedido é poder apontar o caminho da base. Um symlink faz isso em todos os hosts sem conceito novo; variável de ambiente não chega ao app aberto fora do terminal, e `userConfig` mostraria um prompt a toda pesquisadora (Princípio VIII) |
| Listar a base inteira no `write prep` | Uma base com análise e machine learning entraria em todo draft. Só `guides/<kind>/` é obrigatório; o resto é consulta |

## Decisão

O conteúdo pessoal é uma **base de conhecimento**: templates, guias de redação, formatos de análise
de dados, de machine learning, o que o pesquisador quiser guardar. Ela mora numa pasta dele, fora de
qualquer repo do PAR, e conectá-la ao plugin é opcional.

Uma pasta, por convenção, sem configuração: **`~/.config/prumo/`** (ou `$XDG_CONFIG_HOME/prumo/`).
Se existir, o PAR a usa; se não existir, nada muda.

**Conectar é apontar o caminho.** Quem já tem a base em outro lugar (repo git privado, pasta
sincronizada) liga-a com um symlink, e a skill `start` faz isso a pedido ("conecta minha base de
conhecimento em `<caminho>`"):

```bash
ln -s "<caminho da sua base>" ~/.config/prumo
```

O nome no código e na documentação é **pasta do usuário** (`user_dir`) para o lugar e **base de
conhecimento** para o conteúdo. "Overlay" já tem dono no repo: `core/scaffold.py::overlay` é a cópia
do `pj_base`, e os módulos do `prumo add` são overlays.

```
~/.config/prumo/
├── templates/
│   ├── paper.md            # mesmos nomes de <pj>/.claude/writing_templates/<kind>.md
│   ├── projeto-cep.md
│   ├── statistics.md
│   └── scientific.md
├── guides/
│   └── <kind>/*.md         # leitura obrigatória ao escrever aquele kind
└── (qualquer outra pasta)  # consulta livre: analise/, ml/, redacao/ … nomes do pesquisador
```

Só duas pastas têm significado para o PAR, com o vocabulário de `kind` que já existe
(`paper`, `projeto-cep`, `statistics`, `scientific`). O resto da base é livre: o PAR não impõe
estrutura, só avisa as skills de que ela existe.

### 1. `core/paths.py`

```python
def user_dir() -> Path | None:
    """Pasta de conteúdo pessoal (``$XDG_CONFIG_HOME/prumo``, padrão ``~/.config/prumo``), se existir."""
```

`core/` segue sem importar `domains/` (ADR-0005): a função devolve um caminho, e quem sabe o que há
dentro é o domínio `write`.

### 2. Templates: um degrau a mais

`template_candidates` devolve `project_override`, `user_dir`, `plugin_default`, nesta ordem. A cadeia
vira `--template` > projeto > pasta do usuário > plugin. O projeto vence o usuário porque é mais
específico e é o que reproduz o estudo.

`write list-templates` mostra o degrau novo sem mudança (já itera os candidatos). O JSON do
`write prep` ganha `template_source` com o rótulo do candidato vencedor, no espírito do
`language_source`, para a skill dizer ao usuário quando o template veio de fora do projeto.

### 3. Guias obrigatórias: lista no `write prep`

O JSON do `write prep` ganha `guides`: os arquivos de `guides/<kind>/*.md`, em ordem alfabética.
Chave nova e opcional (Princípio IV). O PAR só lista (Princípio II: achar é determinístico; ler e
aplicar é da skill).

Os quatro modos que já leem `template_path` do prep (`write manuscript`, `write section`,
`protocol cep`, `protocol sap`) ganham um passo: ler cada guia antes de escrever. Guia orienta
método, estilo e estrutura; não substitui a citação strict nem o acervo.

### 4. Consulta livre: uma linha no bloco `prumo:runtime`

O resto da base (formatos de análise, de machine learning, notas de método) não cabe em lista
obrigatória: ler tudo a cada draft custaria caro e traria ruído. O bloco `prumo:runtime`, gerado
em todas as skills por `gen_indexes.py`, ganha uma linha:

> Base de conhecimento do pesquisador: `~/.config/prumo/`, se existir. Consulte-a (liste as pastas,
> leia o que for pertinente) quando a tarefa envolver redação, método, análise de dados ou machine
> learning, e diga ao usuário qual arquivo usou.

Texto estático, zero Python, vale em todos os hosts que carregam as skills e em todos os modos,
inclusive `review critique` e `wiki study`.

### 5. Conectar pela skill `start`

A skill `start` ganha a frase "conecta minha base de conhecimento": confere que o caminho informado
é uma pasta, cria o symlink acima se `~/.config/prumo` não existir (nunca sobrescreve) e explica as
duas pastas com significado. Sem comando novo no CLI (Princípio VIII).

### 6. Fora de escopo, com trigger

- **Guias por projeto** (`<pj>/.claude/guides/`). Trigger: um projeto que precise de guia própria.
- **Base de conhecimento fora das skills do PAR** (sessão de código ou de ML num `pj_*` sem skill
  ativa). Trigger: a primeira vez que a base fizer falta ali; o remédio provável é a mesma linha no
  `AGENTS.md` do `pj_base`.
- **Índice ou busca na base** (qmd, catálogo gerado). Trigger: a base crescer a ponto de listar
  pastas não bastar.
- **Origem do template no `_meta` do draft** (Princípio V). O `write draft` não recebe o template:
  teria de resolver a cadeia de novo e erraria quando a skill usou `--template` avulso. Um carimbo
  que pode mentir é pior que nenhum. Trigger: `write prep` aceitar `--template`, ou um caso real de
  draft que não se soube reproduzir.
- **Campo de caminho na interface do plugin** (`userConfig` tipo `directory`), variável de ambiente e
  várias pastas. O symlink dá o mesmo resultado em todos os hosts, e o comportamento do `userConfig`
  no claude.ai não está documentado. Trigger: um host real onde o symlink não resolva.
- **Módulos pessoais para `prumo add`** e **`~/.config/prumo/config.toml`**.
- **Plugin privado.** Se um dia o mantenedor quiser skills ou agents próprios, o caminho é um plugin
  em repo privado com `dependencies` no `par`, instalado por marketplace privado. Não há nada a
  construir neste repo para isso.

## Alcance por host

- **CLI e Claude Code no computador:** funciona.
- **Cowork e chat do claude.ai:** não verificado. O `prumo` desses ambientes pode não enxergar a
  pasta do usuário do computador. O que já funciona neles, por projeto, continua funcionando.

## Privacidade

- Nada da pasta do usuário entra no repo. Testes usam `tmp_path` com texto sintético e
  `XDG_CONFIG_HOME` apontado para lá.
- A suíte roda isolada da pasta real do dono (fixture autouse).
- O JSON do prep imprime caminhos absolutos só na saída local; nenhum artefato versionado os guarda.

## Testes (TDD)

- `tests/unit/core/test_paths.py`: `user_dir()` devolve a pasta quando existe, `None` quando não.
- `tests/unit/write/`: projeto vence usuário, usuário vence plugin, `template_source` bate;
  `guide_paths` devolve só as do `kind`, em ordem; o JSON do `write prep` tem as duas chaves.
- `gen_indexes.py --check` cobre a linha nova do bloco `prumo:runtime`.

## Impacto de release

PATCH (ADR-0015), sem breaking. `uv.lock` e `shims/prumo` intactos: o ambiente do lançador não é
baixado de novo. CHANGELOG cita o Princípio VIII e a ADR-0045.

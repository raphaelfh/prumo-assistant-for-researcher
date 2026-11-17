---
date: 2026-11-16
status: draft
---

# Idioma de interação e saídas seguras configuráveis por projeto

## Problema

Duas regras do `pj_base` são fixas para todo projeto, e as duas deveriam depender do projeto.

1. **Idioma de interação.** `templates/pj_base/AGENTS.md` diz "Idioma de **interação**: pt-BR" em texto fixo. A pesquisadora que conversa em inglês não tem onde dizer isso. O idioma de escrita (`[writing].language`, ADR-0021) e o do callout de extração (`[paper_extract].language`) já são configuráveis; o da conversa, não. O `prumo init` também não pergunta nada sobre idioma.
2. **Célula mínima (k-anonimato).** `templates/pj_base/.claude/rules/safe_outputs.md` fixa célula mínima 5 em todo projeto (spec `2026-09-12-safe-outputs-design.md`). O projeto só pode **subir** o limiar, escrevendo no `docs/project_guide.md`, que nenhum código lê. Projeto sem dado de paciente (revisão, dado público, teórico) carrega a regra mesmo assim, e não há como baixá-la nem desligá-la. A spec de 2026-09-12 recusou uma chave `min_cell` por falta de consumidor determinístico (Princípio VIII); este documento cria esse consumidor.

Há um terceiro problema, que aparece ao olhar o mecanismo: **`.claude/rules/` só é lido pelo Claude Code.** O `pj_base` também serve Codex e Antigravity, que leem `AGENTS.md`. Hoje a regra de célula mínima não existe para quem usa esses dois. E uma rule é prosa estática: não lê o `pj_config.toml`, então não consegue carregar um valor por projeto sem que o agente vá ler outro arquivo.

## Decisão

Três camadas, cada uma com um dono.

| Camada | Onde | Papel |
|---|---|---|
| Valor | `.claude/pj_config.toml` | Fonte única: idioma de interação, se há dado de paciente, célula mínima |
| Instrução | bloco gerado no `AGENTS.md` | Texto que todo agente lê, já com os valores do projeto |
| Garantia | `prumo doctor` | Valida a config e confere se o bloco está em dia |

### 1. Chaves novas em `pj_config.toml`

```toml
[interaction]
# Idioma em que o agente conversa com você. Não muda o idioma de escrita
# ([writing].language) nem o do callout de extração ([paper_extract].language).
# Valores aceitos: "pt-BR" | "en-US"
language = "pt-BR"

[safe_outputs]
# O projeto trabalha com dado de paciente? false = revisão, dado público,
# teórico. Com false, só vale a regra de dado fora do git.
patient_data = true

# Contagem de pacientes de 1 a (min_cell - 1) é suprimida ou agregada.
# 0 desliga a supressão. Comuns: 5 (default), 10, 11.
min_cell = 5
```

- Defaults em `core/config.py::DEFAULTS` iguais ao comportamento de hoje (`pt-BR`, `true`, `5`): projeto existente sem as chaves não muda (Princípio VIII, caminho feliz sem configuração).
- `INTERACTION_LANGUAGES = frozenset({"pt-BR", "en-US"})`, separado de `WRITING_LANGUAGES` e `VALID_LANGUAGES` pelo mesmo motivo do ADR-0021: contratos distintos. Os valores coincidem hoje com `WRITING_LANGUAGES`; ampliar um não amplia o outro.
- `load_project_config` valida: idioma no vocabulário, `patient_data` booleano, `min_cell` inteiro `>= 0`. Erro é `ConfigError` com a correção na mensagem.

### 2. Bloco gerado `prumo:project-rules` no `AGENTS.md`

`templates/pj_base/AGENTS.md` troca a linha fixa de idioma por um bloco machine-owned (ADR-0009):

```markdown
<!-- prumo:project-rules:begin -->
<!-- gerado de .claude/pj_config.toml por `prumo update`; edite a config, não este bloco -->
Idioma de **interação**: pt-BR. Idioma de **escrita científica**: en-US
(`[writing].language`); documento de CEP/CONEP é sempre pt-BR.

## Saídas seguras (dado de paciente)
- **Mínimo necessário.** …
- **Célula mínima = 5.** …
- **Dado fora do git.** …
<!-- prumo:project-rules:end -->
```

- O texto vem de um renderizador único, `core/project_rules.py::render_project_rules(cfg) -> str`, que absorve o conteúdo de `core/safe_outputs.py` (a checagem do `doctor` muda de módulo junto; saldo de módulos zero).
- Variantes da seção de saídas seguras: `patient_data = true` com `min_cell > 0` (as três instruções, com o número do projeto); `patient_data = true` com `min_cell = 0` (mínimo necessário + dado fora do git, e uma linha dizendo que a supressão está desligada por decisão do projeto); `patient_data = false` (só dado fora do git).
- O idioma de escrita aparece no bloco como valor resolvido, para o agente não precisar abrir a config. A cascata do ADR-0021 continua valendo; o bloco só informa o degrau `pj_config`.
- Quem escreve o bloco: `prumo init` (criação) e `prumo update` (regenera a partir da config atual). O bloco fica no `AGENTS.md`, que o `CLAUDE.md` já importa com `@AGENTS.md`: Claude, Codex e Antigravity leem o mesmo texto.
- Conteúdo humano fora do bloco é preservado. Delimitador corrompido é erro reportável (ADR-0009), sem flag nova: a mensagem manda apagar os marcadores que sobraram e rodar `prumo update`, que reinsere o bloco no topo da seção "Persona e filosofia".

### 3. `.claude/rules/safe_outputs.md` sai do `pj_base`

- O arquivo é removido do template. `prumo update` em projeto existente: se o arquivo é idêntico ao template antigo (hash conhecido), apaga e insere o bloco; se foi editado, mantém, insere o bloco e avisa que a rule local duplica o bloco e pode ser apagada depois de conferida.
- Projeto que subiu o limiar no `project_guide.md` (mecanismo antigo): o `update` não interpreta prosa. A mensagem do `update` diz para mover o valor para `[safe_outputs].min_cell`.
- `COMPARE_PREFIX = ".claude/rules"` em `scaffold.py` perde seu único arquivo do núcleo; segue valendo para rules de módulo. O comentário é atualizado.

### 4. `prumo init` pergunta

- Wizard ganha duas perguntas, depois do nome do projeto: idioma de interação (`pt-BR`/`en-US`, default `pt-BR`) e "O projeto usa dado de paciente?" (default sim). Com dado de paciente, pergunta a célula mínima (default 5).
- A escolha de idioma de interação vira o default sugerido de `[paper_extract].language` (`en-US` → `en`). `[writing].language` mantém o default `en-US` do ADR-0021 e é perguntado na mesma tela, já preenchido.
- Modo não-interativo (`--yes`, usado pela skill `start` no chat): flags `--lang pt-BR|en-US` e `--no-patient-data`. A skill `start` faz as mesmas perguntas em linguagem natural antes de chamar `prumo init`. Sem flag, valem os defaults.
- Nenhum comando `prumo config set`: mudar depois é editar `pj_config.toml` e rodar `prumo update`, que o `doctor` já manda rodar quando o bloco está velho.

### 5. `prumo doctor`

- `[dado_versionavel]` continua igual (só troca de módulo).
- `[regras_desatualizadas]`: o bloco `prumo:project-rules` falta ou difere de `render_project_rules(cfg)`. Correção: `prumo update`. Cobre tanto config editada sem regenerar quanto projeto antigo sem o bloco. Um código só para os dois, porque a correção é a mesma (Princípio VIII).
- `[celula_minima_baixa]`: `patient_data = true` e `0 <= min_cell < 5`. Aviso, não erro: o projeto pode ter motivo (comitê aprovou, dado já agregado na fonte). A mensagem diz que 5 é o limiar mais comum em publicação de dado de saúde e como subir. Ação diferente de `[regras_desatualizadas]`, por isso código separado.

### 6. ADR

ADR-0046 registra a troca de mecanismo (rule em `.claude/rules/` → bloco gerado no `AGENTS.md`) e a reversão da alternativa rejeitada "chave `min_cell`" da spec de 2026-09-12.

## Fora de escopo

- `.claude/rules/privacy.md` **deste repo**. Ela protege o repo público do PAR, não os projetos, e continua fixa.
- Idioma das skills em si (`SKILL.md`, mensagens do `prumo`): continuam em pt-BR. O idioma de interação muda como o agente conversa, não traduz o plugin.
- Varredura de célula pequena em tabela do manuscrito: segue recusada pelos motivos da spec de 2026-09-12 (falso positivo é o caso comum).
- Superfície sem CLI (chat do claude.ai sem `pj_*` no disco): não há `AGENTS.md` para ler. A skill `start` pergunta o idioma na primeira resposta; nada é persistido.
- Outros controles de divulgação (arredondamento, supressão secundária, l-diversidade). Sem pedido real (Princípio VI).

## Alternativas rejeitadas

- **Manter a rule e só trocar o "5" por "veja `min_cell` no `pj_config.toml`".** Continua invisível para Codex e Antigravity, e depende de o agente ir ler a config a cada vez.
- **Rule gerada em `.claude/rules/safe_outputs.md` a partir da config.** Resolve o valor, não resolve o alcance: só o Claude lê `.claude/rules/`.
- **Duas fontes (rule para Claude + bloco no `AGENTS.md` para os outros).** O Claude leria o texto duas vezes, e as duas cópias podem divergir.
- **Hook que bloqueia escrita com célula pequena.** Determinístico, mas o falso positivo domina (contagem de clínicos, n de estudos) e hook não roda em toda superfície.
- **Comando `prumo config set`.** Um conceito a mais; editar o TOML e rodar `update` já cobre.

## Testes

- `tests/unit/core/test_config.py`: defaults novos; idioma fora do vocabulário, `patient_data` não booleano e `min_cell` negativo dão `ConfigError` com a correção na mensagem.
- `tests/unit/core/test_project_rules.py`: as três variantes do bloco; idioma de interação e de escrita aparecem com os valores da config; render é idempotente.
- `tests/unit/test_cli_init.py`: wizard grava as respostas no `pj_config.toml` e o bloco no `AGENTS.md`; `--yes` usa defaults; `--lang en-US --no-patient-data` chega à config e ao bloco; `.claude/rules/safe_outputs.md` não é criado.
- `tests/unit/test_cli_update.py`: projeto antigo com a rule idêntica ao template perde a rule e ganha o bloco; rule editada é mantida com aviso; conteúdo humano fora do bloco preservado; delimitador corrompido é erro.
- `tests/unit/test_cli_doctor.py`: `[regras_desatualizadas]` com bloco ausente e com config editada; `[celula_minima_baixa]` com `min_cell = 3` e dado de paciente, silêncio com `patient_data = false`; `[dado_versionavel]` sem regressão.
- Fixtures sintéticas em `tmp_path` (`pj_exemplo`).

## Aceitação

- `prumo init` pergunta idioma e dado de paciente, e o `AGENTS.md` criado traz o bloco com essas respostas.
- Editar `[safe_outputs].min_cell = 10` e rodar `prumo update` muda o número no bloco; antes do `update`, o `doctor` acusa `[regras_desatualizadas]`.
- Um `pj_*` criado antes desta mudança, depois de `prumo update`, não tem mais `.claude/rules/safe_outputs.md` (se não editada) e tem o bloco com os defaults de hoje: nenhum comportamento muda sem a pesquisadora pedir.
- Codex e Antigravity recebem a regra de célula mínima pelo `AGENTS.md`.

## Consequências

- O comportamento de quem não mexe em nada continua o mesmo; a diferença é que agora dá para mexer.
- `pj_config.toml` ganha duas seções. É configuração opcional com default útil, não passo obrigatório.
- Baixar ou desligar a célula mínima passa a ser possível. O aviso do `doctor` e a linha explícita no bloco deixam a escolha visível, mas a responsabilidade é do projeto.
- Release: muda o `pj_base` e o comportamento do `init`/`update`, então é releasável. A remoção da rule é migrada pelo `update`, sem ação manual; o plano decide entre PATCH e MINOR (ADR-0015). Não muda `uv.lock` nem `shims/prumo`, então não força novo download do ambiente.

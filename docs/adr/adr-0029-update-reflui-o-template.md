# ADR-0029 — `prumo update` reflui o `pj_base` num projeto vivo, comparando ao vivo

- Status: aceito
- Data: 2026-09-07
- Origem: auditoria de organização do `pj_piloto_genetica` (2026-09-06), item 2. Precedentes: [ADR-0009](adr-0009-blocos-delimitados.md) (blocos delimitados), [ADR-0027](adr-0027-pj-instalavel.md) (checks de empacotamento no `doctor`). Aplica o Princípio VIII da constitution (1.2.0).

## Contexto

O `prumo init` é overlay de uma vez só. `core/scaffold.py::overlay` copia `templates/pj_base/` para o projeto novo e nunca mais volta: não existia comando que trouxesse o template de volta a um `pj_*` já criado. O efeito é silencioso e caro. O `.claude/rules/documentation.md` vendorizado num projeto real continuou descrevendo `references/notes/<citekey>.md` — o layout flat que a [ADR-0008](adr-0008-layout-alfa-de-notas.md) substituiu — enquanto o template do repo já estava correto. A rule é carregada pelo agente em toda sessão, então o projeto passou meses ensinando o layout errado ao próprio assistente, e nem `prumo doctor` nem `prumo wiki lint` tinham como perceber.

O desenho inicial para detectar isso gravava o hash do arquivo de origem no `pj_config.toml` durante o `init`, e comparava três vias — origem, local, template atual — para só reportar drift quando o arquivo local não tivesse sido customizado. A revisão de simplicidade derrubou esse desenho antes de virar código: `overlay` já devolve `(copied, skipped)` e já é não-destrutivo, de modo que a comparação ao vivo contra o template instalado responde a mesma pergunta sem inventar estado novo.

## Decisão

`prumo update [path]` compara o projeto com o `templates/pj_base/` instalado, **na hora**, e não guarda hash nem marca de versão em lugar nenhum. Um hash gravado seria uma terceira fonte de verdade, livre para dessincronizar do arquivo que diz descrever; a comparação ao vivo não pode mentir. Entre duas implementações que resolvem o mesmo problema, vence a que exige menos estado persistido (Princípio VIII).

O comando distingue dois casos com tratamento diferente, porque o risco é diferente. Arquivo **ausente** é adição pura — nada do pesquisador pode ser perdido — e é restaurado sem perguntar. Arquivo que existe e **difere** só é tocado com confirmação explícita: a customização de uma rule é trabalho humano, e sobrescrevê-la em silêncio seria um estrago pior que o drift que o comando veio consertar. Sem TTY e sem `--yes` a resposta é **não**, para que um `update` rodado em CI ou por agente nunca apague customização por falta de alguém para responder. `--dry-run` mostra o plano sem escrever.

A comparação de **conteúdo** é restrita a `.claude/rules/` (`scaffold.COMPARE_PREFIX`). É a subárvore que o agente lê a cada sessão, onde o drift é caro e silencioso — o gatilho deste ADR. É também a única sem substituição de placeholder: os seis arquivos do `pj_base` que passam por `apply_project_name` divergem do template **por construção**, e compará-los reportaria drift em todo projeto que existe. Fora de `.claude/rules/`, o `update` só afirma presença.

`docs/studies/` fica fora do reflow (`scaffold.UPDATE_SKIP`). O `pj_base` traz `docs/studies/principal/`, e recopiá-lo num projeto que nomeou o escopo de outro jeito injetaria um escopo órfão: um projeto com um escopo só passaria a ter dois, e todo comando por-escopo começaria a exigir `--scope` sem que nada tivesse sido criado de propósito. A árvore de escopo é do projeto, não do template ([ADR-0022](adr-0022-layout-por-escopo.md)).

## Consequências

O `doctor` ganha remédio para citar. O check `[fora_do_padrao]` aponta `prumo update`, e a mensagem deixa de ser um diagnóstico sem saída — antes, um check que só reportasse drift deixaria o pesquisador fazendo diff à mão de um arquivo que ele não escreveu.

O reflow é parcial por desenho, e isso é uma limitação assumida: um arquivo do `pj_base` que mude fora de `.claude/rules/` num projeto existente não é detectado, só a ausência dele. Estender a comparação exigiria normalizar os placeholders antes de comparar, o que só se justifica quando um caso real aparecer.

Não há desfazer. Sobrescrever um divergente com `--yes` perde a versão local, e a proteção contra isso é a confirmação, não um backup — o projeto está em git, que é onde o histórico mora.

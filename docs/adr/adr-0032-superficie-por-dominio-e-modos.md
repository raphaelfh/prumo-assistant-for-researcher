# ADR-0032 — Superfície por domínio: start + 5 skills com modos

- Status: aceito
- Data: 2026-09-12
- Origem: [[2026-09-12-superficie-de-skills-design]] (D1, D2, D6, D7). Precedentes: [ADR-0019](adr-0019-preflight-uniforme-skills.md) (preflight uniforme), [ADR-0029](adr-0029-update-reflui-o-template.md) (`prumo update`).

## Contexto

O plugin chegou a 16 skills com descrições que se sobrepõem. A fricção mais observada no uso real é escolher a skill: "escreve essa seção" disputava três skills, "adiciona esse paper" duas, e as 16 descrições entravam no contexto de toda sessão. O nome da skill descrevia o verbo técnico (`formulate-picot`, `review-reconcile`), não o que o pesquisador quer produzir.

## Decisão

A superfície passa a ser `start` e cinco skills que espelham os domínios do CLI: `paper`, `wiki`, `protocol`, `write`, `review`. Cada skill antiga vira um **modo** 1:1, num arquivo `skills/<skill>/modes/<modo>.md` com frontmatter próprio. O frontmatter do modo é a fonte única de frases de roteamento (`prumo.phrases`), nomes antigos (`prumo.legacy`), requisitos, trava de idioma, `write_kind` e `disclosure_task`.

O `SKILL.md` da skill não contém instrução operacional. `when_to_use`, `allowed-tools`, `argument-hint` e a tabela frase → modo são gerados a partir dos modos, e o preflight e o contrato de prosa são estampados em cada arquivo de modo.

Não há alias para os nomes antigos. `prumo update` reescreve o token `prumo-assist:<antigo>` nos arquivos `.md` e `.toml` do projeto e o `doctor` aponta sobras como `[skill_obsoleta]`. Valores de proveniência já gravados (`generator: wiki-query`, `extracted_model`) não são reescritos; o registry resolve nomes antigos e novos para o mesmo `SkillRef`.

## Consequências

Invocar uma skill antiga deixa de funcionar: é breaking, MINOR sob [ADR-0015](adr-0015-pre-1-0-patch-para-releasavel.md). O custo de roteamento cai de 16 descrições para 6.

Renomear um modo passa a exigir acrescentar o nome anterior a `prumo.legacy`, ou projetos existentes perdem a resolução de proveniência. Duas skills declarando o mesmo nome legado é erro de leitura do registry.

`.claude/skills/<antigo>/` instalado por um `prumo init` anterior não é apagado pelo `update`, porque pode ter sido customizado. O `doctor` aponta e a pessoa decide.

O roteamento real só é medido no agent-host: a lista-ouro `tests/fixtures/routing_phrases.toml` guarda 30 frases e o critério de aceite (≥ 27/30 no Desktop) é manual.

# ADR-0044 — O `connect` grava qual coleção do Zotero alimenta o projeto

- Status: proposto
- Data: 2026-11-16
- Origem: pedido do mantenedor; spec `docs/superpowers/specs/2026-11-16-vinculo-zotero-design.md`. Emenda a [ADR-0020](adr-0020-connect-autoexport-bbt.md); aplica os Princípios IV e VIII

## Contexto

O `prumo status` e o painel "Projeto" ([ADR-0043](adr-0043-painel-de-etapas.md)) não dizem de qual coleção do Zotero vem a bibliografia. O `prumo paper connect` resolve a coleção, chama `autoexport.add` e descarta a resposta. Depois disso ninguém mais sabe: o Better BibTeX não tem `autoexport.list` nem equivalente, o `.bib` exportado não traz a origem, e a configuração do autoexport mora numa preferência interna do Zotero cujo formato já mudou. A API local do Zotero responderia parte disso, mas exige o toggle que a [ADR-0037](adr-0037-ponte-zotero-minima.md) deixou de pedir.

O Princípio VIII manda preferir a implementação com menos estado persistido, e a [ADR-0029](adr-0029-update-reflui-o-template.md) recusou um hash gravado porque a comparação ao vivo respondia a mesma pergunta. Aqui não há comparação ao vivo que responda.

## Decisão

1. O `connect` grava `.claude/zotero.toml`, schema `ZoteroLink/v1` (forward-only, Princípio IV): `library`, `library_id`, `collection`, `collection_key`, `linked_at`, `source`. `library_id` + `collection_key` são o identificador estável; os nomes são os do momento do registro. A chave vem do retorno do `autoexport.add`.
2. `prumo paper connect "<coleção>" --record` registra a coleção de um projeto já conectado. Só lê `user.groups` e nunca chama `autoexport.add`, então as guardas anti-fantasma da ADR-0020 e da ADR-0028 não são tocadas. Sai com `source = "record"`, porque o PAR não consegue conferir o autoexport existente.
3. `ProjectStatus/v1` ganha `library.zotero` (opcional), e o resumo da etapa Bibliografia mostra biblioteca e coleção. O `status` continua só leitura.
4. Arquivo ausente ou inválido é "sem vínculo". Nada bloqueia por causa dele.
5. Rejeitados: usar `autoexport.add` como sonda (dispara export e pode criar autoexport e coleção), ler as preferências do Zotero por fora (formato interno) e a API local (toggle). A tool MCP `paper_connect` não ganha `record`: registrar é raro e fica no CLI.

## Consequências

A pesquisadora vê no painel de onde vem a bibliografia. Projeto conectado antes desta ADR não mostra nada até rodar `--record` uma vez.

É estado novo, e pode envelhecer: trocar o autoexport na UI do Better BibTeX não atualiza o arquivo. O remédio previsto é conferir pelo pull export do Better BibTeX endereçado pela chave, no `doctor`, sem mutar o Zotero; fica fora deste corte, com a chave já gravada para isso.

O arquivo entra no git do projeto com o nome da coleção, que é dado do projeto e não deste repo.

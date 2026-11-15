# Regras de privacidade

O repo é público. Nada de projeto de pesquisa real entra nele: nem no código, nem em teste, fixture, doc, spec, plano, ADR, CHANGELOG ou mensagem de commit.

- Proibido: nome de projeto `pj_*` real, tema ou título de estudo, nome de coleção do Zotero, nome de arquivo de draft ou submissão, periódico-alvo de um draft, instituição, orientador, coautor, participante.
- Proibido: dado de estudo real, mesmo agregado ou anonimizado (n, médias, proporções, IC, p, datas de coleta, população, achado ou hipótese ainda não publicada). Fixture é sempre sintético e diz que é sintético.
- Proibido: caminho absoluto da máquina (`/Users/<nome>/...`, `/home/<nome>/...`), nome de usuário, settings ou inventário de plugins local. Use `<repo>`, `<pj>`, `pj_exemplo`.
- Proibido: segredo de qualquer tipo (chave de API, token, senha, cookie), mesmo de teste.
- Exemplo em doc, teste ou skill é inventado (`pj_exemplo`, `pj_piloto_*`, "Item A"). Medição feita num projeto real é descrita sem identificá-lo ("num projeto piloto", "num draft real").
- Notas de pesquisa pessoais (ex.: `pesquisa-mods.md`) ficam fora do git.
- Antes de commitar: `git diff --cached` sem nenhum dos itens acima. Na dúvida, generalize.

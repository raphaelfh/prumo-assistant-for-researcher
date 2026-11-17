---
title: Vínculo com o Zotero — saber qual coleção alimenta o projeto
date: 2026-11-16
status: approved
tags: [zotero, bbt, connect, status, painel, adr-0044, adr-0020, adr-0037]
---

# Vínculo com o Zotero: saber qual coleção alimenta o projeto

## Problema

O painel "Projeto" e o `prumo status` mostram "23 entrada(s)" na Bibliografia, mas não de onde
elas vêm. A pesquisadora com várias coleções e grupos não tem como conferir, sem abrir o Zotero,
se o projeto está ligado à coleção certa. O `prumo paper connect` sabe a resposta no momento em
que liga o autoexport e a descarta.

## Estudo: o que o Zotero e o Better BibTeX expõem

Fontes: código do Better BibTeX (`content/json-rpc.ts`, `auto-export.ts`, `pull-export.ts`,
`collection.ts`, 9.0.77), código do Zotero (`server_localAPI.js`, `ZoteroProtocolHandler.mjs`) e
uma sonda só de leitura num Zotero 10.0.9 com Better BibTeX 9.0.77.

| Caminho | O que dá | Por que (não) serve |
|---|---|---|
| JSON-RPC `autoexport.*` | Só `add`. Não há `list`, `get`, `status` nem `remove` (sonda: `-32601`). | Não dá para perguntar "qual coleção alimenta este arquivo". |
| Retorno do `autoexport.add` | `{libraryID, key, id}` | A única hora em que o BBT entrega a chave da coleção ligada. É o que gravamos. |
| `autoexport.add` como sonda | Mesmo caminho e mesma coleção: só reagenda. Coleção diferente: recusa sem `replace`. | Confere um palpite, mas com efeito colateral: dispara export, cria o autoexport se não houver, cria a coleção se o caminho não existir. Rejeitado. |
| `user.groups(true)` | Por biblioteca: `id` (libraryID), `name`; por coleção: `key`, `name`, `parentCollection`, `version`. | Só leitura. Resolve nome → chave e chave → nome atual. Já é usado pelo `connect`. |
| Onde o BBT guarda o autoexport | Preferência do Zotero, uma por arquivo, com `id` numérico local da coleção e `status`. | Formato interno, gravado no `prefs.js` com atraso, mudou de lugar em 2024. Ler por fora não é contrato. Rejeitado. |
| Cabeçalho do `.bib` | Nada identifica coleção ou biblioteca. | Não serve. |
| Pull export `/better-bibtex/export/collection?/<libraryID>/<KEY>.biblatex` | O `.bib` de uma coleção, endereçada pela chave, na hora. Só leitura. | Bom para **conferir** um vínculo (comparar citekeys) e medir defasagem. Exige Zotero aberto. Fica como próximo passo. |
| API local `/api/users/0/collections` | Nome, pai, `numItems`. | Exige o toggle "Allow other applications", que a ADR-0037 deixou de pedir. Não reabrir por isso. |
| `zotero://select/library/collections/<KEY>` | Abre a coleção no Zotero. | Grupo pede `groupID`, que o `user.groups` não devolve; só a biblioteca pessoal por ora. |

Conclusão: não existe leitura ao vivo confiável. O identificador estável é `libraryID` + chave da
coleção (sobrevive a renomear e mover), e o `autoexport.add` não aceita chave, só caminho por nome.

## Decisão

1. **Gravar no connect.** `prumo paper connect` grava `.claude/zotero.toml` (`ZoteroLink/v1`):
   `library`, `library_id`, `collection` (caminho), `collection_key`, `linked_at`, `source`.
   A chave vem do retorno do `autoexport.add` (cobre `--create`), com `user.groups` de reserva.
2. **`--record` para quem já conectou.** `prumo paper connect "<coleção>" --record` resolve a
   coleção por `user.groups` (só leitura) e grava o arquivo com `source = "record"`. Nunca chama
   `autoexport.add`. Recusa quando o `.bib` ainda é o placeholder, e não combina com `--create`.
3. **Mostrar.** A etapa Bibliografia passa a `"<biblioteca> › <coleção> · N entrada(s) · sync …"`.
   `ProjectStatus/v1` ganha `library.zotero` (o registro mais `select_uri`), campo novo e opcional.
4. **Arquivo ilegível é "sem vínculo".** O registro é informativo; nada bloqueia por causa dele.

O `status` continua só leitura de disco (ADR-0029): quem grava é o `connect`.

## Limite assumido

O registro pode envelhecer: se a pesquisadora trocar o autoexport na UI do Better BibTeX, o
arquivo continua dizendo a coleção antiga. Com `source = "record"` nem a origem foi conferida.

## Próximos passos (fora deste corte)

- **Conferir o vínculo** com o pull export pela chave: comparar as citekeys com as do `.bib` no
  `prumo doctor` e avisar quando divergem. Resolve o limite acima sem mutar nada.
- **Nome atual** pela chave (`user.groups`) quando o Zotero estiver aberto, para sobreviver a
  renomear.
- **Defasagem**: "3 itens novos na coleção desde o último sync", pela mesma comparação.
- **"Abrir no Zotero"** no painel, com `select_uri`; grupos quando houver `groupID`.
- **"N de M com PDF"** na Bibliografia.

## Testes

- `tests/unit/paper/test_link.py`: round-trip, arquivo ausente e inválido, `connect` grava (com e
  sem `--create`), recusa não grava, `--record` sem `autoexport.add`, `select_uri`.
- `tests/unit/paper/test_cli.py`: `--record` não chama `connect_collection`; `--record --create`.
- `tests/unit/test_status.py`: resumo e JSON com e sem vínculo.

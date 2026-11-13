# Operações avançadas — propagate & diff

Carregue quando ``prumo protocol detect-mode`` retornar ``propagate`` ou ``diff``; ``init``/``formalize`` estão em ``modes/question.md``.

Projeto antigo, só com ``.claude/picot.toml``: tudo abaixo vale igual, porque o CLI lê o arquivo antigo. No passo 4, edite o arquivo que existe (tabela ``[picot]``); o ``prumo protocol adr`` converte, grava ``question.toml`` e remove o ``picot.toml``.

## Operação 3 — ``propagate``

**Quando**: a pergunta canônica (``.claude/question.toml``) existe e há ADR baseline, mas os blocos
delimitados ``<!-- question:begin -->`` em ``docs/studies/<slug>/writing/protocol.md`` e
``docs/project_guide.md`` estão stale (hash mismatch). Sem mudança estrutural.

Executar:

```bash
prumo protocol propagate --json
```

Reportar status por destino (``inserted`` / ``updated`` / ``unchanged`` /
``missing``).

## Operação 4 — ``diff``

**Quando**: o usuário editou ``.claude/question.toml`` (manualmente ou via outra
invocação) e quer registrar a mudança como novo ADR.

### Passo 1. Rodar diff

```bash
prumo protocol diff --json
```

Captura o JSON da última linha. Campos relevantes:

- ``changes`` (lista) — pode estar vazia.
- ``has_structural`` (bool) — distingue mudança estrutural de cosmética.
- ``drift`` (lista) — fatos do draft em ``writing/`` que contradizem
  ``protocol.md``/pergunta do estudo (janela de coleta, ``n``, testes nomeados,
  pré-especificação de subgrupos), com ``protocol_loc``, ``draft_locs`` (todas as ocorrências) e ``hint``.
  Passe o caminho de um ``.md`` para checar só esse draft. Mostre cada item ao
  usuário; nunca edite o manuscrito por conta própria.

### Passo 2. Decidir caminho

- Se ``changes == []`` → nada mudou; sair informando.
- Se ``has_structural == false`` (só campos cosméticos como ``last_updated``
  ou ``hypothesis.rationale``) → chamar ``prumo protocol propagate`` e sair
  **sem ADR**.
- Se ``has_structural == true`` → seguir para Passo 3.

### Passo 3. Capturar motivação

Mostrar o diff campo-a-campo. Perguntar a motivação (livre ou de menu):

- "novo dataset disponível"
- "refinamento conceitual após leitura"
- "feedback de orientador/revisor"
- "consolidação pré-banca/submissão"
- "outro: ___"

Capturar também um slug curto (kebab-case) derivado da motivação.

### Passo 4. Bumpar versão em ``question.toml``

Editar ``.claude/question.toml`` via ``Edit`` (em projeto antigo, ``.claude/picot.toml``, tabela ``[picot]``):

- ``[question] version`` → ``version + 1``
- ``[question] last_updated`` → hoje (ISO ``YYYY-MM-DD``)

### Passo 5. Gerar ADR + propagar

```bash
prumo protocol adr \
    --motivation "<motivação capturada>" \
    --slug "<slug>" \
    --date "<hoje ISO>" --json
```

A saída em stdout é JSON com ``adr_path`` e ``propagate``.

### Passo 6. Reportar

```
✓ ADR gerado: docs/studies/<slug>/decisions/adr-NNNN-question-v<N>-<slug>.md
  Propagate: protocol=<status> · project=<status>
```

## Caso especial — mudança de ``type``

Se ``type`` ou ``framework`` mudou, o ADR
deve trazer warning explícito sobre os campos abandonados na seção
**Notas**. Esse caso é raro e sempre vale confirmação extra com o usuário
antes de prosseguir.

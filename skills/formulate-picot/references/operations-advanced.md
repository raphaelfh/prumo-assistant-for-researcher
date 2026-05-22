# Operações avançadas — propagate & diff

Carregue este arquivo quando ``detect_mode.py`` retornar ``propagate`` ou
``diff``. Para o modo ``init``/``formalize`` o conteúdo em ``SKILL.md`` já
basta — não precisa abrir este arquivo.

## Operação 3 — ``propagate``

**Quando**: ``.claude/picot.toml`` existe e há ADR baseline, mas os blocos
delimitados ``<!-- picot:begin -->`` em ``docs/protocol.md`` e
``docs/project.md`` estão stale (hash mismatch). Sem mudança estrutural.

Executar:

```bash
prumo protocol propagate --json
```

Reportar status por destino (``inserted`` / ``updated`` / ``unchanged`` /
``missing``).

## Operação 4 — ``diff``

**Quando**: o usuário editou ``.claude/picot.toml`` (manualmente ou via outra
invocação) e quer registrar a mudança como novo ADR.

### Passo 1. Rodar diff

```bash
prumo protocol diff --json
```

Captura o JSON da última linha. Campos relevantes:

- ``changes`` (lista) — pode estar vazia.
- ``has_structural`` (bool) — distingue mudança estrutural de cosmética.

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

### Passo 4. Bumpar versão em ``picot.toml``

Editar ``.claude/picot.toml`` via ``Edit``:

- ``[picot] version`` → ``version + 1``
- ``[picot] last_updated`` → hoje (ISO ``YYYY-MM-DD``)

### Passo 5. Gerar ADR + propagar

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/diff_and_adr.py \
    --motivation "<motivação capturada>" \
    --slug "<slug>" \
    --date "<hoje ISO>"
```

A saída em stdout é JSON com ``adr_path`` e ``propagate``.

### Passo 6. Reportar

```
✓ ADR gerado: docs/decisions/adr-NNNN-picot-v<N>-<slug>.md
  Propagate: protocol=<status> · project=<status>
```

## Caso especial — mudança de ``type``

Se ``type`` mudou (``clinical`` → ``methodological`` ou vice-versa), o ADR
deve trazer warning explícito sobre os campos abandonados na seção
**Notas**. Esse caso é raro e sempre vale confirmação extra com o usuário
antes de prosseguir.

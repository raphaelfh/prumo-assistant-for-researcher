# Log do projeto — pj_<NOME>

Registro cronológico append-only. As skills `/prumo-assist:wiki-ingest`, `/prumo-assist:wiki-query` e `/prumo-assist:wiki-lint` adicionam entradas automaticamente. Decisões relevantes também entram aqui (linkadas em `docs/decisions/`).

**Formato fixo:**

```
## [YYYY-MM-DD] <action> | <título curto>

- <detalhe 1>
- <detalhe 2>
```

**Actions suportadas:** `ingest`, `query`, `lint`, `decision`, `milestone`, `note`.

**Parsing rápido:**

```bash
grep "^## \[" docs/_log.md | tail -10       # últimos 10 eventos
grep "^## \[.*ingest" docs/_log.md          # só ingests
grep "^## \[2026-04" docs/_log.md           # eventos de abril/2026
```

---

<!-- As entradas abaixo aparecem em ordem cronológica (mais recentes acima). -->

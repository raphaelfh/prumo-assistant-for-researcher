# Regras de código

- Layering: `core/` NUNCA importa de `domains/`; `domains/` importam `core/`; domínios são mutuamente independentes (única exceção justificada: `write` → `protocol`, guardada por ImportError em `compose.py`).
- Fachadas finas: `cli.py` raiz e `domains/<X>/cli.py` fazem só parsing + chamada do domínio + saída. Todo subcomando Typer envolto em `core/cli_op.cli_run(...)`. Nada de `print()` direto — sempre `core/output.Console`.
- `domains/<X>/api.py` é re-export puro (wrapper passthrough é defeito).
- Tipagem estrita (`mypy --strict`); `from __future__ import annotations` em todo módulo; dataclasses `frozen=True` para value objects; Pydantic só em schemas versionados (`domains/<X>/schemas/v1.py`), forward-only: campo nunca é removido ou renomeado.
- Regiões machine-owned em Markdown usam blocos delimitados HTML-comment (`<!-- x:begin -->` / `<!-- x:end -->`); conteúdo humano fora do bloco é preservado. Ver ADR-0009.
- Testes espelham o layout (`tests/unit/<dominio>/test_<modulo>.py`); dependências externas (Zotero, qmd, pandoc) sempre mockadas nos seams (`_binary_on_path`, `_port_open`, `check_external_deps`).
- Docstrings e mensagens de usuário em pt-BR, com o comando de correção embutido na mensagem de erro; identificadores em inglês.

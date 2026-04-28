"""Domínio ``paper`` — gestão da bibliografia.

Cobre o pilar de **bibliografia**:

- ``sync``         — Better BibTeX → ``references/notes/<citekey>.md``
- ``graph``        — grafo passivo de citação a partir de ``[[@key]]``
- ``find``         — fuzzy lookup sobre `.bib` + notas
- ``lint``         — auditoria de consistência (citekey ↔ nota ↔ pdf)
- ``pdfs``         — symlinks ``references/pdfs/<key>.pdf`` → Zotero
- ``annotations``  — annotations + child notes do Zotero (API local)
- ``callout``      — render do callout estruturado de paper-extract
- ``schemas``      — saídas Pydantic versionadas (``PaperCallout/v1``)

Tudo aqui é determinístico. A parte agêntica (extrair PDF → JSON estruturado)
fica na skill ``paper-extract``, executada pelo agent-host do usuário.
"""

from __future__ import annotations

"""Domínio ``capture`` — router unificado pra ingestão.

Detecta o tipo do input (URL, DOI, arXiv, PDF path, citekey) e indica qual
ferramenta tomar conta. Determinístico — não chama LLM.

Fluxo típico:

    prumo capture https://doi.org/10.1/foo     # → "DOI: rode `paper sync` após adicionar no Zotero"
    prumo capture arXiv:2401.01234              # → idem
    prumo capture ./paper.pdf                   # → "PDF: adicione no Zotero, rode `paper sync`"
    prumo capture https://blog.example.com/x   # → "URL não-acadêmica: rode `wiki ingest` (skill)"
"""

from __future__ import annotations

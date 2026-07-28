"""Tests pro router de capture."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.capture.route import classify


def test_classify_doi() -> None:
    out = classify("https://doi.org/10.1234/foo.bar")
    assert out.kind == "doi"
    assert out.canonical == "https://doi.org/10.1234/foo.bar"


def test_classify_doi_bare() -> None:
    out = classify("10.1234/foo")
    assert out.kind == "doi"


def test_classify_arxiv_id() -> None:
    out = classify("arXiv:2401.01234")
    assert out.kind == "arxiv"
    assert "2401.01234" in out.canonical


def test_classify_arxiv_url() -> None:
    out = classify("https://arxiv.org/abs/2401.01234")
    assert out.kind == "arxiv"


def test_classify_pdf_existing(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = classify(str(pdf))
    assert out.kind == "pdf"


def test_classify_url() -> None:
    out = classify("https://blog.example.com/post")
    assert out.kind == "url"
    assert "wiki-ingest" in out.suggestion


def test_classify_citekey() -> None:
    out = classify("@smith2024combinado")
    assert out.kind == "citekey"


def test_classify_unknown() -> None:
    """Palavra nua agora roteia para `citekey` (é um corpo Pandoc legal, e
    `prumo paper find <palavra>` é sugestão inócua e mais útil que "não sei").
    `unknown` fica para o que não é token único."""
    out = classify("not a citekey!!")
    assert out.kind == "unknown"


def test_classify_pdf_inexistente_nao_vira_citekey() -> None:
    """`.` é pontuação interna válida num citekey Pandoc, então `artigo.pdf`
    casava `CITEKEY_RE` inteiro. Como o ramo de PDF só dispara com
    `path.exists()`, o erro de usuário mais provável — caminho errado —
    virava `citekey` e perdia a mensagem que ensina o formato certo."""
    out = classify("/nao/existe/artigo.pdf")
    assert out.kind == "unknown"
    assert "caminho" in out.suggestion


def test_classify_caminho_relativo_nao_vira_citekey() -> None:
    for raw in ("docs/notes.md", "notas.txt", "relatorio.docx", "pasta/arquivo"):
        assert classify(raw).kind == "unknown", raw


def test_classify_citekey_com_pontuacao_composta() -> None:
    """Chaves REAIS do acervo do usuário que a 2ª gramática rejeitava.

    `route.py` tinha `^@?([a-z][\\w-]*\\d{4}[\\w-]*)$`, que exige inicial
    minúscula e 4 dígitos — 10 de 173 chaves reais caíam em `unknown`.
    """
    for key in (
        "collins2024tripod+ai",
        "2023attentionbased",
        "benjamind.simon2024future",
        "integrative",
        "smith2020:aha-guideline",
    ):
        assert classify(key).kind == "citekey", key
        assert classify(f"@{key}").kind == "citekey", key

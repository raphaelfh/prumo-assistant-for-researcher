"""Tests pro normalizador Obsidian → Pandoc."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.obsidian import (
    normalize_markdown,
    split_frontmatter,
    split_frontmatter_raw,
)


def test_split_frontmatter_extracts_yaml() -> None:
    text = "---\nfoo: bar\n---\n\nbody here\n"
    meta, body = split_frontmatter(text)
    assert meta == {"foo": "bar"}
    assert body == "body here\n"


def test_split_frontmatter_returns_empty_when_absent() -> None:
    text = "no frontmatter here"
    meta, body = split_frontmatter(text)
    assert meta == {}
    assert body == text


def test_split_frontmatter_raw_preserves_yaml_comments_byte_for_byte() -> None:
    """Fix pós-review (Fase 2/Task 9, Crítico 1): `split_frontmatter` faz
    `yaml.safe_load`, que descarta comentários — `split_frontmatter_raw`
    devolve o bloco tal-qual, comentário e espaçamento incomum inclusos."""
    text = "---\ntitle: Pagina  # comentario que nao pode sumir\ntags:   [a, b]\n---\n\nbody here\n"
    raw_fm, body = split_frontmatter_raw(text)
    assert raw_fm + body == text  # round-trip exato
    assert raw_fm == "---\ntitle: Pagina  # comentario que nao pode sumir\ntags:   [a, b]\n---\n\n"
    assert body == "body here\n"


def test_split_frontmatter_raw_returns_empty_when_absent() -> None:
    text = "no frontmatter here"
    raw_fm, body = split_frontmatter_raw(text)
    assert raw_fm == ""
    assert body == text


def test_wikilink_with_alias_replaces_with_alias() -> None:
    out = normalize_markdown("Refer to [[some-page|that page]].")
    assert out == "Refer to that page."


def test_wikilink_without_alias_keeps_target() -> None:
    out = normalize_markdown("See [[some-page]].")
    assert out == "See some-page."


def test_wikilink_legado_de_citacao_degrada_para_narrativa_pandoc() -> None:
    """Achado I3: enquanto `_WIKILINK_RE` excluía `@` do charset do alvo, um
    `[[@key]]` remanescente passava INTACTO pelo normalizador e o pandoc
    entregava `[(Smith 2020)]` no docx — e, com alias,
    `[[@jones2021|Jones et al.]]` virava `[(Jones 2021, |Jones et al.)]`,
    texto corrompido DENTRO da citação, sem erro nenhum.

    Sem reintroduzir suporte legado: caindo na regra NORMAL de wikilink,
    `[[@key]]` degrada para `@key` — citação narrativa Pandoc válida. Com
    alias vale a regra de alias (o alias vence, como em qualquer wikilink);
    o resultado é texto limpo, nunca colchete órfão.
    """
    assert normalize_markdown("Como [[@smith2020]] mostrou.") == "Como @smith2020 mostrou."
    assert normalize_markdown("Ver [[@jones2021|Jones et al.]].") == "Ver Jones et al.."
    assert normalize_markdown("Grupo [[@a2020; @b2021]].") == "Grupo @a2020; @b2021."


def test_image_embed_with_missing_file_keeps_path() -> None:
    out = normalize_markdown("![[fig.png]]", page_dir=Path("/no/such/dir"))
    assert out == "![](fig.png)"


def test_image_embed_with_pdf_anchor_drops_silently() -> None:
    out = normalize_markdown("![[paper.pdf#page=3]]")
    assert out == ""


def test_callout_header_becomes_bold_title() -> None:
    text = "> [!note] Important\n> body line\n"
    out = normalize_markdown(text)
    assert "**Important**" in out
    assert "body line" in out


def test_block_id_anchor_is_stripped() -> None:
    out = normalize_markdown("Some claim. ^abc123\nNext line.")
    assert "^abc123" not in out
    assert "Some claim." in out


def test_code_block_is_preserved() -> None:
    text = "Before\n```python\n[[wikilink]]\n```\nAfter"
    out = normalize_markdown(text)
    assert "[[wikilink]]" in out  # within code block

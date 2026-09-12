"""Tests pra auditoria do wiki, por escopo (``docs/studies/<slug>/``)."""

from __future__ import annotations

from pathlib import Path

from par.domains.wiki.lint import check_single_primary, lint


def _scope(root: Path, slug: str) -> Path:
    s = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (s / sub).mkdir(parents=True, exist_ok=True)
    return s


def _project(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs" / "references" / "papers").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "_references.bib").write_text("", encoding="utf-8")
    (root / "docs" / "_index.md").write_text("# i", encoding="utf-8")
    (root / "docs" / "_log.md").write_text("# l", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Os cinco defeitos consertados por esta task.
# ---------------------------------------------------------------------------


def test_lint_nao_conta_a_bibliografia_como_pagina(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "a")
    papers = root / "docs" / "references" / "papers" / "silva2020"
    papers.mkdir(parents=True)
    (papers / "_meta.md").write_text("---\ntype: paper\n---\n", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "orphan_page" not in codes


def test_bib_ausente_sem_citacao_nao_emite_nada(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").unlink()
    s = _scope(root, "a")
    (s / "notes" / "n.md").write_text("---\ntype: note\n---\nsem citacao", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "bib_missing" not in codes


def test_bib_ausente_com_citacao_emite_warning(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").unlink()
    s = _scope(root, "a")
    (s / "notes" / "n.md").write_text("---\ntype: note\n---\ntexto [@silva2020]", encoding="utf-8")

    issues = [i for i in lint(root)["issues"] if i["code"] == "bib_missing"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"


def test_paginas_homonimas_em_escopos_distintos_nao_se_anulam(tmp_path: Path) -> None:
    root = _project(tmp_path)
    a = _scope(root, "a")
    b = _scope(root, "b")
    (a / "notes" / "metodo.md").write_text("---\ntype: note\n---\nx", encoding="utf-8")
    (a / "writing" / "paper.md").write_text("---\ntype: draft\n---\n[[metodo]]", encoding="utf-8")
    (b / "notes" / "metodo.md").write_text("---\ntype: note\n---\ny", encoding="utf-8")

    orfas = [i for i in lint(root)["issues"] if i["code"] == "orphan_page"]
    paginas = {i["page"] for i in orfas}
    assert any("studies/b/notes/metodo.md" in p for p in paginas)
    assert not any("studies/a/notes/metodo.md" in p for p in paginas)


def test_dead_link_nao_resolve_por_homonimo_de_outro_escopo(tmp_path: Path) -> None:
    """`related: ['[[metodo]]']` em b não deve resolver contra `notes/metodo.md`
    de a. Mesma razão de `orphan_page`/`ambiguous_link`: resolução de link
    acontece dentro do escopo que cita, não pela união global de stems."""
    root = _project(tmp_path)
    a = _scope(root, "a")
    b = _scope(root, "b")
    (a / "notes" / "metodo.md").write_text("---\ntype: note\n---\nx", encoding="utf-8")
    (b / "notes" / "outra.md").write_text(
        "---\ntype: note\nrelated:\n  - '[[metodo]]'\n---\n\nbody\n", encoding="utf-8"
    )
    report = lint(root)
    dead = [i for i in report["issues"] if i["code"] == "dead_link"]
    assert any(i["scope"] == "b" and "metodo" in i["message"] for i in dead)


def test_multiple_primary_desligado_por_default(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "a")
    for key in ("um", "dois"):
        d = root / "docs" / "references" / "papers" / key
        d.mkdir(parents=True)
        (d / "_meta.md").write_text("---\nrole: primary\n---\n", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "multiple_primary" not in codes


# ---------------------------------------------------------------------------
# Comportamento pré-existente, migrado para o layout por escopo.
# ---------------------------------------------------------------------------


def test_lint_clean_when_minimal_structure(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "a")
    report = lint(root)
    assert report["ok"]


def test_lint_flags_missing_docs(tmp_path: Path) -> None:
    report = lint(tmp_path)
    codes = {i["code"] for i in report["issues"]}
    assert "docs_missing" in codes


def test_lint_flags_missing_index_log(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    (docs / "references").mkdir(parents=True)
    (docs / "references" / "_references.bib").write_text("", encoding="utf-8")
    report = lint(tmp_path)
    codes = {i["code"] for i in report["issues"]}
    assert "no_index" in codes
    assert "no_log" in codes


def test_lint_flags_no_scope(tmp_path: Path) -> None:
    root = _project(tmp_path)
    report = lint(root)
    codes = {i["code"] for i in report["issues"]}
    assert "no_scope" in codes
    assert report["ok"]  # warning, não error


def test_lint_flags_broken_citekey(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{real,title={X}}\n", encoding="utf-8"
    )
    s = _scope(root, "a")
    (s / "notes" / "f1.md").write_text(
        "---\ntype: note\n---\n\nSee [@nonexistent] and [@real].\n", encoding="utf-8"
    )
    report = lint(root)
    codes = {i["code"] for i in report["issues"]}
    assert "broken_citekey" in codes


def test_lint_flags_no_frontmatter_in_scope_dirs(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "c1.md").write_text("# nota sem frontmatter\n", encoding="utf-8")
    report = lint(root)
    codes = {i["code"] for i in report["issues"]}
    assert "no_frontmatter" in codes


def test_lint_flags_orphan_pages(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\n---\n\nLinks to [[alpha]].\n", encoding="utf-8"
    )
    report = lint(root)
    pages_orphans = [i["page"] for i in report["issues"] if i["code"] == "orphan_page"]
    assert any(p.endswith("studies/a/notes/beta.md") for p in pages_orphans)
    assert not any(p.endswith("studies/a/notes/alpha.md") for p in pages_orphans)


def test_lint_flags_broken_log_prefix(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "_log.md").write_text(
        "# Log\n\n"
        "## [2026-05-30] ingest | added smith2024\n\n"
        "## not a valid header line\n\n"
        "## [2026-05-30] frobnicate | bad verb\n",
        encoding="utf-8",
    )
    report = lint(root)
    codes = {i["code"] for i in report["issues"]}
    assert "broken_log_prefix" in codes
    msgs = [i["message"] for i in report["issues"] if i["code"] == "broken_log_prefix"]
    assert any("not a valid header" in m for m in msgs)
    assert any("frobnicate" in m for m in msgs)


def test_check_single_primary_flags_multiple(tmp_path: Path) -> None:
    root = _project(tmp_path)
    for key in ("a", "b"):
        d = root / "docs" / "references" / "papers" / key
        d.mkdir(parents=True)
        (d / "_meta.md").write_text(f"---\nid: {key}\nrole: primary\n---\n", encoding="utf-8")
    issues = check_single_primary(root)
    codes = {i.code for i in issues}
    assert "multiple_primary" in codes


def test_check_single_primary_is_clean_with_one(tmp_path: Path) -> None:
    root = _project(tmp_path)
    d = root / "docs" / "references" / "papers" / "a"
    d.mkdir(parents=True)
    (d / "_meta.md").write_text("---\nid: a\nrole: primary\n---\n", encoding="utf-8")
    issues = check_single_primary(root)
    codes = {i.code for i in issues}
    assert "multiple_primary" not in codes


def test_lint_flags_dead_frontmatter_links(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\nrelated:\n  - '[[alpha]]'\n  - '[[ghost]]'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(root)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert any("ghost" in m for m in dead)
    assert not any("alpha" in m for m in dead)  # exists


def test_lint_flags_dead_markdown_link_in_frontmatter(tmp_path: Path) -> None:
    """`related:` com link markdown para página inexistente. É a forma que o
    próprio lint.py reconhece como esperada em projeto Pandoc-puro, e o
    ramo de página não tem rede de segurança (`scan_marked_citekeys` não
    cobre alvo de página)."""
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\nrelated:\n  - '[alpha](alpha.md)'\n"
        "  - '[fantasma](ghostpage.md)'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(root)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert any("ghostpage" in m for m in dead)
    assert not any("alpha" in m for m in dead)  # existe


def test_lint_nao_acusa_texto_livre_em_sources(tmp_path: Path) -> None:
    """`sources:` recebe string livre (título de paper, URL, nome de
    dataset). Aceitar alvo NU inundaria o relatório."""
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{real,title={X}}\n", encoding="utf-8"
    )
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\nsources:\n"
        "  - 'Combinado learning in practice (Nature, 2024)'\n"
        "  - 'https://example.com/artigo'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(root)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert dead == []


def test_lint_nao_acusa_mailto_em_frontmatter(tmp_path: Path) -> None:
    """Achado M8: o caminho do frontmatter pulava só ``"://"``, enquanto o
    do corpo já pulava ``mailto:`` — um `[contato](mailto:x@y.br)` em
    `sources:` virava `dead_link` falso. As duas pontas passam pela MESMA
    checagem agora (`_is_external_link`)."""
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\nsources:\n  - '[contato](mailto:fulano@usp.br)'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(root)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert dead == []


def test_lint_frontmatter_citekey_is_broken_citekey_not_dead_link(tmp_path: Path) -> None:
    """`_WIKILINK_TARGET_RE` deixou de aceitar `@` (só alvo de página) —
    citekey em `sources:`/`related:`/`links_to:` não vira mais `dead_link`;
    segue coberta por `scan_marked_citekeys`, que varre o arquivo inteiro
    (frontmatter incluso) e sinaliza `broken_citekey`."""
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{real,title={X}}\n", encoding="utf-8"
    )
    s = _scope(root, "a")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\nsources:\n  - '[[@real]]'\n  - '[[@missingkey]]'\n---\n\nbody\n",
        encoding="utf-8",
    )
    report = lint(root)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    broken = [i["message"] for i in report["issues"] if i["code"] == "broken_citekey"]
    assert not any("missingkey" in m for m in dead)
    assert not any("real" in m for m in dead)
    assert any("missingkey" in m for m in broken)
    assert not any("real" in m for m in broken)  # existe no .bib


def test_lint_reports_concept_candidates_as_info(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    # "focal loss" wikilinked 3x but has no page for it.
    for i, name in enumerate(("p1", "p2", "p3")):
        (s / "notes" / f"{name}.md").write_text(
            f"---\ntype: note\n---\n\nSee [[focal loss]] here ({i}). Also [[p1]].\n",
            encoding="utf-8",
        )
    report = lint(root)
    cand = [i for i in report["issues"] if i["code"] == "concept_candidate"]
    assert any("focal loss" in i["message"] for i in cand)
    assert all(i["severity"] == "info" for i in cand)
    # info must not break ok:
    assert report["ok"] is True


def test_lint_ignores_low_frequency_concepts(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "p1.md").write_text(
        "---\ntype: note\n---\n\nMentions [[rare term]] once. And [[p1]].\n",
        encoding="utf-8",
    )
    report = lint(root)
    assert not any(i["code"] == "concept_candidate" for i in report["issues"])


def test_lint_flags_broken_citekey_in_pandoc_form(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{real,title={X}}\n", encoding="utf-8"
    )
    s = _scope(root, "a")
    (s / "notes" / "f2.md").write_text(
        "---\ntype: note\n---\n\nVer [@real] e [@ghost2020] e grupo [@real; @ghost2021].\n",
        encoding="utf-8",
    )
    report = lint(root)
    msgs = [i["message"] for i in report["issues"] if i["code"] == "broken_citekey"]
    assert any("ghost2020" in m for m in msgs)
    assert any("ghost2021" in m for m in msgs)
    assert not any("real" in m for m in msgs)


def test_lint_ignores_bare_handles_in_prose(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{real,title={X}}\n", encoding="utf-8"
    )
    s = _scope(root, "a")
    (s / "notes" / "f3.md").write_text(
        "---\ntype: note\n---\n\nO autor @fulano comentou. Cite [@real].\n", encoding="utf-8"
    )
    report = lint(root)
    assert not any(
        i["code"] == "broken_citekey" and "fulano" in i["message"] for i in report["issues"]
    )


def test_lint_counts_markdown_links_as_incoming(tmp_path: Path) -> None:
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "alpha.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "beta.md").write_text(
        "---\ntype: note\n---\n\nVer [alpha](alpha.md). E [[beta]] auto-ref.\n",
        encoding="utf-8",
    )
    report = lint(root)
    orphans = [i["page"] for i in report["issues"] if i["code"] == "orphan_page"]
    assert not any(p.endswith("studies/a/notes/alpha.md") for p in orphans)


def test_lint_ambiguous_link_within_scope(tmp_path: Path) -> None:
    """Duas páginas com o MESMO stem no MESMO escopo: `[[metodo]]` é ambíguo."""
    root = _project(tmp_path)
    s = _scope(root, "a")
    (s / "notes" / "metodo.md").write_text("---\ntype: note\n---\n\nbody\n", encoding="utf-8")
    (s / "writing" / "metodo.md").write_text("---\ntype: draft\n---\n\nbody\n", encoding="utf-8")
    (s / "notes" / "outro.md").write_text(
        "---\ntype: note\n---\n\nVer [[metodo]].\n", encoding="utf-8"
    )
    report = lint(root)
    codes = {i["code"] for i in report["issues"]}
    assert "ambiguous_link" in codes


def test_lint_ignora_cabecalho_de_log_dentro_de_code_fence(tmp_path: Path) -> None:
    """O `_log.md` do `pj_base` documenta o formato das entradas num code fence
    (`## [YYYY-MM-DD] <action> | <título curto>`). O check lia o arquivo linha a
    linha, então esse exemplo virava `broken_log_prefix` e TODO projeto novo
    nascia com um warning — falso positivo que ensinava a ignorar o lint."""
    root = _project(tmp_path)
    (root / "docs" / "_log.md").write_text(
        "# Log\n\n"
        "**Formato fixo:**\n\n"
        "```\n"
        "## [YYYY-MM-DD] <action> | <título curto>\n"
        "```\n\n"
        "## [2026-05-30] ingest | added smith2024\n",
        encoding="utf-8",
    )
    report = lint(root)
    assert not [i for i in report["issues"] if i["code"] == "broken_log_prefix"]

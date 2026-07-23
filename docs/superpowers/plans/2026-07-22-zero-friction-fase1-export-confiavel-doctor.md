# Fase 1 — Export docx confiável + doctor de versões — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O export docx nunca entrega arquivo corrompido silenciosamente (valida → retry 1x → hard-fail) e o `prumo doctor` detecta versão do Zotero fora do par suportado (Zotero 9+) com comando de correção na mensagem.

**Architecture:** Todo o endurecimento vive em `domains/write/export.py` num helper único (`_run_and_validate_docx`) consumido por `export()` e `compose()`, mantendo as fachadas CLI finas; a detecção de versão vive em `core/deps.py` como seam HTTP mockável (`_zotero_version_header`), padrão já usado por `_binary_on_path`/`_port_open`. Nenhuma mudança de trigger/output de skill → release PATCH.

**Tech Stack:** Python 3.11, stdlib apenas (`zipfile`, `xml.etree`, `urllib`), Typer + `core/output.Console`, pytest com `unittest.mock.patch`/`monkeypatch`.

**Spec:** `docs/superpowers/specs/2026-07-22-zero-friction-onboarding-design.md` (Fase 1; decisões D2/D3).

## Global Constraints

- `mypy --strict` limpo; `from __future__ import annotations` em todo módulo (novo ou tocado).
- Mensagens de usuário em pt-BR **com o comando de correção embutido**; identificadores em inglês.
- Nada de `print()` — saída de CLI só via `core/output.Console` dentro de `cli_run`.
- `core/` NUNCA importa de `domains/`.
- Dependências externas (pandoc, Zotero/BBT) sempre mockadas nos seams nos testes; nenhum teste toca rede ou binário real.
- Retry do pandoc é exatamente **1** (N=1, spec Fase 1).
- Par suportado: **Zotero 9+** (`_SUPPORTED_ZOTERO_MAJOR = 9`); versão não-detectável NÃO reprova (fail-safe).
- Comandos de verificação do repo: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`.
- Commits frequentes, mensagem convencional com escopo (padrão do histórico: `fix(write): …`, `feat(core): …`, `test(...): …`).
- NÃO fazer release neste plano (bump/CHANGELOG-move são fluxo do dono via RELEASING.md); apenas registrar em `## [Não publicado]`.

**Nota de desvio vs spec (racional, decidido no planning):**
1. O item "guia de primeira abertura no Word" do spec assumia o defeito do pipeline `zotero.lua` do BBT (popup por citação). O pipeline real do prumo (`zotero_live_docx.lua`) **já embute** `ZOTERO_PREF_1/2` em `docProps/custom.xml` exatamente para evitar isso (docstring de `export.py`). O item vira: **guarda de regressão** das prefs (Task 3) + **nota curta de primeiro uso** na saída do CLI (Task 5).
2. O spec pede versão "do Zotero e do BBT". Não existe endpoint de versão do BBT verificado; a alcançabilidade do BBT já é checada em runtime (`_check_bbt_running` no export). Escopo entregue: **versão do Zotero** (header do connector) — que é o que detecta o churn real (BBT derruba Zotero antigo). Se o passo de descoberta da Task 6 revelar endpoint de versão do BBT, preencher no mesmo seam; senão, registrar como pergunta aberta no plano ao arquivar.

---

### Task 1: Validação estrutural do docx (`_validate_docx_structure` + `CorruptDocxError`)

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (imports no topo; funções novas logo após `_docx_zotero_field_counts`, ~linha 223)
- Test: Create `tests/unit/write/test_export_docx_validation.py`

**Interfaces:**
- Consumes: `zipfile`, `xml.etree.ElementTree` (stdlib); `Path`.
- Produces: `CorruptDocxError(RuntimeError)`; `_validate_docx_structure(docx_path: Path) -> list[str]` (lista de problemas; vazia = docx são); helper de teste `_write_minimal_docx(path, *, items=0, prefs=True, include_types=True, include_document=True, types_xml=None) -> Path` — **reutilizado pelas Tasks 2–4**.

- [ ] **Step 1: Write the failing test**

Criar `tests/unit/write/test_export_docx_validation.py`:

```python
"""Validação estrutural do docx gerado (Fase 1 do zero-friction onboarding).

Fixtures construídas com zipfile em tmp_path — nenhum pandoc/Zotero real.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from prumo_assist.domains.write.export import _validate_docx_structure

_CONTENT_TYPES_OK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    "</Types>"
)


def _write_minimal_docx(
    path: Path,
    *,
    items: int = 0,
    prefs: bool = True,
    include_types: bool = True,
    include_document: bool = True,
    types_xml: str | None = None,
) -> Path:
    """Zip com o esqueleto mínimo que a validação inspeciona."""
    body = "<w:document>" + ("ZOTERO_ITEM CSL_CITATION " * items) + "</w:document>"
    with zipfile.ZipFile(path, "w") as z:
        if include_types:
            z.writestr("[Content_Types].xml", types_xml or _CONTENT_TYPES_OK)
        if include_document:
            z.writestr("word/document.xml", body)
        if prefs:
            z.writestr(
                "docProps/custom.xml",
                '<Properties><property name="ZOTERO_PREF_1"/></Properties>',
            )
    return path


def test_valid_docx_has_no_problems(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "ok.docx")
    assert _validate_docx_structure(docx) == []


def test_missing_file_is_reported(tmp_path: Path) -> None:
    problems = _validate_docx_structure(tmp_path / "nao_existe.docx")
    assert problems and "não foi criado" in problems[0]


def test_non_zip_file_is_reported(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.docx"
    bogus.write_text("isto não é um zip")
    problems = _validate_docx_structure(bogus)
    assert problems and "zip" in problems[0]


def test_missing_document_xml_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "semdoc.docx", include_document=False)
    assert any("word/document.xml" in p for p in _validate_docx_structure(docx))


def test_missing_content_types_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "semtypes.docx", include_types=False)
    assert any("[Content_Types].xml" in p for p in _validate_docx_structure(docx))


def test_malformed_content_types_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "mal.docx", types_xml="<Types><Default</Types>")
    problems = _validate_docx_structure(docx)
    assert any("[Content_Types].xml" in p and "inválido" in p for p in problems)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: FAIL na coleta — `ImportError: cannot import name '_validate_docx_structure'`

- [ ] **Step 3: Write minimal implementation**

Em `src/prumo_assist/domains/write/export.py`, adicionar ao bloco de imports (após `import urllib.request`, linha ~30):

```python
import xml.etree.ElementTree as ET
```

Logo após `_docx_zotero_field_counts` (após a linha 222), adicionar:

```python
class CorruptDocxError(RuntimeError):
    """Docx falhou na validação estrutural mesmo após um retry do pandoc."""


_REQUIRED_DOCX_PARTS = ("[Content_Types].xml", "word/document.xml")


def _validate_docx_structure(docx_path: Path) -> list[str]:
    """Valida o zip do docx gerado. Retorna lista de problemas (vazia = são).

    Cobre a classe de defeito conhecida do pipeline pandoc+filtros Zotero
    (Word acusa "conteúdo ilegível"; docs do BBT recomendam re-rodar o
    pandoc; pandoc issues #8010/#11378): zip inválido/truncado, parte
    obrigatória ausente e ``[Content_Types].xml`` malformado.
    """
    if not docx_path.is_file():
        return [f"arquivo não foi criado: {docx_path}"]
    problems: list[str] = []
    try:
        with zipfile.ZipFile(docx_path) as z:
            names = set(z.namelist())
            for required in _REQUIRED_DOCX_PARTS:
                if required not in names:
                    problems.append(f"parte obrigatória ausente no zip: {required}")
            bad_member = z.testzip()
            if bad_member is not None:
                problems.append(f"membro corrompido no zip (CRC): {bad_member}")
            if "[Content_Types].xml" in names:
                try:
                    ET.fromstring(z.read("[Content_Types].xml"))
                except ET.ParseError as exc:
                    problems.append(f"[Content_Types].xml inválido: {exc}")
    except zipfile.BadZipFile:
        return [f"arquivo não é um zip válido: {docx_path}"]
    return problems
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/write/test_export_docx_validation.py src/prumo_assist/domains/write/export.py
git commit -m "feat(write): validação estrutural do docx gerado (_validate_docx_structure)"
```

---

### Task 2: Retry automático do pandoc (`_run_and_validate_docx`)

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (após `_validate_docx_structure`)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append)

**Interfaces:**
- Consumes: `_validate_docx_structure` e `CorruptDocxError` (Task 1); `subprocess.run` (módulo `subprocess` já importado em `export.py`); `logger` do módulo.
- Produces: `_run_and_validate_docx(cmd: list[str], out: Path) -> None` — roda pandoc, valida, re-roda no máximo 1 vez, levanta `CorruptDocxError` se persistir. **Consumida pela Task 4.**

- [ ] **Step 1: Write the failing tests**

Append em `tests/unit/write/test_export_docx_validation.py`:

```python
import pytest

import prumo_assist.domains.write.export as export_mod
from prumo_assist.domains.write.export import CorruptDocxError, _run_and_validate_docx


def _fake_run_writing(
    out: Path, payloads: list[bytes], calls: list[list[str]]
) -> object:
    """Fabrica um substituto de subprocess.run que escreve payloads[i] em out."""

    def fake_run(cmd: list[str], check: bool, text: bool) -> None:
        calls.append(list(cmd))
        out.parent.mkdir(parents=True, exist_ok=True)
        idx = min(len(calls) - 1, len(payloads) - 1)
        out.write_bytes(payloads[idx])

    return fake_run


def _good_docx_bytes(tmp_path: Path) -> bytes:
    good = _write_minimal_docx(tmp_path / "_good_fixture.docx")
    return good.read_bytes()


def test_run_and_validate_passes_first_try(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [_good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 1


def test_run_and_validate_retries_once_on_corrupt_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [b"lixo nao-zip", _good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 2


def test_run_and_validate_raises_after_second_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    with pytest.raises(CorruptDocxError) as exc:
        _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 2
    assert "re-executar" in str(exc.value)
    assert str(out) in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: FAIL na coleta — `ImportError: cannot import name '_run_and_validate_docx'`

- [ ] **Step 3: Write minimal implementation**

Em `export.py`, após `_validate_docx_structure`:

```python
def _run_and_validate_docx(cmd: list[str], out: Path) -> None:
    """Roda o pandoc para docx garantindo saída estruturalmente válida.

    Defeito documentado do pipeline (docs do BBT): o Word ocasionalmente
    acusa o docx como corrompido e re-executar o mesmo comando conserta.
    Automatiza exatamente isso — valida, re-executa UMA vez, e falha alto
    se persistir. Nunca entrega arquivo suspeito silenciosamente.
    """
    subprocess.run(cmd, check=True, text=True)
    problems = _validate_docx_structure(out)
    if not problems:
        return
    logger.warning(
        "docx falhou na validação estrutural (%s); re-executando o pandoc",
        "; ".join(problems),
    )
    subprocess.run(cmd, check=True, text=True)
    problems = _validate_docx_structure(out)
    if problems:
        raise CorruptDocxError(
            "O docx gerado continua estruturalmente inválido mesmo após "
            f"re-executar o pandoc: {'; '.join(problems)}. Arquivo: {out}. "
            "Rode novamente `prumo write export --to docx`; se persistir, abra "
            "uma issue com o markdown de entrada: "
            "https://github.com/raphaelfh/prumo-assist/issues"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/write/test_export_docx_validation.py src/prumo_assist/domains/write/export.py
git commit -m "feat(write): retry automático do pandoc quando o docx sai corrompido"
```

---

### Task 3: Guarda de regressão das ZOTERO_PREF (`_assert_zotero_prefs_present`)

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (após `_assert_bibliography_present`, ~linha 237)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append)

**Interfaces:**
- Consumes: `_docx_zotero_field_counts` (existente, linha 211); `zipfile`.
- Produces: `MissingZoteroPrefsError(RuntimeError)`; `_assert_zotero_prefs_present(docx_path: Path) -> None`. **Consumida pela Task 4.**

- [ ] **Step 1: Write the failing tests**

Append no mesmo arquivo de teste:

```python
from prumo_assist.domains.write.export import (
    MissingZoteroPrefsError,
    _assert_zotero_prefs_present,
)


def test_prefs_present_with_citations_ok(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "com_prefs.docx", items=2, prefs=True)
    _assert_zotero_prefs_present(docx)  # não levanta


def test_prefs_missing_custom_xml_raises(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_custom.docx", items=2, prefs=False)
    with pytest.raises(MissingZoteroPrefsError) as exc:
        _assert_zotero_prefs_present(docx)
    assert "ZOTERO_PREF_1" in str(exc.value)
    assert "Document Preferences" in str(exc.value)


def test_prefs_custom_xml_without_pref_raises(tmp_path: Path) -> None:
    docx = tmp_path / "custom_vazio.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", "<w:document>ZOTERO_ITEM CSL_CITATION</w:document>")
        z.writestr("docProps/custom.xml", "<Properties/>")
    with pytest.raises(MissingZoteroPrefsError):
        _assert_zotero_prefs_present(docx)


def test_prefs_not_required_without_citations(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_citacao.docx", items=0, prefs=False)
    _assert_zotero_prefs_present(docx)  # não levanta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: FAIL na coleta — `ImportError: cannot import name 'MissingZoteroPrefsError'`

- [ ] **Step 3: Write minimal implementation**

Em `export.py`, após `_assert_bibliography_present`:

```python
class MissingZoteroPrefsError(RuntimeError):
    """Docx com citações vivas mas sem ZOTERO_PREF em ``docProps/custom.xml``."""


def _assert_zotero_prefs_present(docx_path: Path) -> None:
    """Guarda de regressão do ``zotero_live_docx.lua``.

    O filtro embute ``ZOTERO_PREF_1``/``ZOTERO_PREF_2`` para o plugin Word
    reconhecer o documento sem abrir o diálogo "Document Preferences" no
    primeiro Refresh. Se as prefs sumirem (regressão no filtro), o coautor
    Word-cêntrico é exatamente quem paga o pato — falha alto aqui.
    """
    items, _bibl = _docx_zotero_field_counts(docx_path)
    if items == 0:
        return
    with zipfile.ZipFile(docx_path) as z:
        try:
            custom = z.read("docProps/custom.xml").decode("utf-8", errors="replace")
        except KeyError:
            custom = ""
    if "ZOTERO_PREF_1" not in custom:
        raise MissingZoteroPrefsError(
            f"O docx tem {items} citação(ões) vivas mas docProps/custom.xml não "
            "carrega ZOTERO_PREF_1 — regressão do filtro zotero_live_docx.lua "
            "(sem as prefs, o plugin Word abre o diálogo 'Document Preferences' "
            "no primeiro Refresh). Re-exporte com `prumo write export --to docx`; "
            "se persistir, abra uma issue: "
            "https://github.com/raphaelfh/prumo-assist/issues"
        )
```

Nota (classe no meio do arquivo): manter a definição de `MissingZoteroPrefsError` junto das demais exceções do topo do módulo (após `MissingBibliographyPlaceholderError`, linha ~61) se o ruff reclamar de ordem; a função fica após `_assert_bibliography_present`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add tests/unit/write/test_export_docx_validation.py src/prumo_assist/domains/write/export.py
git commit -m "feat(write): guarda de regressão das ZOTERO_PREF no docx exportado"
```

---

### Task 4: Ligar validação+retry em `export()` e `compose()`

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py:401-404` (corpo de `export()`) e `:505-507` (corpo de `compose()`)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append)

**Interfaces:**
- Consumes: `_run_and_validate_docx` (Task 2), `_assert_zotero_prefs_present` (Task 3), `_assert_bibliography_present` (existente).
- Produces: `export()`/`compose()` com `to="docx"` passam pela validação; comportamento dos demais formatos inalterado.

- [ ] **Step 1: Write the failing tests**

Append no mesmo arquivo de teste:

```python
def _fake_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "pj_demo"
    (root / "references").mkdir(parents=True)
    (root / "references" / "_references.bib").write_text("@article{smith2020, title={X}}\n")
    page = root / "docs" / "page.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto sem citação.\n")
    return root, page


def _patch_export_seams(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csl = tmp_path / "apa.csl"
    csl.write_text("<style/>")
    monkeypatch.setattr(export_mod, "_check_pandoc", lambda: "pandoc")
    monkeypatch.setattr(export_mod, "_check_bbt_running", lambda timeout=2.0: None)
    monkeypatch.setattr(export_mod, "resolve_csl", lambda style: csl)
    monkeypatch.setattr(
        export_mod, "fetch_bbt_zotero_metadata", lambda keys, lib: {}
    )


def _fake_run_writing_output_flag(
    payloads: list[bytes], calls: list[list[str]]
) -> object:
    """Substituto de subprocess.run que resolve o alvo pelo --output= do cmd."""

    def fake_run(cmd: list[str], check: bool, text: bool) -> None:
        calls.append(list(cmd))
        target = Path(next(a.split("=", 1)[1] for a in cmd if a.startswith("--output=")))
        target.parent.mkdir(parents=True, exist_ok=True)
        idx = min(len(calls) - 1, len(payloads) - 1)
        target.write_bytes(payloads[idx])

    return fake_run


def test_export_docx_fails_loud_after_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    with pytest.raises(CorruptDocxError):
        export_mod.export(page=page, to="docx", project_root=root)
    assert len(calls) == 2


def test_export_docx_happy_path_single_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([_good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    result = export_mod.export(page=page, to="docx", project_root=root)
    assert result.suffix == ".docx"
    assert result.is_file()
    assert len(calls) == 1


def test_export_html_does_not_validate_docx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"<html>ok</html>"], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    result = export_mod.export(page=page, to="html", project_root=root)
    assert result.suffix == ".html"
    assert len(calls) == 1  # sem retry, sem validação de zip


def test_compose_docx_goes_through_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _page = _fake_project(tmp_path)
    index = root / "docs" / "index.md"
    index.write_text("---\npages: [docs/page.md]\n---\n")
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr(export_mod.subprocess, "run", fake)
    with pytest.raises(CorruptDocxError):
        export_mod.compose(index=index, to="docx", project_root=root)
    assert len(calls) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v`
Expected: `test_export_docx_fails_loud_after_retry` e `test_compose_docx_goes_through_validation` FALHAM (hoje `export()`/`compose()` chamam `subprocess.run` direto — lixo não-zip estoura como `zipfile.BadZipFile` dentro de `_assert_bibliography_present`, não como `CorruptDocxError`, e `calls == 1`). `test_export_docx_happy_path_single_run` e `test_export_html_does_not_validate_docx` já passam antes da implementação — são guardas de regressão.

- [ ] **Step 3: Write the implementation**

Em `export()` (linhas 401–404), substituir:

```python
        logger.info("pandoc cmd: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, text=True)
        if to == "docx":
            _assert_bibliography_present(out)
```

por:

```python
        logger.info("pandoc cmd: %s", " ".join(cmd))
        if to == "docx":
            _run_and_validate_docx(cmd, out)
            _assert_bibliography_present(out)
            _assert_zotero_prefs_present(out)
        else:
            subprocess.run(cmd, check=True, text=True)
```

Em `compose()` (linhas 505–507), substituir:

```python
        subprocess.run(cmd, check=True, text=True)
        if to == "docx":
            _assert_bibliography_present(out)
```

por:

```python
        if to == "docx":
            _run_and_validate_docx(cmd, out)
            _assert_bibliography_present(out)
            _assert_zotero_prefs_present(out)
        else:
            subprocess.run(cmd, check=True, text=True)
```

- [ ] **Step 4: Run the full write suite**

Run: `uv run pytest tests/unit/write/ -v`
Expected: todos passam (17 no arquivo novo + suíte existente inalterada)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/write/test_export_docx_validation.py src/prumo_assist/domains/write/export.py
git commit -m "fix(write): export/compose docx passam por validação estrutural com retry"
```

---

### Task 5: Nota de primeiro uso no Word na saída do CLI

**Files:**
- Modify: `src/prumo_assist/domains/write/cli.py` (em `export_command`, após `console.success` linha ~68; e no comando de compose, após `console.success` linha ~112)
- Test: Modify `tests/unit/write/test_cli.py` (append)

**Interfaces:**
- Consumes: `Console.info` (mesmo padrão do `doctor` em `cli.py:584-590`); `export.export`/`export.compose` (patchados no teste).
- Produces: constante `FIRST_USE_DOCX_NOTE: str` no módulo `domains/write/cli.py`, impressa só quando `to == "docx"`.

- [ ] **Step 1: Write the failing tests**

Append em `tests/unit/write/test_cli.py`:

```python
def _pj_with_bib(tmp_path: Path) -> tuple[Path, Path]:
    pj = tmp_path / "pj_demo"
    (pj / "references").mkdir(parents=True)
    (pj / "references" / "_references.bib").write_text("@article{k2020, title={T}}\n")
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")
    return pj, page


def test_write_export_docx_prints_first_use_note(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    pj, page = _pj_with_bib(tmp_path)
    fake_out = pj / "build" / "exports" / "p.docx"
    monkeypatch.setattr(
        "prumo_assist.domains.write.cli.export.export", lambda **kw: fake_out
    )
    result = runner.invoke(app, ["write", "export", str(page), "--to", "docx"])
    assert result.exit_code == 0, result.output
    assert "Primeiro uso no Word" in result.output


def test_write_export_html_omits_first_use_note(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    pj, page = _pj_with_bib(tmp_path)
    fake_out = pj / "build" / "exports" / "p.html"
    monkeypatch.setattr(
        "prumo_assist.domains.write.cli.export.export", lambda **kw: fake_out
    )
    result = runner.invoke(app, ["write", "export", str(page), "--to", "html"])
    assert result.exit_code == 0, result.output
    assert "Primeiro uso no Word" not in result.output
```

E adicionar `import pytest` no topo do arquivo de teste (junto aos imports existentes) se ainda não houver.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/write/test_cli.py -v -k first_use`
Expected: `test_write_export_docx_prints_first_use_note` FAIL (`"Primeiro uso no Word" not in output`); o teste de html PASSA.

- [ ] **Step 3: Write the implementation**

Em `src/prumo_assist/domains/write/cli.py`, adicionar constante de módulo (após os imports):

```python
FIRST_USE_DOCX_NOTE = (
    "Primeiro uso no Word: abra o arquivo com o plugin do Zotero instalado e "
    "use Zotero → Refresh para atualizar citações e bibliografia. As "
    "preferências do documento já vão embutidas (ZOTERO_PREF) — o diálogo "
    "'Document Preferences' não deve abrir."
)
```

Em `export_command`, substituir:

```python
        console.success(f"exportado: {result}")
        console.emit({"page": str(page_resolved), "output": str(result), "format": to})
```

por:

```python
        console.success(f"exportado: {result}")
        if to == "docx":
            console.info(FIRST_USE_DOCX_NOTE)
        console.emit({"page": str(page_resolved), "output": str(result), "format": to})
```

No comando de compose (linha ~112), substituir:

```python
        console.success(f"composto: {result}")
        console.emit({"index": str(index_resolved), "output": str(result), "format": to})
```

por:

```python
        console.success(f"composto: {result}")
        if to == "docx":
            console.info(FIRST_USE_DOCX_NOTE)
        console.emit({"index": str(index_resolved), "output": str(result), "format": to})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/write/test_cli.py -v`
Expected: todos passam (2 novos + existentes)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/write/test_cli.py src/prumo_assist/domains/write/cli.py
git commit -m "feat(write): nota de primeiro uso no Word na saída do export docx"
```

---

### Task 6: `doctor` detecta versão do Zotero (par suportado: 9+)

**Files:**
- Modify: `src/prumo_assist/core/deps.py`
- Test: Modify `tests/unit/core/test_deps.py`

**Interfaces:**
- Consumes: `_zotero_host_port`, `_port_open` (existentes).
- Produces: `DepStatus` ganha campo `version: str | None = None` (incluído em `as_dict()`); seam `_zotero_version_header(host: str, port: int, timeout: float = 2.0) -> str | None`; `_zotero_major(version: str | None) -> int | None`; constante `_SUPPORTED_ZOTERO_MAJOR = 9`. Nenhuma mudança em `cli.py` — a renderização existente (`✓/○ + detail`, hint quando `present` é False) já cobre o caso.

- [ ] **Step 1: Write the failing tests**

Em `tests/unit/core/test_deps.py`, **substituir** o teste `test_dep_status_is_serializable` por:

```python
def test_dep_status_is_serializable() -> None:
    s = DepStatus(name="x", present=True, required_by=["foo"], detail="d", hint="h")
    assert s.as_dict() == {
        "name": "x",
        "present": True,
        "required_by": ["foo"],
        "detail": "d",
        "hint": "h",
        "version": None,
    }
```

E **append** ao final do arquivo (antes de `_by_name`):

```python
def test_zotero_supported_version_stays_present() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value="9.0.6"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version == "9.0.6"
    assert "9.0.6" in zot.detail


def test_zotero_below_floor_flags_unsupported() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value="8.0.2"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version == "8.0.2"
    assert "Zotero 9+" in zot.detail
    assert "zotero.org/download" in zot.hint


def test_zotero_undetectable_version_is_fail_safe() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value=None),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version is None
    assert "versão não detectada" in zot.detail


def test_zotero_version_probe_skipped_when_port_closed() -> None:
    def _explode(host: str, port: int, timeout: float = 2.0) -> str | None:
        raise AssertionError("probe de versão não deveria rodar com porta fechada")

    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
        patch("prumo_assist.core.deps._zotero_version_header", new=_explode),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_deps.py -v`
Expected: FAIL — `test_dep_status_is_serializable` (sem chave `version`) e os 4 novos com `AttributeError`/`patch` de `_zotero_version_header` inexistente.

- [ ] **Step 3: Write the implementation**

Em `src/prumo_assist/core/deps.py`:

1. Imports — adicionar após `import socket`:

```python
import re
import urllib.error
import urllib.request
```

2. `DepStatus` — adicionar campo e chave no dict:

```python
@dataclass
class DepStatus:
    """Estado de uma dependência externa."""

    name: str
    present: bool
    required_by: list[str]
    detail: str
    hint: str
    version: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "required_by": self.required_by,
            "detail": self.detail,
            "hint": self.hint,
            "version": self.version,
        }
```

3. Após `_zotero_host_port`, adicionar:

```python
_SUPPORTED_ZOTERO_MAJOR = 9


def _zotero_version_header(host: str, port: int, timeout: float = 2.0) -> str | None:
    """Versão do Zotero via header ``X-Zotero-Version`` do connector ping.

    Seam testável. ``None`` = não detectável (fail-safe: não reprova).
    """
    url = f"http://{host}:{port}/connector/ping"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            value = resp.headers.get("X-Zotero-Version")
            return str(value) if value else None
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None


def _zotero_major(version: str | None) -> int | None:
    if not version:
        return None
    m = re.match(r"(\d+)", version)
    return int(m.group(1)) if m else None
```

4. Em `check_external_deps()`, substituir o bloco do zotero (do `host, port = _zotero_host_port()` até o `statuses.append(...)` correspondente) por:

```python
    host, port = _zotero_host_port()
    zotero_up = _port_open(host, port)
    version = _zotero_version_header(host, port) if zotero_up else None
    major = _zotero_major(version)
    supported = major is None or major >= _SUPPORTED_ZOTERO_MAJOR

    if not zotero_up:
        detail = f"nada escutando em {host}:{port}"
        hint = (
            f"Abra o Zotero 9 (com Better BibTeX instalado) — ele expõe a API "
            f"local em {host}:{port}. Só é necessário pros comandos "
            f"que leem anotações/notas; o resto do prumo funciona sem ele."
        )
    elif not supported:
        detail = (
            f"Zotero {version} rodando em {host}:{port} — abaixo do par "
            f"suportado (Zotero 9+ com Better BibTeX)"
        )
        hint = (
            "Atualize para o Zotero 9+: baixe em https://www.zotero.org/download, "
            "instale e reabra o app. Depois atualize o Better BibTeX em "
            "Tools → Plugins se ele avisar (o BBT acompanha o major do Zotero)."
        )
    elif version is None:
        detail = f"API local respondendo em {host}:{port} (versão não detectada)"
        hint = ""
    else:
        detail = f"API local respondendo em {host}:{port} — Zotero {version}"
        hint = ""

    statuses.append(
        DepStatus(
            name="zotero",
            present=zotero_up and supported,
            required_by=["paper sync-annotations", "paper sync-notes", "write export --to docx"],
            detail=detail,
            hint=hint,
            version=version,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_deps.py -v`
Expected: todos passam (7 existentes ajustados + 4 novos)

- [ ] **Step 5: Verificação empírica do endpoint (Zotero real da máquina)**

Run (com o Zotero aberto): `curl -sI http://127.0.0.1:23119/connector/ping | grep -i x-zotero-version`
Expected: `X-Zotero-Version: 9.x.y`

Se o header NÃO vier: rodar `curl -sI http://127.0.0.1:23119/connector/ping` completo e inspecionar os headers reais; ajustar o nome do header na função `_zotero_version_header` (o seam isola a mudança — testes não mudam). Registrar o header observado no checkbox deste passo ao marcar. Aproveitar e testar se existe versão do BBT exposta: `curl -s http://127.0.0.1:23119/better-bibtex/version` — se retornar algo útil, anotar no plano (candidato a preencher `version` do BBT em fase futura; NÃO implementar agora).

- [ ] **Step 6: Commit**

```bash
git add tests/unit/core/test_deps.py src/prumo_assist/core/deps.py
git commit -m "feat(core): doctor detecta versão do Zotero e sinaliza par fora do suportado (9+)"
```

---

### Task 7: CHANGELOG + verificação completa do repo

**Files:**
- Modify: `CHANGELOG.md` (seção `## [Não publicado]`, linha 8)

**Interfaces:**
- Consumes: tudo das Tasks 1–6.
- Produces: entrada de changelog; repo verde em pytest + ruff + mypy + índices.

- [ ] **Step 1: Escrever a entrada do CHANGELOG**

Substituir em `CHANGELOG.md`:

```markdown
## [Não publicado]
```

por:

```markdown
## [Não publicado]

### Corrigido
- `prumo write export/compose --to docx`: o docx gerado passa por validação
  estrutural (zip, partes obrigatórias, `[Content_Types].xml`) com um retry
  automático do pandoc — absorve o defeito intermitente de "arquivo
  corrompido" documentado no pipeline BBT/pandoc; se persistir, falha alto
  (`CorruptDocxError`) em vez de entregar arquivo suspeito. Guarda de
  regressão das `ZOTERO_PREF` embutidas (`MissingZoteroPrefsError`).
  Fase 1 do spec zero-friction onboarding.

### Mudado
- `prumo doctor` detecta a versão do Zotero pela API local e sinaliza par
  fora do suportado (Zotero 9+) com o comando de correção na mensagem;
  o payload JSON de `external_deps` ganha o campo `version`.
- Export docx imprime nota de primeiro uso no Word (Zotero → Refresh;
  prefs já embutidas).
```

- [ ] **Step 2: Rodar a bateria completa do repo**

Run: `uv run pytest`
Expected: suíte inteira verde.

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: sem erros (se `ruff format --check` acusar os arquivos tocados, rodar `uv run ruff format <arquivos>` e re-checar).

Run: `uv run mypy`
Expected: `Success: no issues found`.

Run: `uv run python .github/scripts/gen_indexes.py --check`
Expected: índices em dia (nenhuma skill/índice foi tocado neste plano).

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): registra Fase 1 do zero-friction onboarding em Não publicado"
```

---

## Verificação final (antes de marcar o plano como implemented)

- [ ] Todos os checkboxes acima marcados; suíte, ruff, mypy e `gen_indexes --check` verdes no mesmo commit final.
- [ ] Smoke manual (opcional, exige pandoc+Zotero reais): `uv run prumo write export <página real> --to docx` num `pj_*` de verdade — conferir a nota de primeiro uso e abrir o docx no Word.
- [ ] Critérios do spec Fase 1 cobertos: validação estrutural ✓ (T1), retry+hard-fail ✓ (T2/T4), primeira abertura ✓ (T3 guarda + T5 nota), doctor churn ✓ (T6, com desvio BBT documentado no cabeçalho).
- [ ] Release PATCH: **não** faz parte deste plano — quando o dono decidir, seguir RELEASING.md (o CHANGELOG já está pronto em "Não publicado").

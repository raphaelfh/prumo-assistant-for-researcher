# Zero-friction Fase 4 — Colapso de Dependências (escopo A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prumo paper connect <coleção>` cria programaticamente o fio coleção-do-Zotero→`references/_references.bib` via `autoexport.add` do Better BibTeX, com guardas anti-fantasma — matando a dor nº 1 do piloto; a dor nº 2 (qmd) é resolvida por reposicionamento documentado (fallback lexical = caminho normal da persona) + conectores recomendados nos docs (PubMed oficial, cookjohn não-validado, Zettlr). Zero dependência nova.

**Architecture:** Novo módulo focado `domains/paper/connect.py` reusando o seam JSON-RPC existente (`_http_post_json` + `_bbt_rpc` de `domains/paper/zotero.py`): lista coleções via `user.groups(true)` (read-only, provado ao vivo), resolve nome→caminho BBT com desambiguação multi-library e fuzzy-match, e só então faz a ÚNICA chamada mutante do repo no Zotero do usuário: `autoexport.add(collection, translator, path)` (assinatura provada ao vivo por erro -32602). Guardas: typo NUNCA cria coleção (validação antes do add); bib já povoado → hard-fail orientado (sem re-add cego, que duplicaria autoexport). CLI fachada fina no padrão sync-annotations (Zotero fechado → exit 2). Doctor ganha detecção de "bib ainda é placeholder do scaffold".

**Tech Stack:** Python 3.11 stdlib (urllib via seam existente, difflib p/ sugestões), pytest com seam mockado, Markdown (skill/docs).

## Global Constraints

- Emenda da Fase 4 do spec (aprovada pelo dono 2026-07-25, escopo A): item 1 = connect via autoexport com guardas; item 2 = qmd→MCPB REFUTADO, fallback lexical vira caminho normal documentado; item 3 = docs de conectores (PubMed via `anthropics/life-sciences`, cookjohn com rótulo "não validado neste piloto", Zettlr recomendado).
- Fatos provados AO VIVO (2026-07-25, Zotero 9.0.6 + BBT do dono): `autoexport.add` existe com params obrigatórios `collection`, `translator`, `path` (erro -32602 com params vazios); `user.groups(true)` devolve `[{id, name, collections: [{key, name, parentCollection: false|"<key-do-pai>", ...}]}]` — lista PLANA por library com ponteiro de pai. GUID estável do Better BibLaTeX: `f895aa0d-f28e-47fe-b247-2ea77c6ed583`. Formato de coleção do autoexport: `/<Library>/<Pai>/<Filha>` (biblioteca pessoal aceita `//<Coleção>`; usar SEMPRE a forma com library explícita — o Zotero do piloto tem 6 libraries).
- RISCO CENTRAL (grounding verificado): `autoexport.add` CRIA a coleção (e intermediárias) se não existir → a validação de existência ANTES do add é a guarda inegociável; nenhum teste ou código jamais chama `autoexport.add` contra o Zotero VIVO (testes mockam o seam; smoke real é passo manual do dono).
- NENHUM teste toca rede/Zotero: monkeypatch string-target em `prumo_assist.domains.paper.connect._http_post_json` (re-import local do seam).
- Layering/facade/mensagens: regras da casa (`cli_run`, `Console`, pt-BR com comando de correção, mypy --strict cobrindo tests/, frozen dataclasses, `from __future__ import annotations`).
- Zotero fechado → mesmo padrão do `sync-annotations` (`domains/paper/cli.py` linhas ~175–210): erro pt-BR limpo + `exit_code=2`.
- Bateria completa ao fim de cada task, NENHUM passo pulado: `uv run pytest` && `uv run ruff check .` && `uv run ruff format --check .` && `uv run mypy` && `uv run python .github/scripts/gen_indexes.py --check`. (T5 adiciona `validate_manifests.py`.)
- NÃO bumpar versão (release é ciclo separado; ADR-0015). Não tocar `docs/superpowers/plans/*` nos commits das tasks.
- Fora de escopo: qualquer empacotamento MCPB/.xpi; adoção de zotero-mcp de terceiros como dependência; `--replace`/reconexão automática (re-add cego duplica autoexport — fica registrado como follow-up gated).

---

### Task 1: Motor `connect.py` — resolução de coleção + autoexport com guardas

**Files:**
- Create: `src/prumo_assist/domains/paper/connect.py`
- Test: `tests/unit/paper/test_connect.py` (novo)

**Interfaces:**
- Consumes (existente): `from prumo_assist.domains.paper.zotero import _bbt_rpc, _http_post_json` (seam JSON-RPC sem auth; `_http_post_json(url, payload, timeout=10.0) -> object`); `from prumo_assist.core.bib import parse_bib`.
- Produces (T2/T3 consomem):

```python
BETTER_BIBLATEX_GUID = "f895aa0d-f28e-47fe-b247-2ea77c6ed583"

@dataclass(frozen=True)
class CollectionRef:
    library: str      # ex. "My Library"
    path: str         # ex. "Pesquisa/Colecao do estudo piloto1" (cadeia de pais)
    bbt_path: str     # ex. "/My Library/Pesquisa/Colecao do estudo piloto1"

@dataclass(frozen=True)
class ConnectResult:
    collection: CollectionRef
    bib_path: Path
    exported: bool    # True se o bib deixou de ser placeholder dentro do poll

class ZoteroOfflineError(RuntimeError): ...
class CollectionNotFoundError(RuntimeError): ...
class AmbiguousCollectionError(RuntimeError): ...
class AlreadyConnectedError(RuntimeError): ...

def list_collections() -> list[CollectionRef]: ...
def find_collection(name: str, *, library: str | None = None) -> CollectionRef: ...
def bib_is_placeholder(pj_path: Path) -> bool: ...
def connect_collection(
    pj_path: Path, name: str, *, library: str | None = None,
    poll_timeout: float = 10.0, poll_interval: float = 0.5,
) -> ConnectResult: ...
```

Regras exatas:
- `list_collections`: chama `user.groups` com params `[True]`; para cada library, monta cadeia de pais via mapa `key -> (name, parentCollection)` (parent `False`/ausente = raiz); resposta hostil (não-lista, library sem `collections`) → ignora o pedaço malformado sem crashar. `urllib.error.URLError`/`OSError`/JSON hostil do seam → `ZoteroOfflineError` com msg: `"Zotero não respondeu em 127.0.0.1:23119 — abra o Zotero (com Better BibTeX instalado) e rode de novo."`.
- `find_collection`: match por `casefold()` no ÚLTIMO segmento do path (nome da coleção). 0 matches → `CollectionNotFoundError` com até 3 sugestões via `difflib.get_close_matches` sobre todos os nomes (msg: `"coleção '{name}' não existe no Zotero — NADA foi criado. Parecidas: {sugestões}. Confira o nome exato no Zotero."`); >1 match e `library is None` → `AmbiguousCollectionError` listando os `bbt_path` candidatos + hint `--library`; com `library`, filtra por `library.casefold()` antes.
- `bib_is_placeholder`: True se o arquivo não existe, está vazio, ou (1ª linha começa com `"% Bibliografia do projeto"` E `parse_bib(texto)` devolve `[]`).
- `connect_collection`: (guarda 1) se NÃO `bib_is_placeholder` → `AlreadyConnectedError`: `"references/_references.bib já tem entradas reais — reconectar às cegas duplicaria o export automático. Confira no Zotero: Preferences → Better BibTeX → Automatic export."`; (guarda 2) `find_collection` valida existência ANTES de qualquer mutação; então chama `autoexport.add` com params POSICIONAIS `[ref.bbt_path, BETTER_BIBLATEX_GUID, str(bib.resolve())]`; erro JSON-RPC na resposta (`"error"` no dict) → `ZoteroOfflineError` com a mensagem do BBT embutida; poll: até `poll_timeout`, dormindo `poll_interval` via seam módulo-level `_sleep = time.sleep` (monkeypatchável), checando `not bib_is_placeholder(pj_path)` → `exported=True`; timeout → `exported=False` (não é erro — o export do BBT pode demorar; a mensagem do CLI cobre).

- [ ] **Step 1: Testes que falham** — criar `tests/unit/paper/test_connect.py` (mypy strict cobre tests/; monkeypatch SEMPRE string-target):

```python
"""Testes do prumo paper connect (Fase 4 do zero-friction) — seam 100% mockado."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from prumo_assist.domains.paper import connect

_GROUPS = [
    {
        "id": 1,
        "name": "My Library",
        "collections": [
            {"key": "AAA", "name": "Pesquisa", "parentCollection": False},
            {"key": "BBB", "name": "Colecao do estudo piloto1", "parentCollection": "AAA"},
        ],
    },
    {
        "id": 5,
        "name": "Lab Group",
        "collections": [{"key": "CCC", "name": "Pesquisa", "parentCollection": False}],
    },
]


def _fake_rpc(responses: dict[str, Any]):
    calls: list[dict[str, Any]] = []

    def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        calls.append(payload)
        method = payload["method"]
        if method in responses:
            value = responses[method]
            if isinstance(value, Exception):
                raise value
            return value
        raise AssertionError(f"método inesperado: {method}")

    return fake, calls


def _pj(tmp_path: Path, *, bib_text: str | None) -> Path:
    refs = tmp_path / "references"
    refs.mkdir(parents=True)
    if bib_text is not None:
        (refs / "_references.bib").write_text(bib_text, encoding="utf-8")
    return tmp_path


_PLACEHOLDER = "% Bibliografia do projeto — formato Better BibTeX (BBT).\n%\n% Fluxo...\n"


class TestFindCollection:
    def test_resolve_com_cadeia_de_pais(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        ref = connect.find_collection("Colecao do estudo piloto1")
        assert ref.bbt_path == "/My Library/Pesquisa/Colecao do estudo piloto1"
        assert ref.library == "My Library"

    def test_ambigua_sem_library_lista_candidatos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AmbiguousCollectionError, match="--library"):
            connect.find_collection("Pesquisa")

    def test_ambigua_resolve_com_library(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        ref = connect.find_collection("Pesquisa", library="Lab Group")
        assert ref.bbt_path == "/Lab Group/Pesquisa"

    def test_inexistente_sugere_e_garante_nada_criado(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
            connect.find_collection("Pesquisa Typo")
        assert all(c["method"] == "user.groups" for c in calls)  # nenhum autoexport.add

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        assert connect.find_collection("Colecao do estudo piloto1").library == "My Library"


class TestBibPlaceholder:
    def test_placeholder_do_scaffold(self, tmp_path: Path) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        assert connect.bib_is_placeholder(pj) is True

    def test_bib_com_entrada_real(self, tmp_path: Path) -> None:
        pj = _pj(tmp_path, bib_text="@article{x2020,\n  title = {T},\n}\n")
        assert connect.bib_is_placeholder(pj) is False

    def test_ausente_e_vazio_sao_placeholder(self, tmp_path: Path) -> None:
        assert connect.bib_is_placeholder(_pj(tmp_path, bib_text=None)) is True
        assert connect.bib_is_placeholder(_pj(tmp_path / "b", bib_text="")) is True


class TestConnectCollection:
    def test_happy_path_add_e_export(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        bib = pj / "references" / "_references.bib"

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            if payload["method"] == "autoexport.add":
                assert payload["params"] == [
                    "/My Library/Pesquisa/Colecao do estudo piloto1",
                    connect.BETTER_BIBLATEX_GUID,
                    str(bib.resolve()),
                ]
                bib.write_text("@article{a2020,\n  title = {A},\n}\n", encoding="utf-8")
                return {"jsonrpc": "2.0", "result": {"status": "ok"}}
            raise AssertionError(payload["method"])

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        result = connect.connect_collection(pj, "Colecao do estudo piloto1")
        assert result.exported is True
        assert result.collection.bbt_path.endswith("Colecao do estudo piloto1")

    def test_bib_povoado_recusa_sem_mutacao(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text="@article{x2020,\n  title = {T},\n}\n")
        fake, calls = _fake_rpc({})  # NENHUM método deveria ser chamado
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AlreadyConnectedError, match="Automatic export"):
            connect.connect_collection(pj, "Pesquisa")
        assert calls == []

    def test_poll_timeout_vira_exported_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            return {"jsonrpc": "2.0", "result": {"status": "ok"}}  # add ok, mas bib nunca muda

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        result = connect.connect_collection(pj, "Pesquisa", library="Lab Group", poll_timeout=0.1)
        assert result.exported is False

    def test_erro_jsonrpc_no_add_vira_offline_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": "boom"}}

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.ZoteroOfflineError, match="boom"):
            connect.connect_collection(pj, "Pesquisa", library="My Library")

    def test_zotero_fechado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, _ = _fake_rpc({"user.groups": urllib.error.URLError("refused")})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.ZoteroOfflineError, match="abra o Zotero"):
            connect.connect_collection(pj, "Pesquisa")
```

- [ ] **Step 2: Ver falhar** — `uv run pytest tests/unit/paper/test_connect.py -x -q` → FAIL (módulo inexistente).
- [ ] **Step 3: Implementar `connect.py`** conforme as regras exatas acima (docstring de módulo em pt-BR citando a emenda da F4 e o RISCO do autoexport.add criar coleção — por isso a validação vem antes; `_sleep = time.sleep` módulo-level; imports do seam: `from prumo_assist.domains.paper.zotero import _bbt_rpc, _http_post_json`; re-expor localmente `_http_post_json = _http_post_json` NÃO — em vez disso, chame via nome local importado; para o monkeypatch string-target funcionar, importe como `from prumo_assist.domains.paper import zotero` e defina wrapper fino `def _http_post_json(url, payload, timeout=10.0): return zotero._http_post_json(url, payload, timeout)` — o wrapper É o seam local deste módulo).
- [ ] **Step 4: Bateria completa.**
- [ ] **Step 5: Commit** — `git add src/prumo_assist/domains/paper/connect.py tests/unit/paper/test_connect.py && git commit -m "feat(paper): motor do connect — coleção→bib via BBT autoexport com guardas anti-fantasma (F4 emendada)"`

---

### Task 2: CLI `prumo paper connect` + re-export em `api.py`

**Files:**
- Modify: `src/prumo_assist/domains/paper/cli.py`
- Modify: `src/prumo_assist/domains/paper/api.py` (re-export puro de `connect_collection`)
- Test: `tests/unit/paper/test_cli.py` (append)

**Interfaces:** consome T1 (`connect.connect_collection`, exceções, `ConnectResult`). Padrão de Zotero-fechado: MESMA mecânica do `sync-annotations` (ler `domains/paper/cli.py` linhas ~175–210 antes: catches + `exit_code=2`).

- [ ] **Step 1: Testes que falham** (append em test_cli.py; padrões do arquivo: `runner`, `app`, fakes anotados):

```python
def test_paper_connect_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from prumo_assist.domains.paper.connect import CollectionRef, ConnectResult

    result_obj = ConnectResult(
        collection=CollectionRef(
            library="My Library", path="Pesquisa", bbt_path="/My Library/Pesquisa"
        ),
        bib_path=tmp_path / "references" / "_references.bib",
        exported=True,
    )

    def fake(*args: Any, **kwargs: Any) -> ConnectResult:
        return result_obj

    monkeypatch.setattr("prumo_assist.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "Pesquisa", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Pesquisa" in result.output and "conectada" in result.output


def test_paper_connect_export_pendente_avisa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from prumo_assist.domains.paper.connect import CollectionRef, ConnectResult

    result_obj = ConnectResult(
        collection=CollectionRef(library="My Library", path="G", bbt_path="/My Library/G"),
        bib_path=tmp_path / "b.bib",
        exported=False,
    )

    def fake(*args: Any, **kwargs: Any) -> ConnectResult:
        return result_obj

    monkeypatch.setattr("prumo_assist.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "G", "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "instantes" in result.output  # aviso honesto de export agendado


def test_paper_connect_zotero_fechado_exit_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from prumo_assist.domains.paper.connect import ZoteroOfflineError

    def fake(*args: Any, **kwargs: Any) -> Any:
        raise ZoteroOfflineError("Zotero não respondeu em 127.0.0.1:23119 — abra o Zotero.")

    monkeypatch.setattr("prumo_assist.domains.paper.connect.connect_collection", fake)
    result = runner.invoke(app, ["paper", "connect", "X", "--path", str(tmp_path)])
    assert result.exit_code == 2
    assert "abra o Zotero" in result.output
```

- [ ] **Step 2: Ver falhar** (exit 2 do Typer "No such command").
- [ ] **Step 3: Implementar** — comando `connect` no `paper_app`:

```python
@paper_app.command("connect")
def connect_command(
    collection: Annotated[str, typer.Argument(help="Nome da coleção no Zotero (case-insensitive).")],
    library: Annotated[
        str | None, typer.Option("--library", help="Desambigua quando o nome existe em mais de uma library.")
    ] = None,
    path: Annotated[Path, typer.Option("--path", help="pj_* (default cwd).")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Conecta a coleção do Zotero ao projeto: cria o export automático do BBT → references/_references.bib."""
```

corpo: `cli_run` com catches na mecânica do sync-annotations (exceções de T1: `CollectionNotFoundError`/`AmbiguousCollectionError`/`AlreadyConnectedError` → erro pt-BR exit 1; `ZoteroOfflineError` → `exit_code=2`); sucesso: `console.success(f"coleção '{r.collection.path}' ({r.collection.library}) conectada → {r.bib_path}")` e, quando `exported=False`, `console.info("export agendado no BBT — o arquivo aparece em instantes; confira com `prumo paper sync` em seguida.")`; `console.emit` com dict do resultado; próximo passo no output: `prumo paper sync`.

`api.py`: `from prumo_assist.domains.paper.connect import connect_collection` + `__all__`.

- [ ] **Step 4: Bateria.**
- [ ] **Step 5: Commit** — `git add src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_cli.py && git commit -m "feat(paper): CLI paper connect — fachada fina, Zotero fechado = exit 2"`

---

### Task 3: Doctor detecta bib-placeholder (fio não conectado)

**Files:**
- Modify: `src/prumo_assist/cli.py` (função `doctor_command`, ~linha 554 — adicionar o check estrutural do bib)
- Test: `tests/unit/test_cli_doctor.py` (append)

**Interfaces:** consome `connect.bib_is_placeholder(pj_path)` (T1). Comportamento: quando a estrutura do pj está OK mas `bib_is_placeholder` → **warning não-bloqueante** (doctor continua `ok: True` — coerente com qmd opcional): linha `console.warn` + entrada em um campo novo `warnings: list[str]` do payload do doctor com a mensagem: `"references/_references.bib ainda é o placeholder do scaffold — conecte sua coleção do Zotero: prumo paper connect \"<nome da coleção>\""`. Fora de um pj (estrutura ausente) o check NÃO roda.

- [ ] **Step 1: Testes que falham** — append em `tests/unit/test_cli_doctor.py`, usando o helper EXISTENTE `_project(tmp_path)` e o padrão `with patch("prumo_assist.cli.check_external_deps", return_value=[])` do próprio arquivo:

```python
def test_doctor_avisa_bib_placeholder(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "references" / "_references.bib").write_text(
        "% Bibliografia do projeto — formato Better BibTeX (BBT).\n%\n% Fluxo...\n",
        encoding="utf-8",
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert any("prumo paper connect" in w for w in payload["warnings"])


def test_doctor_sem_aviso_com_bib_real(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "references" / "_references.bib").write_text(
        "@article{x2020,\n  title = {T},\n}\n", encoding="utf-8"
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["warnings"] == []
```

(Atenção ao modo `--json` do Console da casa: o payload sai como envelope JSON no stdout — se `json.loads(result.stdout)` falhar por múltiplas linhas, use o helper `_last_json`-style que os testes de `tests/unit/paper/test_cli.py` usam; espelhe o parsing que os testes EXISTENTES deste arquivo já fazem — `test_doctor_json_includes_external_deps` mostra o caminho.)

- [ ] **Step 2: Ver falhar.** — o primeiro teste falha por ausência do aviso.
- [ ] **Step 3: Implementar** no `doctor_command` (import no topo do `cli.py`: `from prumo_assist.domains.paper.connect import bib_is_placeholder`): após o bloco de estrutura OK, `if bib_is_placeholder(project_path): console.warn(...)` + acrescentar ao payload `warnings` (lista; vazia quando nada).
- [ ] **Step 4: Bateria** (atenção: testes existentes do doctor asserem o payload — adicionar `warnings` não pode quebrá-los; se algum asserir igualdade exata do dict, atualize-o citando isso no report).
- [ ] **Step 5: Commit** — `git add src/prumo_assist/cli.py tests/unit/test_cli_doctor.py && git commit -m "feat(doctor): avisa quando o bib ainda é placeholder — hint do paper connect"`

---

### Task 4: Skill paper-manager (operação connect) + docs de conectores e busca

**Files:**
- Modify: `skills/paper-manager/SKILL.md` (nova operação `connect` no corpo humano; NÃO tocar o bloco gerado de preflight nem o frontmatter além de nada — requires já é `[cli, zotero]`, correto para connect)
- Modify: `skills/start/SKILL.md` (corpo humano: no passo 5 da instalação guiada, após `prumo init`, acrescentar o passo de conexão: `prumo paper connect "<coleção>"` com Zotero aberto)
- Modify: `docs/onboarding-pesquisador.md` (3 adições)
- Test: leitura cética + `gen_indexes --check` (description não muda → índices estáveis; confirmar)

Conteúdo obrigatório (fact-checked; strings de comando EXATAS):
1. **paper-manager § connect:** quando o usuário pedir "conecta minha coleção X" → rodar `prumo paper connect "X"` (com `--library` quando o CLI acusar ambiguidade); pré-condição Zotero aberto; sucesso → sugerir `prumo paper sync` na sequência; NUNCA criar/editar o bib à mão para "ajudar" (o autoexport é do BBT; agente não simula).
2. **onboarding — seção "Conectar sua biblioteca":** substituir/complementar a narrativa do fio manual "Keep updated" pela via nova: pedir ao agente "conecta minha coleção <nome>" (ou rodar o comando); nota de que o typo é seguro (o comando valida ANTES e nada é criado no Zotero).
3. **onboarding — seção "Busca e conectores" (nova):** (a) busca no wiki: o caminho normal é a leitura direta do agente (mesmo mecanismo nativo do Cowork) — qmd é opcional-avançado para wikis grandes (exige bun/terminal); (b) conectores de literatura: marketplace oficial `anthropics/life-sciences` in-app (Cowork → Customize → Plugins → Personal plugins → "+" → Add marketplace → Browse Anthropic sources → Life Sciences), destacando PubMed (MCP remoto da Anthropic, sem chave) e clinical-trials; (c) busca semântica DO ACERVO sem terminal: mencionar cookjohn/zotero-mcp (.xpi dentro do Zotero, servidor em 127.0.0.1:23120/mcp) com o rótulo literal **"não validado neste piloto"**; (d) edição dos arquivos: recomendar Zettlr como editor dos `.md` do projeto (convenção de citação `[@key]` é a nativa dele).
4. Rotular fonte quando a afirmação vier do grounding e não de teste próprio (mesmo padrão da nota Windows/WSL).

- [ ] Steps: editar os 3 arquivos → `uv run python .github/scripts/gen_indexes.py --check` (deve ficar limpo sem regenerar; se o gerador acusar, investigue antes de aceitar) → bateria completa → self-fact-check listado no report → commit `docs+feat(skills): operação connect no paper-manager; conectores e busca na trilha do pesquisador (F4 escopo A)`

---

### Task 5: ADR-0020 + CHANGELOG + bateria final

**Files:**
- Create: `docs/adr/adr-0020-connect-autoexport-bbt.md` (formato da casa: Contexto/Decisão/Consequências, prosa pt-BR, status aceito — molde: adr-0018/0019)
- Modify: `CHANGELOG.md` ("Não publicado")
- Regenerar índices; bateria final completa + `validate_manifests.py`

Conteúdo obrigatório do ADR-0020 (cada claim conferido no código):
- **Contexto:** trigger da F4 disparado no piloto real (2 dores); grounding verificado; `autoexport.add`/`user.groups` provados ao vivo; risco central: add cria coleção fantasma.
- **Decisão:** primeira (e única) chamada MUTANTE do prumo no Zotero do usuário é `autoexport.add`, SEMPRE precedida de validação de existência via `user.groups(true)` (typo nunca cria nada); GUID pinado do Better BibLaTeX `f895aa0d-f28e-47fe-b247-2ea77c6ed583`; caminho de coleção sempre com library explícita (`/<Library>/<Pai>/<Filha>`); bib povoado → recusa orientada (sem re-add cego — duplicaria autoexport); poll de cortesia com `exported=False` honesto; qmd→MCPB REFUTADO fica registrado (evidência: node-llama-cpp multi-binário, ~2 GB GGUF, SQLite Homebrew) e o fallback lexical é o caminho normal documentado da persona; conectores externos (PubMed oficial; cookjohn) são RECOMENDAÇÃO de docs, nunca dependência.
- **Consequências:** doctor ganha o aviso de placeholder; reconexão/`--replace` fica FORA (follow-up gated: exigiria autoexport.remove/list confirmados); smoke real do connect é manual do dono (testes nunca mutam o Zotero vivo); se o BBT mudar a assinatura do RPC, o erro traduzido aponta o doctor.
- **CHANGELOG:** Added — `prumo paper connect` (+ guardas, doctor warning, operação na skill, docs de conectores) com refs ADR-0020 e emenda da F4; Marco — Fase 4 do zero-friction (escopo A) implementada; piloto do connect pendente do dono.

- [ ] Steps: ADR → CHANGELOG → `gen_indexes.py` → bateria FINAL (`pytest`, `ruff check`, `ruff format --check`, `mypy`, `gen_indexes --check`, `validate_manifests.py`) → commit `docs+feat(paper): ADR-0020 connect via BBT autoexport + CHANGELOG do marco F4`

---

## Self-review (contra a emenda aprovada da F4)

- Item 1 da emenda (connect com guardas): T1+T2+T3+T5 ✓ (guarda anti-fantasma testada com assert de zero chamadas mutantes; multi-library; poll honesto)
- Item 2 (qmd reposicionado): T4 §3a + registro no ADR (T5) ✓
- Item 3 (docs de conectores): T4 §3b–d ✓ (PubMed 6 passos verificados; cookjohn com rótulo literal; Zettlr)
- Zero deps novas ✓; nenhuma chamada mutante em teste ✓; smoke real = dono (registrado no ADR) ✓

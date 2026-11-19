"""Notebooks numerados com cabeçalho e índice gerado por escopo (ADR-0047).

Notebook mora em ``notebooks/<nome de código do escopo>/`` com nome ``NN_<nome>.py``
(marimo) ou ``NN_<nome>.ipynb`` (Jupyter). ``NN`` vem da faixa do tipo: 00–09 explorar,
10–19 preparar, 20–29 ajustar, 30–39 figuras. O topo de cada notebook diz a pergunta, a
entrada e a saída; o ``README.md`` da pasta lista todos num bloco machine-owned
(``prumo:notebooks``, ADR-0009), reescrito por ``prumo add notebook`` e ``prumo update``.

Nada aqui executa o notebook: o cabeçalho sai do AST (``.py``) ou do JSON (``.ipynb``).
"""

from __future__ import annotations

import ast
import contextlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from par import ConfigError, PrumoError
from par.core import pj_layout
from par.core.paths import resolve_resource
from par.core.scaffold import PKG_MARKER, SCOPE_MARKER, pkg_name

#: Tipo → faixa de numeração. A ordem é a do fluxo de análise.
KINDS: dict[str, range] = {
    "eda": range(0, 10),
    "prep": range(10, 20),
    "model": range(20, 30),
    "figures": range(30, 40),
}

#: Nome do módulo cujo ``prumo add`` semeia o primeiro notebook do escopo.
MODULE = "notebooks"

#: Único tipo com modelo ``.ipynb``: Jupyter é para material herdado, não para notebook novo.
IPYNB_KINDS = frozenset({"eda"})

BLOCK_BEGIN = "<!-- prumo:notebooks:begin -->"
BLOCK_END = "<!-- prumo:notebooks:end -->"
_BLOCK_RE = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END), re.DOTALL)

NOTEBOOK_RE = re.compile(r"^(\d{2})_([a-z][a-z0-9_]*)\.(py|ipynb)$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
#: Valor com ``<...>`` ainda é o exemplo do modelo, não preenchido.
_PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
_FIELD_RE = re.compile(
    r"^[\s>*#-]*\**\s*(pergunta|entrada|sa[ií]da)\s*\**\s*:\s*\**\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_FIELD_KEYS = {"pergunta": "question", "entrada": "input", "saída": "output", "saida": "output"}
_TITLE_MARKER = "__title__"


@dataclass(frozen=True)
class NotebookHeader:
    """O que o topo do notebook declara; ``None`` = campo ausente ou ainda placeholder."""

    question: str | None = None
    input: str | None = None
    output: str | None = None

    @property
    def missing(self) -> tuple[str, ...]:
        """Rótulos dos campos que faltam, na ordem do cabeçalho."""
        pairs = (("Pergunta", self.question), ("Entrada", self.input), ("Saída", self.output))
        return tuple(label for label, value in pairs if value is None)

    @property
    def complete(self) -> bool:
        return not self.missing


@dataclass(frozen=True)
class NotebookEntry:
    """Um notebook numerado da pasta do escopo."""

    number: int
    filename: str
    header: NotebookHeader


def _check_kind(kind: str) -> range:
    if kind not in KINDS:
        raise PrumoError(f"Tipo de notebook '{kind}' desconhecido. Use um de: {', '.join(KINDS)}.")
    return KINDS[kind]


def next_number(nb_dir: Path, kind: str) -> int:
    """Primeiro número livre da faixa de ``kind`` em ``nb_dir`` (``.py`` e ``.ipynb``)."""
    band = _check_kind(kind)
    used = {
        int(m.group(1))
        for p in (nb_dir.iterdir() if nb_dir.is_dir() else ())
        if (m := NOTEBOOK_RE.match(p.name))
    }
    for n in band:
        if n not in used:
            return n
    raise PrumoError(
        f"A faixa {band.start:02d}–{band.stop - 1:02d} ({kind}) está cheia em {nb_dir}. Junte "
        "notebooks que respondem a mesma pergunta, ou promova o código comum para "
        "`src/<pacote>/<escopo>/` e importe de lá."
    )


def _clean(value: str) -> str | None:
    value = value.strip()
    return None if not value or _PLACEHOLDER_RE.search(value) else value


def _parse_fields(text: str) -> NotebookHeader:
    found: dict[str, str | None] = {}
    for m in _FIELD_RE.finditer(text):
        key = _FIELD_KEYS[m.group(1).lower()]
        found.setdefault(key, _clean(m.group(2)))
    return NotebookHeader(found.get("question"), found.get("input"), found.get("output"))


def _ipynb_header_text(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cells = data["cells"]
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError):
        return ""
    for cell in cells if isinstance(cells, list) else ():
        if isinstance(cell, dict) and cell.get("cell_type") == "markdown":
            source = cell.get("source", "")
            return "".join(source) if isinstance(source, list) else str(source)
    return ""


def read_header(path: Path) -> NotebookHeader:
    """Cabeçalho do notebook, sem executá-lo. Ilegível ou sem cabeçalho = tudo vazio."""
    if path.suffix == ".ipynb":
        return _parse_fields(_ipynb_header_text(path))
    try:
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return NotebookHeader()
    return _parse_fields(doc) if doc else NotebookHeader()


def list_notebooks(nb_dir: Path) -> list[NotebookEntry]:
    """Notebooks numerados de ``nb_dir`` (só o nível de cima), em ordem de número e nome."""
    if not nb_dir.is_dir():
        return []
    entries = [
        NotebookEntry(int(m.group(1)), p.name, read_header(p))
        for p in nb_dir.iterdir()
        if p.is_file() and (m := NOTEBOOK_RE.match(p.name))
    ]
    return sorted(entries, key=lambda e: (e.number, e.filename))


def _cell(value: str | None) -> str:
    return "—" if value is None else value.replace("|", "\\|").replace("\n", " ")


def render_index(entries: list[NotebookEntry]) -> str:
    """Bloco ``prumo:notebooks`` (com os delimitadores) para ``entries``."""
    lines = [
        BLOCK_BEGIN,
        "<!-- Gerado pelo `prumo add notebook` e pelo `prumo update` a partir do topo de cada "
        "notebook. Edite o notebook, não este bloco. -->",
        "| Nº | Notebook | Pergunta | Entrada | Saída |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {e.number:02d} | [{e.filename}]({e.filename}) | {_cell(e.header.question)} | "
        f"{_cell(e.header.input)} | {_cell(e.header.output)} |"
        for e in entries
    ]
    lines.append(BLOCK_END)
    return "\n".join(lines)


def _new_readme(scope: str, block: str) -> str:
    return (
        f"# Notebooks — {scope}\n\n"
        "Faixas: 00–09 explorar, 10–19 preparar, 20–29 ajustar modelo, 30–39 figuras e "
        "tabelas. Crie notebook com `prumo add notebook <nome> --kind <tipo>`. Notas suas "
        "ficam fora do bloco abaixo, que o `prumo` regenera.\n\n"
        f"{block}\n"
    )


def sync_index(
    nb_dir: Path, scope: str, *, write: bool = True
) -> Literal["created", "inserted", "updated"] | None:
    """Põe o índice de ``nb_dir/README.md`` em dia; diz o que mudou (ou ``None``).

    Só reescreve dentro do bloco. README sem bloco recebe o bloco no fim; README ausente
    é criado. ``write=False`` só responde (``doctor`` e ``update --dry-run``).

    Raises:
        ConfigError: delimitador sem par no README.
    """
    readme = nb_dir / "README.md"
    block = render_index(list_notebooks(nb_dir))
    if not readme.is_file():
        if write:
            nb_dir.mkdir(parents=True, exist_ok=True)
            readme.write_text(_new_readme(scope, block), encoding="utf-8")
        return "created"
    text = readme.read_text(encoding="utf-8")
    change: Literal["inserted", "updated"]
    if _BLOCK_RE.search(text):
        new = _BLOCK_RE.sub(lambda _: block, text, count=1)
        change = "updated"
    elif BLOCK_BEGIN in text or BLOCK_END in text:
        raise ConfigError(
            f"{readme}: bloco `prumo:notebooks` com delimitador sem par. Apague o marcador "
            "que sobrou e rode `prumo update`, que reinsere o bloco."
        )
    else:
        new = text.rstrip("\n") + "\n\n" + block + "\n"
        change = "inserted"
    if new == text:
        return None
    if write:
        readme.write_text(new, encoding="utf-8")
    return change


def suggest_name(raw: str) -> str:
    """``raw`` como nome de notebook válido (ASCII, minúsculo, ``_``), ou ``exploracao``."""
    ascii_ = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-z0-9]+", "_", ascii_.lower()).strip("_")
    name = re.sub(r"^[\d_]+", "", name)
    return name or "exploracao"


def _title(name: str) -> str:
    return name.replace("_", " ").capitalize()


def default_kinds_dir() -> Path:
    """``templates/notebook_kinds/`` — modelos por tipo, fora do payload dos módulos."""
    return resolve_resource("templates") / "notebook_kinds"


def create_notebook(
    pj_root: Path,
    scope: str,
    name: str,
    *,
    kind: str = "eda",
    ipynb: bool = False,
    question: str | None = None,
    templates: Path | None = None,
) -> Path:
    """Cria ``notebooks/<escopo>/NN_<name>`` a partir do modelo de ``kind`` e reindexa.

    Nunca sobrescreve. ``question`` preenche o campo Pergunta do cabeçalho.

    Raises:
        PrumoError: escopo inexistente, nome ou tipo inválido, ``.ipynb`` para tipo sem
            modelo Jupyter, faixa cheia ou notebook com o mesmo nome.
    """
    if not (pj_root / pj_layout.STUDIES_RELPATH / scope).is_dir():
        raise PrumoError(
            f"Escopo '{scope}' não existe em {pj_root}. Crie com `prumo add study {scope}` "
            "ou escolha outro com `--scope`."
        )
    if not _NAME_RE.match(name):
        raise PrumoError(
            f"Nome de notebook inválido: '{name}'. Use minúsculas sem acento, números e `_`, "
            f"começando por letra, sem o número (ele é posto sozinho). Ex.: "
            f"`prumo add notebook {suggest_name(name)}`."
        )
    _check_kind(kind)
    if ipynb and kind not in IPYNB_KINDS:
        raise PrumoError(
            f"Não há modelo Jupyter para o tipo '{kind}': notebook novo é marimo. Tire o "
            "`--ipynb`, ou use `--kind eda --ipynb` para um `.ipynb` de exploração."
        )
    nb_dir = pj_layout.notebooks_dir(pj_root, scope)
    for existing in list_notebooks(nb_dir):
        m = NOTEBOOK_RE.match(existing.filename)
        if m and m.group(2) == name:
            raise PrumoError(
                f"Já existe {existing.filename} em {nb_dir}. Abra esse, ou escolha outro "
                f"nome: `prumo add notebook {name}_2`."
            )
    suffix = ".ipynb" if ipynb else ".py"
    template = (templates or default_kinds_dir()) / f"{kind}{suffix}"
    text = (
        template.read_text(encoding="utf-8")
        .replace(_TITLE_MARKER, _title(name))
        .replace(SCOPE_MARKER, pj_layout.code_scope_name(scope))
    )
    # Diretório fora do padrão `pj_<nome>`: o marcador fica visível no exemplo.
    with contextlib.suppress(PrumoError):
        text = text.replace(PKG_MARKER, pkg_name(pj_root.name))
    if question:
        text = _fill_question(text, question, ipynb=ipynb)
    target = nb_dir / f"{next_number(nb_dir, kind):02d}_{name}{suffix}"
    nb_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    sync_index(nb_dir, pj_layout.code_scope_name(scope))
    return target


def _fill_question(text: str, question: str, *, ipynb: bool) -> str:
    value = json.dumps(question)[1:-1] if ipynb else question.replace('"""', "'''")
    return text.replace("Pergunta: <preencha>", f"Pergunta: {value}", 1)


def seed_scope(pj_root: Path, scope: str, *, templates: Path | None = None) -> Path | None:
    """Primeiro notebook do escopo (``00_exploracao.py``), se a pasta ainda não tem nenhum.

    Com notebook já presente só reindexa e devolve ``None``: o módulo pode ser
    reaplicado sem duplicar nada.
    """
    nb_dir = pj_layout.notebooks_dir(pj_root, scope)
    if list_notebooks(nb_dir):
        sync_index(nb_dir, pj_layout.code_scope_name(scope))
        return None
    return create_notebook(pj_root, scope, "exploracao", kind="eda", templates=templates)


# --- doctor e update -----------------------------------------------------------

#: Pastas que a varredura de notebook nunca entra: ambiente, saída de máquina, dado.
_SKIP_DIRS = frozenset(
    {".venv", "venv", ".git", "build", "experiments", "content", "node_modules", "__marimo__"}
)
_MARIMO_RE = re.compile(r"marimo\.App\(")


def _is_notebook_file(path: Path) -> bool:
    if path.suffix == ".ipynb":
        return True
    if path.suffix != ".py":
        return False
    try:
        return bool(_MARIMO_RE.search(path.read_text(encoding="utf-8", errors="ignore")))
    except OSError:
        return False


def _walk(root: Path) -> list[Path]:
    """Arquivos de ``root`` para baixo, sem entrar em pasta oculta nem em :data:`_SKIP_DIRS`."""
    out: list[Path] = []
    for child in sorted(root.iterdir()) if root.is_dir() else ():
        if child.name.startswith(".") or child.name in _SKIP_DIRS:
            continue
        if child.is_dir():
            out.extend(_walk(child))
        elif child.is_file():
            out.append(child)
    return out


def scope_dirs(pj_root: Path) -> list[Path]:
    """Pastas de escopo em ``notebooks/`` (filhos diretos, sem ocultas nem ``__marimo__``)."""
    root = pj_root / pj_layout.NOTEBOOKS_RELPATH
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name not in _SKIP_DIRS
    )


def _target_scope(pj_root: Path) -> str:
    scopes = pj_layout.iter_scopes(pj_root)
    if len(scopes) == 1:
        try:
            return pj_layout.code_scope_name(scopes[0].name)
        except PrumoError:
            pass
    return "<escopo>"


def notebook_issues(pj_root: Path) -> tuple[list[str], list[str]]:
    """``(issues, avisos)`` de notebook do projeto. Nada é movido nem escrito."""
    issues: list[str] = []
    warnings: list[str] = []
    scopes = scope_dirs(pj_root)
    in_place = {p for d in scopes for p in d.iterdir() if p.is_file()}

    fora = [p for p in _walk(pj_root) if p not in in_place and _is_notebook_file(p)]
    if fora:
        dest = f"notebooks/{_target_scope(pj_root)}/"
        cmds = "; ".join(f"`git mv {p.relative_to(pj_root).as_posix()} {dest}`" for p in fora)
        issues.append(
            f"[notebook_fora_do_lugar] notebook fora de `notebooks/<escopo>/`: {cmds}. "
            "Depois, numere-os e rode `prumo update` para o índice."
        )

    for d in scopes:
        rel = d.relative_to(pj_root).as_posix()
        try:
            code = pj_layout.code_scope_name(d.name)
        except PrumoError:
            code = d.name
        if code != d.name:
            issues.append(
                f"[notebook_escopo_prefixado] `{rel}/` usa o slug com prefixo numérico; o nome "
                f"de código do escopo é `{code}`. Rode: `git mv {rel} notebooks/{code}`."
            )
        sem_numero = sorted(
            p
            for p in d.iterdir()
            if p.is_file() and _is_notebook_file(p) and not NOTEBOOK_RE.match(p.name)
        )
        try:
            n = next_number(d, "eda")
        except PrumoError:
            n = 0
        for p in sem_numero:
            novo = f"{n:02d}_{suggest_name(p.stem)}{p.suffix}"
            issues.append(
                f"[notebook_sem_numero] `{rel}/{p.name}` não tem o número da etapa. Rode: "
                f"`git mv {rel}/{p.name} {rel}/{novo}` (troque o número pela faixa certa: "
                "00 explorar, 10 preparar, 20 modelo, 30 figuras)."
            )
            n += 1
        for e in list_notebooks(d):
            if not e.header.complete:
                warnings.append(
                    f"[notebook_sem_cabecalho] `{rel}/{e.filename}`: falta "
                    f"{', '.join(e.header.missing)} no cabeçalho (a docstring do topo, uma "
                    "linha `Campo: valor` para Pergunta, Entrada e Saída). Preencha e rode "
                    "`prumo update` para o índice."
                )
        if list_notebooks(d):
            try:
                atrasado = sync_index(d, code, write=False) is not None
            except ConfigError as exc:
                issues.append(f"[notebook_indice_desatualizado] {exc}")
                continue
            if atrasado:
                issues.append(
                    f"[notebook_indice_desatualizado] `{rel}/README.md` não lista os notebooks "
                    "da pasta como estão. Rode: `prumo update`."
                )
    return issues, warnings


def sync_all_indexes(pj_root: Path, *, write: bool = True) -> list[str]:
    """Põe em dia o índice de toda pasta de escopo com notebook; devolve os README mudados."""
    changed: list[str] = []
    for d in scope_dirs(pj_root):
        if not list_notebooks(d):
            continue
        try:
            code = pj_layout.code_scope_name(d.name)
        except PrumoError:
            code = d.name
        if sync_index(d, code, write=write) is not None:
            changed.append((d / "README.md").relative_to(pj_root).as_posix())
    return changed

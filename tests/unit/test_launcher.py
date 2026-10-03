"""Lançador `shims/prumo` (ADR-0038): roda por subprocess em `/bin/sh` e em `dash`.

O uv é falso (`PRUMO_UV`), o cache é temporário (`PRUMO_CACHE_DIR`) e o ambiente do
lançador é montado do zero, para que `SANDBOX_RUNTIME`, `WSL_DISTRO_NAME` e
`WSL_INTEROP` da máquina nunca vazem para o teste.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SHELLS = ["/bin/sh"] + ([d] if (d := shutil.which("dash")) else [])

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="lançador POSIX")

_FAKE_CLI = """\
import json, os, sys

def app(prog_name: str) -> None:
    import yaml
    print(json.dumps({"prog": prog_name, "argv": sys.argv[1:], "env": dict(os.environ),
                      "yaml": yaml.__file__, "par": __file__}))
"""

_FAKE_UV = """\
#!/bin/sh
printf '%s|%s|%s\\n' "$*" "${UV_NATIVE_TLS:-}" "${UV_SYSTEM_CERTS:-}" >>"$FAKE_UV_LOG"
if [ -n "${FAKE_UV_TLS_ONCE:-}" ] && [ "${UV_NATIVE_TLS:-}" != 1 ]; then
  echo "error: invalid peer certificate: UnknownIssuer" >&2; exit 2
fi
if [ -n "${FAKE_UV_STDERR:-}" ]; then printf '%s\\n' "$FAKE_UV_STDERR" >&2; exit 2; fi
[ -z "${FAKE_UV_NO_PYTHON:-}" ] || exit 0
mkdir -p "$UV_PROJECT_ENVIRONMENT/bin"
rm -f "$UV_PROJECT_ENVIRONMENT/bin/python"
printf '#!/bin/sh\\nexec "%s" "$@"\\n' "$FAKE_PY" >"$UV_PROJECT_ENVIRONMENT/bin/python"
chmod 755 "$UV_PROJECT_ENVIRONMENT/bin/python"
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Raiz de plugin mínima: o lançador real, um `uv.lock` e um `par.cli` falso."""
    r = tmp_path / "root"
    (r / "shims").mkdir(parents=True)
    shim = r / "shims" / "prumo"
    shutil.copyfile(REPO / "shims" / "prumo", shim)
    shim.chmod(0o755)
    (r / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (r / "src" / "par").mkdir(parents=True)
    (r / "src" / "par" / "__init__.py").write_text("", encoding="utf-8")
    (r / "src" / "par" / "cli.py").write_text(_FAKE_CLI, encoding="utf-8")
    return r


@pytest.fixture
def fake_uv(tmp_path: Path) -> Path:
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True)
    uv.write_text(_FAKE_UV, encoding="utf-8")
    uv.chmod(0o755)
    return uv


def _env(tmp_path: Path, fake_uv: Path, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "PRUMO_CACHE_DIR": str(tmp_path / "cache"),
        "PRUMO_UV": str(fake_uv),
        "FAKE_UV_LOG": str(tmp_path / "uv.log"),
        "FAKE_PY": sys.executable,
    }
    env.update(extra)
    return env


def _run(
    shell: str, root: Path, env: dict[str, str], *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shell, str(root / "shims" / "prumo"), *args],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _out(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert proc.returncode == 0, proc.stderr
    data: dict[str, Any] = json.loads(proc.stdout)
    return data


def _log_lines(tmp_path: Path) -> list[str]:
    log = tmp_path / "uv.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.mark.parametrize("shell", SHELLS)
def test_frio_monta_venv_e_roda_o_cli(
    shell: str, root: Path, fake_uv: Path, tmp_path: Path
) -> None:
    data = _out(_run(shell, root, _env(tmp_path, fake_uv), "--version"))
    assert data["prog"] == "prumo"
    assert data["argv"] == ["--version"]
    assert list((tmp_path / "cache").glob("venv-3.12-*/.prumo-ok"))


@pytest.mark.parametrize("shell", SHELLS)
def test_quente_nao_chama_o_uv(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    _out(_run(shell, root, _env(tmp_path, fake_uv), "--version"))
    proc = _run(shell, root, _env(tmp_path, fake_uv, PRUMO_UV="/inexistente"), "--version")
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_python_quebrado_reconstroi(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    _out(_run(shell, root, _env(tmp_path, fake_uv), "--version"))
    venv = next((tmp_path / "cache").glob("venv-3.12-*"))
    (venv / "bin" / "python").unlink()
    os.symlink(tmp_path / "sumiu" / "python", venv / "bin" / "python")
    proc = _run(shell, root, _env(tmp_path, fake_uv), "--version")
    assert proc.returncode == 0, proc.stderr
    assert len(_log_lines(tmp_path)) == 2


_CLASSIFICACAO = [
    ("error: Failed to parse `uv.lock`", {}, 78, "uv self update"),
    (
        "hint: Python 3.12 is not installed, but Python downloads are set to 'never'",
        {},
        78,
        "uv python install 3.12",
    ),
    ("error: Read-only file system (os error 30)", {"SANDBOX_RUNTIME": "1"}, 77, "fora do sandbox"),
    ("error: Read-only file system (os error 30)", {}, 73, "chown"),
    ("error: Operation not permitted (os error 1)", {}, 77, "fora do sandbox"),
    ("error: No space left on device (os error 28)", {}, 73, "chown"),
    (
        "error: Request failed after 3 retries\n  Caused by: dns error",
        {},
        69,
        "release-assets.githubusercontent.com",
    ),
    (
        "error: Request failed after 3 retries\n  Caused by: dns error",
        {"SANDBOX_RUNTIME": "1"},
        77,
        "fora do sandbox",
    ),
]


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(("stderr", "extra", "rc", "remedio"), _CLASSIFICACAO)
def test_classifica_falha_do_uv(
    shell: str,
    stderr: str,
    extra: dict[str, str],
    rc: int,
    remedio: str,
    root: Path,
    fake_uv: Path,
    tmp_path: Path,
) -> None:
    env = _env(tmp_path, fake_uv, FAKE_UV_STDERR=stderr, **extra)
    proc = _run(shell, root, env, "--version")
    assert proc.returncode == rc, proc.stderr
    assert proc.stderr.startswith("PAR: ")
    assert remedio in proc.stderr
    assert "Detalhe: " in proc.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_uv_sai_zero_sem_python(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    proc = _run(shell, root, _env(tmp_path, fake_uv, FAKE_UV_NO_PYTHON="1"), "--version")
    assert proc.returncode == 70
    assert proc.stderr.startswith("PAR: ")


@pytest.mark.parametrize("shell", SHELLS)
def test_sem_uv(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    proc = _run(shell, root, _env(tmp_path, fake_uv, PRUMO_UV="/inexistente"), "--version")
    assert proc.returncode == 127
    assert proc.stderr.startswith("PAR: falta o uv")


@pytest.mark.parametrize("shell", SHELLS)
@pytest.mark.parametrize(
    "extra",
    [
        {"OS": "Windows_NT"},
        {"WSL_DISTRO_NAME": "Ubuntu"},
        {"WSL_INTEROP": "/run/WSL/1_interop"},
    ],
)
def test_windows_e_wsl(
    shell: str, extra: dict[str, str], root: Path, fake_uv: Path, tmp_path: Path
) -> None:
    proc = _run(shell, root, _env(tmp_path, fake_uv, **extra), "--version")
    assert proc.returncode == 71
    assert proc.stderr.startswith("PAR: ")
    assert "nem no WSL" in proc.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_raiz_sem_src(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    (root / "src" / "par" / "cli.py").unlink()
    proc = _run(shell, root, _env(tmp_path, fake_uv), "--version")
    assert proc.returncode == 1
    assert proc.stderr.startswith("PAR: ")
    assert "link simbólico" in proc.stderr


@pytest.mark.parametrize("shell", SHELLS)
def test_tls_tenta_de_novo_com_certificados_do_sistema(
    shell: str, root: Path, fake_uv: Path, tmp_path: Path
) -> None:
    proc = _run(shell, root, _env(tmp_path, fake_uv, FAKE_UV_TLS_ONCE="1"), "--version")
    assert proc.returncode == 0, proc.stderr
    lines = _log_lines(tmp_path)
    assert len(lines) == 2
    assert lines[0].endswith("||")
    assert lines[1].endswith("|1|1")


@pytest.mark.parametrize("shell", SHELLS)
def test_cache_fixo_ignora_xdg(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    env = _env(tmp_path, fake_uv, XDG_CACHE_HOME=str(tmp_path / "xdg"))
    del env["PRUMO_CACHE_DIR"]
    _out(_run(shell, root, env, "--version"))
    assert list((tmp_path / "home" / ".cache" / "prumo").glob("venv-3.12-*/.prumo-ok"))
    xdg = tmp_path / "xdg"
    assert not xdg.exists() or not any(xdg.iterdir())


@pytest.mark.parametrize("shell", SHELLS)
def test_cwd_nao_sequestra(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    cwd = tmp_path / "projeto"
    (cwd / "par").mkdir(parents=True)
    (cwd / "yaml.py").write_text('raise SystemExit("HIJACKED")\n', encoding="utf-8")
    (cwd / "typer.py").write_text('raise SystemExit("HIJACKED")\n', encoding="utf-8")
    (cwd / "par" / "__init__.py").write_text("", encoding="utf-8")
    (cwd / "par" / "cli.py").write_text(
        'print("HIJACKED")\n\ndef app(prog_name: str) -> None:\n    print("HIJACKED")\n',
        encoding="utf-8",
    )
    proc = _run(shell, root, _env(tmp_path, fake_uv), "--version", cwd=cwd)
    assert "HIJACKED" not in proc.stdout + proc.stderr
    data = _out(proc)
    assert not Path(data["yaml"]).resolve().is_relative_to(cwd.resolve())
    assert Path(data["par"]).resolve().is_relative_to((root / "src").resolve())


@pytest.mark.parametrize("shell", SHELLS)
def test_ambiente_do_filho_so_ganha_sufixo_no_path(
    shell: str, root: Path, fake_uv: Path, tmp_path: Path
) -> None:
    env_in = _env(tmp_path, fake_uv)
    data = _out(_run(shell, root, env_in, "--version"))
    ignored = {"_", "SHLVL", "PWD", "OLDPWD", "__CF_USER_TEXT_ENCODING"} | (
        {"LC_CTYPE"} if "LC_CTYPE" not in env_in else set()
    )
    got = {k: v for k, v in data["env"].items() if k not in ignored}
    home = tmp_path / "home"
    want = dict(env_in)
    want["PATH"] = env_in["PATH"] + f":{home}/.local/bin:/opt/homebrew/bin:/usr/local/bin"
    assert got == want


@pytest.mark.parametrize("shell", SHELLS)
def test_poda_venvs_velhos(shell: str, root: Path, fake_uv: Path, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    velho = cache / "venv-3.12-velho"
    recente = cache / "venv-3.12-recente"
    now = time.time()
    for path, days in ((velho, 40), (recente, 10)):
        path.mkdir(parents=True)
        t = now - days * 86400
        os.utime(path, (t, t))
    _out(_run(shell, root, _env(tmp_path, fake_uv), "--version"))
    assert not velho.exists()
    assert recente.exists()
    assert list(cache.glob("venv-3.12-*/.prumo-ok"))


# --- hook SessionStart (A5) ---------------------------------------------------------

HOOK = REPO / "hooks" / "session-start.sh"


def _plugin_root(path: Path) -> Path:
    """Raiz de plugin mínima para o hook: só `shims/prumo` executável."""
    (path / "shims").mkdir(parents=True)
    shim = path / "shims" / "prumo"
    shutil.copyfile(REPO / "shims" / "prumo", shim)
    shim.chmod(0o755)
    return path


def _hook(shell: str, plugin_root: Path, env_file: Path | None) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "CLAUDE_PLUGIN_ROOT": str(plugin_root)}
    if env_file is not None:
        env["CLAUDE_ENV_FILE"] = str(env_file)
    return subprocess.run(
        [shell, str(HOOK)], env=env, capture_output=True, text=True, timeout=30, check=False
    )


@pytest.mark.parametrize("shell", SHELLS)
def test_hook_idempotente(shell: str, tmp_path: Path) -> None:
    plugin_root = _plugin_root(tmp_path / "root")
    env_file = tmp_path / "env"
    env_file.write_text("", encoding="utf-8")
    for _ in range(2):
        proc = _hook(shell, plugin_root, env_file)
        assert proc.returncode == 0
        assert proc.stdout == "" and proc.stderr == ""
    assert len(env_file.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize("shell", SHELLS)
def test_hook_raiz_com_aspas_dolar_e_crase(shell: str, tmp_path: Path) -> None:
    plugin_root = _plugin_root(tmp_path / ("r'o$o" + chr(96) + "t"))
    env_file = tmp_path / "env"
    env_file.write_text("", encoding="utf-8")
    assert _hook(shell, plugin_root, env_file).returncode == 0
    want = str(plugin_root / "shims" / "prumo")
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    for sh in ("bash", "/bin/sh"):
        if sh == "bash" and shutil.which("bash") is None:
            continue
        got = subprocess.run(
            [sh, "-c", '. "$1"; command -v prumo', "_", str(env_file)],
            env=base,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert got.returncode == 0, got.stderr
        assert got.stdout.strip() == want


@pytest.mark.parametrize("shell", SHELLS)
def test_hook_sem_env_file_sai_calado(shell: str, tmp_path: Path) -> None:
    proc = _hook(shell, _plugin_root(tmp_path / "root"), None)
    assert proc.returncode == 0
    assert proc.stdout == "" and proc.stderr == ""


@pytest.mark.parametrize("shell", SHELLS)
def test_hook_env_file_so_leitura_sai_calado(shell: str, tmp_path: Path) -> None:
    env_file = tmp_path / "env"
    env_file.write_text("", encoding="utf-8")
    env_file.chmod(0o444)
    try:
        proc = _hook(shell, _plugin_root(tmp_path / "root"), env_file)
    finally:
        env_file.chmod(0o644)
    assert proc.returncode == 0
    assert proc.stderr == ""

"""Layout do plugin: o que o `.mcp.json` distribui aos consumidores."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_mcp_json_eh_so_o_prumo_pelo_lancador() -> None:
    """Só o servidor `prumo`, via `/bin/sh` no lançador do plugin; sem qmd (A5, A9)."""
    data = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    assert data == {
        "mcpServers": {
            "prumo": {
                "command": "/bin/sh",
                "args": ["${CLAUDE_PLUGIN_ROOT}/shims/prumo", "mcp", "serve"],
            }
        }
    }


def test_shims_so_tem_prumo() -> None:
    """`shims/` só leva o lançador: tudo ali entra no PATH do Bash da sessão (A5)."""
    names = sorted(p.name for p in (REPO / "shims").iterdir() if p.name != ".DS_Store")
    assert names == ["prumo"]


def test_modo_100755_no_git() -> None:
    """Lançador e hook são executáveis no git (o cache do plugin preserva o modo)."""
    if not (REPO / ".git").exists() or shutil.which("git") is None:
        pytest.skip("fora de um checkout git")
    out = subprocess.run(
        ["git", "ls-files", "-s", "shims/prumo", "hooks/session-start.sh"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert len(out) == 2
    assert all(line.startswith("100755") for line in out)


def test_sem_bin_na_raiz() -> None:
    """`bin/` na raiz entraria no PATH do Bash por conta do Claude Code (A1)."""
    assert not (REPO / "bin").exists()


def test_hooks_json_so_sessionstart_em_forma_exec() -> None:
    """Só o `SessionStart`, sem matcher, em forma exec via `/bin/sh` (A5)."""
    hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == {"SessionStart"}
    entries = hooks["SessionStart"]
    assert len(entries) == 1
    assert "matcher" not in entries[0]
    (hook,) = entries[0]["hooks"]
    assert hook["command"] == "/bin/sh"
    assert hook["args"] == ["${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"]


def test_settings_do_template_liga_o_auto_update() -> None:
    """O template liga a atualização automática do PAR no pj e o oferece ao coautor (D4, A13)."""
    path = REPO / "templates" / "pj_base" / ".claude" / "settings.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "extraKnownMarketplaces": {
            "prumo-assistant-for-researcher": {
                "source": {"source": "github", "repo": "raphaelfh/prumo-assistant-for-researcher"},
                "autoUpdate": True,
            }
        },
        "enabledPlugins": {"par@prumo-assistant-for-researcher": True},
    }

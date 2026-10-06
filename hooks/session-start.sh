#!/bin/sh
# SessionStart do plugin PAR (ADR-0038): põe o lançador desta raiz (shims/prumo)
# à frente do PATH do Bash da sessão, para `prumo` sem caminho casar com as
# permissões Bash(prumo ...) das skills. Idempotente, silencioso (stdout de
# SessionStart vira contexto do modelo) e nunca falha a sessão.
if [ -z "${CLAUDE_ENV_FILE:-}" ] || [ ! -f "${CLAUDE_PLUGIN_ROOT:-}/shims/prumo" ]; then exit 0; fi
_q=$(printf '%s' "$CLAUDE_PLUGIN_ROOT/shims" | sed "s/'/'\\\\''/g")
_line="export PATH='$_q':\"\$PATH\""
{ grep -qxF -- "$_line" "$CLAUDE_ENV_FILE" || printf '%s\n' "$_line" >>"$CLAUDE_ENV_FILE"; } 2>/dev/null
exit 0

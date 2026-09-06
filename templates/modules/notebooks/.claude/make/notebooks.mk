# Alvos do módulo notebooks — incluídos por `-include .claude/make/*.mk`
nb-edit:  ## Abre um notebook marimo no editor (uso: make nb-edit NB=notebooks/<escopo>/00_exploracao.py)
	@test -n "$(NB)" || (echo 'Uso: make nb-edit NB=notebooks/<escopo>/<arquivo>.py' && exit 1)
	@uv run marimo edit --no-token "$(NB)"

nb-run:  ## Roda o notebook como app somente-leitura (uso: make nb-run NB=notebooks/<escopo>/x.py)
	@test -n "$(NB)" || (echo 'Uso: make nb-run NB=notebooks/<escopo>/<arquivo>.py' && exit 1)
	@uv run marimo run "$(NB)"

nb-convert:  ## Converte um notebook Jupyter em marimo (uso: make nb-convert NB=notebooks/<escopo>/x.ipynb)
	@test -n "$(NB)" || (echo 'Uso: make nb-convert NB=notebooks/<escopo>/<arquivo>.ipynb' && exit 1)
	@uv run marimo convert "$(NB)" -o "$(NB:.ipynb=.py)"

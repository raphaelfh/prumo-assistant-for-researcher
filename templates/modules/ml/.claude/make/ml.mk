# Alvos de dev do módulo ml — incluídos por `-include .claude/make/*.mk`
lint:  ## Ruff check no projeto
	uv run ruff check .

format:  ## Ruff format no projeto
	uv run ruff format .

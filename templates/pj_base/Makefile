.PHONY: wiki-index wiki-search sync-pdfs sync-paper sync-pdf-paper sync-annotations extract-paper-all cite cite-styles export preview help

# === Wiki / busca (qmd) ===
wiki-index:  ## Indexa docs/ + references/ via qmd
	@qmd collection add . --name $(notdir $(CURDIR)) 2>/dev/null || true
	@qmd embed

wiki-search:  ## Busca híbrida no wiki (uso: make wiki-search Q="termo")
	@test -n "$(Q)" || (echo "Uso: make wiki-search Q=\"...\"" && exit 1)
	@qmd query "$(Q)"

# === Bibliografia (Zotero + Better BibTeX) ===
sync-pdfs:  ## Cria symlinks references/pdfs/<citekey>.pdf -> Zotero
	@prumo paper sync-pdfs

sync-paper:  ## Sync .bib -> notas + grafo passivo de citação
	@prumo paper sync
	@prumo paper graph

sync-pdf-paper: sync-pdfs sync-paper  ## Atalho: sync-pdfs + sync-paper

sync-annotations:  ## Sync annotations + child notes do Zotero
	@prumo paper sync-annotations

extract-paper-all:  ## Roda /paper-extract-all via Claude Code headless ([LIMIT=N] [STALE=1])
	@command -v claude >/dev/null || (echo "Claude Code CLI não encontrado no PATH." && exit 1)
	@claude -p "Invoque a skill paper-extract em modo batch para todos os papers elegíveis$(if $(LIMIT), (--limit $(LIMIT)),)$(if $(STALE), (--stale-only),)."

cite:  ## Fuzzy lookup de citekey (uso: make cite Q="autor titulo")
	@test -n "$(Q)" || (echo 'Uso: make cite Q="termo"' && exit 1)
	@prumo paper find "$(Q)"

# === Export bibliográfico (Pandoc + CSL) ===
cite-styles:  ## Lista estilos CSL disponíveis
	@prumo write list-styles

export:  ## Exporta uma página (uso: make export PAGE=docs/foo.md [STYLE=apa] [TO=docx])
	@test -n "$(PAGE)" || (echo 'Uso: make export PAGE=docs/<arquivo>.md [STYLE=apa] [TO=docx|typst|pdf|html]' && exit 1)
	@prumo write export "$(PAGE)" $(if $(STYLE),--style $(STYLE),) $(if $(TO),--to $(TO),)

preview:  ## Exporta para HTML e abre no browser (uso: make preview PAGE=docs/foo.md)
	@test -n "$(PAGE)" || (echo 'Uso: make preview PAGE=docs/<arquivo>.md' && exit 1)
	@out=$$(prumo write export "$(PAGE)" --to html $(if $(STYLE),--style $(STYLE),) --json | python3 -c 'import json,sys; print(json.loads(sys.stdin.read().splitlines()[-1])["output"])') && \
	    echo "Abrindo $$out" && open "$$out"

help:  ## Lista comandos disponíveis (núcleo + módulos)
	@grep -hE '^[a-zA-Z_-]+:.*##' Makefile .claude/make/*.mk 2>/dev/null | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

-include .claude/make/*.mk

.DEFAULT_GOAL := help

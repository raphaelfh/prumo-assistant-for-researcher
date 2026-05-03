.PHONY: wiki-index wiki-search sync-pdfs sync-paper sync-pdf-paper sync-annotations extract-paper-all cite cite-styles export preview export-doc watch extract-comments lint format help

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

sync-paper:  ## Sync .bib → notas + grafo passivo de citação
	@prumo paper sync
	@prumo paper graph

sync-pdf-paper: sync-pdfs sync-paper  ## Atalho: sync-pdfs + sync-paper

sync-annotations:  ## Sync annotations do Zotero -> references/notes/<citekey>/_annotations.md
	@prumo paper sync-annotations

extract-paper-all:  ## Roda /paper-extract-all via Claude Code headless ([LIMIT=N] [STALE=1])
	@command -v claude >/dev/null || (echo "Claude Code CLI não encontrado no PATH." && exit 1)
	@claude -p "Invoque a skill paper-extract em modo batch para todos os papers elegíveis$(if $(LIMIT), (--limit $(LIMIT)),)$(if $(STALE), (--stale-only),)."

cite:  ## Fuzzy lookup de citekey no acervo (uso: make cite Q="autor titulo")
	@test -n "$(Q)" || (echo 'Uso: make cite Q="termo"' && exit 1)
	@prumo paper find "$(Q)"

# === Export bibliografico (Pandoc + CSL) ===
cite-styles:  ## Lista estilos CSL disponiveis em ~/Zotero/styles/
	@prumo write list-styles

export:  ## Exporta uma pagina (uso: make export PAGE=docs/findings/foo.md [STYLE=apa] [TO=docx])
	@test -n "$(PAGE)" || (echo 'Uso: make export PAGE=docs/<arquivo>.md [STYLE=apa] [TO=docx|typst|pdf|html]' && exit 1)
	@prumo write export "$(PAGE)" \
	    $(if $(STYLE),--style $(STYLE),) \
	    $(if $(TO),--to $(TO),)

preview:  ## Exporta para HTML e abre no browser (uso: make preview PAGE=docs/findings/foo.md [STYLE=apa])
	@test -n "$(PAGE)" || (echo 'Uso: make preview PAGE=docs/<arquivo>.md' && exit 1)
	@out=$$(prumo write export "$(PAGE)" --to html $(if $(STYLE),--style $(STYLE),) --json | python3 -c 'import json,sys; print(json.loads(sys.stdin.read().splitlines()[-1])["output"])') && \
	    echo "Abrindo $$out" && open "$$out"

export-doc:  ## Compoe varias paginas via index file (uso: make export-doc INDEX=docs/qualification/cap.idx.md)
	@test -n "$(INDEX)" || (echo 'Uso: make export-doc INDEX=docs/<arquivo>.idx.md [STYLE=apa] [TO=docx]' && exit 1)
	@prumo write compose --index "$(INDEX)" \
	    $(if $(STYLE),--style $(STYLE),) \
	    $(if $(TO),--to $(TO),)

watch:  ## Polimento Typst com PDF live (uso: make watch PAGE=docs/findings/foo.md)
	@test -n "$(PAGE)" || (echo 'Uso: make watch PAGE=docs/<arquivo>.md' && exit 1)
	@out=$$(prumo write export "$(PAGE)" --to typst $(if $(STYLE),--style $(STYLE),) --json | python3 -c 'import json,sys; print(json.loads(sys.stdin.read().splitlines()[-1])["output"])') && \
	    pdf=$${out%.typ}.pdf && \
	    echo "Watching $$out -> $$pdf (Ctrl+C para parar)" && \
	    typst watch "$$out" "$$pdf"

extract-comments:  ## Extrai comentarios + track changes de um .docx revisado para checklist md (uso: make extract-comments DOCX=path/revisao.docx)
	@test -n "$(DOCX)" || (echo 'Uso: make extract-comments DOCX=path/revisao.docx' && exit 1)
	@prumo write extract-comments "$(DOCX)"

# === Dev tools ===
lint:  ## Ruff check no projeto
	uv run ruff check .

format:  ## Ruff format no projeto
	uv run ruff format .

help:  ## Lista comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*##' Makefile | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help

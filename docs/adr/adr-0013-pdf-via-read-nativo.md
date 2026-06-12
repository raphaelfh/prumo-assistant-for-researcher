# ADR-0013 — PDFs lidos com a tool Read nativa; sem MCP pdf-reader

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D9)

## Contexto
`mcp__pdf-reader__read_pdf` era referenciado por 2 skills e 2 agents, mas nunca foi declarado em `.mcp.json` nem documentado como pré-requisito — consumidores sem um servidor global tinham falha silenciosa. O Read nativo do Claude Code lê PDF diretamente (com seleção de páginas).

## Decisão
Remover todas as referências ao MCP pdf-reader. Skills instruem a leitura de PDF com a tool `Read` (em blocos de páginas quando o PDF é longo).

## Consequências
Um pré-requisito externo a menos; `prumo doctor` continua cobrindo apenas qmd e Zotero. Se um host futuro do plugin não ler PDF nativamente, reavaliar aqui (novo ADR), nunca reintroduzindo dependência não-declarada.

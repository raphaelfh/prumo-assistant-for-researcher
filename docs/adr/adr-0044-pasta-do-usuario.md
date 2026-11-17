# ADR-0044 — Conteúdo pessoal fora do repo: base de conhecimento na pasta do usuário

- Status: proposto
- Data: 2026-11-16
- Origem: pedido do mantenedor; spec `docs/superpowers/specs/2026-11-16-conteudo-pessoal-fora-do-repo-design.md`

## Contexto

O repo é público e não pode carregar conteúdo pessoal. O mantenedor quer conectar ao plugin, de forma opcional, uma base de conhecimento própria: templates de escrita e protocolo, guias de redação, formatos de análise de dados e de machine learning. Hoje o único override de template é por projeto (`<pj>/.claude/writing_templates/`), copiado em cada `pj_*`, e guias não têm lugar. `core/paths.py` resolve só recursos empacotados (ADR-0002, ADR-0038). Um plugin privado não resolve: a doc oficial do Claude Code descreve dependência entre plugins, não extensão das skills de outro plugin.

## Decisão

1. **Uma pasta do usuário, por convenção:** `$XDG_CONFIG_HOME/prumo/` (padrão `~/.config/prumo/`), devolvida por `core/paths.py::user_dir()` quando existe. Sem variável de ambiente, sem campo de configuração, sem manifesto.
2. **Conectar é apontar o caminho com um symlink** para onde a base já mora; a skill `start` faz isso a pedido e nunca sobrescreve.
3. **Duas pastas têm significado:** `templates/<kind>.md` e `guides/<kind>/*.md`, com o vocabulário de `kind` que já existe. O resto da base é livre.
4. **Templates:** a cadeia passa a ser `--template` > projeto > pasta do usuário > plugin. O projeto vence porque é mais específico e é o que reproduz o estudo.
5. **Guias obrigatórias:** `write prep` devolve `guides/<kind>/` em `guides`; o PAR só lista, a skill lê.
6. **Consulta livre:** `write prep` devolve `knowledge`, o índice (caminho e título do primeiro `# `) de todo `*.md` da base fora de `templates/` e `guides/`, com teto de 200; os modos escolhem pelo título e leem. O bloco gerado `prumo:runtime` de todas as skills manda listar a base antes de responder pergunta de redação, método, análise ou ML. A primeira versão, só com a linha de aviso, falhou em sessão real (0 de 2 consultaram a base).
7. **O nome é "pasta do usuário" (`user_dir`)**, não "overlay", que já designa a cópia do `pj_base` e os módulos do `prumo add`.

## Consequências

- Um template pessoal serve a todos os projetos sem cópia; o projeto que precisa congelá-lo copia para `.claude/writing_templates/`.
- Um draft pode depender de um arquivo que não está no projeto, e o `_meta` ainda não registra isso (adiado, com trigger na spec).
- Leitura obrigatória só existe nos modos que passam pelo `write prep`. Nos demais, e para o resto da base, a consulta depende de a skill seguir o passo do `prumo:runtime`: é barata, mas não garantida.
- A base só é anunciada com uma skill do PAR ativa; sessão de código ou de ML sem skill não a vê (adiado, com trigger na spec).
- Fora do computador (Cowork, chat do claude.ai) o alcance não foi verificado.
- Skills e agents pessoais não passam por aqui: são assunto de plugin privado, sem mudança neste repo.
- "Packs externos" seguem adiados (ROADMAP): a pasta do usuário não carrega skill nem código.

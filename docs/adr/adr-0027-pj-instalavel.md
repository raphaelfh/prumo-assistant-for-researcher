# ADR-0027 — O `pj_*` é pacote instalável; código compartilhado tem nome

- Status: aceito
- Data: 2026-08-24
- Origem: [[2026-08-24-pj-instalavel-design]]; complementa [ADR-0022](adr-0022-layout-por-escopo.md)

## Contexto

A ADR-0022 modelou `docs/studies/<slug>/` como unidade de **escrita** e tirou `src/`, `tests/`, `notebooks/` e `pyproject.toml` do núcleo, empurrando-os para módulos. O que ela não decidiu — e ninguém decidiu depois — foi o que vai **dentro** de `src/`.

O módulo `code` entrega `src/.gitkeep`, `tests/.gitkeep` e um `pyproject.toml` **sem `[build-system]`**. Sem build backend, o `uv` trata o projeto como *virtual project*: ele nunca é instalado no próprio `.venv`. O resultado é que código próprio não tem como ser importado, e projetos reais preenchem o vazio com `sys.path.insert` calculado a partir de `Path.cwd()`.

Esse padrão cobra quatro pedágios que não são estéticos. O IDE não segue `sys.path` (análise estática), então o import fica unresolved e o pesquisador perde navegação e refactoring **exatamente no código que é dele**. O `# noqa: E402` vira ruído permanente e treina o olho a ignorar lint. `papermill` e CI dependem do `cwd`, que num runner não é a pasta do notebook. E o `joblib` grava o `__module__` no bundle, então mover o arquivo quebra a desserialização em silêncio, meses depois.

A ausência de `[build-system]` nunca foi escolha registrada — é o default de quem escreveu um `[project]` para declarar dependências.

## Decisão

O `pj_*` com o módulo `code` é um **pacote instalável**: `[build-system]` com hatchling, `uv sync` instalando o projeto em editable no `.venv`. O import de código próprio resolve por instalação, não por `cwd` nem por ordem de `sys.path`.

O pacote é **um por projeto**, em `src/<pkg>/`, com o **compartilhado na raiz do pacote** e um **subpacote por estudo** para o que é específico. A assimetria é deliberada: o caminho curto pertence ao código reutilizável, que é o caso a incentivar. Pacote por estudo foi descartado — código que serve a dois estudos exigiria um pacote comum além deles, com dependência entre pacotes, para resolver o caso que é justamente o mais frequente.

O nome do pacote de import é o nome do projeto **sem o prefixo `pj_`** (`pj_piloto_genetica` → `piloto_genetica`): o prefixo marca diretório de projeto, e em `import` é ruído repetido em toda célula. Slug de estudo vira subpacote por normalização (remove prefixo numérico, hífen vira underscore); o slug da escrita não muda.

O módulo `notebooks` passa a ser por escopo (`notebooks/<estudo>/`), reaproveitando o marcador `__scope__` que `core/scaffold.py` já substitui em qualquer segmento de caminho. Com isso deixa de haver motivo para o tree paralelo `studies/<slug>/{notebooks,scripts}/` que projetos inventaram.

O `doctor` ganha quatro checks determinísticos — `projeto_nao_instalavel`, `pacote_sem_nome`, `sys_path_hack`, `projeto_nao_sincronizado` — e a migração de projeto legado é **agêntica**, no molde do check `legacy_layout`: o CLI detecta e convida, o agente adequa. Não há comando de migração, porque o estado de partida de cada projeto é arbitrário e um migrador determinístico erraria onde o agente acerta lendo o projeto.

Fica **fora** o check "import de módulo não declarado": exigiria resolver o grafo de imports contra os `[dependency-groups]`, que são opt-in (`uv sync --group tabular`), tornando o falso-positivo o caso comum. Isso é trabalho de `deptry` ou do `ruff`.

## Consequências

A questão de IDE se dissolve em vez de ser respondida: com o pacote instalado em editable, PyCharm e VS Code resolvem por interpretador, sem source root, sem `python.analysis.extraPaths`, sem `.iml` versionado. O `.gitignore` do `pj_base` segue ignorando `.idea/` e `.vscode/`. Qualquer solução que exigisse versionar config de editor seria sinal de que a convenção de packaging está errada.

Instalável **não** conserta o pickle. O caminho do módulo continua gravado no bundle; o que muda é que ele passa a ser estável e que sobra um único movimento perigoso — promover de subpacote de estudo para a raiz do pacote. A mitigação é orientação na rule do módulo `code`, não código.

Dois breaks. `prumo add code` muda de forma (cria `src/<pkg>/__init__.py` e emite `[build-system]`), e projetos que já o rodaram passam a acusar `projeto_nao_instalavel`. O `anchor` do módulo `notebooks` muda para `notebooks/__scope__/.gitkeep`, então projeto que já o aplicou volta a aparecer como não-aplicado em `prumo add --list` — ruído, não perda, já que o overlay nunca sobrescreve.

`uv sync` passa a ser pré-requisito para importar código próprio. Invisível em projeto que já usa o `.venv` como kernel; um passo novo em projeto que importava por `sys.path`, e é o que o check `projeto_nao_sincronizado` nomeia.

# ADR-0047 — Notebooks numerados com índice gerado e rodada de modelo por helper do projeto

- Status: proposto
- Data: 2026-11-18
- Origem: pedido do mantenedor; spec `docs/superpowers/specs/2026-11-18-notebooks-e-rodadas-de-modelo-design.md`

## Contexto

Os módulos `notebooks` e `ml` do scaffolding descrevem onde notebook e rodada de modelo moram, mas não criam nada além do primeiro notebook. O segundo notebook é cópia manual, a pasta `notebooks/<escopo>/` não tem índice, e `experiments/<run_id>/` é só um README: cada rodada sai num formato. O overlay troca `__scope__` pelo slug cru, então um escopo `01_estudo` gera `notebooks/01_estudo/`, contra a rule do próprio módulo. O módulo `ml` ainda copia um `eda.ipynb` para a raiz do projeto e não orienta o ajuste do modelo além do vazamento de dados.

## Decisão

1. **`prumo add notebook <nome> --kind eda|prep|model|figures`** é o único caminho que cria notebook. O arquivo nasce como `NN_<nome>.py`, com `NN` na faixa do tipo (00–09, 10–19, 20–29, 30–39), a partir de um modelo em `templates/notebook_kinds/`. O módulo `notebooks` deixa de ter payload por-escopo e chama esse caminho.
2. **Cabeçalho obrigatório** (`Pergunta`, `Entrada`, `Saída`) no topo de cada notebook, lido sem executar o arquivo.
3. **Índice gerado** em `notebooks/<escopo>/README.md`, num bloco `<!-- prumo:notebooks:begin/end -->` (ADR-0009), reescrito por `prumo add notebook` e `prumo update`.
4. **Pasta de escopo sem prefixo numérico** em `notebooks/` e `src/<pkg>/`, por uma função única em `core/pj_layout.py`.
5. **Rodada por helper do projeto**: o módulo `ml` copia `src/<pkg>/runs.py`, que grava `run.json`, `metrics.csv`, `figs/` e o `README.md` da rodada. O helper é código do projeto, não import do `prumo`. `experiments/` continua plano.
6. **Módulo `ml`** perde o `eda.ipynb`, ganha a rule `ml_modeling.md` e declara `requires = ["code"]`; `_module.toml` passa a aceitar `requires`.
7. **`prumo doctor`** acusa notebook fora do lugar, pasta de escopo com prefixo, arquivo sem número, cabeçalho incompleto e índice desatualizado, sempre com o comando de correção e sem mover nada.

## Consequências

- Criar notebook vira um comando; o diretório fica legível pelo nome, pelo número e pelo índice.
- Há um contrato novo a manter: faixas de numeração, campos do cabeçalho e formato do `run.json`. Mudar qualquer um exige cuidar dos projetos existentes pelo `doctor`.
- Projeto existente não é migrado: `eda.ipynb`, pastas com prefixo e rodadas antigas continuam válidos, e o `doctor` aponta o que diverge.
- `runs.py` copiado envelhece no projeto: correção no template não chega a quem já aplicou o módulo. É o preço de o estudo não depender da versão do plugin para reproduzir.
- Módulo com `requires` aplica outro módulo em cadeia; a saída do `prumo add` precisa dizer o que foi aplicado.
- O cabeçalho em docstring depende de o editor do marimo preservá-la ao salvar; a spec prevê comentário `#` como alternativa.

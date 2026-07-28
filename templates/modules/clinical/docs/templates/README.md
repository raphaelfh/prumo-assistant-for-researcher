---
tags: [templates, ethics, cep, writing]
aliases: ["Templates do pj_*", "Modelos administrativos"]
---

# `docs/templates/` — modelos administrativos do projeto

Diretório de **modelos prontos** para artefatos formais que cada `pj_*`
costuma produzir (submissão CEP, dicionário de dados, plano estatístico).
Mantenha os arquivos aqui **intocados** e use-os como base para escrever
versões específicas em `docs/` quando o projeto evoluir.

## Conteúdo

| Arquivo | Uso |
|---|---|
| `Template submissão Plataforma Brasil.docx` | Layout oficial usado como `--reference-doc` do `pandoc` para gerar o `.docx` final de submissão à Plataforma Brasil. **Não edite o conteúdo** — só estilos. |
| `projeto-cep.md` | Esqueleto Markdown da submissão CEP (resumo, justificativa, métodos, considerações éticas, dispensa TCLE, cronograma). Cópia para `docs/cep_submission.md` quando começar a redigir. |
| `data_dictionary_skeleton.md` | Esqueleto Markdown do dicionário de dados em **duas camadas** (Camada 1 — estratégia de extração fornecedor→nós; Camada 2 — engineered features organizadas por pergunta clínica do SAP). Padrões do dataset final, schema atômico long-format `(ID, VAR, RESULT_N, RESULT_RAW, UNIT, DATE, STATUS)`, edge cases (borderline, mesmo dia, cancelados), bibliografia rastreável via `[@citekey]`. Cópia para `docs/data_dictionary.md`. |
| `data_dictionary_example.csv` | Gabarito pipe-delimited (`|`) para a **tabela operacional** (Anexo B do skeleton) — view achatada para a equipe de TI do fornecedor (NAME · DEFINITION · MIN_OR_VALUES · MAX · UNIT · TYPE · WINDOW · SELECTION_RULE · SOURCE_AVAILABLE · NOTES). Convenção: variáveis UPPERCASE ≤10 chars, datas `YYYY-MM-DD`, decimal `.`. Cópia para `docs/data_dictionary.csv` no projeto. |
| `statistical_analysis_plan_skeleton.md` | Esqueleto de SAP (Statistical Analysis Plan) com seções pré-especificadas: princípios, populações de análise, descritiva, sobrevida, longitudinais, sensibilidade, subgrupos, reporting (STROBE/RECORD), figuras-chave. Cópia para `docs/statistical_analysis_plan.md`. |

## Fluxo recomendado

1. **Copie** o template para `docs/` (não edite o original):
   ```bash
   cp docs/templates/projeto-cep.md docs/cep_submission.md
   cp docs/templates/data_dictionary_skeleton.md docs/data_dictionary.md
   cp docs/templates/data_dictionary_example.csv docs/data_dictionary.csv
   cp docs/templates/statistical_analysis_plan_skeleton.md docs/statistical_analysis_plan.md
   ```

2. **Preencha** o conteúdo no arquivo de `docs/` (não no de `templates/`).

3. **Gere o `.docx` final** da submissão CEP usando o `.docx` deste diretório como reference-doc do pandoc:

   ```bash
   pandoc docs/cep_submission.md \
     -o docs/cep_submission.docx \
     --reference-doc="docs/templates/Template submissão Plataforma Brasil.docx"
   ```

   O resultado preserva fontes, espaçamento, cabeçalhos e tabelas no
   formato esperado pelo CEP/CONEP via Plataforma Brasil.

## Por que estes 5 templates?

Os cinco artefatos cobrem o **ciclo mínimo de governança** de qualquer
estudo observacional em saúde:

- **Submissão CEP** (.docx + .md) → autorização ética prévia obrigatória
  (Resolução CNS 466/2012)
- **Dicionário de dados** (.md + .csv) → reprodutibilidade do dataset
  analítico (RECORD item 6c). Camada 1 (extração) endereça a equipe de
  TI do fornecedor; Camada 2 (engineered features) endereça o analista
  e amarra cada feature a um item do SAP via `[@citekey]`.
- **Statistical Analysis Plan** (.md) → análises pré-especificadas
  evitam HARKing e fishing (STROBE item 12)

Mantenha-os atualizados conforme o projeto evolui — toda alteração
deve ser registrada em `docs/decisions/` (ADRs) e refletida em
`docs/_log.md`.

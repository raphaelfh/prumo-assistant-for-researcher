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

`projeto-cep.md`, `statistical_analysis_plan_skeleton.md` e `protocol.md`
não moram mais aqui — vivem prontos para edição direta em
`docs/studies/principal/writing/` (o escopo de escrita). Os dois que
sobram neste diretório são modelos **administrativos**, copiados antes de
preencher:

| Arquivo | Uso |
|---|---|
| `Template submissão Plataforma Brasil.docx` | Layout oficial usado como `--reference-doc` do `pandoc` para gerar o `.docx` final de submissão à Plataforma Brasil. **Não edite o conteúdo** — só estilos. |
| `data_dictionary_skeleton.md` | Esqueleto Markdown do dicionário de dados em **duas camadas** (Camada 1 — estratégia de extração fornecedor→nós; Camada 2 — engineered features organizadas por pergunta clínica do SAP). Padrões do dataset final, schema atômico long-format `(ID, VAR, RESULT_N, RESULT_RAW, UNIT, DATE, STATUS)`, edge cases (borderline, mesmo dia, cancelados), bibliografia rastreável via `[@citekey]`. Cópia para `docs/data_dictionary.md`. |
| `data_dictionary_example.csv` | Gabarito pipe-delimited (`|`) para a **tabela operacional** (Anexo B do skeleton) — view achatada para a equipe de TI do fornecedor (NAME · DEFINITION · MIN_OR_VALUES · MAX · UNIT · TYPE · WINDOW · SELECTION_RULE · SOURCE_AVAILABLE · NOTES). Convenção: variáveis UPPERCASE ≤10 chars, datas `YYYY-MM-DD`, decimal `.`. Cópia para `docs/data_dictionary.csv` no projeto. |

## Fluxo recomendado

1. **`protocol.md`, `projeto-cep.md` e `statistical_analysis_plan_skeleton.md`**
   já chegam em `docs/studies/principal/writing/` — edite-os direto ali,
   sem copiar.
2. **Copie** os modelos administrativos que sobram aqui para `docs/`
   (não edite o original em `templates/`):
   ```bash
   cp docs/templates/data_dictionary_skeleton.md docs/data_dictionary.md
   cp docs/templates/data_dictionary_example.csv docs/data_dictionary.csv
   ```
3. **Preencha** o conteúdo no arquivo de `docs/` (não no de `templates/`).
4. **Gere o `.docx` final** da submissão CEP usando o `.docx` deste diretório como reference-doc do pandoc:

   ```bash
   pandoc docs/studies/principal/writing/projeto-cep.md \
     -o docs/studies/principal/writing/projeto-cep.docx \
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
deve ser registrada em `docs/studies/principal/decisions/` (ADRs) e
refletida em `docs/_log.md`.

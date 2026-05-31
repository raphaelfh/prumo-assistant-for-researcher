---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/code_library.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Padrões de código — healthcare

## I/O tabular

- Preferir **Parquet** em `content/02_processed/` via Polars ou pandas + PyArrow.
- Schema/contrato: **Pandera** (DataFrame checks) ou Frictionless em pipelines de ingestão.

## I/O imagem

- DICOM: **pydicom** para metadados e arrays; pipelines pesados: **SimpleITK** ou **NiBabel** conforme modalidade.
- Nunca alterar `content/01_raw/` in-place; derivados em `content/02_processed/`.

## sklearn (modelo tabular)

- Usar `Pipeline` + `ColumnTransformer` para imputação, encoding e modelo em sequência única serializável.
- Particionamento: `GroupKFold` ou split manual por `patient_id` / `study_id` para evitar vazamento entre pacientes.

## Checklist anti-leakage

1. Definir **janela temporal** e ordem de eventos antes de qualquer split.
2. Normalização/imputação: fit **somente no treino**, dentro do `Pipeline` ou fold.
3. Validar que duplicatas e o mesmo paciente não aparecem em splits distintos.
4. Combinado: alinhar chaves (IDs) entre tabelas e manifestos de imagem antes de treinar.

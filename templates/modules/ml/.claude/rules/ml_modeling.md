---
paths:
  - "notebooks/**"
  - "src/**"
  - "experiments/**"
---

# Ajuste de modelo (módulo `ml`)

Checklist de todo ajuste que pode informar uma decisão do estudo. Notebook de ajuste
novo nasce com ele pronto: `prumo add notebook <nome> --kind model`.

1. **Plano primeiro.** A análise segue o plano de análise do estudo
   (`docs/studies/<slug>/writing/statistical_analysis_plan*.md`, módulo `protocol`).
   Desvio do plano é registrado no resumo da rodada, com o motivo.
2. **Referência simples antes.** Regressão logística (ou linear) é a primeira rodada;
   modelo complexo só entra comparado a ela.
3. **Split por paciente, antes de tudo.** `GroupShuffleSplit`/`GroupKFold` por
   `patient_id`; com tempo, split temporal. Imputação, escala e seleção de variável
   ficam dentro do `Pipeline`, ajustadas só no treino de cada fold.
4. **Tuning sem tocar no teste.** Validação cruzada aninhada (fora estima o desempenho,
   dentro escolhe o hiperparâmetro) ou conjunto de validação próprio. O teste é usado
   uma vez, no fim.
5. **Três perguntas no relato.** Discriminação (AUC/C), calibração (intercepto,
   inclinação e curva) e utilidade clínica (curva de decisão) quando houver limiar de
   decisão. Acurácia sozinha não basta, sobretudo com desfecho raro.
6. **Incerteza sempre.** Intervalo por bootstrap em toda métrica relatada. Só validação
   interna: corrija o otimismo (bootstrap de Harrell) e diga que é interna.
7. **Semente fixa e registrada.** Uma `SEED` no topo do notebook, passada a split,
   modelo e bootstrap.
8. **Toda rodada que informa decisão vai para `experiments/`.** Use o helper do projeto:

   ```python
   from __pkg__.runs import start_run

   run = start_run("baseline", seed=SEED, scope="<escopo>")
   run.log_params(...); run.log_metrics(...); run.save_fig(fig, "calibracao")
   run.finish("O que mudou e o que a rodada mostrou.")
   ```

   Ele grava `run.json` (parâmetros, semente, commit, versões), `metrics.csv`, `figs/`
   e o `README.md` da rodada. Rodada com o código fora do commit fica marcada no README:
   commite antes da rodada que vai para o manuscrito.
9. **Relato pelo TRIPOD+AI** (predição) ou pela diretriz do desenho do estudo. O número
   do manuscrito sai do `metrics.csv` da rodada, não de uma execução solta.

Métrica e figura são agregadas: nunca linha por paciente em `metrics.csv`, e a regra de
célula mínima do `AGENTS.md` vale para tabela e figura de rodada.

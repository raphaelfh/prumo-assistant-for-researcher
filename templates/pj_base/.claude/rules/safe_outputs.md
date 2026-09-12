# Saídas seguras (dado de paciente)

Vale em toda sessão deste projeto. Referência: Five Safes / controle estatístico de divulgação (UK Data Service).

- **Mínimo necessário.** Nunca copie dado linha-a-linha ou identificável (nome, prontuário, CPF, data de nascimento, endereço, texto livre de prontuário) para prosa, notas, findings, wiki ou contexto da conversa além do que a tarefa exige. Para entender um dataset, leia esquema e agregados, não linhas.
- **Célula mínima = 5.** Tabela ou texto com contagem de **pacientes** entre 1 e 4 (e o percentual ou a diferença que a revela) é suprimido ou agregado com a categoria vizinha. O projeto pode declarar limiar maior no `docs/project_guide.md`. Contagem de não-pacientes (clínicos respondentes, "1 de 33"; estudos incluídos) não entra na regra.
- **Dado fora do git.** `content/` (dado bruto e processado) e `.prumo/` (trace local de LLM) ficam no `.gitignore` e nunca são rastreados. `prumo doctor` confere.

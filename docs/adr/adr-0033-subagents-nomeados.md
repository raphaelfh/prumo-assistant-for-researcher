# ADR-0033 — Três subagents read-only com contrato verificado pelo CLI

- Status: aceito
- Data: 2026-09-12
- Origem: [[2026-09-12-superficie-de-skills-design]] (D3, D4). Revisita a [ADR-0012](adr-0012-remocao-agents-ml.md), que removeu `agents/` até haver agents alinhados ao fluxo clínico.

## Contexto

Três operações pagam caro por rodar no thread principal. Extrair um PDF despeja o conteúdo dele no contexto da sessão, e em batch isso escala com o número de papers. Checar se uma citação sustenta a frase lia o `_extract.md`, um resumo gerado por LLM, e um extract errado produzia confirmação ativa (achado "Groundedness" do ROADMAP). E a crítica de um draft era feita pelo mesmo contexto que acompanhou a redação dele.

A ADR-0012 impôs três condições para agent futuro: servir o fluxo clínico, funcionar standalone e usar só tools universais. A documentação do Claude Code, consultada em 2026-09-11, não garante que agents de plugin rodem na aba Code do Desktop nem no Cowork.

## Decisão

Três subagents, cada um justificado por pelo menos um critério — isolamento de contexto, independência de julgamento ou paralelismo:

- **`reader`** extrai um PDF e grava via `prumo paper extract`, com locators por seção.
- **`verifier`** lê o PDF para julgar se a fonte sustenta a frase. O locator só orienta onde procurar, e o `_extract.md` nunca é evidência.
- **`reviewer`** critica um draft sem receber a conversa de redação.

O prompt canônico de cada um mora em `agents/<nome>.md`, na raiz do plugin. O diretório vai no wheel, e `prumo init` o copia para `.claude/agents/`.

Nenhum agent tem ferramenta de escrita. O único caminho de persistência é um comando `prumo`, e todo JSON devolvido é validado pelo CLI. `prumo paper extract` valida `PaperCallout/v1` antes de gravar e carimba o `_meta` de proveniência. `prumo validate` valida `SupportReport/v1` e `PeerReviewReport/v1`. JSON inválido volta ao agent uma vez, com a mensagem de erro.

O transporte é duplo e usa o mesmo arquivo. O modo despacha o agent pelo nome. Se o tipo não existir na sessão, lê `agents/<nome>.md` e despacha `general-purpose` com o corpo como prompt. A decisão não depende do spike F0, que só mede qual dos dois caminhos roda em cada superfície.

## Consequências

O PDF sai do contexto principal na extração, e o thread principal só recebe status. O veredito de suporte passa a exigir trecho literal do PDF quando é positivo. `paper extract` torna-se fail-closed: seção fora do template ou valor que não é texto é recusado sem gravar.

Agent novo precisa cumprir um dos três critérios e as condições da ADR-0012. Contrato novo devolvido por agent entra no registry de `contracts.py`, com teste.

`prumo paper extract` fica mais estrito. Um agent que mande chave fora do template, que antes virava seção "pendente" em silêncio, agora recebe erro com a lista de seções esperadas.

---
title: Trilha do pesquisador — prumo-assist sem terminal
tags: [onboarding, pesquisador, golden-path, desktop, cowork]
---

# Trilha do pesquisador (Desktop/Cowork, sem terminal)

Este guia é para quem quer usar o prumo-assist sem instalar nada no terminal —
só conversando com o Claude, no Claude Desktop ou no Cowork. Se você programa e
prefere o Claude Code, veja a trilha dev no [README do projeto](../README.md);
este documento e aquela seção se referenciam mutuamente.

Duas coisas antes de começar:

- Você precisa de um plano Claude pago (Pro ou Max) — plugins não funcionam no
  plano gratuito.
- As superfícies Desktop/Cowork estão em *research preview*: se uma tela não
  bater exatamente com a descrição abaixo, o caminho geral (menu de plugins →
  adicionar repositório) continua valendo.

## 1. Instalar o plugin, direto na conversa

No menu de plugins do Claude Desktop ou do Cowork, procure **"Add from a
repository"** e informe:

```
raphaelfh/prumo-assist
```

(ou a URL completa do repositório, se preferir). O catálogo vai mostrar o nome
do plugin (`prumo-assist`), a versão publicada no momento — ela muda com as
releases, não estranhe se for diferente do que alguém te contou — e as skills
listadas no catálogo. Depois de instalado, as skills aparecem com o prefixo
`/prumo-assist:...`.

## 2. Seu primeiro resultado, em poucos minutos

Cole um trecho de um draft seu (paper, capítulo, projeto de pesquisa) na
conversa e peça:

```
/prumo-assist:peer-review
```

Isso já foi testado na prática: numa sessão real, o `/prumo-assist:peer-review`
rodou o fluxo completo sem precisar de CLI, Zotero ou busca semântica, e pegou
todos os problemas plantados de propósito num draft de teste (claims sem
evidência, superlativos, contradição com a própria fonte citada). Essa skill é
declarada "julgamento puro": o próprio contrato dela (o preflight do
ADR-0019) diz que roda em qualquer superfície Claude — porque Desktop, Cowork
e Claude Code sincronizam o mesmo plugin, não sistemas diferentes. É esse o
valor imediato: o Claude lê o que você colou e responde, antes de você
instalar qualquer coisa.

## 3. Quando você quiser ir além

Skills que dependem de bibliografia real (Zotero), de um projeto no disco, ou
do CLI `prumo` — por exemplo, gerar um draft de paper a partir do seu protocolo
— vão recusar rodar se essa peça estiver faltando (o contrato de preflight,
ADR-0019, existe exatamente para isso: nunca simular o que não pode ser feito
de verdade) e vão te apontar para `/prumo-assist:start`.

O `/prumo-assist:start` é o instalador guiado: explica o que cada passo faz,
pede seu "sim" antes de rodar, e só segue adiante se o passo anterior
funcionou. Nenhum comando roda sem sua permissão. Os passos que ele oferece,
nesta ordem:

- **uv** (gerenciador de pacotes Python): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **CLI do prumo**: `uv tool install git+https://github.com/raphaelfh/prumo-assist.git`
- **Diagnóstico**: `prumo doctor` — confere se o Zotero está aberto e acessível
- **qmd (opcional — busca semântica)**: `bun install -g @tobilu/qmd`
- **Seu projeto**: `prumo init pj_<nome>`, na pasta que você indicar

No Cowork, esses comandos rodam dentro da pasta do projeto que você conectar
(a "pasta designada") — é ali que os arquivos são lidos e escritos. Numa
conversa sem pasta conectada (chat simples, sem execução de comandos), o
assistente não consegue rodar nada sozinho: ele vai te indicar este mesmo
documento, e você vai precisar do Cowork (ou de alguém com Claude Code) para
de fato instalar.

> **Nota para quem usa Windows:** os comandos acima são de macOS/Linux — no
> Windows, rode-os dentro do WSL (Windows Subsystem for Linux).

## 4. O que é opcional (e o que não é)

- **qmd** (busca semântica no seu wiki) é opcional — exige `bun` instalado.
  Sem ele, a busca continua funcionando por leitura direta dos arquivos, só
  que mais devagar. Pode pular sem culpa.
- **Zotero** só é necessário para as skills de bibliografia (sincronizar
  referências, verificar citações). Escrita e revisão crítica (peer-review,
  scientific-writing) não dependem dele.

## Trilha dev (Claude Code, terminal)

Se você — ou um colega — prefere o terminal, o [README do
projeto](../README.md) tem a trilha completa: instalação do plugin via Claude
Code, instalação do CLI via `uv`, e a tabela de pré-requisitos externos
(Zotero, qmd).

## Kit do piloto (para quem está conduzindo o teste, não para quem está testando)

Esta seção é para o dono do projeto, não para o colega que está
experimentando. Ela documenta o que medir ao rodar o piloto com 1 colega real
(item 4 do spec de zero-friction onboarding) — o resultado calibra as Fases
4–5 do mesmo programa:

- **Cronômetro:** do momento em que você manda o link do marketplace até o
  colega ter um primeiro output real (por exemplo, o resultado de um
  `/prumo-assist:peer-review`). Meta: **≤15 minutos**.
- **Onde travou:** qual passo gerou dúvida, qual mensagem confundiu, o que a
  pessoa tentou clicar e não achou.
- **Consentimento na UI:** capture prints de como o pedido de permissão
  aparece na tela antes de cada comando — é o material bruto que ainda
  faltava da Fase 0 (o spike validou que o consentimento existe, mas não
  registrou a tela).
- **O resultado calibra as Fases 4–5** do guarda-chuva de zero-friction
  (colapsar qmd/Zotero em instalação one-click; empacotar o CLI): elas só
  começam se o piloto mostrar bloqueio real — sem bloqueio observado, essas
  fases não entram (Princípio VI, YAGNI militante).

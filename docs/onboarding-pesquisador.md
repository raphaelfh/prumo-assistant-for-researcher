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
evidência, superlativos, contradição com a própria fonte citada) (no spike da
Fase 0, testado no Claude Code). Essa skill é declarada "julgamento puro": o
próprio contrato dela (o preflight do ADR-0019) diz que roda em qualquer
superfície Claude — porque Desktop, Cowork e Claude Code instalam a partir do
mesmo `marketplace.json` do mesmo repositório, não sistemas diferentes. É esse
o valor imediato: o Claude lê o que você colou e responde, antes de você
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

> Os comandos desta trilha foram validados em macOS/Linux. No Windows, use o
> WSL — ou os instaladores nativos de Windows documentados pelo uv e pelo bun
> (não validados neste piloto).

## 4. Conectar sua biblioteca

Com o projeto criado (`prumo init pj_<nome>`) e o Zotero aberto, ligar a
bibliografia do projeto a uma coleção do Zotero é um comando — peça ao
agente:

```
conecta minha coleção <nome da coleção>
```

Por trás, isso roda `prumo paper connect "<nome da coleção>"`. Antes desse
comando existir, chegar ao mesmo resultado exigia configurar o "Keep
updated" à mão dentro do Zotero (clicar com o botão direito na coleção,
exportar, marcar a opção de manter atualizado e apontar para o
`references/_references.bib` certo dentro do projeto) — um fio fácil de
errar.

Digitar o nome errado é seguro: o comando confere se a coleção existe
**antes** de qualquer mudança no Zotero, então um typo só gera uma mensagem
de erro com sugestões parecidas — nada é criado no Zotero por engano. Se o
mesmo nome existir em mais de uma biblioteca, o agente vai pedir para você
escolher com `--library`.

Depois de conectar, o próximo passo sugerido é sincronizar:

```
prumo paper sync
```

Pular esse passo por enquanto não quebra nada — `prumo doctor` avisa depois
se o `.bib` do projeto ainda estiver no placeholder do scaffold.

## 5. O que é opcional (e o que não é)

- **qmd** (busca semântica no seu wiki) é opcional — exige `bun` instalado.
  Sem ele, a busca continua funcionando por leitura direta dos arquivos, só
  que mais devagar. Pode pular sem culpa.
- **Zotero** só é necessário para as skills de bibliografia (sincronizar
  referências, verificar citações). Escrita e revisão crítica (peer-review,
  scientific-writing) não dependem dele.

## 6. Busca e conectores

### Busca no seu wiki

O caminho normal é o mais simples: peça ao agente e ele lê os arquivos de
`docs/` diretamente — é o mesmo mecanismo nativo do Cowork usado em
qualquer outra pasta, sem ferramenta extra nenhuma.

O `qmd` (busca semântica indexada) é **opcional-avançado**: só compensa em
wikis grandes, e exige `bun` + terminal — por isso não faz parte da trilha
100% sem terminal deste guia (a seção anterior já trata `qmd` como
opcional mesmo para quem tem o CLI).

### Conectores de literatura (PubMed, ensaios clínicos)

A Anthropic mantém um marketplace curado para pesquisa em ciências da
vida, [`anthropics/life-sciences`](https://github.com/anthropics/life-sciences),
instalável in-app (sem terminal):

1. No Cowork: **Customize** → **Plugins** → **Personal plugins** → **"+"**.
2. **Add marketplace** → **Browse Anthropic sources** → **Life Sciences**.

Dois conectores desse marketplace valem destaque:

- **PubMed** — MCP remoto hospedado pela própria Anthropic, sem exigir
  chave de API.
- **clinical-trials** — busca em registros de ensaios clínicos.

> A navegação exata (nomes de menu, número de cliques) segue documentação
> pública da Anthropic sobre plugins — não foi re-testada dentro deste
> piloto (mesmo tratamento do aviso de Windows/WSL acima).

### Busca semântica no seu acervo do Zotero, sem terminal

Existe uma ponte de terceiros que embute um servidor MCP dentro do próprio
Zotero via extensão `.xpi` (Tools → Add-ons), expondo busca semântica do
seu acervo em `127.0.0.1:23120/mcp`:
[cookjohn/zotero-mcp](https://github.com/cookjohn/zotero-mcp). Citamos para
quem quiser explorar — **não validado neste piloto**.

### Editando os arquivos `.md` do projeto

Recomendamos o [Zettlr](https://www.zettlr.com) como editor dos arquivos
`.md` do projeto (drafts, notas, wiki): a convenção de citação `[@key]` que
o prumo usa é a nativa dele, com autocomplete lendo direto o
`references/_references.bib`.

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
- **O piloto já rodou (2026-07-25) e calibrou as Fases 4–5** do guarda-chuva
  de zero-friction. A Fase 4 (colapsar qmd/Zotero em instalação one-click)
  **disparou**: o colega relatou as duas dores reais — o fio manual
  Zotero→bib e o `qmd` inutilizável sem terminal — e o `prumo paper connect`
  (ADR-0020) é o resultado direto, já implementado. A Fase 5 (empacotar o
  CLI) **encerrou fechada**: a instalação guiada da Fase 2 passou no piloto
  sem travar, então o trigger dela (colega travado *apesar* da instalação
  guiada) não disparou — YAGNI militante aplicado corretamente, não
  adiamento (Princípio VI).

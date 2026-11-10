---
title: Trilha do pesquisador — Claude, ChatGPT ou Antigravity
tags: [onboarding, pesquisador, golden-path, desktop]
---

# Trilha do pesquisador

Este guia é para quem quer usar o PAR conversando com um agente de IA, sem
terminal. Funciona com o agente que você já usa:

- **app Claude**, aba **Code** (plano pago, Pro ou Max: plugins não funcionam no gratuito);
- **app ChatGPT**, no **Codex** (Mac);
- **Antigravity**, do Google.

Os três usam as mesmas skills e o mesmo CLI `prumo`. Muda só o jeito de instalar e
de chamar uma skill.

## 1. Instalar o plugin (uma vez)

**App Claude, aba Code.** Cole, um de cada vez:

```
/plugin marketplace add raphaelfh/prumo-assistant-for-researcher
/plugin install par@prumo-assistant-for-researcher
```

e escolha **Instalar para você**. Se o comando não for aceito, use a interface:
**+** → **Plugins** → **Add plugin**, com o endereço
`raphaelfh/prumo-assistant-for-researcher`.

**App ChatGPT (Codex).** Abra uma conversa do Codex numa pasta qualquer e peça:

```
rode codex plugin marketplace add raphaelfh/prumo-assistant-for-researcher
e depois codex plugin add par@prumo-assistant-for-researcher
```

Aprove o acesso à rede quando o Codex pedir. Depois, feche e abra o app. (O PAR
também aparece na aba **Plugins**, no catálogo dele, para instalar com **+**.)

**Antigravity.** Peça ao agente:

```
rode git clone https://github.com/raphaelfh/prumo-assistant-for-researcher ~/.gemini/config/plugins/par
```

Aprove quando ele pedir para rodar fora do sandbox. Mantenha o nome da pasta
`par`: é dele que sai o nome das ferramentas do PAR. O plugin aparece em
**Customizations** e já vale na mensagem seguinte, sem reiniciar. Para atualizar
depois, peça "rode `git -C ~/.gemini/config/plugins/par pull`". Quem instalou o
CLI `agy` pode usar `agy plugin install https://github.com/raphaelfh/prumo-assistant-for-researcher`.

## 2. Começar

Abra uma conversa nova e chame a skill `start`:

| Agente | Como chamar |
|---|---|
| Claude | `/par:start` |
| ChatGPT (Codex) | `$par:start` |
| Antigravity | `/start` |

Ela confere o que falta, explica cada passo e pede o seu "sim" antes de rodar
qualquer comando. Daqui em diante, este guia escreve as skills do jeito do Claude
(`/par:review critique`); no Codex troque `/par:` por `$par:`, no Antigravity use
`/review critique`. Você também pode só pedir em português ("revisa este draft").

## 3. Seu primeiro resultado, em poucos minutos

Cole um trecho de um draft seu (paper, capítulo, projeto de pesquisa) e peça
`/par:review critique`. Essa skill é de julgamento puro: não precisa de CLI,
Zotero nem busca semântica, e roda em qualquer lugar, até num chat web.

## 4. Quando você quiser ir além

Skills que dependem de bibliografia real (Zotero), de um projeto no disco ou do
CLI `prumo` recusam rodar se essa peça faltar (nunca simulam) e apontam para o
`start`. Os passos que ele oferece, nesta ordem:

- **uv** (gerenciador de Python que o PAR usa): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Diagnóstico**: `prumo doctor`, que confere Zotero, pandoc e qmd
- **qmd (opcional, busca semântica)**: `npm install -g @tobilu/qmd`
- **Seu projeto**: `prumo init pj_<nome>`, na pasta que você indicar; depois abra
  essa pasta no seu agente

Na primeira vez, o PAR baixa cerca de 60 MB (uma vez só). No Codex, se aparecer
uma linha `PAR:` falando de sandbox, aprove repetir o comando fora do sandbox.

> Validado em macOS e Linux. Windows (inclusive WSL): ainda não suportado.

## 5. Conectar sua biblioteca

Você precisa do Zotero 9 ou mais novo, com o Better BibTeX 9.0.65 ou mais novo (versões
anteriores não exportam itens novos com a janela do Zotero fechada).

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
`docs/references/_references.bib` certo dentro do projeto) — um fio fácil de
errar.

Digitar o nome errado é seguro: o comando confere se a coleção existe
**antes** de qualquer mudança no Zotero, então um typo só gera uma mensagem
de erro com sugestões parecidas — nada é criado no Zotero por engano. Se o
mesmo nome existir em mais de uma biblioteca, o agente vai pedir para você
escolher com `--library`.

Se a coleção **ainda não existe** — o caso de quem está começando um projeto
do zero — você não precisa sair para o Zotero, criá-la na mão e voltar. Peça:

```
essa coleção ainda não existe, pode criar
```

Isso roda `prumo paper connect "<nome>" --create`, que cria a coleção e liga o
export no mesmo passo. Antes de criar qualquer coisa, o comando imprime o
caminho completo que vai materializar e pede confirmação — leia esse eco, é a
sua chance de pegar um typo antes que ele vire uma coleção de verdade. **Não
há desfazer pelo CLI**: se criar a errada, apague na interface do Zotero (a
coleção e a entrada em Preferences → Better BibTeX → Automatic export). O
agente nunca acrescenta `--create` sozinho; a criação é sempre decisão sua.

Depois de conectar, o próximo passo sugerido é sincronizar:

```
prumo paper sync
```

Pular esse passo por enquanto não quebra nada — `prumo doctor` avisa depois
se o `.bib` do projeto ainda estiver no placeholder do scaffold.

## 6. O que é opcional (e o que não é)

- **qmd** (busca semântica no seu wiki) é opcional — `npm install -g @tobilu/qmd` (ou bun); o próprio agente roda a busca.
  Sem ele, a busca continua funcionando por leitura direta dos arquivos, só
  que mais devagar. Pode pular sem culpa.
- **Zotero** só é necessário para as skills de bibliografia (sincronizar
  referências, verificar citações). Escrita e revisão crítica (`review critique`,
  `write style`) não dependem dele.

## 7. Busca e conectores

### Busca no seu wiki

O caminho normal é o mais simples: peça ao agente e ele lê os arquivos de
`docs/` diretamente — é o mesmo mecanismo nativo do agente usado em
qualquer outra pasta, sem ferramenta extra nenhuma.

O `qmd` (busca semântica indexada) é **opcional-avançado**: só compensa em
wikis grandes. O qmd é um CLI opcional (`npm install -g @tobilu/qmd`); o próprio
agente roda a busca.

### Conectores de literatura (PubMed, ensaios clínicos)

A Anthropic mantém um marketplace curado para pesquisa em ciências da
vida, [`anthropics/life-sciences`](https://github.com/anthropics/life-sciences),
instalável in-app (sem terminal):

1. No app Claude: **Customize** → **Plugins** → **Personal plugins** → **"+"**.
2. **Add marketplace** → **Browse Anthropic sources** → **Life Sciences**.

Dois conectores desse marketplace valem destaque:

- **PubMed** — MCP remoto hospedado pela própria Anthropic, sem exigir
  chave de API.
- **clinical-trials** — busca em registros de ensaios clínicos.

> A navegação exata (nomes de menu, número de cliques) segue documentação
> pública da Anthropic sobre plugins — não foi re-testada dentro deste
> piloto.

### Perguntar ao seu Zotero (opcional, ferramenta de terceiros)

O PAR não lê destaques nem notas do Zotero, nem busca na biblioteca inteira. A ferramenta [54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp) (licença MIT) faz isso. **Ela não foi validada neste piloto** e muda com frequência (12 versões entre agosto e setembro de 2026). Para a bibliografia do projeto, continue usando `/par:paper`.

**No Claude Code (terminal, aba Code do app ou IDE).** Rode no terminal, ou cole cada linha para o agente rodar com a sua permissão:

1. No Zotero 7 ou mais novo: Settings → Advanced → marque "Allow other applications on this computer to communicate with Zotero". Essa ferramenta exige essa opção.
2. `uv tool install zotero-mcp-server`
3. `zotero-mcp install-skill --target claude-user` (sem `--target`, o instalador grava também dentro do projeto).
4. Abra uma sessão nova e pergunte "o que eu anotei no paper X?". Cada comando pede permissão; aprove os de leitura.

Não é preciso rodar `zotero-mcp setup`: sem chave, a ferramenta usa o Zotero local.
Para escrever no Zotero (precisa do Zotero 10 ou mais novo): `zotero-mcp authorize-local` e clique em "Always Allow" no Zotero.
Para atualizar: `zotero-mcp update` e depois `zotero-mcp install-skill --target claude-user --force` (o update não atualiza a skill).

**No chat do app Claude (fora da aba Code).** No terminal: `zotero-mcp setup --skip-semantic-search`; depois reinicie o app. Isso registra 38 ferramentas, que custam cerca de 13 mil tokens em toda mensagem. No Cowork, não testado.

**Privacidade**
- O que o Claude lê (anotações, texto de PDF) entra na conversa. Não use em biblioteca com documento identificável de paciente.
- Nunca configure `ZOTERO_API_KEY`: o modo local basta, e a chave da Web API dá acesso à biblioteca inteira, PDFs incluídos.
- Não instale o extra `[semantic]`. Se um dia instalar, use só o modelo local padrão: as opções OpenAI e Gemini mandam texto para fora.
- Escritas vão para o Zotero e, com o sync ligado, para o zotero.org e seus outros dispositivos.
- A ferramenta lê o banco do Zotero (`zotero.sqlite`) direto, em modo `immutable=1`, e só faz uma cópia temporária privada (apagada ao sair) quando há escritas pendentes no WAL. Com o Zotero aberto, esse modo pode devolver dado inconsistente sem avisar: confira no Zotero o que for citar.

### Editando os arquivos `.md` do projeto

Recomendamos o [Zettlr](https://www.zettlr.com) como editor dos arquivos
`.md` do projeto (drafts, notas, wiki): a convenção de citação `[@key]` que
o prumo usa é a nativa dele, com autocomplete lendo direto o
`docs/references/_references.bib`.

## Trilha dev (terminal)

Quem prefere o terminal instala igual (`claude`, `codex` ou `agy`) e encontra no
[README do projeto](../README.md) a tabela de pré-requisitos externos e como o
plugin roda em cada agente. `uv run prumo` e `claude --plugin-dir .` são só para
desenvolver o PAR.

## Kit do piloto (para quem conduz o teste)

Meça do link enviado até o primeiro output real (por exemplo, um
`/par:review critique`), com meta de **≤15 minutos**; anote onde a pessoa travou e
capture a tela de cada pedido de permissão. O piloto de 2026-07-25 bateu a meta no
app Claude. Em 2026-11-08, o dono instalou no Antigravity 2.29.1 como usuário novo
(clone): skills e as 10 ferramentas carregaram; o piloto com pesquisadora no Codex e no
Antigravity ainda não rodou.

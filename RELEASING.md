# Política de versionamento e processo de release

`prumo-assist` segue [SemVer](https://semver.org/lang/pt-BR/) — `MAJOR.MINOR.PATCH` — adaptado para a realidade de um plugin do Claude Code (skills + agents + MCP). Este documento explica **quando bumpar cada componente** para que a versão seja informativa, sem virar ruído.

## Regra-mãe

A versão é a **interface pública** do plugin para quem consome (`marketplace update` + `/reload-plugins`). Bumpar significa "tem algo que o usuário precisa saber". Não bumpe quando a mudança é invisível para quem usa o plugin.

## Quando bumpar `PATCH` (0.1.0 → 0.1.1)

Mudanças que **não alteram o que o usuário pode invocar** e não mudam comportamento esperado.

- Fix em manifest (`plugin.json`, `marketplace.json`) — ex.: campo com tipo errado, typo no `description`.
- Refinamento do prompt de uma skill existente sem alterar **quando ela dispara** ou **o que ela produz**.
- Correção de bug em script auxiliar (ex.: `data-cleaning` gerava relatório com header errado).
- Atualização de versão de dependência transitiva sem efeito visível.
- Reformulação textual de `description` (do plugin, da skill, do agent) que não muda o triggering.

Critério prático: se o `CHANGELOG.md` só tem entradas em **Corrigido** e **Documentação**, é PATCH.

## Quando bumpar `MINOR` (0.1.x → 0.2.0)

Adições retrocompatíveis — quem já usava continua funcionando, mas há **algo novo** que vale anunciar.

- Skill nova (ex.: `clinical-stats`).
- Agent novo.
- Trigger novo numa skill existente (ex.: `data-cleaning` agora também dispara em "QC the table").
- Argumento opcional novo numa skill que aceita parâmetros.
- MCP novo exposto.
- Reescrita significativa de uma skill que muda a qualidade do output (mesmo sem renomear nada).

Critério prático: se a entrada do `CHANGELOG.md` em **Adicionado** descreve algo invocável, é MINOR.

## Quando bumpar `MAJOR` (0.x.y → 1.0.0)

Mudanças que **quebram** o uso anterior — quem dependia do comportamento antigo precisa ajustar.

- Skill removida ou renomeada (`/prumo-assist:foo` deixou de existir).
- Trigger de skill ficou mais restrito (algo que disparava antes não dispara mais).
- Estrutura de projeto exigida pelo plugin mudou (ex.: skill agora exige `docs/_index.md` e antes não exigia).
- Schema de configuração (`pj_config.toml`, `paper_extraction.md`) mudou de forma incompatível.
- Output de skill mudou de formato e quebra consumidores downstream.

Antes do `1.0.0`, breaking changes podem ir em MINOR (`0.x.0`) — é o que SemVer permite. Mas marque a entrada do CHANGELOG com **⚠ Breaking** para deixar explícito.

## Quando **NÃO** bumpar

Mudanças invisíveis para o consumidor não viram release:

- Edição em `.github/workflows/`, `.github/schemas/`, `.github/scripts/`.
- Edição em `README.md`, `CHANGELOG.md`, `RELEASING.md`, `LICENSE`.
- Edição em `.gitignore`, `.editorconfig`.
- Refator interno de skill que não muda comportamento perceptível.
- Comentário em código.

Essas mudanças **podem** entrar na seção "Não publicado" do CHANGELOG e ser anunciadas no próximo release real, ou simplesmente serem commitadas sem entrada no CHANGELOG (julgue caso a caso — refator significativo merece registro mesmo invisível ao usuário).

## Política de cadência

- **Não há release programada.** O bump acontece quando há algo a anunciar.
- **Acumule mudanças pequenas** na seção `## [Não publicado]` do `CHANGELOG.md`. Quando juntar peso suficiente (ou houver mudança maior), faça o release.
- **Releases curtos são bons.** Prefira muitos `PATCH` claros a um `MINOR` enorme com 15 itens misturados.
- **Não rebata mudança trivial num release imediato.** Se acabou de sair `0.2.0` e você corrigiu um typo numa description, espere mais 1-2 mudanças antes de cortar `0.2.1`.

## Processo de release (passo-a-passo)

Suposição: você está num branch de trabalho ou direto no `main`, com mudanças prontas e CI passando.

1. **Decida o tipo de bump** consultando as seções acima.
2. **Atualize `CHANGELOG.md`:**
   - Mova as entradas de `## [Não publicado]` para `## [X.Y.Z] - AAAA-MM-DD`.
   - Recrie `## [Não publicado]` vazia no topo.
   - Atualize as referências de link no rodapé do arquivo.
3. **Bump em ambos os manifests** (use o script abaixo ou edite à mão):
   ```bash
   # .claude-plugin/plugin.json -> "version": "X.Y.Z"
   # .claude-plugin/marketplace.json -> plugins[0].version: "X.Y.Z"
   ```
   Ambos **devem ficar iguais** — o CI valida isso (`validate_manifests.py` checa coerência cruzada).
4. **Valide local:**
   ```bash
   python .github/scripts/validate_manifests.py
   ```
5. **Commit** com mensagem `release: X.Y.Z - <resumo>`:
   ```bash
   git add CHANGELOG.md .claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "release: X.Y.Z - resumo curto"
   git push origin main
   ```
6. **Aguarde o CI passar** (workflow `validate-manifests`).
7. **Crie a tag e o release no GitHub:**
   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   gh release create vX.Y.Z --notes-from-tag --title "vX.Y.Z"
   # ou:
   gh release create vX.Y.Z --notes "$(awk '/^## \[X.Y.Z\]/,/^## \[/' CHANGELOG.md | head -n -1)"
   ```
8. **Comunique aos consumidores** (se aplicável) que devem rodar:
   ```
   /plugin marketplace update prumo-assist
   /reload-plugins
   ```

## Como consumidores aplicam novas versões

Em qualquer Claude Code que já tem o plugin instalado:

```
/plugin marketplace update prumo-assist
/reload-plugins
```

`/plugin marketplace update` puxa o último commit do branch padrão do remoto. `/reload-plugins` recarrega skills/agents na sessão ativa sem reiniciar o CLI.

## Exemplo aplicado (release real)

A `0.1.1` deste plugin foi cortada em 2026-04-26 com:

- **Adicionado:** `marketplace.json` (habilita instalação via `/plugin marketplace add raphaelfh/prumo-assist`), CI de validação, este `RELEASING.md`, `CHANGELOG.md`.
- **Corrigido:** `repository` em `plugin.json` virou string (era objeto e o validador rejeitava); typo no README.

Nada disso adiciona skill ou trigger novo → ficou em `PATCH`. Se tivesse incluído uma skill nova (ex.: `clinical-stats`), seria `0.2.0`.

# Contrato de prosa — fonte do bloco `prumo:prose`

Este arquivo é a **fonte canônica** do bloco machine-owned estampado em cada
`SKILL.md` que declara `prumo.prose: true`. Edite aqui e rode
`uv run python .github/scripts/gen_indexes.py`. Nunca edite o bloco dentro de
uma skill à mão — o `--check` do CI reverte (ADR-0009, ADR-0021).

O gerador antepõe seu próprio cabeçalho (`_PROSE_HEADER` em `gen_indexes.py`) e
compõe o corpo com (`lang-free` **ou** `lang-locked`, conforme
`prumo.locale_lock`) + `core`. Em `lang-locked`, `{locale}` é substituído pelo
idioma travado da skill.

O detalhamento completo das convenções (C1–C8, tabelas por idioma, greps de
audit, fluxo de aplicação) vive em `skills/scientific-writing/SKILL.md`, que é a
skill que fiscaliza. Este contrato é o resumo que toda skill de prosa carrega.

<!-- prose:lang-free:begin -->
> 1. **Idioma.** Resolva nesta ordem e **declare qual usou e por qual regra** antes
>    de escrever: (a) pedido explícito (`--lang pt-BR|en-US` ou em linguagem
>    natural); (b) `[writing].language` de `.claude/pj_config.toml`; (c) idioma do
>    texto alvo, quando já existe; (d) default `en-US`. **Nunca traduza** texto
>    existente: se o idioma resolvido divergir do idioma do texto, avise e escreva
>    no idioma do texto.
<!-- prose:lang-free:end -->

<!-- prose:lang-locked:begin -->
> 1. **Idioma travado em `{locale}`.** Este gênero é documento regulatório
>    brasileiro (CEP/CONEP, Plataforma Brasil, TCLE) e não admite outro idioma. Se
>    o usuário pedir idioma diferente, avise que a trava existe e escreva em
>    `{locale}` mesmo assim. **Nunca traduza** texto existente.
<!-- prose:lang-locked:end -->

<!-- prose:core:begin -->
> 2. **Citação no fim do período.** Toda `[@citekey]` fica imediatamente antes do
>    terminador do período (`.`, `?`, `!`), nunca no meio da frase. Sem exceção para
>    autor-sujeito: reescreva (`Liang et al. [@a] propõem X.` → `X foi proposto por
>    Liang et al. [@a].`). Duas fontes sustentando claims distintos viram dois
>    períodos, um para cada.
> 3. **Agrupamento.** Fontes que sustentam a mesma afirmação vão num colchete só,
>    separadas por `;` — `[@a; @b; @c]`. Nunca `[@a], [@b]` nem colchetes adjacentes.
> 4. **Pontuação.** Em texto corrido, sem ` — `, `:` nem `;`. Use vírgula, ponto,
>    parênteses ou conectivo. Preservados em YAML, tabelas, URLs/DOIs, títulos da
>    lista de referências e notação matemática.
> 5. **Sem superlativo.** Intensificador sem número não existe em escrita
>    científica: remova (`highly accurate` → `accurate`) ou troque pelo valor medido.
>    `significant`/`significativo` só no sentido estatístico, com p ou IC no mesmo
>    período. Claim descalibrado (causalidade em desenho associacional, hedging
>    excessivo, antropomorfismo de modelo) é **sinalizado**, nunca reescrito.
> 6. **Voz e tempo.** pt-BR impessoal ou passiva (`avaliou-se`, `foram coletados`);
>    en-US aceita `we` ativo em Methods e Results (AMA/ICMJE) e evita passiva
>    desnecessária. Methods e Results em pretérito; estado da arte no presente.
> 7. **Padrão en-US** (só quando o idioma resolvido é en-US). Ortografia americana
>    (`analyze`, `behavior`, `center`, `modeling`); vírgula serial; decimal com ponto
>    e milhar com vírgula (`0.89`, `1,200`); pontuação final dentro das aspas;
>    numerais exceto em início de período. Termo técnico em inglês **sem itálico** —
>    o itálico é regra de pt-BR.
<!-- prose:core:end -->

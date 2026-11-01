import type { On } from 'claude-code'

const SECTION_ID = 'par:picot'
// Teto do TOML injetado: uma PICOT real tem ~1-2 KB; acima disso algo está errado.
const MAX_CHARS = 8000

/** Texto da seção "PICOT vigente", ou `null` sem `.claude/picot.toml` no cwd. */
export function picotSection(toml: string | null): string | null {
  if (toml === null || toml.trim() === '') return null
  const body = toml.length > MAX_CHARS ? `${toml.slice(0, MAX_CHARS)}\n# (cortado)` : toml
  return [
    '# PICOT vigente do projeto',
    '',
    'Este projeto PAR tem a pergunta de pesquisa fechada em `.claude/picot.toml` (schema `PicotSpec/v1`).',
    'Use-a como referência ao escrever, revisar ou planejar análises: população, intervenção ou preditor (index),',
    'comparador (opcional em `type = "prediction"`), desfecho, tempo ou horizonte, e a hipótese formal.',
    'Não edite o arquivo diretamente: mudanças passam por `/par:protocol picot`, que versiona e grava ADR.',
    '',
    '```toml',
    body.trimEnd(),
    '```',
  ].join('\n')
}

async function readPicot(read: (path: string) => Promise<string>): Promise<string | null> {
  try {
    return await read('.claude/picot.toml')
  } catch {
    return null
  }
}

export function registerPicot(on: On): void {
  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    const text = picotSection(await readPicot(path => $.fs.read(path)))
    const sections = composed.sections.filter(section => section.id !== SECTION_ID)
    if (text === null) return { ...composed, sections }

    return { ...composed, sections: [...sections, { id: SECTION_ID, text, scope: 'session' }] }
  })
}

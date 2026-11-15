import type { On } from 'claude-code'

const SECTION_ID = 'par:question'
// Teto do TOML injetado: uma pergunta do estudo real tem ~1-2 KB; acima disso algo está errado.
const MAX_CHARS = 8000

/** Arquivo lido: `question.toml` (ADR-0041) ou, em projeto antigo, `picot.toml`. */
export interface QuestionFile {
  path: '.claude/question.toml' | '.claude/picot.toml'
  toml: string
}

/** Texto da seção "Pergunta do estudo vigente", ou `null` sem arquivo no cwd. */
export function questionSection(file: QuestionFile | null): string | null {
  if (file === null || file.toml.trim() === '') return null
  const { path, toml } = file
  const body = toml.length > MAX_CHARS ? `${toml.slice(0, MAX_CHARS)}\n# (cortado)` : toml
  const schema = path.endsWith('question.toml') ? 'QuestionSpec/v1' : 'PicotSpec/v1, formato anterior'
  return [
    '# Pergunta do estudo vigente',
    '',
    `Este projeto PAR tem a pergunta do estudo fechada em \`${path}\` (schema \`${schema}\`).`,
    'Use-a como referência ao escrever, revisar ou planejar análises: tipo e desenho do estudo, a pergunta,',
    'o framework opcional (PICOT, PECO, PCC, PICo, SPIDER...) com seus elementos, e o objetivo ou a hipótese formal.',
    'Não edite o arquivo diretamente: mudanças passam por `/par:protocol question`, que versiona e grava ADR.',
    '',
    '```toml',
    body.trimEnd(),
    '```',
  ].join('\n')
}

async function readQuestion(read: (path: string) => Promise<string>): Promise<QuestionFile | null> {
  for (const path of ['.claude/question.toml', '.claude/picot.toml'] as const) {
    try {
      return { path, toml: await read(path) }
    } catch {
      // ausente: tenta o próximo
    }
  }
  return null
}

export function registerPicot(on: On): void {
  on('prompt.compose', async ($, e, next) => {
    const composed = await next(e)
    const text = questionSection(await readQuestion(path => $.fs.read(path)))
    const sections = composed.sections.filter(
      section => section.id !== SECTION_ID && section.id !== 'par:picot',
    )
    if (text === null) return { ...composed, sections }

    return { ...composed, sections: [...sections, { id: SECTION_ID, text, scope: 'session' }] }
  })
}

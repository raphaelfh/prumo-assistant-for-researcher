import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'par',
  component: 'Pane',
  requestId: 'par-revisao',
  props: {
    title: 'Revisão do manuscrito',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const COMPOSE = {
  model: 'claude-opus-5-5',
  promptModel: 'claude-opus-5-5',
  surfaces: ['desktop'],
  tools: [],
  outputStyle: null,
  traits: [],
} as const

const REVISAO = {
  command: 'revisao',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: true, columns: 120 },
} as const

const PICOT = `[picot]
type = "prediction"
population = "adultos com dor torácica"
intervention = "troponina na admissão"
outcome = "IAM"
time = "30 dias"
`

const WORKLIST = `---
title: Métodos
---
O desfecho foi {--mortalidade--}{++IAM++} em 30 dias.{>>citar diretriz<<}
`

const QUESTION = `[question]
type = "review"
question = "O que se sabe sobre telessaúde na APS rural?"
objective = "Mapear a evidência."
framework = "PCC"
`

test('a pergunta do estudo vigente entra no system prompt como seção de sessão', async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'oi', scope: 'shared' }] }))
  on('fs.read', (_, e) => {
    if (e.path.endsWith('question.toml')) return { value: QUESTION }
    throw new Error('ENOENT')
  })

  const { sections } = await $.prompt.compose(COMPOSE)
  const question = sections.find(section => section.id === 'par:question')
  expect(question?.scope).toBe('session')
  expect(question?.text).toContain('type = "review"')
  expect(question?.text).toContain('QuestionSpec/v1')
  expect(question?.text).toContain('/par:protocol question')
})

test('projeto antigo: cai no picot.toml', async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'oi', scope: 'shared' }] }))
  on('fs.read', (_, e) => {
    if (e.path.endsWith('picot.toml')) return { value: PICOT }
    throw new Error('ENOENT')
  })

  const { sections } = await $.prompt.compose(COMPOSE)
  const question = sections.find(section => section.id === 'par:question')
  expect(question?.text).toContain('type = "prediction"')
  expect(question?.text).toContain('.claude/picot.toml')
})

test('sem question.toml nem picot.toml o system prompt fica como está', async ($, on) => {
  on('prompt.compose', () => ({ sections: [{ id: 'intro', text: 'oi', scope: 'shared' }] }))
  on('fs.read', () => {
    throw new Error('ENOENT')
  })

  const { sections } = await $.prompt.compose(COMPOSE)
  expect(sections.map(section => section.id)).toEqual(['intro'])
})

test('o painel lista as marcas pendentes de cada página, em todo surface', async ($, on) => {
  on('command.register', () => ({ value: { command: 'revisao' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('fs.exists', () => ({ value: true }))
  on('fs.list', () => ({
    value: [{ name: 'metodos', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }],
  }))
  on('fs.read', () => ({ value: 'schema_version: ReviewEventsFile/v1\npage: docs/metodos.md\nevents: []\n' }))
  on('session.cwd', () => ({ value: '/pj' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', (_, e) => {
    const text =
      e.tool === 'review_status'
        ? JSON.stringify({ pending_marks: 3, comments: 1, pending_drops: 0 })
        : WORKLIST
    return { value: { content: [{ type: 'text', text }], isError: false } }
  })

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })
  await $.command.run(REVISAO)

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /docs\/metodos\.md/ }))?.text).toBe(
      'docs/metodos.md',
    )
    expect((await ui.find({ type: 'Text', text: /marcas pendentes/ }))?.text).toContain(
      '3 marcas pendentes',
    )
    expect(await ui.find({ type: 'Button', key: 'mark-metodos-2' })).toBeDefined()
    await ui.unmount()
  }
})

test('com o prumo fora do ar o painel diz o que fazer', async ($, on) => {
  on('command.register', () => ({ value: { command: 'revisao' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('fs.exists', () => ({ value: true }))
  on('mcp.connect', () => ({ value: { isConnected: false, reason: 'failed', message: 'x' } }))

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })
  await $.command.run(REVISAO)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /prumo indisponível/ }))?.text).toContain('/par:start')
  await ui.unmount()
})

import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'par',
  component: 'Pane',
  requestId: 'par-projeto',
  props: {
    title: 'Projeto',
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

const PROJETO = {
  command: 'projeto',
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

const NEXT = {
  skill: 'paper',
  mode: 'extract',
  say: 'extraia os principais pontos do paper',
  why: '2 paper(s) com PDF e sem extract',
  scope: null,
  invocation: '/par:paper extract',
}

// ProjectStatus/v1 sintético: só o que o painel lê.
const STATUS = {
  schema_version: 'ProjectStatus/v1',
  next: NEXT,
  stages: [
    { id: 'question', title: 'Pergunta', state: 'done', summary: 'observational · PECO', next: null, scope: null },
    { id: 'library', title: 'Bibliografia', state: 'done', summary: '12 entrada(s)', next: null, scope: null },
    { id: 'reading', title: 'Leitura', state: 'current', summary: '2 sem extract', next: NEXT, scope: null },
    { id: 'writing', title: 'Escrita', state: 'todo', summary: 'sem draft', next: null, scope: 'demo' },
  ],
}

const ok = (payload: unknown) => ({
  value: { content: [{ type: 'text', text: JSON.stringify(payload) }], isError: false },
})

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

test('o painel desenha uma linha por etapa e um botão no próximo passo, em todo surface', async ($, on) => {
  const filled: string[] = []
  const lines: (string | undefined)[] = []
  let calls = 0
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/pj' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', (_, e) => {
    calls += 1
    expect(e.tool).toBe('project_status')
    return ok(STATUS)
  })
  on('ui.status', (_, e) => {
    lines.push(e.text)
    return { value: undefined }
  })
  on('prompt.fill', (_, e) => {
    filled.push(e.text)
    return { isFilled: true }
  })

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })
  await $.command.run(PROJETO)

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    for (const title of ['Pergunta', 'Bibliografia', 'Leitura', 'Escrita']) {
      expect(await ui.find({ type: 'Text', text: new RegExp(title) })).toBeDefined()
    }
    expect(await ui.find({ type: 'Button', key: 'next-writing-demo' })).toBeUndefined()
    await ui.press({ key: 'next-reading' })
    await ui.unmount()
  }

  expect(filled).toEqual([NEXT.say, NEXT.say])
  expect(lines.at(-1)).toBe('Etapa 3/4 · Leitura')
  // session.start + /projeto: uma chamada MCP por atualização.
  expect(calls).toBe(2)
})

test('fora de um pj_* o painel não abre sozinho e /projeto mostra o erro', async ($, on) => {
  let opened = 0
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => {
    opened += 1
    return { value: { isPlaced: true } }
  })
  on('ui.status', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/tmp' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', () => ({
    value: { content: [{ type: 'text', text: 'Raiz de projeto não encontrada. Rode `prumo init`.' }], isError: true },
  }))

  await $.session.start({ cwd: '/tmp', surface: 'desktop', isInteractive: true })
  expect(opened).toBe(0)
  await $.command.run(PROJETO)
  expect(opened).toBe(1)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /prumo init/ }))?.text).toContain('Raiz de projeto')
  await ui.unmount()
})

test('com o prumo fora do ar o painel diz o que fazer', async ($, on) => {
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('mcp.connect', () => ({ value: { isConnected: false, reason: 'failed', message: 'x' } }))

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })
  await $.command.run(PROJETO)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /prumo indisponível/ }))?.text).toContain('/par:start')
  await ui.unmount()
})

test('servidor antigo sem project_status: o painel mostra o erro em vez de ficar vazio', async ($, on) => {
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/pj' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', () => {
    throw new Error('Unknown tool: project_status')
  })

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })
  await $.command.run(PROJETO)

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /não consegui ler o projeto/ }))?.text).toContain('/par:start')
  await ui.unmount()
})

const err = (text: string) => ({ value: { content: [{ type: 'text', text }], isError: true } })

test('pasta com vários pj_*: o painel pede para escolher e lembra a escolha', async ($, on) => {
  const asked: string[] = []
  const lines: (string | undefined)[] = []
  let opened = 0
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => {
    opened += 1
    return { value: { isPlaced: true } }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/ws' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', (_, e) => {
    if (e.tool === 'project_list') {
      return ok({
        projects: [
          { name: 'pj_piloto_a', path: '/ws/pj_piloto_a' },
          { name: 'pj_piloto_b', path: '/ws/pj_piloto_b' },
        ],
      })
    }
    const where = String(e.args.pj_path)
    asked.push(where)
    return where === '/ws' ? err('Raiz de projeto não encontrada. Rode `prumo init`.') : ok(STATUS)
  })
  on('ui.status', (_, e) => {
    lines.push(e.text)
    return { value: undefined }
  })

  await $.session.start({ cwd: '/ws', surface: 'desktop', isInteractive: true })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect(await ui.find({ type: 'Text', text: /2 projetos/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Raiz de projeto/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /Leitura/ })).toBeUndefined()
  // abriu sozinho no session.start, sem /projeto
  expect(opened).toBe(1)

  await ui.press({ key: 'pick-pj_piloto_a' })
  expect(asked.at(-1)).toBe('/ws/pj_piloto_a')
  expect(await ui.find({ type: 'Text', text: /Leitura/ })).toBeDefined()
  expect(await ui.find({ type: 'Button', key: 'switch' })).toBeDefined()
  expect(lines.at(-1)).toBe('pj_piloto_a · Etapa 3/4 · Leitura')

  // a escolha vale para as próximas atualizações
  await $.command.run(PROJETO)
  expect(asked.at(-1)).toBe('/ws/pj_piloto_a')

  await ui.press({ key: 'switch' })
  expect(await ui.find({ type: 'Button', key: 'pick-pj_piloto_b' })).toBeDefined()
  await ui.unmount()
})

test('Atualizar mostra a hora da última leitura e avisa que rodou', async ($, on) => {
  const toasts: string[] = []
  on('command.register', () => ({ value: { command: 'projeto' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.status', () => ({ value: undefined }))
  on('ui.toast', (_, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: '/pj' }))
  on('mcp.connect', () => ({ value: { isConnected: true, server: 'plugin:par:prumo' } }))
  on('mcp.call', () => ok(STATUS))

  await $.session.start({ cwd: '/pj', surface: 'desktop', isInteractive: true })

  const ui = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await ui.find({ type: 'Text', text: /Atualizado às/ }))?.text).toMatch(/\d\d:\d\d:\d\d/)
  await ui.press({ key: 'refresh' })
  expect(toasts).toEqual(['Projeto atualizado.'])
  await ui.unmount()
})

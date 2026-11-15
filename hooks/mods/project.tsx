import { atom, read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { ProjectSnapshot, ProjectStatusJson, Stage } from '../../types'

export const PANE = 'par-projeto'
const TITLE = 'Projeto'
const COMMAND = 'projeto'

// Troque o tag quando os campos de ProjectSnapshot mudarem: o valor guardado
// por uma versão anterior sobrevive ao reload e seria lido com o shape errado.
const project = atom({ plugin: 'par', key: 'project' } as const, { status: null, updatedAt: 0 }, {
  shape: 'project-1',
})

/** Mesmos marcadores do `prumo status` (STAGE_MARKS em src/par/status.py). */
const MARKS: Record<Stage['state'], string> = { done: '✓', current: '●', attention: '!', todo: '○' }

function textOf(result: { content: { type: string; text?: string }[] }): string {
  return result.content
    .filter(block => block.type === 'text')
    .map(block => block.text ?? '')
    .join('')
}

/** "Etapa 3/6 · Leitura", ou `undefined` quando nada está pendente. */
export function statusLine(status: ProjectStatusJson): string | undefined {
  const index = status.stages.findIndex(stage => stage.state === 'current')
  if (index < 0) return undefined
  return `Etapa ${index + 1}/${status.stages.length} · ${status.stages[index]?.title ?? ''}`
}

/** Uma chamada a `project_status` (ADR-0043); toda a lógica das etapas mora no Python. */
async function collect($: EngineInterface): Promise<ProjectSnapshot> {
  const now = Date.now()
  const connected = await $.mcp.connect('prumo')
  if (!connected.isConnected) {
    return {
      status: null,
      updatedAt: now,
      error: `servidor prumo indisponível (${connected.reason}); rode /par:start`,
    }
  }
  const result = await $.mcp.call(connected.server, 'project_status', {
    pj_path: await $.session.cwd(),
  })
  if (result.isError) return { status: null, updatedAt: now, error: textOf(result) }
  return { status: JSON.parse(textOf(result)) as ProjectStatusJson, updatedAt: now }
}

/** Relê o projeto, grava o retrato do painel e a linha de status; devolve o retrato. */
async function refresh($: EngineInterface): Promise<ProjectSnapshot> {
  // Uma exceção (tool ausente num servidor antigo, JSON inválido) vira erro visível:
  // engolida, deixaria o painel só com o botão "Atualizar".
  const snapshot = await collect($).catch(
    (err: unknown): ProjectSnapshot => ({
      status: null,
      updatedAt: Date.now(),
      error: `não consegui ler o projeto (${err instanceof Error ? err.message : String(err)}); rode /par:start`,
    }),
  )
  await update($, project, () => snapshot)
  $.ui.status(snapshot.status === null ? undefined : statusLine(snapshot.status))
  return snapshot
}

export function registerProject(on: On): void {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Abre o painel com as etapas do estudo e o próximo passo',
    })
    const result = await next(e)
    // Abre sozinho só dentro de um pj_* (a tool responde sem erro).
    void refresh($)
      .then(snapshot => (snapshot.status !== null ? $.ui.open({ id: PANE, title: TITLE }) : undefined))
      .catch(() => undefined)
    return result
  })

  on('command.run', { command: COMMAND }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    void refresh($).catch(() => undefined)
    return { text: 'Painel do projeto aberto.' }
  }).catch(() => ({ text: 'Não consegui abrir o painel do projeto. Rode `/par:start`.' }))

  // As etapas mudam pelo que a skill ou o CLI gravam no disco durante o turno.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    void refresh($).catch(() => undefined)
    return result
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const snapshot = await read($, project)
    const stages = snapshot.status?.stages ?? []

    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button key="refresh" onPress={() => refresh($)}>
            Atualizar
          </Button>
        </Box>
        {snapshot.error !== undefined && <Text color="red">{snapshot.error}</Text>}
        {snapshot.error === undefined && snapshot.status === null && <Text dimColor>Lendo o projeto…</Text>}
        {stages.map((stage: Stage, index: number) => {
          const where = stage.scope !== null ? ` (${stage.scope})` : ''
          const say = stage.next?.say
          return (
            <Box flexDirection="column" key={`stage-${index}`}>
              <Text bold={stage.state === 'current'}>
                {MARKS[stage.state]} {stage.title}
                {where} <Text dimColor>{stage.summary}</Text>
              </Text>
              {say !== undefined && (
                <Button
                  key={`next-${stage.id}${stage.scope !== null ? `-${stage.scope}` : ''}`}
                  {...(stage.state === 'current' ? {} : { plain: true })}
                  onPress={() => $.prompt.fill({ text: say, mode: 'replace' })}
                >
                  {stage.state === 'current' ? 'Próximo passo' : 'Resolver'}: {say}
                </Button>
              )}
            </Box>
          )
        })}
      </Box>
    )
  })
}

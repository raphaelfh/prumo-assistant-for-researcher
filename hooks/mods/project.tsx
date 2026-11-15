import { atom, read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { ProjectRef, ProjectSnapshot, ProjectStatusJson, Stage } from '../../types'

export const PANE = 'par-projeto'
const TITLE = 'Projeto'
const COMMAND = 'projeto'

const EMPTY: ProjectSnapshot = { status: null, updatedAt: 0, projects: [], selected: null, loading: false }

// Troque o tag quando os campos de ProjectSnapshot mudarem: o valor guardado
// por uma versão anterior sobrevive ao reload e seria lido com o shape errado.
const project = atom({ plugin: 'par', key: 'project' } as const, EMPTY, { shape: 'project-2' })

/** Mesmos marcadores do `prumo status` (STAGE_MARKS em src/par/status.py). */
const MARKS: Record<Stage['state'], string> = { done: '✓', current: '●', attention: '!', todo: '○' }

type CallResult = { content: { type: string; text?: string }[]; isError?: boolean }

function textOf(result: CallResult): string {
  return result.content
    .filter(block => block.type === 'text')
    .map(block => block.text ?? '')
    .join('')
}

/** "14:05:09", na hora local de quem vê o painel. */
export function clockTime(ms: number): string {
  const at = new Date(ms)
  return [at.getHours(), at.getMinutes(), at.getSeconds()].map(n => String(n).padStart(2, '0')).join(':')
}

/** "Etapa 3/6 · Leitura", ou `undefined` quando nada está pendente. */
export function statusLine(status: ProjectStatusJson): string | undefined {
  const index = status.stages.findIndex(stage => stage.state === 'current')
  if (index < 0) return undefined
  return `Etapa ${index + 1}/${status.stages.length} · ${status.stages[index]?.title ?? ''}`
}

function nameOf(path: string): string {
  return path.split('/').filter(Boolean).at(-1) ?? path
}

/**
 * Lê o projeto pelas tools do `prumo` (ADR-0043); toda a lógica mora no Python.
 * Uma chamada por atualização dentro de um `pj_*`. Numa pasta com vários, a
 * pesquisadora escolhe na lista (`project_list`) e o painel lembra a escolha.
 */
async function collect($: EngineInterface, previous: ProjectSnapshot): Promise<ProjectSnapshot> {
  const base = { ...previous, status: null, loading: false, updatedAt: Date.now() }
  delete base.error
  const connected = await $.mcp.connect('prumo')
  if (!connected.isConnected) {
    return { ...base, error: `servidor prumo indisponível (${connected.reason}); rode /par:start` }
  }
  const cwd = await $.session.cwd()
  const result: CallResult = await $.mcp.call(connected.server, 'project_status', {
    pj_path: previous.selected ?? cwd,
  })
  if (result.isError !== true) return { ...base, status: JSON.parse(textOf(result)) as ProjectStatusJson }
  if (previous.selected !== null) return { ...base, error: textOf(result) }

  // A pasta da sessão não é um projeto: oferece os pj_* que ela contém.
  const listed: CallResult = await $.mcp.call(connected.server, 'project_list', { path: cwd })
  const projects =
    listed.isError === true ? [] : (JSON.parse(textOf(listed)) as { projects: ProjectRef[] }).projects
  const only = projects.length === 1 ? projects[0] : undefined
  if (only !== undefined) return collect($, { ...base, projects, selected: only.path })
  if (projects.length > 1) return { ...base, projects }
  return { ...base, projects, error: textOf(result) }
}

/** Relê o projeto, grava o retrato do painel e a linha de status; devolve o retrato. */
async function refresh($: EngineInterface): Promise<ProjectSnapshot> {
  const previous = await update($, project, value => ({ ...value, loading: true }))
  // Uma exceção (tool ausente num servidor antigo, JSON inválido) vira erro visível:
  // engolida, deixaria o painel só com o botão "Atualizar".
  const snapshot = await collect($, previous).catch(
    (err: unknown): ProjectSnapshot => ({
      ...previous,
      status: null,
      loading: false,
      updatedAt: Date.now(),
      error: `não consegui ler o projeto (${err instanceof Error ? err.message : String(err)}); rode /par:start`,
    }),
  )
  // Se a pesquisadora trocou de projeto durante a leitura, a leitura antiga não vale.
  const saved = await update($, project, current =>
    current.selected === previous.selected ? snapshot : { ...current, loading: false },
  )
  const line = saved.status === null ? undefined : statusLine(saved.status)
  const where = saved.selected !== null && saved.projects.length > 1 ? `${nameOf(saved.selected)} · ` : ''
  $.ui.status(line === undefined ? undefined : `${where}${line}`)
  return saved
}

/** Escolhe um projeto da lista (ou volta à lista com `null`) e relê. */
async function choose($: EngineInterface, path: string | null): Promise<void> {
  const chosen = await update($, project, value => {
    const next: ProjectSnapshot = { ...value, selected: path, status: null }
    delete next.error
    return next
  })
  if (chosen.selected !== null) await refresh($)
  else $.ui.status(undefined)
}

export function registerProject(on: On): void {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Abre o painel com as etapas do estudo e o próximo passo',
    })
    const result = await next(e)
    // Abre sozinho dentro de um pj_* ou numa pasta com vários deles.
    void refresh($)
      .then(snapshot =>
        snapshot.status !== null || snapshot.projects.length > 1 ? $.ui.open({ id: PANE, title: TITLE }) : undefined,
      )
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
    const many = snapshot.projects.length > 1
    const picking = many && snapshot.selected === null
    const when = snapshot.loading
      ? 'Atualizando…'
      : snapshot.updatedAt > 0
        ? `Atualizado às ${clockTime(snapshot.updatedAt)}`
        : ''

    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button
            key="refresh"
            onPress={async () => {
              const done = await refresh($)
              $.ui.toast(done.error === undefined ? 'Projeto atualizado.' : 'Não consegui atualizar o projeto.')
            }}
          >
            Atualizar
          </Button>
          <Text dimColor> {when}</Text>
        </Box>
        {many && snapshot.selected !== null && (
          <Box flexDirection="row">
            <Text bold>{`${nameOf(snapshot.selected)} `}</Text>
            <Button key="switch" plain onPress={() => choose($, null)}>
              Trocar projeto
            </Button>
          </Box>
        )}
        {picking && <Text>{`Esta pasta tem ${snapshot.projects.length} projetos. Qual abrir?`}</Text>}
        {picking &&
          snapshot.projects.map((ref: ProjectRef) => (
            <Button key={`pick-${ref.name}`} onPress={() => choose($, ref.path)}>
              {ref.name}
            </Button>
          ))}
        {snapshot.error !== undefined && <Text color="red">{snapshot.error}</Text>}
        {snapshot.error === undefined && snapshot.status === null && !picking && (
          <Text dimColor>Lendo o projeto…</Text>
        )}
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

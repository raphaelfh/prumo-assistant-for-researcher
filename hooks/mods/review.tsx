import { atom, read, update } from 'claude-code'
import type { EngineInterface, On } from 'claude-code'

import type { ReviewMark, ReviewPage, ReviewSnapshot } from '../../types'

export const PANE = 'par-revisao'
const TITLE = 'Revisão do manuscrito'
const COMMAND = 'revisao'
const MAX_MARKS = 30

// Troque o tag quando os campos de ReviewSnapshot mudarem: o valor guardado
// por uma versão anterior sobrevive ao reload e seria lido com o shape errado.
const review = atom({ plugin: 'par', key: 'review' } as const, { pages: [], updatedAt: 0 }, {
  shape: 'review-1',
})

const MARK_RE = /\{\+\+([\s\S]*?)\+\+\}|\{--([\s\S]*?)--\}|\{~~([\s\S]*?)~>([\s\S]*?)~~\}|\{>>([\s\S]*?)<<\}|\{==([\s\S]*?)==\}/g

function short(text: string, size = 80): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > size ? `${flat.slice(0, size - 1)}…` : flat
}

/** Marcas CriticMarkup pendentes do corpo de `review.md` (frontmatter ignorado). */
export function pendingMarks(worklist: string): ReviewMark[] {
  const body = worklist.replace(/^---\n[\s\S]*?\n---\n/, '')
  const marks: ReviewMark[] = []
  for (const m of body.matchAll(MARK_RE)) {
    if (m[1] !== undefined) marks.push({ kind: 'inserção', excerpt: short(m[1]) })
    else if (m[2] !== undefined) marks.push({ kind: 'remoção', excerpt: short(m[2]) })
    else if (m[3] !== undefined)
      marks.push({ kind: 'troca', excerpt: short(`${m[3]} → ${m[4] ?? ''}`) })
    else if (m[5] !== undefined) marks.push({ kind: 'comentário', excerpt: short(m[5]) })
    else if (m[6] !== undefined) marks.push({ kind: 'destaque', excerpt: short(m[6]) })
  }
  return marks
}

/** O campo `page` de `events.yaml` (caminho relativo à raiz do projeto). */
export function pageOf(eventsYaml: string): string | undefined {
  const m = /^page:\s*(['"]?)(.+?)\1\s*$/m.exec(eventsYaml)
  return m?.[2]
}

function textOf(result: { content: { type: string; text?: string }[] }): string {
  return result.content
    .filter(block => block.type === 'text')
    .map(block => block.text ?? '')
    .join('')
}

async function loadPage($: EngineInterface, server: string, cwd: string, slug: string) {
  const events = await $.fs.read(`reviews/${slug}/events.yaml`)
  const page = pageOf(events)
  if (page === undefined) return undefined
  const base: ReviewPage = { slug, page, pendingMarks: 0, comments: 0, pendingDrops: 0, marks: [] }
  const absolute = page.startsWith('/') ? page : `${cwd}/${page}`
  try {
    const status = await $.mcp.call(server, 'review_status', { page: absolute })
    if (status.isError) return { ...base, error: short(textOf(status), 160) }
    const counts = JSON.parse(textOf(status)) as {
      pending_marks?: number
      comments?: number
      pending_drops?: number
    }
    const worklist = await $.mcp.call(server, 'review_worklist', { page: absolute })
    const marks = worklist.isError ? [] : pendingMarks(textOf(worklist))
    return {
      ...base,
      pendingMarks: counts.pending_marks ?? marks.length,
      comments: counts.comments ?? 0,
      pendingDrops: counts.pending_drops ?? 0,
      marks: marks.slice(0, MAX_MARKS),
    }
  } catch (err) {
    return { ...base, error: short(String(err), 160) }
  }
}

/** Relê `reviews/*` do projeto e grava o retrato no estado do painel. */
async function refresh($: EngineInterface): Promise<void> {
  const snapshot = await collect($)
  await update($, review, () => snapshot)
}

async function collect($: EngineInterface): Promise<ReviewSnapshot> {
  const now = Date.now()
  if (!(await $.fs.exists('reviews'))) return { pages: [], updatedAt: now }
  const connected = await $.mcp.connect('prumo')
  if (!connected.isConnected) {
    return {
      pages: [],
      updatedAt: now,
      error: `servidor prumo indisponível (${connected.reason}); rode /par:start`,
    }
  }
  const cwd = await $.session.cwd()
  const dirs = (await $.fs.list('reviews')).filter(entry => entry.kind === 'dir')
  const pages: ReviewPage[] = []
  for (const dir of dirs) {
    try {
      const page = await loadPage($, connected.server, cwd, dir.name)
      if (page !== undefined) pages.push(page)
    } catch {
      // Diretório sem events.yaml (ingest incompleto): fica fora do painel.
    }
  }
  pages.sort((a, b) => b.pendingMarks - a.pendingMarks || a.page.localeCompare(b.page))
  return { pages, updatedAt: now }
}

export function registerReview(on: On): void {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: 'Abre o painel de revisão do manuscrito (marcas pendentes do prumo)',
    })
    const result = await next(e)
    if (await $.fs.exists('reviews')) {
      void refresh($).catch(() => undefined)
      void $.ui.open({ id: PANE, title: TITLE })
    }
    return result
  })

  on('command.run', { command: COMMAND }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })
    void refresh($).catch(() => undefined)
    return { text: 'Painel de revisão aberto.' }
  }).catch(() => ({ text: 'Não consegui abrir o painel de revisão. Rode `/par:start`.' }))

  // O ciclo de revisão muda por `prumo write review ...` e pelo propose_prose_edit.
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (await $.fs.exists('reviews')) void refresh($).catch(() => undefined)
    return result
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const snapshot = await read($, review)
    const fill = (text: string) => () => $.prompt.fill({ text, mode: 'replace' })

    return (
      <Box flexDirection="column">
        <Box flexDirection="row">
          <Button key="refresh" onPress={() => refresh($)}>
            Atualizar
          </Button>
        </Box>
        {snapshot.error !== undefined && <Text color="red">{snapshot.error}</Text>}
        {snapshot.error === undefined && snapshot.pages.length === 0 && (
          <Text dimColor>
            Nenhuma revisão ingerida. Rode `prumo write review ingest &lt;docx&gt; --page &lt;page.md&gt;`.
          </Text>
        )}
        {snapshot.pages.map(page => (
          <Box flexDirection="column" key={`page-${page.slug}`}>
            <Text bold>{page.page}</Text>
            {page.error !== undefined ? (
              <Text color="red">{page.error}</Text>
            ) : (
              <Text dimColor>
                {page.pendingMarks} marcas pendentes · {page.comments} comentários ·{' '}
                {page.pendingDrops} citações removidas a confirmar
              </Text>
            )}
            <Button
              key={`reconcile-${page.slug}`}
              onPress={fill(`/par:review reconcile --page ${page.page}`)}
            >
              Reconciliar
            </Button>
            {page.marks.map((mark: ReviewMark, index: number) => (
              <Button
                key={`mark-${page.slug}-${index}`}
                plain
                onPress={fill(
                  `Na revisão de \`${page.page}\`, me ajude a decidir esta marca (${mark.kind}): «${mark.excerpt}»`,
                )}
              >
                {mark.kind} <Text dimColor>{mark.excerpt}</Text>
              </Button>
            ))}
          </Box>
        ))}
      </Box>
    )
  })
}

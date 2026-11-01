/** Uma marca CriticMarkup pendente no worklist (`review.md`) de uma página. */
export type ReviewMark = { kind: string; excerpt: string }

/** Uma página do manuscrito com ciclo de revisão em `reviews/<slug>/`. */
export type ReviewPage = {
  slug: string
  page: string
  pendingMarks: number
  comments: number
  pendingDrops: number
  marks: ReviewMark[]
  error?: string
}

export type ReviewSnapshot = {
  pages: ReviewPage[]
  updatedAt: number
  error?: string
}

declare module 'claude-code' {
  interface PluginState {
    par: { review: Shaped<ReviewSnapshot> }
  }
}

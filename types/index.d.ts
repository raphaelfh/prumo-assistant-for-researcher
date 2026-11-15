/** O próximo passo de uma etapa: a frase a dizer, a invocação e o motivo. */
export type StageNext = {
  skill: string
  mode: string
  say: string
  why: string
  scope: string | null
  invocation: string
}

/** Uma etapa do estudo, como `prumo status --json` e a tool `project_status` a devolvem. */
export type Stage = {
  id: string
  title: string
  state: 'done' | 'current' | 'attention' | 'todo'
  summary: string
  next: StageNext | null
  scope: string | null
}

/** A parte de `ProjectStatus/v1` que o painel "Projeto" desenha. */
export type ProjectStatusJson = {
  schema_version: string
  stages: Stage[]
  next: StageNext | null
}

export type ProjectSnapshot = {
  status: ProjectStatusJson | null
  updatedAt: number
  error?: string
}

declare module 'claude-code' {
  interface PluginState {
    par: { project: Shaped<ProjectSnapshot> }
  }
}

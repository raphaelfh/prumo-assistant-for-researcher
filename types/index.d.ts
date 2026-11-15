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
  project: string
  stages: Stage[]
  next: StageNext | null
}

/** Um `pj_*` da pasta de trabalho, como a tool `project_list` o devolve. */
export type ProjectRef = {
  name: string
  path: string
}

export type ProjectSnapshot = {
  status: ProjectStatusJson | null
  updatedAt: number
  error?: string
  /** Os `pj_*` da pasta da sessão quando ela não é um projeto; vazio dentro de um. */
  projects: ProjectRef[]
  /** O caminho do projeto escolhido na lista, ou `null` para usar a pasta da sessão. */
  selected: string | null
  /** Verdadeiro enquanto uma atualização está em curso. */
  loading: boolean
}

declare module 'claude-code' {
  interface PluginState {
    par: { project: Shaped<ProjectSnapshot> }
  }
}

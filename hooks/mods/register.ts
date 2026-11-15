import type { Register } from 'claude-code'

import { registerPicot } from './picot'
import { registerProject } from './project'

/** Mods do PAR: seção "Pergunta do estudo vigente" no system prompt e painel "Projeto". */
export const register: Register = on => {
  registerPicot(on)
  registerProject(on)
}

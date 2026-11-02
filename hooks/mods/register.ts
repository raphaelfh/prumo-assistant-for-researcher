import type { Register } from 'claude-code'

import { registerPicot } from './picot'
import { registerReview } from './review'

/** Mods do PAR: seção "PICOT vigente" no system prompt e painel de revisão. */
export const register: Register = on => {
  registerPicot(on)
  registerReview(on)
}

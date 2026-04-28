"""Domínios de negócio — uma pasta por pilar funcional.

Regra de dependência: ``domains/`` pode importar de ``core/``, mas ``core/``
nunca importa de ``domains/``. Domínios devem ser independentes uns dos outros
quando possível (importações cruzadas só com justificativa explícita).
"""

from __future__ import annotations

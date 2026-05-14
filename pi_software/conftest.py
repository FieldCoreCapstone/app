"""Make `services` importable when pytest is run from the app root.

The existing tests under `pi_software/tests/` import via `from services.X import ...`,
which works when pytest is invoked from the `pi_software/` directory but not from
the app root (the new combined-suite layout). Adding this conftest at the
`pi_software/` level prepends that directory to sys.path during collection so
the existing imports keep working unchanged.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

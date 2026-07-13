from __future__ import annotations

import sys

from agentgoals import run as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical

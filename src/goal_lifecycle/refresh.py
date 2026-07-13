from __future__ import annotations

import sys

from agentgoals import refresh as _canonical

sys.modules[__name__] = _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

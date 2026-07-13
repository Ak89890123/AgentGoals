from __future__ import annotations

import sys

from agentgoals import resolver as _canonical

sys.modules[__name__] = _canonical

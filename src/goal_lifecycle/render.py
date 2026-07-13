from __future__ import annotations

import sys

from agentgoals import render as _canonical

sys.modules[__name__] = _canonical

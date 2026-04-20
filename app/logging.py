from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


def setup_logging(level: str | None = None) -> logging.Logger:
    lvl = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(lvl)
        return logging.getLogger("cs_agent")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(lvl)
    return logging.getLogger("cs_agent")


def jsonl(event: str, **fields: Any) -> str:
    return json.dumps({"event": event, **fields}, default=str, sort_keys=True)

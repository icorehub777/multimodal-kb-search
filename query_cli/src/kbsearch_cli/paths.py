from __future__ import annotations

import os
from pathlib import Path

from kbsearch_cli.errors import QueryInputError


def require_scoped_path(path: Path, boundary: Path) -> Path:
    """Validate a path before access, including redirected directory components."""
    try:
        root = boundary.resolve()
        lexical = Path(os.path.abspath(path))
        if not lexical.is_relative_to(root) or lexical.resolve() != lexical:
            raise QueryInputError(f"Path must remain within its boundary without redirection ({root}): {path}")
        return lexical
    except QueryInputError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise QueryInputError(f"Cannot resolve path within boundary ({boundary}): {path}") from exc

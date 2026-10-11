from __future__ import annotations

import os
from pathlib import Path

from kbsearch_cli.errors import QueryInputError


def require_scoped_path(path: Path, boundary: Path) -> Path:
    """Validate a path before access, including redirected directory components."""
    try:
        root = boundary.resolve()
        lexical = Path(os.path.abspath(path))
        resolved = lexical.resolve()
        if not resolved.is_relative_to(root):
            raise QueryInputError(f"Path must remain within its boundary without redirection ({root}): {path}")
        for component in (lexical, *lexical.parents):
            if component.is_symlink() or component.is_junction():
                raise QueryInputError(f"Path must remain within its boundary without redirection ({root}): {path}")
        if resolved != lexical:
            # Expand an existing ancestor's name without accepting redirected paths.
            ancestor = lexical
            while not ancestor.exists():
                if ancestor.parent == ancestor:
                    raise QueryInputError(f"Path has no accessible filesystem root: {path}")
                ancestor = ancestor.parent
            canonical_ancestor = ancestor.resolve()
            if not ancestor.samefile(canonical_ancestor) or (
                canonical_ancestor / lexical.relative_to(ancestor) != resolved
            ):
                raise QueryInputError(f"Path must remain within its boundary without redirection ({root}): {path}")
        return resolved
    except QueryInputError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise QueryInputError(f"Cannot resolve path within boundary ({boundary}): {path}") from exc

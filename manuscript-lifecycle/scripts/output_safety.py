"""Preflight report destinations without touching the filesystem.

Reports and execution receipts use fresh paths. Canonical path comparison and
samefile cover ordinary aliases, symlinks and hard links. This is not a sandbox
for the subprocess chosen by the caller.
"""
from pathlib import Path


def same_file(left, right):
    left, right = Path(left).resolve(), Path(right).resolve()
    if left == right:
        return True
    try:
        return left.exists() and right.exists() and left.samefile(right)
    except OSError:
        return False


def declared_paths(data, base):
    """Collect explicit path fields and receipt input/output mapping keys only."""
    found = []
    if isinstance(data, dict):
        value = data.get('path')
        if isinstance(value, str) and value.strip():
            found.append((base / value).resolve())
        for key in ('inputs', 'outputs'):
            mapping = data.get(key)
            if isinstance(mapping, dict):
                found.extend((base / name).resolve() for name in mapping if isinstance(name, str) and name.strip())
        for value in data.values():
            found.extend(declared_paths(value, base))
    elif isinstance(data, list):
        for value in data:
            found.extend(declared_paths(value, base))
    return found


def output_path(destination, protected=()):
    """Require a fresh output, distinct from all declared protected inputs."""
    path = Path(destination).resolve()
    for item in protected:
        source = Path(item).resolve()
        if same_file(path, source) or (source.is_dir() and path.is_relative_to(source)):
            raise ValueError('Output must not overwrite or be inside protected input: ' + str(source))
    if path.exists() or path.is_symlink():
        raise ValueError('Output already exists; use a fresh report path: ' + str(path))
    return path


def write_fresh(path, text):
    """Exclusive creation also refuses a destination created after preflight."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(text)

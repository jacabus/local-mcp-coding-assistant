"""Local filesystem helpers: no network, no TLS, no HTTP."""

from pathlib import Path


def list_py_files(root: str) -> list[str]:
    base = Path(root)
    return sorted(str(path) for path in base.rglob("*.py") if path.is_file())


def read_first_line(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").splitlines()[0]

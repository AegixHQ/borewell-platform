"""Tiny .env reader shared by the go-live tools (stdlib only).

Same rules docker compose uses for the simple cases we have: KEY=value per
line, '#' starts a comment line, surrounding quotes are stripped. Anything
fancier (multi-line values, ${} expansion inside the file) is not supported
and not needed.
"""
from pathlib import Path


def parse(text: str) -> dict:
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load(path) -> dict:
    return parse(Path(path).read_text())

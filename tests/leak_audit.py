"""Auditoría de fuga de secretos sobre el árbol del repo.

Grep de patrones peligrosos: claves privadas EVM, HMAC tokens, DSNs de
PostgreSQL/MongoDB, IPs internas de Linode/Azure, credenciales en texto.
Exit 1 si encuentra algo.

    python tests/leak_audit.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("clave privada EVM (0x64hex)", re.compile(r"0x[0-9a-fA-F]{64}")),
    ("clave privada EVM sin prefijo", re.compile(r"(?<![\w./])privkey|private_key\s*=\s*['\"](?!env)", re.I)),
    ("mnemonic/seed", re.compile(r"\b(abandon ability|mnemonic|seed phrase)\b", re.I)),
    ("HMAC/Dharma signature", re.compile(r"X-Dharma-Signature|hmac(_key)?\s*=", re.I)),
    ("DSN PostgreSQL", re.compile(r"postgres(ql)?://[^\s'\"]*:[^\s'\"]*@")),
    ("DSN MongoDB", re.compile(r"mongodb(\+srv)?://[^\s'\"]*:[^\s'\"]*@")),
    ("DSN MySQL", re.compile(r"mysql://[^\s'\"]*:[^\s'\"]*@")),
    ("API key genérica", re.compile(r"\b(api[_-]?key|secret[_-]?key)\b\s*[:=]\s*['\"][A-Za-z0-9]{16,}['\"]", re.I)),
    ("IP interna Linode/Azure documentada", re.compile(r"\b(10\.100\.\d+\.\d+|172\.16\.\d+\.\d+)\b")),
    ("credenciales clouding/edge", re.compile(r"187\.33\.159\.243")),
]

ALLOWED_MARKERS = {
    # textos didácticos que mencionan la variable sin contener el secreto
    "RADHIKA_PRIVATE_KEY",
    "private_key_env",
    "os.environ[",
    'os.getenv("RADHIKA_PRIVATE_KEY")',
    "RADHIKA_GATEWAY_URL",
}

SKIP_SUFFIXES = {".pyc", ".egg-info"}


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    hits: list[tuple[int, str, str, str]] = []
    text = path.read_text(errors="replace")
    for name, pat in PATTERNS:
        for m in pat.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            snippet = text.splitlines()[line_no - 1].strip()[:120]
            if any(marker in snippet for marker in ALLOWED_MARKERS):
                continue
            hits.append((line_no, name, snippet, str(path)))
    return hits


def main() -> None:
    all_hits: list[tuple[int, str, str, str]] = []
    files = [
        p
        for p in ROOT.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and not any(p.suffix == s for s in SKIP_SUFFIXES)
        and "venv" not in p.parts
        and "build" not in p.parts
        and "dist" not in p.parts
        and p.name not in {"E2E_VERIFICATION_REPORT.md", "leak_audit.py"}
    ]
    for p in sorted(files):
        all_hits.extend(scan_file(p))

    if all_hits:
        print("[FAIL] leak audit — patrones encontrados:")
        for line_no, name, snippet, path in all_hits:
            print(f"  {path}:{line_no} [{name}] {snippet}")
        sys.exit(1)
    print(f"[PASS] leak audit — 0 patrones de secretos en {len(files)} archivos del repo")


if __name__ == "__main__":
    main()

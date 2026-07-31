#!/usr/bin/env python3
"""Validate a generated static-website WebDAV/isql deployment bundle.

Offline, marker/substring-based -- mirrors weblog-from-webdav's
validate_generated_weblog_bundle.py style exactly, adapted for a
pre-rendered static site instead of a live-rendering VSP weblog.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_one(bundle: Path, pattern: str) -> Path | None:
    matches = sorted(bundle.glob(pattern))
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path, help="Directory containing generated/, assets/, and deploy-website-route.sql")
    args = parser.parse_args()

    bundle = args.bundle
    missing: list[str] = []
    if not bundle.is_dir():
        print(f"not a directory: {bundle}", file=sys.stderr)
        return 2

    generated_dir = bundle / "generated"
    assets_dir = bundle / "assets"
    route_sql = find_one(bundle, "deploy-website-route*.sql") or find_one(bundle, "*route*.sql")
    readme = find_one(bundle, "README*")

    generated_pages = sorted(generated_dir.rglob("*.html")) if generated_dir.is_dir() else []
    non_empty_pages = [p for p in generated_pages if p.stat().st_size > 0]

    route_text = read(route_sql) if route_sql else ""
    # Strip `--` SQL comment lines before content checks, so explanatory
    # comments (e.g. warning against a wrong value) can't trip a check
    # meant to catch that value actually being *assigned*.
    route_code_only = "\n".join(
        line for line in route_text.splitlines() if not line.strip().startswith("--")
    )

    checks = [
        ("generated/ directory exists", generated_dir.is_dir()),
        ("at least one generated *.html page", len(generated_pages) > 0),
        ("every generated page is non-empty", generated_pages != [] and len(non_empty_pages) == len(generated_pages)),
        ("assets/ directory exists", assets_dir.is_dir()),
        ("assets/site.css present", (assets_dir / "site.css").exists()),
        ("assets/theme.js present", (assets_dir / "theme.js").exists()),
        ("deploy-website-route.sql found", route_sql is not None),
        ("route SQL removes prior conflicting VHOST_DEFINE", "VHOST_REMOVE" in route_text),
        ("route SQL defines VHOST_DEFINE", "VHOST_DEFINE" in route_text),
        ("route SQL serves static files (is_dav=>1)", re.search(r"is_dav\s*=>\s*1", route_text) is not None),
        ("route SQL uses index.html, not a VSP entry point", "def_page" in route_text and "'index.html'" in route_text),
        ("route SQL does not assign def_page to a .vsp file", re.search(r"def_page\s*=>\s*'[^']*\.vsp'", route_code_only) is None),
        ("verification query against HTTP_PATH", "DB.DBA.HTTP_PATH" in route_text),
        ("verification query against SYS_DAV_RES", "WS.WS.SYS_DAV_RES" in route_text),
        ("no isql macro-like replacement tokens", re.search(r"\$[0-9]", route_text) is None),
        ("run notes / README present", readme is not None),
    ]

    for label, ok in checks:
        if not ok:
            missing.append(label)

    if missing:
        for item in missing:
            print(f"FAIL: {item}", file=sys.stderr)
        return 1

    print(f"generated website bundle OK ({len(generated_pages)} page(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

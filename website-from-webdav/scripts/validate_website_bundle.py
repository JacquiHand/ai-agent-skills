#!/usr/bin/env python3
"""Sanity-check a website-from-webdav skill bundle itself (dev-only).

Checks that fixed skill-package files still contain their signature
markers -- catches drift in the skill's own SKILL.md/references/templates,
not a user's generated site. Mirrors weblog-from-webdav's
validate_weblog_bundle.py CHECKS-dict pattern exactly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


CHECKS = {
    "SKILL.md": [
        "A Local File Is Not a Valid Completion",
        "validate_generated_website_bundle.py",
        "publish_static_bundle.py",
        "is_dav=>1",
    ],
    "references/webdav-website-engine-gate.md": [
        "Nothing here re-derives HTML from RDF at request time",
        "No VSP execution",
        "validate_generated_website_bundle.py",
    ],
    "references/rdf-content-mode.md": [
        ":ClaimShape",
        "validate_shacl.py",
        "build.py",
    ],
    "references/isql-route-mode.md": [
        "VHOST_DEFINE",
        "is_dav=>1",
        "def_page=>'index.html'",
    ],
    "references/webdav-publish-mode.md": [
        "publish_static_bundle.py",
        "verify-after-write",
    ],
    "references/opal-tool-mode.md": [
        "Not Implemented",
        "WEBLOG_DAV_SET_PIN",
    ],
    "templates/deploy-website-route.sql": [
        "VHOST_REMOVE",
        "VHOST_DEFINE",
        "is_dav      => 1",
        "def_page    => 'index.html'",
        "WS.WS.SYS_DAV_RES",
    ],
    "scripts/validate_generated_website_bundle.py": [
        "VHOST_DEFINE",
        "assets/site.css",
        "assets/theme.js",
    ],
    "scripts/publish_static_bundle.py": [
        "CONTENT_TYPES",
        "verify_file",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    missing: list[str] = []
    for rel, needles in CHECKS.items():
        path = args.skill_dir / rel
        if not path.exists():
            missing.append(f"missing file: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            if needle not in text:
                missing.append(f"{rel}: missing marker {needle!r}")
    if missing:
        for item in missing:
            print(item, file=sys.stderr)
        return 1
    print("website-from-webdav bundle markers OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

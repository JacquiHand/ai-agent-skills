#!/usr/bin/env python3
"""Publish a generated static website bundle to a WebDAV collection.

Uploads generated/*.html and every file under assets/ (recursively,
preserving relative paths) via curl PUT, then verifies each upload with a
follow-up GET compared byte-for-byte against the local file. Same auth-flag
surface as weblog-from-webdav's publish_with_metadata.py, minus the
schema:category inference/PROPPATCH step -- this skill never guesses or
sets content metadata, it only publishes files. See
references/webdav-publish-mode.md for the mode boundary.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, urljoin

CONTENT_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
}


def content_type_for(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def build_url(base_url: str, relative: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", quote(relative))


def curl_base(args: argparse.Namespace) -> list[str]:
    cmd = ["curl", "--fail", "--silent", "--show-error", "--location", "--anyauth"]
    if args.insecure:
        cmd.append("--insecure")
    if args.curl_config:
        cmd.extend(["--config", args.curl_config])
    if args.user:
        password = os.environ.get(args.password_env) if args.password_env else None
        if args.password_env and password is None:
            raise RuntimeError(f"Missing password environment variable: {args.password_env}")
        cmd.extend(["--user", f"{args.user}:{password or ''}"])
    if args.cert_type:
        cmd.extend(["--cert-type", args.cert_type])
    if args.cert:
        cmd.extend(["--cert", args.cert])
    if args.cacert:
        cmd.extend(["--cacert", args.cacert])
    if args.on_behalf_of:
        cmd.extend(["-H", f"On-Behalf-Of: {args.on_behalf_of}"])
    return cmd


def run_curl(cmd: list[str], dry_run: bool, capture_output: bool = False) -> str:
    if dry_run:
        print(f"DRY-RUN\t{' '.join(cmd)}")
        return ""
    completed = subprocess.run(cmd, check=True, text=True, capture_output=capture_output)
    return completed.stdout if capture_output else ""


def put_file(args: argparse.Namespace, path: Path, url: str) -> None:
    cmd = curl_base(args) + [
        "-T", str(path),
        "-H", f"Content-Type: {content_type_for(path)}",
        url,
    ]
    run_curl(cmd, args.dry_run)


def verify_file(args: argparse.Namespace, path: Path, url: str) -> bool:
    if args.dry_run:
        return True
    cmd = curl_base(args) + [url]
    fetched = run_curl(cmd, dry_run=False, capture_output=True)
    local = path.read_text(encoding="utf-8", errors="replace")
    return fetched == local


def collect_files(bundle: Path) -> list[tuple[Path, str]]:
    """Return (local_path, remote_relative_path) pairs for generated/**/*.html and assets/**."""
    pairs: list[tuple[Path, str]] = []

    generated_dir = bundle / "generated"
    for html_file in sorted(generated_dir.rglob("*.html")):
        rel = str(html_file.relative_to(generated_dir)).replace(os.sep, "/")
        pairs.append((html_file, rel))

    assets_dir = bundle / "assets"
    if assets_dir.is_dir():
        for asset_file in sorted(assets_dir.rglob("*")):
            if asset_file.is_file():
                rel = "assets/" + str(asset_file.relative_to(assets_dir)).replace(os.sep, "/")
                pairs.append((asset_file, rel))

    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a generated static website bundle via WebDAV PUT.")
    parser.add_argument("bundle", type=Path, help="Directory containing generated/ and assets/")
    parser.add_argument("--base-url", required=True, help="Target WebDAV collection URL, e.g. https://host/DAV/home/user/sites/openlink/")
    parser.add_argument("--user")
    parser.add_argument("--password-env")
    parser.add_argument("--curl-config")
    parser.add_argument("--cert-type")
    parser.add_argument("--cert")
    parser.add_argument("--cacert")
    parser.add_argument("--on-behalf-of")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.bundle.is_dir():
        print(f"not a directory: {args.bundle}", file=sys.stderr)
        return 2

    files = collect_files(args.bundle)
    if not files:
        print(f"no generated/*.html or assets/ files found under {args.bundle}", file=sys.stderr)
        return 2

    failures = 0
    try:
        for local_path, relative in files:
            url = build_url(args.base_url, relative)
            print(f"publish\t{local_path}\t->\t{url}")
            put_file(args, local_path, url)
            if local_path.suffix.lower() in (".html", ".css", ".js"):
                if verify_file(args, local_path, url):
                    print(f"verified\t{relative}")
                else:
                    print(f"verify-failed\t{relative}", file=sys.stderr)
                    failures += 1
            else:
                print(f"uploaded\t{relative}\t(binary, not byte-verified)")
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error\t{exc}", file=sys.stderr)
        return 1

    if failures:
        print(f"{failures} file(s) failed verification", file=sys.stderr)
        return 1

    print(f"published {len(files)} file(s) to {args.base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# WebDAV Publish Mode

Scope: publishing already-generated files only. WebDAV mode never bootstraps a route, never runs the RDF/SHACL/Jinja2 pipeline, and never edits content.

## Out of scope for WebDAV mode

The following are `isql-route-mode.md`'s or `rdf-content-mode.md`'s job, never this mode's:

- Creating or modifying the `VHOST_DEFINE` route.
- Running `rdf/validate_shacl.py` or `rdf/build.py`.
- Editing any `.ttl` file or Jinja2 template.
- Deciding what content should say.

If any of the above seems necessary mid-publish, stop and hand off to the right mode rather than improvising a workaround here.

## Publication pattern

1. Confirm the target route already exists (per `isql-route-mode.md`'s engine check) before publishing — publishing into a DAV collection with no route mapped leaves the content unreachable, and the skill would silently under-deliver if this step is skipped.
2. Use `scripts/publish_static_bundle.py` to PUT `generated/*.html` and every file under `assets/` (recursively) into the target DAV collection.
3. Each PUT is followed by a GET (or PROPFIND for existence) to verify the uploaded bytes match the local file — this verify-after-write step is not optional, it's how "published" gets distinguished from "attempted."
4. Report the DAV path each file landed at, and the verification result per file.

## `curl` auth flag surface

Same surface as `weblog-from-webdav`'s `publish_with_metadata.py`, for consistency across skills:

- `--user <username>:<password>` or `--password-env <VAR>` for plain credential auth.
- `--cert-type P12 --cert "$P12_FILE:$P12_PASSWORD" --cacert "$CA_BUNDLE"` for mTLS.
- `-H "On-Behalf-Of: {principal-webid}"` for delegated identity — a separate fact from the mTLS calling-agent certificate, never conflate the two.
- `--dry-run` prints the intended PUT/verify calls without executing them; always run this first when publishing to an unfamiliar target.
- `--anyauth` for negotiated auth where the server's scheme isn't known in advance.

## Hard rule

A successful GET or PROPFIND does not prove PUT/write rights. If a PUT fails with repeated 401/403, stop and report an authorization failure — do not retry with different paths hoping one works, and do not fall back to a different, unauthenticated-seeming endpoint.

## Content-Type

Publish `.html` files as `text/html`, `.css` as `text/css`, `.js` as `text/javascript` (or `application/javascript`) — an incorrect `Content-Type` on `site.css`/`theme.js` is a common cause of a page loading with no styling even though the route and files are otherwise correct.

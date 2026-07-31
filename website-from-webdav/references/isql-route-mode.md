# isql Route Mode

Use `isql` for bootstrapping or verifying the WebDAV/VHOST route only — never for editing site content, and never for anything `webdav-publish-mode.md` already covers.

## Engine (route) check pattern

Before assuming a route needs to be created, check whether it already exists:

```sql
SELECT HP_LPATH, HP_PPATH, HP_HOST FROM DB.DBA.HTTP_PATH WHERE HP_PPATH LIKE '/DAV/home/kidehen/sites/openlink/%';
SELECT RES_FULL_PATH FROM WS.WS.SYS_DAV_RES WHERE RES_FULL_PATH LIKE '/DAV/home/kidehen/sites/openlink/%';
```

If a row for the target `HP_LPATH` already exists and points at the correct `HP_PPATH`, the route is already bootstrapped — skip to `webdav-publish-mode.md` for a content-only republish.

## Bootstrap pattern

1. Copy `templates/deploy-website-route.sql`.
2. Literal find/replace (no `{{token}}` templating engine, same convention as `weblog-from-webdav`'s deploy templates) the placeholder DAV collection path, public route path, virtual host, and site title.
3. Run with `isql`.
4. Verify with the two `SELECT`s above, and confirm `HP_LPATH` resolves to the intended public route.

## `isql` invocation syntax

Plain credentials:

```bash
isql <host>:<port> <username> <password> deploy-website-route.sql
```

TLS + WebID (same flag semantics as `weblog-from-webdav/references/isql-mode.md`):

```bash
isql linkeddata.uriburner.com:1113 "" "$P12_PASSWORD" \
  -X my_software_agent_id.p12 \
  -T ca_list_shop_2016.pem \
  -W 'http://kingsley.idehen.net/public_home/kidehen/profile.ttl#i' \
  deploy-website-route.sql
```

- `-X` / `--cert`: the PKCS#12 bundle identifying the *calling agent*.
- `-T` / `--cacert`: the CA bundle for the TLS handshake.
- `-W`: the delegated WebID *principal* whose ACL rights should be evaluated — a separate fact from the calling agent's identity, never conflate the two.
- Empty `""` username signals certificate/WebID authentication rather than a SQL login.

## What `deploy-website-route.sql` must contain

- Removal of any prior conflicting `VHOST_DEFINE` for the same host/path (never leave two competing definitions).
- `DB.DBA.VHOST_DEFINE(lhost=>..., vhost=>..., lpath=>'<public route>', ppath=>'<DAV collection>', is_dav=>1, is_brws=>0, def_page=>'index.html', vsp_user=>'dba', ses_vars=>0, opts=>vector('browse_sheet','','noinherit','yes'), is_default_host=>0)` — note `is_dav=>1` with `def_page=>'index.html'`, not `index.vsp`; this route serves static files, it does not execute anything.
- Verification `SELECT`s against `DB.DBA.HTTP_PATH` and `WS.WS.SYS_DAV_RES`, run at the end of the script so the isql session output itself is evidence the route exists.

## Common failure signatures

| Symptom | Likely cause |
|---|---|
| 404 at the public route after deploy | `ppath` doesn't match the actual DAV collection the files were published into, or the files weren't published yet |
| Raw HTML source served instead of rendered page | Browser MIME-sniffing issue or `Content-Type` not set correctly on the published files — check `publish_static_bundle.py`'s upload headers |
| Old content still served after republish | Stale browser cache — hard-refresh before concluding the publish failed; static-file DAV serving has no server-side render cache to flush (unlike `osdi-inclusion-engine`'s compiled-XSLT cache) |
| Two different pages serve for the same route | Leftover conflicting `VHOST_DEFINE` from a prior deploy — remove-then-redefine was skipped |

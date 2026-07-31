# OPAL Tool Mode — Not Implemented (v1)

`weblog-from-webdav` and `osdi-inclusion-engine` both expose server-side operations as OPAL/MCP-callable stored procedures (post pinning, chrome-override config) via `OAI.DBA.REGISTER_CHAT_FUNCTION`. This skill does not do that yet, and the omission is deliberate, not an oversight.

## Why not yet

Those tools operate on state that already lives *inside* Virtuoso — a DAV-resident weblog collection, an inclusion-engine config graph. This skill's content lives in local `.ttl` files on the machine running the pipeline, not in a graph loaded into Virtuoso. There's nothing meaningful to register as a live, agent-callable operation yet: "reorder the product stack" or "publish a page" are pipeline-authoring and WebDAV-publish actions respectively, not database operations.

## The extension point, if this changes

If the RDF graph is ever also loaded live into Virtuoso (not just used locally by `rdflib` at build time — see `rdf-content-mode.md`), the natural tools to register at that point would be:

- A stack-reorder tool taking a page slug and a new `schema:position`, mirroring `weblog-from-webdav`'s `WEBLOG_DAV_SET_PIN` pattern (clear/reset conflicting positions, verify the resulting order, return a JSON result).
- A republish-trigger tool that re-runs `build.py` + `publish_static_bundle.py` server-side, so an agent could request "publish page X" without a human running the pipeline manually.

Building either now would be speculative — there's no live graph for them to operate on, and registering a stub tool that doesn't do anything useful yet is worse than not registering one. Revisit this file specifically once/if the rendering-model decision in `webdav-website-engine-gate.md` changes.

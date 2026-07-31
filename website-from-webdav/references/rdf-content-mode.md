# RDF Content Mode — Pipeline Boundary

This skill never authors, edits, or hand-fixes RDF/Turtle content, and never bypasses SHACL validation. If content is wrong, the fix belongs in `rdf/data/*.ttl` or `rdf/shapes.ttl`, upstream of this skill, not in a generated HTML file or in this skill's own scripts.

## What "the pipeline" means here

A source directory such as `sites/openlink/rdf/` containing:

- `ontology.ttl` — the site's vocabulary (custom terms kept minimal; schema.org/DCAT/PROV-O reused wherever an adequate term exists).
- `shapes.ttl` — SHACL constraints. Notably a `:ClaimShape` requiring every `schema:Claim` to carry either `schema:citation` or an explicit `:isPlaceholder true` flag — this is the mechanism that catches fabricated or unsourced claims before they can ever reach a page.
- `data/*.ttl` — one file per page (or shared site-wide data), conforming to the shapes.
- `validate_shacl.py` — `rdflib` parses the data, `pyshacl.validate()` checks it against the shapes, exit 0/1.
- `build.py` — validates, runs SPARQL/rdflib queries against the graph, renders through `templates/*.j2` (Jinja2), writes static HTML to `generated/`.

## What this skill does

1. Runs `python3 rdf/validate_shacl.py` and `python3 rdf/build.py`, unchanged, exactly as documented in the pipeline's own plan document.
2. Treats a non-zero exit from either as a hard stop — not something to retry with different flags or work around.
3. Reads `generated/*.html` and the site's `assets/` as the publish payload. Nothing else.

## What this skill does not do

- Does not edit any `.ttl` file to make validation pass.
- Does not add new ontology terms, shapes, or template partials — that's a pipeline-authoring change, a different task with its own plan.
- Does not run SPARQL queries against a *live* Virtuoso graph to render pages — the pipeline's queries run locally, offline, against files on disk via `rdflib`, before this skill ever starts.
- Does not decide page content, ordering, or copy. If the generated output looks wrong, that's a signal to go fix the source `.ttl`/templates and rerun the pipeline, not to patch the generated HTML by hand (patching generated output defeats the entire point of generating it).

## Adding a new page

Out of scope for this skill to perform, but useful context for judging whether a publish request is premature: a new page means a new `rdf/data/<slug>.ttl` conforming to `:ProductPageShape`, added to the `PAGES` list in `build.py`. If asked to publish a page that doesn't yet exist in `generated/`, say so and point at this as the missing step — don't invent a page to satisfy the request.

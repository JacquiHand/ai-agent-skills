# RDF Infographic Template Options

Use templates as visual and interaction references, not as hard dependencies. The strict harness contract defines required behavior; templates are selectable shells that must be adapted to pass validation.

## Selection Rule

- If the user names or supplies a template, use that as the visual reference and retrofit the contract features into it.
- If the user asks for the "usual" collection and gives no preference, infer the best template from the source content, audience, and nearby prior artifacts.
- If an existing artifact is being repaired, preserve its visual language unless the user asks for a redesign.
- If a helper script is convenient, use it; if the template calls for a different implementation, implement directly and run the validator.

## Available References

### Harness Reference

Asset: `scripts/rdf_infographic_harness.py`

Best for:

- New article collections where consistency matters more than a bespoke layout.
- Cases where previous KG Explorer regressions are the main risk.
- Fast generation using known IDs and validation-friendly controls.

Characteristics:

- Floating compact navigation.
- Single KG Explorer SVG with controls tray closed by default.
- Advanced-only settings panel.
- Footer SPARQL workbench with named graph and query recipe selectors.
- Full attribution card set.

### Competitive / Head-to-Head Analysis

Asset: `assets/templates/competitive-analysis-head-to-head-claude_sonnet_4_6.html`

Best for:

- Sources that compare **two or more** named platforms, products, systems, harnesses, or vendors.
- Feature matrices, capability scoreboards, and tabulated peer comparisons (including Grok/X share tables).

Characteristics worth preserving:

- Premium dark aesthetic, hero dual-badges, horizontal timeline.
- **Responsive dual comparison presentation (skill contract item 15):**
  - `.comparison-table-view` — semantic multi-column matrix for viewports **≥901px**
  - `.comparison-cards-view` — one product card per entity for viewports **≤900px**
  - Identical facts in both views; CSS-only switch at 900px; no JS required for the switch
  - Resolver-linked entity names in table headers **and** card headers
  - **Each aspect/dimension described in companion TTL** and **resolver-linked in the first column** of every comparison table row (and matching card row labels)
  - Overflow-safe cells (`min-width:0`, `overflow-wrap:anywhere`)
- Two-column capability panels that collapse to one column on narrow screens.
- Glossary/FAQ/HowTo patterns consistent with the harness contract.

Required adaptations before reuse:

- Substitute compared entities and matrix cells from the companion RDF (do not invent competitors).
- Keep dual markup when the matrix has ≥2 entity columns — do **not** ship a phone-only horizontal-scroll table.
- Retrofit full harness features (nav collapsed default, theme toggle, KG Explorer, SPARQL workbench, attribution cards) if the shell is used as a visual reference rather than a complete page.
- Verify both viewports before delivery (table visible at desktop; cards visible at ~390px).

### Claude Sonnet 4 Gartner Dashboard

Asset: `assets/templates/gartner-da-london-2026-claude-sonnet4-dashboard.html`

Best for:

- Dense conference reports, field notes, strategy analysis, or operational dashboards.
- Documents with many sections, metrics, tables, chips, archetypes, and quick SPARQL recipes.
- User preference for a compact top navigation bar and work-focused dashboard feel.

Characteristics worth preserving:

- Fixed top horizontal navigation with compact menu expansion.
- Dense metric/stat pills and dashboard cards.
- Top-level theme button.
- Two-pane Basic/Advanced KG Explorer pattern.
- Advanced settings drawer rather than large card controls.
- Footer quick-explore SPARQL links.

Required adaptations before reuse:

- Keep navigation collapsed by default and include the required page-level theme control.
- Ensure KG controls are closed by default. If using a two-pane Basic/Advanced layout, Advanced settings must still be hidden until Advanced mode and Settings are explicitly selected.
- Build KG data from companion RDF, not hand-authored subsets unless the RDF itself is the source of those subsets.
- Make SVG node labels and edge labels resolver-backed anchors using RDF IRIs.
- Use sticky node drag with double-click unpin.
- Replace `format=text/html` SPARQL links with query-type-specific formats: `text/x-html+tr` for SELECT and `text/x-html-nice-turtle` for DESCRIBE/CONSTRUCT.
- Add or preserve full attribution: source material, companion files, skills, generation environment, Linked Data runtime, named graph IRIs, resolver pattern, and extraction provenance.
- Ensure every non-fragment HTML link opens in a new tab with `target="_blank" rel="noopener noreferrer"`.

### Semantic Medallion Editorial Technical Template

Asset: `assets/templates/semantic-medallion-editorial-technical.html`

Best for:

- Technical explainers, architecture patterns, ontology/SPARQL tutorials, and documentation-style artifacts.
- Articles where the main story is a layered architecture, implementation path, vocabulary mapping, or executable query examples.
- Outputs that need a polished editorial feel with dense technical sections rather than a dashboard/briefing feel.

Characteristics worth preserving:

- Compact movable/resizable navigation panel that starts as a small header control.
- Separate page-level theme button.
- Narrow reading column with technical cards, architecture layers, capability cards, FAQ, glossary, and downloads.
- Strong medallion/layer visual language suitable for Bronze/Silver/Gold/Platinum or other staged architectures.
- SPARQL query accordions with syntax-styled query blocks and live-run buttons.
- Single-canvas D3 KG Explorer with legend and toolbar.
- Footer with source, companion artifact, skill, resolver, and server/platform references.

Required adaptations before reuse:

- Keep or retrofit POSH links for the companion HTML/MD/RDF set, including Markdown parity when a Markdown output is requested.
- Ensure every external link has `target="_blank" rel="noopener noreferrer"`; this template has some same-folder artifact links and source links that may need updating.
- Replace static or hand-authored KG nodes/links with graph data derived from the companion RDF, unless the static subset is programmatically derived from that RDF.
- Make KG node labels and edge labels resolver-backed anchors using RDF IRIs, not just click handlers or plain text.
- Keep controls closed by default; if the toolbar is visible, wrap it in a compact Controls tray or otherwise preserve the first visible KG state required by the contract.
- Scope settings to Advanced mode if settings are present.
- Add predicate Select All/Deselect All when predicate filtering is available.
- Preserve sticky drag and double-click unpin.
- Replace `format=text/html` SPARQL links with query-type-specific formats: `text/x-html+tr` for SELECT and `text/x-html-nice-turtle` for DESCRIBE/CONSTRUCT.
- If the footer uses a single quick SPARQL link, upgrade it to either the full workbench or an equivalent set of quick links plus editable/query recipe capability, depending on user preference.
- Include named graph IRIs and extraction/generation provenance in the attribution block.

## Validation

Run:

```bash
python3 scripts/validate-harness-contract.py path/to/page.html --ttl path/to/page.ttl --jsonld path/to/page.jsonld
```

The validator is a contract gate, not a template selector. A page may use any visual template if it passes the contract checks.

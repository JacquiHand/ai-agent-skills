/**
 * HTML Assembler — TypeScript edition (Node.js ≥ 18, requires n3).
 * Assembles RDF data into a self-contained HTML infographic.
 * Mirrors html_assembler.py — same signature, same output.
 *
 * Install: npm install (from rdf-infographic-skill/scripts/)
 * Import:  import { assembleHtml } from "./html_assembler.ts";
 */

import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  buildKgdata,
  extractNarrative,
  getBaseIri,
  validateOrphans,
} from "./rdf_parser.ts";

const __dirname_compat = dirname(
  typeof __filename !== "undefined"
    ? __filename
    : fileURLToPath(import.meta.url),
);
const TEMPLATES_DIR = join(__dirname_compat, "templates");
const VALIDATOR    = join(__dirname_compat, "validate-harness-contract.ts");

// ── Mini Jinja2-compatible template engine ────────────────────────────────────

function escHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function resolvePath(ctx: Record<string, unknown>, path: string): unknown {
  const parts = path.split(".");
  let val: unknown = ctx;
  for (const p of parts) {
    if (val == null || typeof val !== "object") return "";
    val = (val as Record<string, unknown>)[p];
  }
  return val ?? "";
}

function renderTemplate(tpl: string, ctx: Record<string, unknown>): string {
  // 1. {% for item in list %}...{% endfor %}
  tpl = tpl.replace(
    /\{%-?\s*for\s+(\w+)\s+in\s+(\w+)\s*-?%\}([\s\S]*?)\{%-?\s*endfor\s*-?%\}/g,
    (_, item, listName, body) => {
      const list = resolvePath(ctx, listName);
      if (!Array.isArray(list)) return "";
      return list
        .map((el: unknown) => renderTemplate(body, { ...ctx, [item]: el }))
        .join("");
    },
  );

  // 2. {% if var %}...{% endif %} (truthy check; no else branch needed)
  tpl = tpl.replace(
    /\{%-?\s*if\s+([\w.]+)\s*-?%\}([\s\S]*?)\{%-?\s*endif\s*-?%\}/g,
    (_, cond, body) =>
      resolvePath(ctx, cond) ? renderTemplate(body, ctx) : "",
  );

  // 3. {{ a or b }} — Jinja2-style fallback expression
  tpl = tpl.replace(
    /\{\{\s*([\w.]+)\s+or\s+([\w.]+)\s*\}\}/g,
    (_, a, b) => String(resolvePath(ctx, a) || resolvePath(ctx, b) || ""),
  );

  // 4. {{ var|e }} — HTML-escaped output
  tpl = tpl.replace(
    /\{\{\s*([\w.]+)\|e\s*\}\}/g,
    (_, path) => escHtml(String(resolvePath(ctx, path))),
  );

  // 5. {{ var }} and {{ obj.prop }} — raw output
  tpl = tpl.replace(
    /\{\{\s*([\w.]+)\s*\}\}/g,
    (_, path) => String(resolvePath(ctx, path)),
  );

  return tpl;
}

// ── Template asset loader ─────────────────────────────────────────────────────

function loadAsset(name: string): string {
  const assetPath = join(TEMPLATES_DIR, name);
  if (!existsSync(assetPath)) throw new Error(`Missing template asset: ${assetPath}`);
  return readFileSync(assetPath, "utf-8");
}

// ── Narrative builder ─────────────────────────────────────────────────────────

interface NavLink { href: string; label: string; }
interface SparqlRecipe { label: string; query: string; }

function makeSectionHtml(id: string, title: string, inner: string): string {
  return (
    `<section class="section section-alt" id="${id}">` +
    `<h2>${title}<a class="headline-anchor" href="#${id}" aria-label="Link to this section">¶</a></h2>` +
    `${inner}` +
    `</section>`
  );
}

function resolverLink(iri: string, pattern: string): string {
  return pattern + encodeURIComponent(iri);
}

function renderNarrative(
  rdfPath: string,
  baseIri: string,
  resolverPattern: string,
): { html: string; navLinks: NavLink[]; sections: string[] } {
  const narrative = extractNarrative(rdfPath, baseIri);
  const navLinks: NavLink[] = [{ href: "#hero", label: "Overview" }];
  const htmlParts: string[] = [];
  const sections: string[] = [];

  if (narrative.synopsis) {
    const syn = narrative.synopsis;
    const abstract = escHtml(syn.abstract);
    const heading = syn.headline ? escHtml(syn.headline) : "Synopsis";
    const lo = syn.iri ? `<a href="${resolverLink(syn.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">` : "";
    const lc = syn.iri ? "</a>" : "";
    let inner = abstract ? `<p style="font-size:1.05rem;line-height:1.7">${abstract}</p>` : "";
    if (syn.iri) inner += `<p style="margin-top:1rem;font-size:0.85rem">${lo}View this analysis as a KG entity${lc}</p>`;
    htmlParts.push(makeSectionHtml("synopsis", "Synopsis", inner));
    navLinks.push({ href: "#synopsis", label: "Synopsis" });
    sections.push("synopsis");
  }

  narrative.sections.forEach((sec, idx) => {
    const secId = `analysis-${idx + 1}`;
    const secName = escHtml(sec.name);
    const secAbstract = escHtml(sec.abstract);
    let inner = secAbstract ? `<p style="font-size:0.98rem;line-height:1.7;color:var(--text-secondary)">${secAbstract}</p>` : "";
    if (sec.items.length) {
      inner += '<div class="cards-grid mt-2">';
      for (const item of sec.items) {
        inner +=
          `<div class="card">` +
          `<h3><a href="${resolverLink(item.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">${escHtml(item.name)}</a></h3>` +
          `<p>${escHtml(item.description)}</p></div>`;
      }
      inner += "</div>";
    }
    const lo = sec.iri ? `<a href="${resolverLink(sec.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">` : "";
    const lc = sec.iri ? "</a>" : "";
    const titleHtml = sec.iri ? `${lo}${secName}${lc}` : secName;
    htmlParts.push(
      `<section class="section section-alt" id="${secId}">` +
      `<h2>${titleHtml}<a class="headline-anchor" href="#${secId}" aria-label="Link to this section">¶</a></h2>` +
      `${inner}</section>`
    );
    navLinks.push({ href: `#${secId}`, label: sec.name.slice(0, 28) });
    sections.push(secId);
  });

  if (narrative.people.length) {
    let inner = "";
    for (const p of narrative.people) {
      const href = resolverLink(p.iri, resolverPattern);
      inner += `<div class="card"><h3><a href="${href}" target="_blank" rel="noopener noreferrer">${escHtml(p.name)}</a></h3><p>${escHtml(p.description)}</p></div>`;
    }
    htmlParts.push(makeSectionHtml("people", "People", `<div class="cards-grid">${inner}</div>`));
    navLinks.push({ href: "#people", label: "People" });
    sections.push("people");
  }

  if (narrative.organizations.length) {
    let inner = "";
    for (const o of narrative.organizations) {
      const href = resolverLink(o.iri, resolverPattern);
      inner += `<div class="card"><h3><a href="${href}" target="_blank" rel="noopener noreferrer">${escHtml(o.name)}</a></h3><p>${escHtml(o.description)}</p></div>`;
    }
    htmlParts.push(makeSectionHtml("organizations", "Organizations", `<div class="cards-grid">${inner}</div>`));
    navLinks.push({ href: "#organizations", label: "Organizations" });
    sections.push("organizations");
  }

  if (narrative.faq.length) {
    let inner = '<div class="faq-list">';
    for (const faq of narrative.faq) {
      const lo = faq.iri ? `<a href="${resolverLink(faq.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">` : "";
      const lc = faq.iri ? "</a>" : "";
      inner +=
        `<div class="faq-item anim-fade">` +
        `<div class="faq-question">${lo}${escHtml(faq.question)}${lc}<span class="faq-chevron">▼</span></div>` +
        `<div class="faq-answer"><p>${escHtml(faq.answer)}</p></div>` +
        `</div>`;
    }
    inner += "</div>";
    htmlParts.push(makeSectionHtml("faq", "Frequently Asked Questions", inner));
    navLinks.push({ href: "#faq", label: "FAQ" });
    sections.push("faq");
  }

  if (narrative.glossary.length) {
    let inner = '<div class="glossary-grid">';
    for (const g of narrative.glossary) {
      const lo = g.iri ? `<a href="${resolverLink(g.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">` : "";
      const lc = g.iri ? "</a>" : "";
      inner += `<div class="glossary-term"><h4>${lo}${escHtml(g.term)}${lc}</h4><p>${escHtml(g.definition)}</p></div>`;
    }
    inner += "</div>";
    htmlParts.push(makeSectionHtml("glossary", "Glossary of Terms", inner));
    navLinks.push({ href: "#glossary", label: "Glossary" });
    sections.push("glossary");
  }

  if (narrative.howto.length) {
    let inner = '<div class="howto-list">';
    narrative.howto.forEach((step, i) => {
      const lo = step.iri ? `<a href="${resolverLink(step.iri, resolverPattern)}" target="_blank" rel="noopener noreferrer">` : "";
      const lc = step.iri ? "</a>" : "";
      inner +=
        `<div class="howto-step anim-fade">` +
        `<div class="howto-num">${i + 1}</div>` +
        `<div class="howto-content"><h4>${lo}${escHtml(step.step)}${lc}</h4><p>${escHtml(step.description)}</p></div>` +
        `</div>`;
    });
    inner += "</div>";
    htmlParts.push(makeSectionHtml("howto", "How-To Guide", inner));
    navLinks.push({ href: "#howto", label: "HowTo" });
    sections.push("howto");
  }

  navLinks.push(
    { href: "#kg-explorer", label: "KG Explorer" },
    { href: "#sparql-explorer", label: "SPARQL" },
    { href: "#footer", label: "Footer" },
  );

  return { html: htmlParts.join("\n"), navLinks, sections };
}

const KIDEHEN_WEBID = "https://www.linkedin.com/in/kidehen#this";
const KG_GENERATOR_URL = "https://github.com/OpenLinkSoftware/ai-agent-skills/tree/main/kg-generator";
const RDF_INFOGRAPHIC_SKILL_URL = "https://github.com/OpenLinkSoftware/ai-agent-skills/tree/main/rdf-infographic-skill";

/**
 * Build the embedded JSON-LD block.
 *
 * The KG-curation delegation chain (schema:author / accountablePerson on the
 * document, prov:wasGeneratedBy + prov:actedOnBehalfOf on each generating
 * agent) is always included — never opt-in. Mirrors html_assembler.py's
 * renderJsonLd, which closed a recurring gap (5 documented occurrences in
 * agent-rdf-memory/howto/kg-curation-attribution.ttl) where the generator
 * shipped HTML with no delegation chain, or with prov:actedOnBehalfOf
 * pointing at the LLM/tool itself instead of the human principal.
 */
function renderJsonLd(
  title: string,
  description: string,
  baseIri: string,
  rdfRelPath: string,
  llmName = "Claude Sonnet 5",
  llmUrl = "https://www.anthropic.com/claude",
  principalWebid = KIDEHEN_WEBID,
): string {
  return JSON.stringify(
    {
      "@context": { "@vocab": "http://schema.org/", "@language": "en", prov: "http://www.w3.org/ns/prov#" },
      "@type": "Article",
      "@id": baseIri,
      headline: title,
      description,
      mainEntity: { "@type": "CreativeWork", "@id": baseIri },
      sameAs: rdfRelPath,
      author: { "@id": principalWebid },
      accountablePerson: { "@id": principalWebid },
      "prov:wasGeneratedBy": [
        {
          "@id": `${KG_GENERATOR_URL}#this`,
          "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
          name: "kg-generator",
          url: KG_GENERATOR_URL,
          "prov:actedOnBehalfOf": { "@id": principalWebid },
        },
        {
          "@id": `${RDF_INFOGRAPHIC_SKILL_URL}#this`,
          "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
          name: "rdf-infographic-skill",
          url: RDF_INFOGRAPHIC_SKILL_URL,
          "prov:actedOnBehalfOf": { "@id": principalWebid },
        },
        {
          "@id": `${llmUrl}#this`,
          "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
          name: llmName,
          url: llmUrl,
          "prov:actedOnBehalfOf": { "@id": principalWebid },
        },
      ],
    },
    null,
    2,
  );
}

/**
 * Build the visible hero-meta "KG curated by ... on behalf of ..." line.
 * Rendered by default (see assembleHtml's metaHtml handling), not left as an
 * opt-in caller-supplied string — mirrors html_assembler.py's renderHeroMeta.
 */
function renderHeroMeta(
  llmName = "Claude Sonnet 5",
  llmUrl = "https://www.anthropic.com/claude",
  principalName = "Kingsley Idehen",
  principalResolver = "https://linkeddata.uriburner.com/describe/?url=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fkidehen%23this",
): string {
  return (
    "KG curated by " +
    `<a href="${KG_GENERATOR_URL}" target="_blank" rel="noopener noreferrer">kg-generator</a>, ` +
    `<a href="${RDF_INFOGRAPHIC_SKILL_URL}" target="_blank" rel="noopener noreferrer">rdf-infographic-skill</a>, ` +
    `and <a href="${llmUrl}" target="_blank" rel="noopener noreferrer">${llmName}</a> ` +
    `on behalf of <a href="${principalResolver}" target="_blank" rel="noopener noreferrer">${principalName}</a>`
  );
}

const DAV_GRAPH_BASE = "https://linkeddata.uriburner.com/DAV/demos/daas/";

/**
 * The SPARQL GRAPH/FROM IRI for a generated artifact once uploaded to
 * URIBurner. NEVER the same as the document/base IRI (used for entity
 * resolver links) — see the skill's "Document IRI vs SPARQL GRAPH IRI" rule.
 */
function computeDavGraphIri(rdfFilename: string): string {
  return DAV_GRAPH_BASE + rdfFilename;
}

/** Canonical entity-type-summary query mandated by the Footer SPARQL Button
 * contract: SAMPLE-based projection, GROUP BY type, no default-graph-uri
 * URL parameter, no FILTER(STRSTARTS(...)) workaround. */
function buildCanonicalEntitySummaryQuery(davGraphIri: string): string {
  return (
    "SELECT ?type (SAMPLE(?s) AS ?sampleEntity) (SAMPLE(?label) AS ?sampleLabel) (COUNT(?s) AS ?entityCount)\n" +
    "WHERE {\n" +
    `  GRAPH <${davGraphIri}> {\n` +
    "    ?s a ?type .\n" +
    "    OPTIONAL { ?s rdfs:label|<http://schema.org/name> ?label }\n" +
    "  }\n" +
    "}\n" +
    "GROUP BY ?type\n" +
    "ORDER BY DESC(?entityCount)"
  );
}

/** href for the required <a id="sparqlBtn"> CTA. */
function buildSparqlBtnHref(davGraphIri: string): string {
  const query = buildCanonicalEntitySummaryQuery(davGraphIri);
  const encoded = encodeURIComponent(query);
  return (
    "https://linkeddata.uriburner.com/sparql?default-graph-uri=&query=" +
    `${encoded}&format=text%2Fx-html%2Btr&timeout=0&debug=on&run=+Run+Query+`
  );
}

function buildSparqlRecipes(baseIri: string, davGraphIri: string): SparqlRecipe[] {
  return [
    {
      label: "All triples (sample)",
      query: `SELECT ?s ?p ?o\nWHERE { GRAPH <${davGraphIri}> { ?s ?p ?o } }\nLIMIT 25`,
    },
    {
      label: "Entity types summary",
      query: buildCanonicalEntitySummaryQuery(davGraphIri),
    },
    {
      label: "Named graph triples",
      query: `SELECT ?s ?p ?o\nFROM <${davGraphIri}>\nWHERE { ?s ?p ?o }\nLIMIT 25`,
    },
  ];
}

// ── Public API ────────────────────────────────────────────────────────────────

export interface AssembleHtmlOptions {
  rdfPath: string;
  outputPath: string;
  title?: string;
  description?: string;
  sourceUrl?: string;
  sourceLabel?: string;
  resolverPattern?: string;
  tagline?: string;
  heroTagline?: string;
  metaHtml?: string;
  llmName?: string;
  llmUrl?: string;
}

export function assembleHtml(opts: AssembleHtmlOptions): boolean {
  const {
    rdfPath,
    outputPath,
    title: titleOpt = "",
    description: descOpt = "",
    sourceUrl = "",
    sourceLabel = "",
    resolverPattern = "https://linkeddata.uriburner.com/describe/?url=",
    tagline = "",
    heroTagline = "",
    llmName = "Claude Sonnet 5",
    llmUrl = "https://www.anthropic.com/claude",
  } = opts;

  // KG-curation attribution defaults on unless the caller explicitly overrides
  // metaHtml — see renderHeroMeta docstring for why this is not opt-in.
  const metaHtml = opts.metaHtml || renderHeroMeta(llmName, llmUrl);

  const stem   = basename(rdfPath).replace(/\.[^.]+$/, "");
  const title  = titleOpt  || `Knowledge Graph Infographic — ${stem}`;
  const description = descOpt || `Interactive infographic generated from ${basename(rdfPath)}`;

  const baseIri       = getBaseIri(rdfPath);
  const rdfRelPath    = relative(dirname(resolve(outputPath)), resolve(rdfPath));
  const rdfFilename   = basename(rdfPath);
  const outputFilename = basename(outputPath);

  console.log("Parsing RDF...");
  const kgdata  = buildKgdata(rdfPath);
  console.log(`  Nodes: ${kgdata.nodes.length}, Links: ${kgdata.links.length}`);

  const orphans = validateOrphans(kgdata);
  if (orphans.length) {
    console.log(`  Warning: ${orphans.length} orphan nodes — ${orphans.slice(0, 5).join(", ")}`);
  } else {
    console.log("  Zero orphan nodes");
  }

  console.log("Extracting narrative...");
  const { html: narrativeHtml, navLinks, sections } = renderNarrative(
    rdfPath, baseIri, resolverPattern,
  );
  console.log(`  Sections: ${sections.join(", ") || "(none)"}`);

  const jsonldContent  = renderJsonLd(title, description, baseIri, rdfRelPath, llmName, llmUrl);
  const davGraphIri    = computeDavGraphIri(rdfFilename);
  const sparqlRecipes  = buildSparqlRecipes(baseIri, davGraphIri);
  const defaultSparql  = sparqlRecipes[0].query;
  const sparqlBtnHref  = buildSparqlBtnHref(davGraphIri);
  const cssContent     = loadAsset("styles.css");
  const kgExplorerJs   = loadAsset("kg_explorer.js");
  const kgdataJson     = JSON.stringify(kgdata);

  console.log("Assembling HTML...");
  const templateStr = loadAsset("base_template.html");
  const html = renderTemplate(templateStr, {
    title,
    description,
    tagline,
    hero_tagline:    heroTagline,
    meta_html:       metaHtml,
    rdf_rel_path:    rdfRelPath,
    rdf_filename:    rdfFilename,
    output_filename: outputFilename,
    base_iri:        baseIri,
    css_content:     cssContent,
    jsonld_content:  jsonldContent,
    kgdata_json:     kgdataJson,
    kg_explorer_js:  kgExplorerJs,
    nav_links:       navLinks,
    narrative_html:  narrativeHtml,
    sparql_recipes:  sparqlRecipes,
    default_sparql:  defaultSparql,
    dav_graph_iri:   davGraphIri,
    sparql_btn_href: sparqlBtnHref,
    source_url:      sourceUrl,
    source_label:    sourceLabel,
  });

  mkdirSync(dirname(resolve(outputPath)), { recursive: true });
  writeFileSync(outputPath, html, "utf-8");
  const sizeKb = (statSync(outputPath).size / 1024).toFixed(1);
  console.log(`Written: ${outputPath} (${sizeKb} KB)`);

  if (existsSync(VALIDATOR)) {
    console.log("Running harness contract validation...");
    const result = spawnSync(
      "npx",
      ["tsx", VALIDATOR, outputPath, "--ttl", rdfPath],
      { encoding: "utf-8", shell: true },
    );
    if (result.status === 0) {
      console.log("  PASS");
      return true;
    }
    console.log("  FAIL");
    if (result.stdout) console.log("  " + result.stdout.replace(/\n/g, "\n  "));
    return false;
  }

  console.log(`  Validator not found at ${VALIDATOR}`);
  return true;
}

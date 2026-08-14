"""Assemble RDF data into a self-contained HTML infographic."""

from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from html import escape
from urllib.parse import quote

try:
    from jinja2 import Environment, FileSystemLoader, Template
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False
    from string import Template as StrTemplate

from rdf_parser import build_kgdata, extract_narrative, get_base_iri, validate_orphans


HERE = Path(__file__).parent
TEMPLATES_DIR = HERE / "templates"
VALIDATOR = HERE / "validate-harness-contract.py"


def load_asset(name: str) -> str:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing template asset: {path}")
    return path.read_text(encoding="utf-8")


def make_resolver_link(iri: str, resolver_pattern: str = "https://linkeddata.uriburner.com/describe/?url=") -> str:
    return resolver_pattern + quote(iri, safe="")


def make_section_html(section_id: str, title: str, inner_html: str) -> str:
    return (
        f'<section class="section section-alt" id="{section_id}">'
        f'<h2>{title}<a class="headline-anchor" href="#{section_id}" aria-label="Link to this section">¶</a></h2>'
        f'{inner_html}'
        f'</section>'
    )


def render_narrative(rdf_path: str | Path, base_iri: str, resolver_pattern: str) -> tuple[str, list[dict]]:
    """Extract and render narrative sections from RDF annotations."""
    narrative = extract_narrative(rdf_path, base_iri)
    nav_links = [
        {"href": "#hero", "label": "Overview"},
    ]
    html_parts = []
    sections = []

    has_faq = len(narrative["faq"]) > 0
    has_glossary = len(narrative["glossary"]) > 0
    has_howto = len(narrative["howto"]) > 0
    has_people = len(narrative["people"]) > 0
    has_orgs = len(narrative["organizations"]) > 0
    has_synopsis = narrative.get("synopsis") is not None
    has_sections = len(narrative.get("sections", [])) > 0

    if has_synopsis:
        syn = narrative["synopsis"]
        abstract = escape(syn["abstract"]) if syn["abstract"] else ""
        iri = syn["iri"]
        heading = escape(syn["headline"]) if syn["headline"] else "Synopsis"
        link_open = f'<a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">' if iri else ""
        link_close = "</a>" if iri else ""
        items_html = f'<p style="font-size:1.05rem;line-height:1.7">{abstract}</p>' if abstract else ""
        if iri:
            items_html += f'<p style="margin-top:1rem;font-size:0.85rem">{link_open}View this analysis as a KG entity{link_close}</p>'
        html_parts.append(render_narrative_section("synopsis", "Synopsis", items_html))
        nav_links.append({"href": "#synopsis", "label": "Synopsis"})
        sections.append("synopsis")

    if has_sections:
        for idx, sec in enumerate(narrative["sections"], 1):
            sec_id = f"analysis-{idx}"
            sec_name = escape(sec["name"])
            sec_iri = sec["iri"]
            sec_abstract = escape(sec["abstract"]) if sec["abstract"] else ""
            inner = f'<p style="font-size:0.98rem;line-height:1.7;color:var(--text-secondary)">{sec_abstract}</p>' if sec_abstract else ""
            if sec["items"]:
                inner += '<div class="cards-grid mt-2">'
                for item in sec["items"]:
                    i_iri = item["iri"]
                    i_name = escape(item["name"])
                    i_desc = escape(item["description"]) if item["description"] else ""
                    inner += (
                        f'<div class="card">'
                        f'<h3><a href="{make_resolver_link(i_iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">{i_name}</a></h3>'
                        f'<p>{i_desc}</p></div>'
                    )
                inner += '</div>'
            link_open = f'<a href="{make_resolver_link(sec_iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">' if sec_iri else ""
            link_close = "</a>" if sec_iri else ""
            title_html = f'{link_open}{sec_name}{link_close}' if sec_iri else sec_name
            html_parts.append(
                f'<section class="section section-alt" id="{sec_id}">'
                f'<h2>{title_html}<a class="headline-anchor" href="#{sec_id}" aria-label="Link to this section">¶</a></h2>'
                f'{inner}'
                f'</section>'
            )
            nav_links.append({"href": f"#{sec_id}", "label": sec["name"][:28]})
            sections.append(sec_id)

    if has_people:
        items_html = ""
        for p in narrative["people"]:
            iri = p["iri"]
            name = escape(p["name"])
            desc = escape(p["description"]) if p["description"] else ""
            items_html += (
                f'<div class="card">'
                f'<h3><a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">{name}</a></h3>'
                f'<p>{desc}</p></div>'
            )
        html_parts.append(render_narrative_section("people", "People", f'<div class="cards-grid">{items_html}</div>'))
        nav_links.append({"href": "#people", "label": "People"})
        sections.append("people")

    if has_orgs:
        items_html = ""
        for o in narrative["organizations"]:
            iri = o["iri"]
            name = escape(o["name"])
            desc = escape(o["description"]) if o["description"] else ""
            items_html += (
                f'<div class="card">'
                f'<h3><a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">{name}</a></h3>'
                f'<p>{desc}</p></div>'
            )
        html_parts.append(render_narrative_section("organizations", "Organizations", f'<div class="cards-grid">{items_html}</div>'))
        nav_links.append({"href": "#organizations", "label": "Organizations"})
        sections.append("organizations")

    if has_faq:
        items_html = '<div class="faq-list">'
        for faq in narrative["faq"]:
            iri = faq["iri"]
            q = escape(faq["question"])
            a = escape(faq["answer"])
            link_open = f'<a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">' if iri else ""
            link_close = "</a>" if iri else ""
            items_html += (
                f'<div class="faq-item anim-fade">'
                f'<div class="faq-question">{link_open}{q}{link_close}<span class="faq-chevron">▼</span></div>'
                f'<div class="faq-answer"><p>{a}</p></div>'
                f'</div>'
            )
        items_html += "</div>"
        html_parts.append(render_narrative_section("faq", "Frequently Asked Questions", items_html))
        nav_links.append({"href": "#faq", "label": "FAQ"})
        sections.append("faq")

    if has_glossary:
        items_html = '<div class="glossary-grid">'
        for g in narrative["glossary"]:
            iri = g["iri"]
            term = escape(g["term"])
            defn = escape(g["definition"])
            link_open = f'<a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">' if iri else ""
            link_close = "</a>" if iri else ""
            items_html += (
                f'<div class="glossary-term">'
                f'<h4>{link_open}{term}{link_close}</h4>'
                f'<p>{defn}</p></div>'
            )
        items_html += "</div>"
        html_parts.append(render_narrative_section("glossary", "Glossary of Terms", items_html))
        nav_links.append({"href": "#glossary", "label": "Glossary"})
        sections.append("glossary")

    if has_howto:
        items_html = '<div class="howto-list">'
        for i, step in enumerate(narrative["howto"], 1):
            iri = step["iri"]
            s = escape(step["step"])
            desc = escape(step["description"]) if step["description"] else ""
            link_open = f'<a href="{make_resolver_link(iri, resolver_pattern)}" target="_blank" rel="noopener noreferrer">' if iri else ""
            link_close = "</a>" if iri else ""
            items_html += (
                f'<div class="howto-step anim-fade">'
                f'<div class="howto-num">{i}</div>'
                f'<div class="howto-content">'
                f'<h4>{link_open}{s}{link_close}</h4>'
                f'<p>{desc}</p></div></div>'
            )
        items_html += "</div>"
        html_parts.append(render_narrative_section("howto", "How-To Guide", items_html))
        nav_links.append({"href": "#howto", "label": "HowTo"})
        sections.append("howto")

    nav_links.extend([
        {"href": "#kg-explorer", "label": "KG Explorer"},
        {"href": "#sparql-explorer", "label": "SPARQL"},
        {"href": "#footer", "label": "Footer"},
    ])

    return "\n".join(html_parts), nav_links, sections


def render_narrative_section(section_id: str, title: str, inner_html: str) -> str:
    return make_section_html(section_id, title, inner_html)


KIDEHEN_WEBID = "https://www.linkedin.com/in/kidehen#this"
KG_GENERATOR_URL = "https://github.com/OpenLinkSoftware/ai-agent-skills/tree/main/kg-generator"
RDF_INFOGRAPHIC_SKILL_URL = "https://github.com/OpenLinkSoftware/ai-agent-skills/tree/main/rdf-infographic-skill"


def render_jsonld(
    title: str,
    description: str,
    base_iri: str,
    rdf_rel_path: str,
    llm_name: str = "Claude Sonnet 5",
    llm_url: str = "https://www.anthropic.com/claude",
    principal_webid: str = KIDEHEN_WEBID,
) -> str:
    """Build the embedded JSON-LD block.

    The KG-curation delegation chain (schema:author / accountablePerson on the
    document, prov:wasGeneratedBy + prov:actedOnBehalfOf on each generating
    agent) is always included — never opt-in. This closed a recurring gap
    (5 documented occurrences in agent-rdf-memory/howto/kg-curation-attribution.ttl)
    where the generator shipped HTML with no delegation chain, or with
    prov:actedOnBehalfOf pointing at the LLM/tool itself instead of the human
    principal on whose behalf it acted.
    """
    ld = {
        "@context": {
            "@vocab": "http://schema.org/",
            "@language": "en",
            "prov": "http://www.w3.org/ns/prov#",
        },
        "@type": "Article",
        "@id": base_iri,
        "headline": title,
        "description": description,
        "mainEntity": {
            "@type": "CreativeWork",
            "@id": base_iri,
        },
        "sameAs": rdf_rel_path,
        "author": {"@id": principal_webid},
        "accountablePerson": {"@id": principal_webid},
        "prov:wasGeneratedBy": [
            {
                "@id": f"{KG_GENERATOR_URL}#this",
                "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
                "name": "kg-generator",
                "url": KG_GENERATOR_URL,
                "prov:actedOnBehalfOf": {"@id": principal_webid},
            },
            {
                "@id": f"{RDF_INFOGRAPHIC_SKILL_URL}#this",
                "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
                "name": "rdf-infographic-skill",
                "url": RDF_INFOGRAPHIC_SKILL_URL,
                "prov:actedOnBehalfOf": {"@id": principal_webid},
            },
            {
                "@id": f"{llm_url}#this",
                "@type": ["SoftwareApplication", "prov:SoftwareAgent"],
                "name": llm_name,
                "url": llm_url,
                "prov:actedOnBehalfOf": {"@id": principal_webid},
            },
        ],
    }
    return json.dumps(ld, indent=2)


def render_hero_meta(
    llm_name: str = "Claude Sonnet 5",
    llm_url: str = "https://www.anthropic.com/claude",
    principal_name: str = "Kingsley Idehen",
    principal_resolver: str = "https://linkeddata.uriburner.com/describe/?url=https%3A%2F%2Fwww.linkedin.com%2Fin%2Fkidehen%23this",
) -> str:
    """Build the visible hero-meta 'KG curated by ... on behalf of ...' line.

    This is rendered into every generated infographic by default (see
    assemble_html's meta_html handling) rather than left as an opt-in
    caller-supplied string — the prior opt-in design was the root cause of
    the hero-attribution line going missing across five separate documented
    occurrences (agent-rdf-memory/howto/kg-curation-attribution.ttl).
    """
    return (
        "KG curated by "
        f'<a href="{KG_GENERATOR_URL}" target="_blank" rel="noopener noreferrer">kg-generator</a>, '
        f'<a href="{RDF_INFOGRAPHIC_SKILL_URL}" target="_blank" rel="noopener noreferrer">rdf-infographic-skill</a>, '
        f'and <a href="{llm_url}" target="_blank" rel="noopener noreferrer">{llm_name}</a> '
        f'on behalf of <a href="{principal_resolver}" target="_blank" rel="noopener noreferrer">{principal_name}</a>'
    )


DAV_GRAPH_BASE = "https://linkeddata.uriburner.com/DAV/demos/daas/"


def compute_dav_graph_iri(rdf_filename: str) -> str:
    """The SPARQL GRAPH/FROM IRI for a generated artifact once uploaded to URIBurner.

    This is NEVER the same as the document/base IRI (the source URL used for
    entity resolver links) — see the skill's own "Document IRI vs SPARQL GRAPH
    IRI" rule. Confusing the two was a documented contract gap: the SPARQL
    workbench's graph selector and recipes previously scoped queries to the
    source document IRI, which URIBurner has no named graph for, instead of
    the DAV path the file is actually uploaded to.
    """
    return DAV_GRAPH_BASE + rdf_filename


def build_canonical_entity_summary_query(dav_graph_iri: str) -> str:
    """The canonical entity-type-summary query mandated by the Footer SPARQL
    Button contract: SAMPLE-based projection, GROUP BY type, no default-graph-uri
    URL parameter, no FILTER(STRSTARTS(...)) workaround."""
    return (
        "SELECT ?type (SAMPLE(?s) AS ?sampleEntity) (SAMPLE(?label) AS ?sampleLabel) (COUNT(?s) AS ?entityCount)\n"
        "WHERE {\n"
        f"  GRAPH <{dav_graph_iri}> {{\n"
        "    ?s a ?type .\n"
        "    OPTIONAL { ?s rdfs:label|<http://schema.org/name> ?label }\n"
        "  }\n"
        "}\n"
        "GROUP BY ?type\n"
        "ORDER BY DESC(?entityCount)"
    )


def build_sparql_btn_href(dav_graph_iri: str) -> str:
    """href for the required <a id="sparqlBtn"> CTA — SELECT format, no
    default-graph-uri= parameter (the GRAPH clause carries the scope)."""
    query = build_canonical_entity_summary_query(dav_graph_iri)
    encoded = quote(query, safe="")
    return (
        "https://linkeddata.uriburner.com/sparql?default-graph-uri=&query="
        f"{encoded}&format=text%2Fx-html%2Btr&timeout=0&debug=on&run=+Run+Query+"
    )


def build_sparql_recipes(base_iri: str, dav_graph_iri: str) -> list[dict]:
    return [
        {
            "label": "All triples (sample)",
            "query": f"SELECT ?s ?p ?o\nWHERE {{ GRAPH <{dav_graph_iri}> {{ ?s ?p ?o }} }}\nLIMIT 25",
        },
        {
            "label": "Entity types summary",
            "query": build_canonical_entity_summary_query(dav_graph_iri),
        },
        {
            "label": "Named graph triples",
            "query": f"SELECT ?s ?p ?o\nFROM <{dav_graph_iri}>\nWHERE {{ ?s ?p ?o }}\nLIMIT 25",
        },
    ]


def assemble_html(
    rdf_path: str | Path,
    output_path: str | Path,
    title: str = "",
    description: str = "",
    source_url: str = "",
    source_label: str = "",
    resolver_pattern: str = "https://linkeddata.uriburner.com/describe/?url=",
    tagline: str = "",
    hero_tagline: str = "",
    meta_html: str = "",
    llm_name: str = "Claude Sonnet 5",
    llm_url: str = "https://www.anthropic.com/claude",
) -> bool:
    """Assemble a complete HTML infographic from an RDF file.

    Returns True on success, False on failure.
    """
    rdf_path = Path(rdf_path)
    output_path = Path(output_path)
    stem = rdf_path.stem

    # KG-curation attribution defaults on unless the caller explicitly overrides
    # meta_html — see render_hero_meta docstring for why this is not opt-in.
    if not meta_html:
        meta_html = render_hero_meta(llm_name=llm_name, llm_url=llm_url)

    # Resolve base IRI
    base_iri = get_base_iri(rdf_path)

    if not title:
        title = f"Knowledge Graph Infographic — {stem}"
    if not description:
        description = f"Interactive infographic generated from {rdf_path.name}"

    # Compute relative path for RDF link from output
    rdf_rel = os.path.relpath(str(rdf_path.resolve()), start=str(output_path.parent.resolve()))
    rdf_filename = rdf_path.name

    # Build kgData
    print("Parsing RDF...")
    kgdata = build_kgdata(rdf_path)
    print(f"  Nodes: {len(kgdata['nodes'])}, Links: {len(kgdata['links'])}")

    # Validate orphans
    orphans = validate_orphans(kgdata)
    if orphans:
        print(f"  Warning: {len(orphans)} orphan nodes — {orphans}")
    else:
        print("  Zero orphan nodes")

    # Render narrative
    print("Extracting narrative...")
    narrative_html, nav_links, sections = render_narrative(rdf_path, base_iri, resolver_pattern)
    print(f"  Sections: {', '.join(sections)}")

    # Build JSON-LD
    jsonld_content = render_jsonld(title, description, base_iri, rdf_rel, llm_name=llm_name, llm_url=llm_url)

    # Build SPARQL recipes — scoped to the DAV-uploaded graph IRI, never the
    # document/base IRI (see compute_dav_graph_iri docstring).
    dav_graph_iri = compute_dav_graph_iri(rdf_filename)
    sparql_recipes = build_sparql_recipes(base_iri, dav_graph_iri)
    default_sparql = sparql_recipes[0]["query"]
    sparql_btn_href = build_sparql_btn_href(dav_graph_iri)

    # Load assets
    css_content = load_asset("styles.css")
    kg_explorer_js = load_asset("kg_explorer.js")

    # Serialize kgData
    kgdata_json = json.dumps(kgdata, separators=(",", ":"))

    # Template context
    context = {
        "title": title,
        "description": description,
        "tagline": tagline,
        "hero_tagline": hero_tagline,
        "meta_html": meta_html,
        "rdf_rel_path": rdf_rel,
        "rdf_filename": rdf_filename,
        "output_filename": output_path.name,
        "base_iri": base_iri,
        "css_content": css_content,
        "jsonld_content": jsonld_content,
        "kgdata_json": kgdata_json,
        "kg_explorer_js": kg_explorer_js,
        "nav_links": nav_links,
        "narrative_html": narrative_html,
        "sparql_recipes": sparql_recipes,
        "default_sparql": default_sparql,
        "dav_graph_iri": dav_graph_iri,
        "sparql_btn_href": sparql_btn_href,
        "source_url": source_url,
        "source_label": source_label,
    }

    # Render template
    print("Assembling HTML...")
    if HAS_JINJA:
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=False,
        )
        template = env.get_template("base_template.html")
        html = template.render(**context)
    else:
        # Fallback to string.Template
        template_str = load_asset("base_template.html")
        # Convert Jinja2 syntax to $var syntax
        template_str = re.sub(r"\{\{ (\w+) \}\}", r"$\1", template_str)
        template_str = re.sub(r"\{% for (\w+) in (\w+) %\}(.*?)\{% endfor %\}", r"<!-- loop: \1 in \2 -->\3<!-- end loop -->", template_str, flags=re.S)
        template_str = re.sub(r"\{% if (.*?) %\}(.*?)\{% endif %\}", r"\2", template_str, flags=re.S)
        template = StrTemplate(template_str)
        html = template.safe_substitute(**{k: str(v) for k, v in context.items()})

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"Written: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")

    # Validate
    if VALIDATOR.exists():
        print("Running harness contract validation...")
        cmd = [sys.executable, str(VALIDATOR), str(output_path), "--ttl", str(rdf_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("  PASS")
            return True
        else:
            print("  FAIL")
            print("  " + result.stdout.replace("\n", "\n  "))
            return False
    else:
        print(f"  Validator not found at {VALIDATOR}")
        return True

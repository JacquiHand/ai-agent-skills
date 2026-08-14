"""Parse RDF documents and extract KG Explorer data + narrative sections."""

from __future__ import annotations
import re
from pathlib import Path
from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD, Namespace


SCHEMA = Namespace("http://schema.org/")
PROV = Namespace("http://www.w3.org/ns/prov#")
KNOWN_CLASS_URIS = {
    RDF.Property, RDFS.Class, OWL.Class, OWL.NamedIndividual,
    SCHEMA.Person, SCHEMA.Organization, SCHEMA.Article,
    SCHEMA.FAQPage, SCHEMA.Question, SCHEMA.DefinedTermSet,
    SCHEMA.DefinedTerm, SCHEMA.HowTo, SCHEMA.HowToStep,
    SCHEMA.SoftwareApplication, SCHEMA.SoftwareSourceCode,
    SCHEMA.Thing, SCHEMA.CreativeWork,
}


def classify(node_uri: URIRef, g: Graph) -> str:
    """Classify a URIRef node as Class, Property, or Instance."""
    types = set(g.objects(node_uri, RDF.type))
    if not types:
        # Check if it's used as a predicate
        if (None, node_uri, None) in g or (node_uri, RDF.type, RDF.Property) in g:
            return "Property"
        # Check if it's used as a class
        for s, p, o in g:
            if p == RDF.type and o == node_uri:
                return "Class"
        return "Instance"

    for t in types:
        if t in (RDFS.Class, OWL.Class):
            return "Class"
        if t == RDF.Property:
            return "Property"

    for t in types:
        if t in KNOWN_CLASS_URIS:
            return "Instance"

    return "Instance"


def shorten(uri: URIRef, g: Graph) -> str:
    """Try to shorten a URI using namespace prefixes from the graph."""
    for prefix, ns in g.namespaces():
        if str(uri).startswith(str(ns)):
            return f"{prefix}:{str(uri)[len(str(ns)):]}"
    # Last resort: extract local name
    uri_str = str(uri)
    if "#" in uri_str:
        return uri_str.split("#")[-1]
    return uri_str.split("/")[-1] if "/" in uri_str else uri_str


def extract_label(uri: URIRef, g: Graph) -> str:
    """Extract the best label for a URI."""
    for label in g.objects(uri, RDFS.label):
        return str(label)
    for label in g.objects(uri, SCHEMA.name):
        return str(label)
    return shorten(uri, g)


def extract_description(uri: URIRef, g: Graph) -> str:
    """Extract description/comment/body text for a URI.

    Checks rdfs:comment and schema:description first (short summaries),
    then falls back to schema:text (the body of HowToStep, Answer, etc.,
    which carries the actual content and must not be dropped).
    """
    for desc in g.objects(uri, RDFS.comment):
        return str(desc)[:400]
    for desc in g.objects(uri, SCHEMA.description):
        return str(desc)[:400]
    for desc in g.objects(uri, SCHEMA.text):
        return str(desc)[:400]
    return ""


def build_kgdata(rdf_path: str | Path) -> dict:
    """Build kgData payload from an RDF file.

    Returns: {'nodes': [...], 'links': [...]}
    """
    g = Graph()
    g.parse(str(rdf_path))

    nodes_map: dict[str, dict] = {}
    links: list[dict] = []
    seen_predicates: set[str] = set()

    for s, p, o in g:
        if isinstance(s, BNode) or isinstance(o, BNode) and isinstance(p, URIRef):
            continue

        pred_short = shorten(p, g) if isinstance(p, URIRef) else str(p)
        seen_predicates.add(pred_short)

        subj_id = str(s) if isinstance(s, URIRef) else f"_:{s}"
        obj_id = str(o) if isinstance(o, URIRef) else f"_:{o}"

        # Add subject node
        if subj_id not in nodes_map and isinstance(s, URIRef):
            nodes_map[subj_id] = {
                "id": subj_id,
                "group": classify(s, g),
                "label": extract_label(s, g),
                "desc": extract_description(s, g),
                "iri": str(s),
            }

        # Add object node
        if obj_id not in nodes_map and isinstance(o, URIRef):
            nodes_map[obj_id] = {
                "id": obj_id,
                "group": classify(o, g),
                "label": extract_label(o, g),
                "desc": extract_description(o, g),
                "iri": str(o),
            }

        # Add link
        if isinstance(p, URIRef) and isinstance(s, (URIRef, BNode)) and isinstance(o, (URIRef, BNode)):
            link = {
                "source": subj_id,
                "target": obj_id,
                "predicate": pred_short,
                "label": pred_short,
            }
            links.append(link)

    nodes = list(nodes_map.values())

    # Orphan check
    incident_ids: set[str] = set()
    for link in links:
        incident_ids.add(link["source"] if isinstance(link["source"], str) else link["source"])
        incident_ids.add(link["target"] if isinstance(link["target"], str) else link["target"])
    orphans = [n for n in nodes if n["id"] not in incident_ids]
    if orphans:
        orphan_ids = [n["id"] for n in orphans]
        print(f"Warning: {len(orphans)} orphan nodes found: {orphan_ids}")

    return {
        "nodes": nodes,
        "links": links,
    }


def extract_narrative(rdf_path: str | Path, base_iri: str) -> dict:
    """Extract narrative sections (FAQ, glossary, HowTo, People, Orgs) from RDF."""
    g = Graph()
    g.parse(str(rdf_path))

    result = {
        "synopsis": None,
        "faq": [],
        "glossary": [],
        "howto": [],
        "people": [],
        "organizations": [],
        "sections": [],
    }

    # Synopsis: the main article/report entity — prefer schema:Article, then
    # any subject with the most schema:hasPart links (the de facto hub node).
    main_entity = None
    for candidate in g.subjects(RDF.type, SCHEMA.Article):
        main_entity = candidate
        break
    if main_entity is None:
        best_count = -1
        for s in set(g.subjects(SCHEMA.hasPart, None)):
            count = len(list(g.objects(s, SCHEMA.hasPart)))
            if count > best_count:
                best_count = count
                main_entity = s
    if main_entity is not None:
        headline = ""
        for h in g.objects(main_entity, SCHEMA.headline):
            headline = str(h)
            break
        if not headline:
            headline = extract_label(main_entity, g) if isinstance(main_entity, URIRef) else ""
        abstract = ""
        for a in g.objects(main_entity, SCHEMA.abstract):
            abstract = str(a)
            break
        if not abstract:
            for a in g.objects(main_entity, SCHEMA.articleBody):
                abstract = str(a)[:600]
                break
        if headline or abstract:
            result["synopsis"] = {
                "headline": headline,
                "abstract": abstract,
                "iri": str(main_entity) if isinstance(main_entity, URIRef) else "",
            }

    # FAQ
    for faq in g.subjects(RDF.type, SCHEMA.FAQPage):
        for q_item in g.objects(faq, SCHEMA.hasPart):
            q_text = extract_label(q_item, g) if isinstance(q_item, URIRef) else str(q_item)
            a_iri = None
            for a_item in g.objects(q_item, SCHEMA.acceptedAnswer):
                a_iri = a_item
                break
            a_text = ""
            for txt in g.objects(a_item, SCHEMA.text):
                a_text = str(txt)
                break
            for txt in g.objects(a_item, RDFS.comment):
                if not a_text:
                    a_text = str(txt)
                break
            if q_text and a_text:
                result["faq"].append({
                    "question": q_text,
                    "answer": a_text,
                    "iri": str(q_item) if isinstance(q_item, URIRef) else "",
                })

    # Fallback: look for Question nodes directly
    if not result["faq"]:
        for q in g.subjects(RDF.type, SCHEMA.Question):
            q_text = extract_label(q, g) or ""
            for a in g.objects(q, SCHEMA.acceptedAnswer):
                a_text = ""
                for txt in g.objects(a, SCHEMA.text):
                    a_text = str(txt)
                    break
                if q_text and a_text:
                    result["faq"].append({
                        "question": q_text,
                        "answer": a_text,
                        "iri": str(q) if isinstance(q, URIRef) else "",
                    })

    # Glossary
    for term_set in g.subjects(RDF.type, SCHEMA.DefinedTermSet):
        for term in g.objects(term_set, SCHEMA.hasPart):
            term_text = extract_label(term, g) if isinstance(term, URIRef) else str(term)
            term_desc = extract_description(term, g) if isinstance(term, URIRef) else ""
            if term_text and term_desc:
                result["glossary"].append({
                    "term": term_text,
                    "definition": term_desc,
                    "iri": str(term) if isinstance(term, URIRef) else "",
                })

    # Fallback glossary: DefinedTerm nodes
    if not result["glossary"]:
        for term in g.subjects(RDF.type, SCHEMA.DefinedTerm):
            term_text = extract_label(term, g) or ""
            desc = extract_description(term, g) or ""
            if term_text:
                result["glossary"].append({
                    "term": term_text,
                    "definition": desc,
                    "iri": str(term) if isinstance(term, URIRef) else "",
                })

    # HowTo
    for howto in g.subjects(RDF.type, SCHEMA.HowTo):
        for step in g.objects(howto, SCHEMA.step):
            step_text = extract_label(step, g) if isinstance(step, URIRef) else str(step)
            step_desc = extract_description(step, g) if isinstance(step, URIRef) else ""
            if step_text:
                result["howto"].append({
                    "step": step_text,
                    "description": step_desc,
                    "iri": str(step) if isinstance(step, URIRef) else "",
                })

    # People
    for person in g.subjects(RDF.type, SCHEMA.Person):
        name = extract_label(person, g)
        if name:
            desc = extract_description(person, g)
            result["people"].append({
                "name": name,
                "description": desc,
                "iri": str(person) if isinstance(person, URIRef) else "",
            })

    # Organizations
    for org in g.subjects(RDF.type, SCHEMA.Organization):
        name = extract_label(org, g)
        if name:
            desc = extract_description(org, g)
            result["organizations"].append({
                "name": name,
                "description": desc,
                "iri": str(org) if isinstance(org, URIRef) else "",
            })

    # Generic narrative content sections (article-body substance beyond
    # FAQ/glossary/HowTo/People/Organizations) — e.g. a schema:CreativeWork
    # or schema:ItemList that is schema:hasPart of the main article, whose
    # own children carry the actual analysis. Without this, an infographic
    # can pass every structural check while silently dropping the source's
    # substantive narrative (see generator-script-output-not-a-substitute-
    # for-contract-check.ttl for the recurring pattern this closes).
    if main_entity is not None:
        excluded_types = {SCHEMA.FAQPage, SCHEMA.DefinedTermSet, SCHEMA.HowTo, OWL.Ontology}
        excluded_iris = set()
        for faq in g.subjects(RDF.type, SCHEMA.FAQPage):
            excluded_iris.add(faq)
        for ts in g.subjects(RDF.type, SCHEMA.DefinedTermSet):
            excluded_iris.add(ts)
        for ht in g.subjects(RDF.type, SCHEMA.HowTo):
            excluded_iris.add(ht)
        for onto in g.subjects(RDF.type, OWL.Ontology):
            excluded_iris.add(onto)

        for part in g.objects(main_entity, SCHEMA.hasPart):
            if not isinstance(part, URIRef) or part in excluded_iris:
                continue
            part_types = set(g.objects(part, RDF.type))
            if not (part_types & {SCHEMA.CreativeWork, SCHEMA.ItemList}) or (part_types & excluded_types):
                continue
            sec_name = extract_label(part, g)
            if not sec_name:
                continue
            sec_abstract = ""
            for a in g.objects(part, SCHEMA.abstract):
                sec_abstract = str(a)
                break
            if not sec_abstract:
                for a in g.objects(part, SCHEMA.description):
                    sec_abstract = str(a)
                    break

            # Children: entities that declare schema:isPartOf this section
            # (schema:hasPart / schema:itemListElement give the same set via
            # the inverse-relationship contract), excluding media objects.
            child_iris = set(g.subjects(SCHEMA.isPartOf, part))
            child_iris |= set(g.objects(part, SCHEMA.hasPart))
            child_iris |= set(g.objects(part, SCHEMA.itemListElement))
            children = []
            for child in child_iris:
                if not isinstance(child, URIRef) or child == part:
                    continue
                child_types = set(g.objects(child, RDF.type))
                if child_types & {SCHEMA.ImageObject, SCHEMA.VideoObject, SCHEMA.AudioObject}:
                    continue
                c_name = extract_label(child, g)
                if not c_name:
                    continue
                c_desc = extract_description(child, g)
                c_pos = None
                for p in g.objects(child, SCHEMA.position):
                    try:
                        c_pos = int(p)
                    except (TypeError, ValueError):
                        pass
                    break
                children.append({
                    "name": c_name,
                    "description": c_desc,
                    "iri": str(child),
                    "position": c_pos if c_pos is not None else 9999,
                })
            children.sort(key=lambda c: c["position"])

            if sec_abstract or children:
                result["sections"].append({
                    "name": sec_name,
                    "abstract": sec_abstract,
                    "iri": str(part),
                    "items": children,
                })

    return result


def get_base_iri(rdf_path: str | Path) -> str:
    """Extract the base IRI from an RDF file if available."""
    g = Graph()
    g.parse(str(rdf_path))
    for s in set(g.subjects()):
        if isinstance(s, URIRef):
            uri = str(s)
            if "#" in uri:
                return uri.split("#")[0] + "#"
            return uri.rsplit("/", 1)[0] + "/"
    return "https://linkedin.com/pulse/"


def get_entity_count(rdf_path: str | Path) -> int:
    """Return the number of triples in the RDF file."""
    g = Graph()
    g.parse(str(rdf_path))
    return len(g)


def validate_orphans(kgdata: dict) -> list[str]:
    """Return list of orphan node IDs (nodes with no incident links)."""
    incident: set[str] = set()
    for link in kgdata["links"]:
        src = link["source"] if isinstance(link["source"], str) else link["source"]["id"]
        tgt = link["target"] if isinstance(link["target"], str) else link["target"]["id"]
        incident.add(src)
        incident.add(tgt)
    orphans = [n["id"] for n in kgdata["nodes"] if n["id"] not in incident]
    return orphans

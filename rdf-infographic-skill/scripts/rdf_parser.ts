/**
 * RDF Parser — TypeScript edition (Node.js ≥ 18, requires n3).
 * Consolidates rdf_parser.py (importable) and rdf-parser.py (CLI) into one file.
 *
 * Install: npm install (from rdf-infographic-skill/scripts/)
 * Run CLI: npx tsx rdf_parser.ts input.ttl [--format turtle|nt|n3]
 */

import { readFileSync } from "node:fs";
import { DataFactory, Parser, Store, type Quad_Object, type Quad_Subject, type Term } from "n3";

const { namedNode } = DataFactory;

// ── Well-known IRIs ───────────────────────────────────────────────────────────

const RDF_TYPE      = namedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type");
const RDFS_LABEL    = namedNode("http://www.w3.org/2000/01/rdf-schema#label");
const RDFS_COMMENT  = namedNode("http://www.w3.org/2000/01/rdf-schema#comment");
const RDFS_CLASS    = namedNode("http://www.w3.org/2000/01/rdf-schema#Class");
const OWL_CLASS     = namedNode("http://www.w3.org/2002/07/owl#Class");
const OWL_PROPERTY  = namedNode("http://www.w3.org/2002/07/owl#ObjectProperty");
const RDF_PROPERTY  = namedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#Property");

const SCHEMA_NAME        = namedNode("http://schema.org/name");
const SCHEMA_DESCRIPTION = namedNode("http://schema.org/description");
const SCHEMA_PERSON      = namedNode("http://schema.org/Person");
const SCHEMA_ORG         = namedNode("http://schema.org/Organization");
const SCHEMA_ARTICLE     = namedNode("http://schema.org/Article");
const SCHEMA_FAQPAGE     = namedNode("http://schema.org/FAQPage");
const SCHEMA_QUESTION    = namedNode("http://schema.org/Question");
const SCHEMA_HOWTO       = namedNode("http://schema.org/HowTo");
const SCHEMA_HOWTO_STEP  = namedNode("http://schema.org/HowToStep");
const SCHEMA_DEFINED_TERM_SET = namedNode("http://schema.org/DefinedTermSet");
const SCHEMA_DEFINED_TERM    = namedNode("http://schema.org/DefinedTerm");
const SCHEMA_HAS_PART    = namedNode("http://schema.org/hasPart");
const SCHEMA_STEP        = namedNode("http://schema.org/step");
const SCHEMA_ACCEPTED_ANSWER = namedNode("http://schema.org/acceptedAnswer");
const SCHEMA_TEXT        = namedNode("http://schema.org/text");
const SCHEMA_CREATIVE_WORK = namedNode("http://schema.org/CreativeWork");
const SCHEMA_HEADLINE     = namedNode("http://schema.org/headline");
const SCHEMA_ABSTRACT     = namedNode("http://schema.org/abstract");
const SCHEMA_ARTICLE_BODY = namedNode("http://schema.org/articleBody");
const SCHEMA_ITEM_LIST    = namedNode("http://schema.org/ItemList");
const SCHEMA_IS_PART_OF   = namedNode("http://schema.org/isPartOf");
const SCHEMA_ITEM_LIST_ELEMENT = namedNode("http://schema.org/itemListElement");
const SCHEMA_POSITION     = namedNode("http://schema.org/position");
const SCHEMA_IMAGE_OBJECT = namedNode("http://schema.org/ImageObject");
const SCHEMA_VIDEO_OBJECT = namedNode("http://schema.org/VideoObject");
const SCHEMA_AUDIO_OBJECT = namedNode("http://schema.org/AudioObject");
const OWL_ONTOLOGY        = namedNode("http://www.w3.org/2002/07/owl#Ontology");

const KNOWN_CLASS_IRIS = new Set([
  RDF_PROPERTY.value, RDFS_CLASS.value, OWL_CLASS.value,
  SCHEMA_PERSON.value, SCHEMA_ORG.value, SCHEMA_ARTICLE.value,
  SCHEMA_FAQPAGE.value, SCHEMA_QUESTION.value,
  SCHEMA_DEFINED_TERM_SET.value, SCHEMA_DEFINED_TERM.value,
  SCHEMA_HOWTO.value, SCHEMA_HOWTO_STEP.value,
  "http://schema.org/SoftwareApplication", "http://schema.org/SoftwareSourceCode",
  "http://schema.org/Thing", SCHEMA_CREATIVE_WORK.value,
]);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface KgNode {
  id: string;
  group: string;
  label: string;
  desc: string;
  iri: string;
}

export interface KgLink {
  source: string;
  target: string;
  predicate: string;
  label: string;
}

export interface KgData {
  nodes: KgNode[];
  links: KgLink[];
}

export interface NarrativeEntry {
  name?: string;
  question?: string;
  term?: string;
  step?: string;
  answer?: string;
  definition?: string;
  description?: string;
  iri: string;
}

export interface NarrativeData {
  synopsis: { headline: string; abstract: string; iri: string } | null;
  faq: Array<{ question: string; answer: string; iri: string }>;
  glossary: Array<{ term: string; definition: string; iri: string }>;
  howto: Array<{ step: string; description: string; iri: string }>;
  people: Array<{ name: string; description: string; iri: string }>;
  organizations: Array<{ name: string; description: string; iri: string }>;
  sections: Array<{
    name: string;
    abstract: string;
    iri: string;
    items: Array<{ name: string; description: string; iri: string; position: number }>;
  }>;
}

// ── Parse helpers ─────────────────────────────────────────────────────────────

/** Parse an RDF file and return a populated n3 Store + prefix map. */
export function parseFile(rdfPath: string, format?: string): { store: Store; prefixes: Map<string, string> } {
  const content = readFileSync(rdfPath, "utf-8");
  return parseText(content, format ?? autoFormat(rdfPath));
}

export function parseText(content: string, format = "Turtle"): { store: Store; prefixes: Map<string, string> } {
  const store = new Store();
  const prefixes = new Map<string, string>();
  // n3 Parser is synchronous when given a string
  const parser = new Parser({ format: format as Parameters<typeof Parser>[0]["format"] });
  const quads = parser.parse(content, null, (prefix, ns) => {
    prefixes.set(prefix, ns.value);
  });
  store.addQuads(quads);
  return { store, prefixes };
}

function autoFormat(path: string): string {
  const ext = path.toLowerCase().split(".").pop() ?? "";
  return ({ ttl: "Turtle", n3: "N3", nt: "N-Triples", rdf: "application/rdf+xml", xml: "application/rdf+xml" } as Record<string, string>)[ext] ?? "Turtle";
}

// ── Label / description helpers ───────────────────────────────────────────────

function firstLiteral(store: Store, subject: Term, ...predicates: Term[]): string {
  for (const pred of predicates) {
    for (const obj of store.getObjects(subject, pred, null)) {
      if (obj.termType === "Literal") return obj.value;
    }
  }
  return "";
}

function shortenUri(uri: string, prefixes: Map<string, string>): string {
  for (const [prefix, ns] of prefixes) {
    if (uri.startsWith(ns)) return `${prefix}:${uri.slice(ns.length)}`;
  }
  if (uri.includes("#")) return uri.split("#").pop() ?? uri;
  return uri.split("/").pop() ?? uri;
}

function extractLabel(uri: string, store: Store, prefixes: Map<string, string>): string {
  const node = namedNode(uri);
  return firstLiteral(store, node, RDFS_LABEL, SCHEMA_NAME) || shortenUri(uri, prefixes);
}

function extractDescription(uri: string, store: Store): string {
  const node = namedNode(uri);
  // rdfs:comment / schema:description are short summaries; schema:text is the
  // body of HowToStep, Answer, etc. and must not be dropped when present.
  const desc = firstLiteral(store, node, RDFS_COMMENT, SCHEMA_DESCRIPTION, SCHEMA_TEXT);
  return desc.slice(0, 400);
}

function classifyNode(uri: string, store: Store): string {
  const node = namedNode(uri);
  const types = store.getObjects(node, RDF_TYPE, null).map(t => t.value);
  if (types.includes(RDFS_CLASS.value) || types.includes(OWL_CLASS.value)) return "Class";
  if (types.includes(RDF_PROPERTY.value) || types.includes(OWL_PROPERTY.value)) return "Property";
  // Check if used as predicate
  if (store.countQuads(null, node, null, null) > 0) return "Property";
  // Check if used as a class (something has rdf:type pointing to it)
  if (store.countQuads(null, RDF_TYPE, node, null) > 0) return "Class";
  // Check known class IRIs
  if (KNOWN_CLASS_IRIS.has(uri)) return "Instance";
  return "Instance";
}

// ── buildKgdata ───────────────────────────────────────────────────────────────

export function buildKgdata(rdfPath: string): KgData {
  const { store, prefixes } = parseFile(rdfPath);
  const nodesMap = new Map<string, KgNode>();
  const links: KgLink[] = [];

  for (const quad of store) {
    const { subject: s, predicate: p, object: o } = quad;
    if (s.termType === "BlankNode") continue;
    if (o.termType === "BlankNode") continue;

    const predShort = p.termType === "NamedNode" ? shortenUri(p.value, prefixes) : p.value;
    const subjId = s.termType === "NamedNode" ? s.value : `_:${(s as Term).value}`;
    const objId  = o.termType === "NamedNode" ? o.value : `_:${(o as Term).value}`;

    if (s.termType === "NamedNode" && !nodesMap.has(subjId)) {
      nodesMap.set(subjId, {
        id: subjId, group: classifyNode(subjId, store),
        label: extractLabel(subjId, store, prefixes),
        desc: extractDescription(subjId, store), iri: subjId,
      });
    }
    if (o.termType === "NamedNode" && !nodesMap.has(objId)) {
      nodesMap.set(objId, {
        id: objId, group: classifyNode(objId, store),
        label: extractLabel(objId, store, prefixes),
        desc: extractDescription(objId, store), iri: objId,
      });
    }
    if (p.termType === "NamedNode" && s.termType !== "Literal" && o.termType !== "Literal") {
      links.push({ source: subjId, target: objId, predicate: predShort, label: predShort });
    }
  }

  const nodes = [...nodesMap.values()];
  const incidentIds = new Set(links.flatMap(l => [l.source, l.target]));
  const orphans = nodes.filter(n => !incidentIds.has(n.id));
  if (orphans.length) {
    process.stderr.write(`Warning: ${orphans.length} orphan nodes found\n`);
  }

  return { nodes, links };
}

// ── extractNarrative ──────────────────────────────────────────────────────────

export function extractNarrative(rdfPath: string, _baseIri: string): NarrativeData {
  const { store, prefixes } = parseFile(rdfPath);
  const result: NarrativeData = {
    synopsis: null, faq: [], glossary: [], howto: [], people: [], organizations: [], sections: [],
  };

  // Synopsis: the main article/report entity — prefer schema:Article, then
  // any subject with the most schema:hasPart links (the de facto hub node).
  let mainEntity: Quad_Subject | null = null;
  for (const candidate of store.getSubjects(RDF_TYPE, SCHEMA_ARTICLE, null)) {
    mainEntity = candidate;
    break;
  }
  if (mainEntity === null) {
    let bestCount = -1;
    const seen = new Set<string>();
    for (const s of store.getSubjects(SCHEMA_HAS_PART, null, null)) {
      if (seen.has(s.value)) continue;
      seen.add(s.value);
      const count = store.getObjects(s, SCHEMA_HAS_PART, null).length;
      if (count > bestCount) {
        bestCount = count;
        mainEntity = s;
      }
    }
  }
  if (mainEntity !== null && mainEntity.termType === "NamedNode") {
    const headline = firstLiteral(store, mainEntity, SCHEMA_HEADLINE) || extractLabel(mainEntity.value, store, prefixes);
    let abstract = firstLiteral(store, mainEntity, SCHEMA_ABSTRACT);
    if (!abstract) {
      const body = firstLiteral(store, mainEntity, SCHEMA_ARTICLE_BODY);
      if (body) abstract = body.slice(0, 600);
    }
    if (headline || abstract) {
      result.synopsis = { headline, abstract, iri: mainEntity.value };
    }
  }

  // Generic narrative content sections (article-body substance beyond
  // FAQ/glossary/HowTo/People/Organizations) — mirrors rdf_parser.py so a
  // source's substantive narrative is never silently dropped just because
  // this document was generated via the Node/tsx toolchain instead of Python.
  if (mainEntity !== null) {
    const excludedTypes = new Set([SCHEMA_FAQPAGE.value, SCHEMA_DEFINED_TERM_SET.value, SCHEMA_HOWTO.value, OWL_ONTOLOGY.value]);
    const excludedIris = new Set<string>();
    for (const faq of store.getSubjects(RDF_TYPE, SCHEMA_FAQPAGE, null)) excludedIris.add(faq.value);
    for (const ts of store.getSubjects(RDF_TYPE, SCHEMA_DEFINED_TERM_SET, null)) excludedIris.add(ts.value);
    for (const ht of store.getSubjects(RDF_TYPE, SCHEMA_HOWTO, null)) excludedIris.add(ht.value);
    for (const onto of store.getSubjects(RDF_TYPE, OWL_ONTOLOGY, null)) excludedIris.add(onto.value);

    for (const part of store.getObjects(mainEntity, SCHEMA_HAS_PART, null)) {
      if (part.termType !== "NamedNode" || excludedIris.has(part.value)) continue;
      const partTypes = new Set(store.getObjects(part, RDF_TYPE, null).map(t => t.value));
      const isCreativeOrList = partTypes.has(SCHEMA_CREATIVE_WORK.value) || partTypes.has(SCHEMA_ITEM_LIST.value);
      const isExcludedType = [...excludedTypes].some(t => partTypes.has(t));
      if (!isCreativeOrList || isExcludedType) continue;

      const secName = extractLabel(part.value, store, prefixes);
      if (!secName) continue;
      const secAbstract = firstLiteral(store, part, SCHEMA_ABSTRACT) || firstLiteral(store, part, SCHEMA_DESCRIPTION);

      const childIris = new Set<string>();
      const childNodes = new Map<string, Quad_Subject | Quad_Object>();
      for (const child of store.getSubjects(SCHEMA_IS_PART_OF, part, null)) {
        childIris.add(child.value);
        childNodes.set(child.value, child);
      }
      for (const child of store.getObjects(part, SCHEMA_HAS_PART, null)) {
        childIris.add(child.value);
        childNodes.set(child.value, child);
      }
      for (const child of store.getObjects(part, SCHEMA_ITEM_LIST_ELEMENT, null)) {
        childIris.add(child.value);
        childNodes.set(child.value, child);
      }

      const items: Array<{ name: string; description: string; iri: string; position: number }> = [];
      for (const childIri of childIris) {
        if (childIri === part.value) continue;
        const child = childNodes.get(childIri)!;
        if (child.termType !== "NamedNode") continue;
        const childTypes = new Set(store.getObjects(child, RDF_TYPE, null).map(t => t.value));
        if (childTypes.has(SCHEMA_IMAGE_OBJECT.value) || childTypes.has(SCHEMA_VIDEO_OBJECT.value) || childTypes.has(SCHEMA_AUDIO_OBJECT.value)) continue;
        const cName = extractLabel(childIri, store, prefixes);
        if (!cName) continue;
        const cDesc = extractDescription(childIri, store);
        const posLit = firstLiteral(store, child, SCHEMA_POSITION);
        const cPos = posLit ? parseInt(posLit, 10) : NaN;
        items.push({ name: cName, description: cDesc, iri: childIri, position: Number.isNaN(cPos) ? 9999 : cPos });
      }
      items.sort((a, b) => a.position - b.position);

      if (secAbstract || items.length) {
        result.sections.push({ name: secName, abstract: secAbstract, iri: part.value, items });
      }
    }
  }

  // FAQ via FAQPage
  for (const faq of store.getSubjects(RDF_TYPE, SCHEMA_FAQPAGE, null)) {
    for (const qItem of store.getObjects(faq, SCHEMA_HAS_PART, null)) {
      if (qItem.termType !== "NamedNode") continue;
      const qText = extractLabel(qItem.value, store, prefixes);
      const aItems = store.getObjects(qItem, SCHEMA_ACCEPTED_ANSWER, null);
      for (const aItem of aItems) {
        const aText = firstLiteral(store, aItem, SCHEMA_TEXT, RDFS_COMMENT);
        if (qText && aText) {
          result.faq.push({ question: qText, answer: aText, iri: qItem.value });
        }
        break;
      }
    }
  }

  // FAQ fallback: direct Question nodes
  if (!result.faq.length) {
    for (const q of store.getSubjects(RDF_TYPE, SCHEMA_QUESTION, null)) {
      if (q.termType !== "NamedNode") continue;
      const qText = extractLabel(q.value, store, prefixes);
      for (const a of store.getObjects(q, SCHEMA_ACCEPTED_ANSWER, null)) {
        const aText = firstLiteral(store, a, SCHEMA_TEXT, RDFS_COMMENT);
        if (qText && aText) result.faq.push({ question: qText, answer: aText, iri: q.value });
        break;
      }
    }
  }

  // Glossary via DefinedTermSet
  for (const ts of store.getSubjects(RDF_TYPE, SCHEMA_DEFINED_TERM_SET, null)) {
    for (const term of store.getObjects(ts, SCHEMA_HAS_PART, null)) {
      if (term.termType !== "NamedNode") continue;
      const termText = extractLabel(term.value, store, prefixes);
      const termDesc = extractDescription(term.value, store);
      if (termText && termDesc) result.glossary.push({ term: termText, definition: termDesc, iri: term.value });
    }
  }

  // Glossary fallback: direct DefinedTerm nodes
  if (!result.glossary.length) {
    for (const term of store.getSubjects(RDF_TYPE, SCHEMA_DEFINED_TERM, null)) {
      if (term.termType !== "NamedNode") continue;
      const termText = extractLabel(term.value, store, prefixes);
      const termDesc = extractDescription(term.value, store);
      if (termText) result.glossary.push({ term: termText, definition: termDesc, iri: term.value });
    }
  }

  // HowTo
  for (const howto of store.getSubjects(RDF_TYPE, SCHEMA_HOWTO, null)) {
    for (const step of store.getObjects(howto, SCHEMA_STEP, null)) {
      if (step.termType !== "NamedNode") continue;
      const stepText = extractLabel(step.value, store, prefixes);
      const stepDesc = extractDescription(step.value, store);
      if (stepText) result.howto.push({ step: stepText, description: stepDesc, iri: step.value });
    }
  }

  // People
  for (const person of store.getSubjects(RDF_TYPE, SCHEMA_PERSON, null)) {
    if (person.termType !== "NamedNode") continue;
    const name = extractLabel(person.value, store, prefixes);
    if (name) result.people.push({ name, description: extractDescription(person.value, store), iri: person.value });
  }

  // Organizations
  for (const org of store.getSubjects(RDF_TYPE, SCHEMA_ORG, null)) {
    if (org.termType !== "NamedNode") continue;
    const name = extractLabel(org.value, store, prefixes);
    if (name) result.organizations.push({ name, description: extractDescription(org.value, store), iri: org.value });
  }

  return result;
}

// ── Utility exports ───────────────────────────────────────────────────────────

export function getBaseIri(rdfPath: string): string {
  const { store } = parseFile(rdfPath);
  for (const subject of store.getSubjects(null, null, null)) {
    if (subject.termType === "NamedNode") {
      const uri = subject.value;
      if (uri.includes("#")) return uri.split("#")[0] + "#";
      return uri.replace(/\/[^/]*$/, "/");
    }
  }
  return "https://linkedin.com/pulse/";
}

export function getEntityCount(rdfPath: string): number {
  const { store } = parseFile(rdfPath);
  return store.size;
}

export function validateOrphans(kgdata: KgData): string[] {
  const incident = new Set(kgdata.links.flatMap(l => [
    typeof l.source === "string" ? l.source : (l.source as { id: string }).id,
    typeof l.target === "string" ? l.target : (l.target as { id: string }).id,
  ]));
  return kgdata.nodes.filter(n => !incident.has(n.id)).map(n => n.id);
}

// ── CLI (mirrors rdf-parser.py) ───────────────────────────────────────────────

if (
  process.argv[1] &&
  (process.argv[1].endsWith("rdf_parser.ts") || process.argv[1].endsWith("rdf_parser.js"))
) {
  const argv = process.argv.slice(2);
  if (!argv.length) {
    process.stderr.write("Usage: npx tsx rdf_parser.ts <input.ttl> [--format turtle|nt|n3]\n");
    process.exit(1);
  }
  const inputFile = argv[0];
  let format = "Turtle";
  const fmtIdx = argv.indexOf("--format");
  if (fmtIdx >= 0 && argv[fmtIdx + 1]) format = argv[fmtIdx + 1];

  try {
    const kgdata = buildKgdata(inputFile);
    const { store, prefixes } = parseFile(inputFile, format);
    const entityTypes: Record<string, string[]> = {};
    for (const quad of store.match(null, RDF_TYPE, null, null)) {
      const t = quad.object.value;
      (entityTypes[t] ??= []).push(quad.subject.value);
    }
    const config = {
      ENTITY_TYPES: Object.keys(entityTypes).slice(0, 10),
      ENTITIES_COUNT: kgdata.nodes.length,
      RELATIONSHIPS_COUNT: kgdata.links.length,
    };
    process.stdout.write(JSON.stringify(config, null, 2) + "\n");
  } catch (err) {
    process.stderr.write(`Error: ${(err as Error).message}\n`);
    process.exit(1);
  }
}

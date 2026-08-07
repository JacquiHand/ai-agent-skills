---
name: resource-access-offers-generator
description: "Generate RDF Turtle offer/license/price bundles for File Access, Graph Access, and API Access products. Trigger on phrases like 'generate offers', 'create license bundle', 'make a file access offer', 'generate graph access offer', 'create API access offers', or any request to produce resource-access offers in Turtle format."
---
# Resource Access Offers Generator
Generate valid RDF Turtle documents containing File Access, Graph Access, or API Access offers.
## Minimum Input Requirements
| Input | Required | Example |
|-------|----------|---------|
| License resource IRI | Yes | URL of protected file/graph |
| Price | Yes | `2.99` |
| Description | Yes | Free text — name/prefLabel/comment auto-derived |
| Host platform | No (default: URIBurner) | `linkeddata.uriburner.com` |
## Host Platform Profiles
URIBurner (`linkeddata.uriburner.com`), ODS-QA (`ods-qa.openlinksw.com`), Localhost (`localhost`)
## Workflow
1. Elicit offer type (file/graph/api), host, license IRI, price, description
2. Derive name, prefLabel, comment from description
3. Load prompt template from `prompts/`
4. Substitute placeholders, generate Turtle
5. Validate syntax (rdflib), validate SHACL (`scripts/validate-offers-shacl.py`)
6. Run Post-Generation Checklist, save, provide loading instructions
## Document Metadata Block (source:)
Immediately after the `@prefix` declarations, every generated file MUST open with a `schema:CreativeWork` block describing **the Turtle file being generated itself** — never the licensed resource (file/graph/API being sold). Declare:
```turtle
@prefix source: <http://virtuoso.openlinksw.com/data/turtle/{output-filename}> .
@prefix :       <#> .

source: a schema:CreativeWork ;
    schema:name "{Document title}" ;
    schema:description "{What this document's offers cover}" ;
    schema:author <http://www.openlinksw.com/#this> ;
    cc:attributionName "OpenLink Software" ;
    schema:datePublished "{dateTime}"^^xsd:dateTime ;
    schema:dateModified "{dateTime}"^^xsd:dateTime .
```
`{output-filename}` is the actual filename this Turtle file will be saved as (matching the convention in the two prior art files: `http://virtuoso.openlinksw.com/data/turtle/FileAccessOffers-License-Prices.ttl`, `http://virtuoso.openlinksw.com/data/turtle/OPALOffers-Licenses-Prices-ods-qa-SPARQL-API.ttl`) — this host/path is fixed regardless of which host platform profile the licensed resource lives on.
Every generated Offer, License, and PriceSpecification node MUST carry `wdrs:describedby source:` pointing at this document node — that relation is what "identifies" the document as their source. The licensed resource itself is never separately described as a `schema:CreativeWork` — it's referenced only via `opllic:uriParameter`/`opllic:graphParameter`. The SHACL gate enforces `wdrs:describedby` (`sh:class schema:CreativeWork`) as required on Offer, License, and PriceSpecification shapes, and `DocumentShape` requires `schema:name`/`schema:author`/`schema:datePublished`/`schema:dateModified` on whatever node that resolves to.
## Entity IRI Naming Convention
The Offer, License, and PriceSpecification each get their own dedicated path segment — see `references/offer-iri-patterns.md` for the full template table and `host_suffix` derivation:
- PriceSpecification: `http://data.openlinksw.com/oplweb/offer-unitprice/{OfferIdentifier}PriceSpecification#this` — no host suffix.
- License: `http://data.openlinksw.com/oplweb/license/{OfferIdentifier}License{host_suffix}#this`
- Offer: `http://data.openlinksw.com/oplweb/offer/{OfferIdentifier}Offer{host_suffix}#this`

`{OfferIdentifier}` is a PascalCase name for the specific thing being offered (e.g. `DataTwinglerSpecificModuleEntryLevel`), derived from the offer's subject — not an ad-hoc slug and not reusing the Product's IRI shape. `{host_suffix}` is `host_short` with its first letter capitalized (`URIBurner` → `URIBurner`, `ods-qa` → `Ods-qa`, `localhost` → `Localhost`). The SHACL gate enforces the path segment and substring for each (`sh:pattern` on the shape itself, checked against the focus node's own IRI) — an Offer/License/PriceSpecification IRI that doesn't follow this shape now fails, even if every other property is correct.
## File Access Product (WebAPI) Description Template
The Product node for a **File Access** offer MUST follow this full template — not a minimal stub:
```turtle
<http://data.openlinksw.com/oplweb/{host_short}FA#this> a schema:WebAPI ;
    schema:name "File access via {host_short}"@en ;
    schema:applicationCategory "File Access"@en ;
    schema:applicationSubCategory "ACL controlled file access"@en ;
    schema:description """Attribute-based, access control constrained access to a File hosted by {host_hostname}."""@en ;
    skos:related <http://data.openlinksw.com/oplweb/{host_short}OPAL#this> ;
    schema:provider [
        a schema:Organization ;
        schema:name "OpenLink Software"@en ;
        schema:url <https://www.openlinksw.com/> ;
    ] ;
    schema:url <https://{host_hostname}/> ;
    schema:hasPart [
        a schema:WebAPI ;
        schema:name "WebDAV Service Endpoint"@en ;
        schema:description """WebDAV Endpoint for file interactions."""@en ;
        schema:serviceType "WebDAV Service"@en ;
        schema:url <https://{host_hostname}/DAV>
    ] .
```
Notes:
- All the literal values shown (`"File Access"@en`, `"ACL controlled file access"@en`, `"WebDAV Service"@en`) are fixed conventions, including the `@en` language tag — the gate checks exact term equality, so a plain string without the tag fails.
- `schema:url` on the top-level Product is the **host root** (`https://{host_hostname}/`), not the `/DAV` path — the `/DAV` endpoint belongs to the nested `schema:hasPart` sub-resource's `schema:url`.
- `skos:related` points at the OPAL ACL server Product (`http://data.openlinksw.com/oplweb/{host_short}OPAL#this`, see `references/offer-iri-patterns.md`) — required because an OPAL server is what actually creates the ACLs backing file access.
- The SHACL gate targets this shape via `sh:targetSubjectsOf schema:applicationCategory` rather than `sh:targetClass schema:WebAPI` — the nested WebDAV sub-resource is also `a schema:WebAPI` but has no `schema:applicationCategory`, so it's correctly excluded from this shape and validated only by its own (lighter) constraints (`schema:name`, `schema:description`, `schema:serviceType "WebDAV Service"@en`, `schema:url`).
## Auto-Derivation
- name: First sentence ≤80 chars
- pref_label: Abbreviated ≤60 chars
- comment: "Purchasing this offer grants {description}"
- description: The Offer node MUST also carry its own `schema:description` (distinct from `schema:comment` above) — required, e.g. "{Offer type} offer providing {description}." Omitting it is not just a SHACL gate failure: `OPLSHOP.DBA.offers_sparql_base()` in the live shop's `opl_shop_offer_ui.sql` requires `schema:description` as a non-optional triple in its main catalog listing query — an Offer without it is silently excluded from every offer listing in the shop, even though nothing else about the file is wrong.
- itemOffered: `schema:itemOffered` on the Offer MUST point at the **License** IRI (the `opllic:ProductLicense` node), never at the Product (the `schema:WebAPI` node). The shop's detail-population queries (`get_offer_info`, `get_offer_dbms_info`, `get_subscription_info`, `get_eval_action`, `get_service_uri` in `opl_shop_offer_ui.sql`) all do `?offer schema:itemOffered ?lic` and then read License-only properties off `?lic` (`schema:image`, `oplsof:hasOperatingSystemFamily`, `opllic:productLicenseOf`, `opllic:hasDuration`, ...). Pointing `itemOffered` at the Product instead makes every one of those AJAX calls return empty, breaking the offer card's detail rendering even if the offer otherwise appears in the catalog list.
- duration: If price is a recurring monthly price ("per month"), `opllic:hasDuration` MUST be the canonical `<http://data.openlinksw.com/oplweb/license/License-Duration#ongoing-subscription>` IRI (see `references/offer-iri-patterns.md`) — never invent/type a local Duration node.
- potentialAction: `schema:potentialAction` on the Offer MUST always be a direct "add to cart" IRI on the production shop, **regardless of which host platform profile the licensed resource itself lives on** (URIBurner, ODS-QA, Localhost — the cart is always `shop.openlinksw.com`): `https://shop.openlinksw.com/shop/cart.vsp?command=add&item={percent-encoded Offer IRI}`. Percent-encode the full Offer IRI (`:` → `%3A`, `/` → `%2F`, `#` → `%23`) as the `item` value. Never emit a blank-node `schema:Action`/`EntryPoint` structure — the shop's listing query reads `schema:potentialAction` as a flat triple and expects the value itself to be the clickable cart URL.
- subscription pricing: Whenever the input price is phrased as "per <unit>" (per month, per year, ...) — i.e. it recurs on a billing cadence rather than being a one-time charge — the PriceSpecification MUST carry `oplofr:interval "<unit>"^^xsd:string` (e.g. `"month"`) and `oplofr:intervalCount "<n>"^^xsd:integer` (e.g. `1`), and the Offer MUST carry an additional `rdf:type oplofr:SubscriptionOffer` alongside `schema:Offer` and the offer-type-specific classes (`oplofr:DAVOffer`/`oplofr:DemoFileAccessOffer` etc.). One-time, non-recurring prices carry neither `oplofr:interval` nor the `SubscriptionOffer` type. The SHACL gate enforces the pairing both ways: a PriceSpecification with `oplofr:interval` but no `oplofr:intervalCount` fails, and an Offer whose price has `oplofr:interval` but isn't typed `oplofr:SubscriptionOffer` fails.
- validity: Unless the user gives an explicit validity window, default `schema:validFrom` on **both** the Offer and its PriceSpecification to the file's creation date/time (the same instant used for the `source:` document's `schema:datePublished`), and default `schema:validThrough` to exactly 3 months after that. Keep the Offer's and the PriceSpecification's validity window identical to each other unless told otherwise.
- image: The License MUST carry `schema:image`. If the user doesn't specify a particular image for this offer, default to `<https://www.openlinksw.com/DAV/oplweb3/images/controlled-access-to-data-assets.jpg>`.
- license typing: Every License (File Access, Graph Access, or API Access — all three) MUST be typed with all four classes, not just `opllic:ProductLicense`: `a opllic:ProductLicense, opllic:Product, opllic:ACLOnly, opllic:SubscriptionLicense`. This applies regardless of whether the price is one-time or recurring. The SHACL gate checks each of the three extra types as an independent required value on `rdf:type` — a License missing any one of them fails, with a separate violation naming exactly which type is absent.
- priceCurrency literal form: `schema:priceCurrency` MUST always be written with an explicit `^^xsd:string` datatype annotation — `schema:priceCurrency "USD"^^xsd:string ;` — never the bare/plain form (`schema:priceCurrency "USD" ;`). This is a serialization convention only, not something the SHACL gate can check: a plain string and an explicitly-typed `"USD"^^xsd:string` are the same RDF term under RDF 1.1 simple-literal semantics, so `sh:datatype xsd:string` already accepts both and can't tell them apart. Get it right at generation time.
## GATE: 0 FAIL
`python3 scripts/validate-offers-shacl.py output.ttl --type {file|graph|api}` — must pass before delivery.
## Loading into Shop
```sql
SPARQL define get:soft "no-sponge" LOAD <file:///path/to/output.ttl> INTO <urn:opl:shop:offering:sponging:cache:official> ;
```
## License
AGPL-3.0

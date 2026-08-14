#!/usr/bin/env bash
# validate-kg-compliance.sh — Automated compliance audit for KG generator output
# Usage: ./validate-kg-compliance.sh <file.ttl|file.jsonld> [--turtle|--jsonld]

# NOTE: no `pipefail` — the checks below pipe a large $CONTENT into `grep -q`,
# which exits as soon as it finds a match. On large files that early exit can
# SIGPIPE the upstream `echo` before it finishes writing, and under pipefail
# that turns a real match into a false FAIL. Reproduced 2026-08-06 on an
# 83KB/2400-char-line Turtle file where `@prefix schema:` is a genuine, early,
# single-line match but the script still reported it missing.
set -eu

FILE="$1"
FORMAT="${2:-}"

if [ ! -f "$FILE" ]; then
  echo "ERROR: File not found: $FILE"
  exit 1
fi

# Auto-detect format from extension
if [ -z "$FORMAT" ]; then
  case "$FILE" in
    *.ttl)   FORMAT="--turtle" ;;
    *.jsonld) FORMAT="--jsonld" ;;
    *)       echo "ERROR: Cannot auto-detect format. Pass --turtle or --jsonld"; exit 1 ;;
  esac
fi

PASS=0
FAIL=0
CONTENT=$(cat "$FILE")

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== KG Compliance Audit: $FILE ==="
echo ""

if [ "$FORMAT" = "--turtle" ]; then
  # ── Turtle-specific checks ──

  # 1. schema: namespace is HTTP not HTTPS
  if echo "$CONTENT" | grep -q '@prefix[[:space:]]\+schema:[[:space:]]*<http://schema.org/>'; then
    pass "schema: namespace uses http://schema.org/"
  elif echo "$CONTENT" | grep -q '@prefix[[:space:]]\+schema:[[:space:]]*<https://schema.org/>'; then
    fail "schema: namespace uses https://schema.org/ (must be http://schema.org/)" "Change @prefix schema: <https://schema.org/> to <http://schema.org/>"
  else
    fail "schema: namespace not found or uses non-standard prefix" "Add @prefix schema: <http://schema.org/>"
  fi

  # 2. No file: scheme IRIs
  if echo "$CONTENT" | grep -q 'file://'; then
    fail "file: scheme IRIs found" "$(echo "$CONTENT" | grep -n 'file://' | head -3 | sed 's/^/    Line /')"
  else
    pass "No file: scheme IRIs"
  fi

  # 3. FAQPage wrapper with mainEntity
  if echo "$CONTENT" | grep -q 'schema:FAQPage'; then
    pass "schema:FAQPage present"
    if echo "$CONTENT" | grep -q 'schema:mainEntity'; then
      pass "FAQPage has schema:mainEntity"
    else
      fail "FAQPage missing schema:mainEntity" "Add schema:mainEntity listing all question IRIs"
    fi
  else
    fail "No schema:FAQPage wrapper" "Wrap all schema:Question entities in a schema:FAQPage"
  fi

  # 4. DefinedTermSet wrapper with hasDefinedTerm
  if echo "$CONTENT" | grep -q 'schema:DefinedTermSet'; then
    pass "schema:DefinedTermSet present"
    if echo "$CONTENT" | grep -q 'schema:hasDefinedTerm'; then
      pass "DefinedTermSet has schema:hasDefinedTerm"
    else
      fail "DefinedTermSet missing schema:hasDefinedTerm" "Add schema:hasDefinedTerm listing all term IRIs"
    fi
  else
    fail "No schema:DefinedTermSet wrapper" "Wrap all glossary terms in a schema:DefinedTermSet"
  fi

  # 5. Main article/report has schema:hasPart
  if echo "$CONTENT" | grep -q 'schema:hasPart'; then
    pass "Article has schema:hasPart"
  else
    fail "Article missing schema:hasPart" "Add schema:hasPart linking FAQPage, DefinedTermSet, and HowTo"
  fi
  # 5b. Ontology is linked via hasPart
  if echo "$CONTENT" | grep -q 'a owl:Ontology'; then
    # Find the ontology's own subject IRI (e.g. `:ontology` or bare `:`), then
    # confirm that exact token appears in some schema:hasPart list.
    ONT_SUBJECT=$(echo "$CONTENT" | grep -B5 'a owl:Ontology' | grep -oE '^:[A-Za-z0-9_]*|^\s*:\s' | tail -1 | tr -d ' ')
    if [ -z "$ONT_SUBJECT" ]; then
      ONT_SUBJECT=':'
    fi
    if echo "$CONTENT" | grep -A3 'schema:hasPart' | grep -qE "(^|[[:space:]])${ONT_SUBJECT}([[:space:]]|,|;|\))"; then
      pass "Ontology linked via schema:hasPart"
    else
      fail "Ontology not linked via schema:hasPart" "Add '${ONT_SUBJECT}' to the article's schema:hasPart list"
    fi
  fi

  # 6. owl:sameAs used for DBpedia (not schema:sameAs)
  if echo "$CONTENT" | grep -q 'schema:sameAs.*dbpedia'; then
    fail "schema:sameAs used for DBpedia links" "Replace schema:sameAs with owl:sameAs"
  else
    pass "No schema:sameAs for DBpedia"
  fi

  # 7. Prefix declarations use expanded IRIs for external namespaces
  if echo "$CONTENT" | grep -qE 'owl:[[:space:]]*<http://www.w3.org/2002/07/owl#>'; then
    pass "owl: namespace declared"
  else
    fail "owl: namespace not declared" "Add @prefix owl: <http://www.w3.org/2002/07/owl#>"
  fi

  # 8. @prefix : uses https: (not file:)
  BASE=$(echo "$CONTENT" | sed -n 's/.*@prefix[[:space:]]*:[[:space:]]*<\([^>]*\)>.*/\1/p' | head -1)
  if [ -n "$BASE" ]; then
    if echo "$BASE" | grep -q '^https\?://'; then
      pass "@prefix : uses $BASE"
    else
      fail "@prefix : uses non-HTTP scheme: $BASE" "Use the canonical https: URL of the source document"
    fi
  fi

  # 9. FAQ question count
  FAQ_COUNT=$(echo "$CONTENT" | grep -c 'a schema:Question' || true)
  if [ "$FAQ_COUNT" -ge 8 ]; then
    pass "FAQ question count: $FAQ_COUNT"
  else
    fail "FAQ question count: $FAQ_COUNT (should be >= 8)" "Add more schema:Question entities"
  fi

  # 10. HowTo steps (if present)
  HOWTO_COUNT=$(echo "$CONTENT" | grep -c 'a schema:HowToStep' || true)
  if [ "$HOWTO_COUNT" -gt 0 ]; then
    if echo "$CONTENT" | grep -q 'a schema:HowTo'; then
      pass "HowTo present ($HOWTO_COUNT steps)"
    else
      fail "HowToSteps present but no schema:HowTo wrapper" "Wrap steps in a schema:HowTo"
    fi
  fi

  # 11. Ontology: rdfs:isDefinedBy on classes and properties
  ONTOLOGY_COUNT=$(echo "$CONTENT" | grep -c 'a owl:Ontology' || true)
  if [ "$ONTOLOGY_COUNT" -gt 0 ]; then
    HAS_NAME=$(echo "$CONTENT" | grep -c 'schema:name' || true)
    HAS_DESC=$(echo "$CONTENT" | grep -c 'schema:description' || true)
    if [ "$HAS_NAME" -gt 0 ] && [ "$HAS_DESC" -gt 0 ]; then
      pass "Ontology has schema:name and schema:description"
    else
      fail "Ontology missing schema:name or schema:description" "Add schema:name and schema:description to the owl:Ontology"
    fi
    CLASS_COUNT=$(echo "$CONTENT" | grep -c 'a owl:Class' || true)
    PROP_COUNT=$(echo "$CONTENT" | grep -c 'a owl:ObjectProperty' || true)
    DEFINEDBY_COUNT=$(echo "$CONTENT" | grep -c 'rdfs:isDefinedBy' || true)
    NEEDED=$((CLASS_COUNT + PROP_COUNT))
    if [ "$DEFINEDBY_COUNT" -ge "$NEEDED" ]; then
      pass "All classes/properties have rdfs:isDefinedBy ($DEFINEDBY_COUNT/$NEEDED)"
    else
      fail "Missing rdfs:isDefinedBy ($DEFINEDBY_COUNT of $NEEDED classes/properties)" "Add rdfs:isDefinedBy : to each class and property"
    fi

    # 11b. Document entity (<>) must NOT duplicate the owl:Ontology entity's
    # schema:name/schema:description verbatim — they are two distinct entities
    # (the CreativeWork document vs. the OWL ontology it describes) and must
    # carry differentiated text: the document's name/description should read
    # as being ABOUT the ontology (e.g. "{Name} Document" / "Document about
    # ..."), not restate the ontology's own self-description.
    DOC_NAME=$(echo "$CONTENT" | grep -A3 '^<> a schema:CreativeWork' | grep 'schema:name' | head -1 | sed -n 's/.*schema:name *"\([^"]*\)".*/\1/p')
    ONT_NAME=$(echo "$CONTENT" | grep -B1 -A3 'a owl:Ontology' | grep 'schema:name' | head -1 | sed -n 's/.*schema:name *"\([^"]*\)".*/\1/p')
    if [ -n "$DOC_NAME" ] && [ -n "$ONT_NAME" ]; then
      if [ "$DOC_NAME" = "$ONT_NAME" ]; then
        fail "Document entity (<>) schema:name is identical to the owl:Ontology entity's schema:name ('$DOC_NAME')" "Differentiate: document entity name should read '{Ontology Name} Document' or similar, not restate the ontology's own name verbatim"
      else
        pass "Document entity and owl:Ontology entity have differentiated schema:name"
      fi
    fi

    # 11c. rdfs:isDefinedBy must point to the entity actually typed owl:Ontology,
    # not the bare `:` (empty-fragment `<#>`) IRI — `:` is a valid Turtle prefix
    # shorthand but is not itself typed owl:Ontology unless the ontology entity
    # IS minted at `<#>` with no local name. If the ontology is minted at a named
    # fragment (e.g. `:hospitalOS a owl:Ontology`), every `rdfs:isDefinedBy :` is
    # pointing at the wrong (untyped) resource.
    ONTOLOGY_SUBJECT=$(echo "$CONTENT" | grep -oE '^:[A-Za-z0-9_-]+ a owl:Ontology' | head -1 | sed -E 's/^(:[A-Za-z0-9_-]+).*/\1/')
    if [ -n "$ONTOLOGY_SUBJECT" ] && [ "$ONTOLOGY_SUBJECT" != ":" ]; then
      BARE_DEFINEDBY_COUNT=$(echo "$CONTENT" | grep -cE 'rdfs:isDefinedBy[[:space:]]*:[[:space:]]*\.' || true)
      if [ "$BARE_DEFINEDBY_COUNT" -gt 0 ]; then
        fail "rdfs:isDefinedBy points to the bare ':' (<#>) IRI in $BARE_DEFINEDBY_COUNT place(s), not to '$ONTOLOGY_SUBJECT' (the entity actually typed owl:Ontology)" "Replace 'rdfs:isDefinedBy : .' with 'rdfs:isDefinedBy $ONTOLOGY_SUBJECT .' throughout"
      else
        pass "rdfs:isDefinedBy correctly points to the owl:Ontology-typed entity ($ONTOLOGY_SUBJECT)"
      fi
    fi
  fi

  # 12. Undeclared prefixes — every CURIE used must have a @prefix declaration
  DECLARED=$(echo "$CONTENT" | sed -n 's/.*@prefix[[:space:]]*\([a-zA-Z0-9_-]*\):.*/\1/p' | sort -u)
  USED=$(echo "$CONTENT" | grep -oE '\b[a-zA-Z][a-zA-Z0-9_-]*:[a-zA-Z]' | sed 's/:.*//' | sort -u)
  UNDECLARED=""
  for p in $USED; do
    case "$p" in a|xsd|rdf|rdfs|owl|skos|schema|dct|foaf|prov|org|dcterms|dc) continue ;; esac  # well-known, check below
    if ! echo "$DECLARED" | grep -qx "$p"; then
      UNDECLARED="$UNDECLARED $p"
    fi
  done
  # Also check common prefixes that SHOULD be declared explicitly
  for p in rdf rdfs owl xsd skos schema dct foaf prov org; do
    if echo "$USED" | grep -qx "$p" && ! echo "$DECLARED" | grep -qx "$p"; then
      UNDECLARED="$UNDECLARED $p"
    fi
  done
  if [ -n "$UNDECLARED" ]; then
    fail "Undeclared prefix(es):$UNDECLARED — add @prefix declaration(s)" "Add: @prefix {prefix}: <{namespace}> . for each"
  else
    pass "All CURIE prefixes have @prefix declarations"
  fi

  # 13. Fully expanded DBpedia/Wikidata IRIs (not CURIEs)
  if echo "$CONTENT" | grep -qE 'dbo:|dbp:|dbr:|wd:|wdt:'; then
    CURIEs=$(echo "$CONTENT" | grep -nE 'dbo:|dbp:|dbr:|wd:|wdt:' | head -5)
    fail "Prefixed DBpedia/Wikidata CURIEs found (must be fully expanded)" "$CURIEs"
  else
    pass "No DBpedia/Wikidata CURIEs (all expanded)"
  fi

elif [ "$FORMAT" = "--jsonld" ]; then
  # ── JSON-LD-specific checks ──

  # 1. @base set
  if echo "$CONTENT" | grep -q '"@base"'; then
    pass "@base present"
  else
    fail "@base not set" "Add @base with the canonical source URL"
  fi

  # 2. schema: namespace HTTP not HTTPS
  if echo "$CONTENT" | grep -q '"schema":[[:space:]]*"http://schema.org/"'; then
    pass "schema: namespace uses http://schema.org/"
  elif echo "$CONTENT" | grep -q 'schema.*https://schema.org/'; then
    fail "schema: namespace uses https://schema.org/" "Change to http://schema.org/"
  fi

  # 3. FAQPage
  if echo "$CONTENT" | grep -q '"FAQPage"'; then
    pass "schema:FAQPage present"
  else
    fail "No schema:FAQPage" "Wrap questions in a FAQPage"
  fi

  # 4. DefinedTermSet
  if echo "$CONTENT" | grep -q '"DefinedTermSet"'; then
    pass "schema:DefinedTermSet present"
  else
    fail "No schema:DefinedTermSet" "Wrap glossary terms in a DefinedTermSet"
  fi

  # 5. hasPart
  if echo "$CONTENT" | grep -q '"hasPart"'; then
    pass "hasPart linking present"
  else
    fail "No hasPart" "Use hasPart to link FAQ, glossary, howto to article"
  fi

  # 6. owl:sameAs (not schema:sameAs)
  if echo "$CONTENT" | grep -q '"schema:sameAs".*dbpedia'; then
    fail "schema:sameAs used for DBpedia" "Replace with owl:sameAs"
  else
    pass "No schema:sameAs for DBpedia"
  fi

  # 7. Question count
  Q_COUNT=$(echo "$CONTENT" | grep -o '"Question"' | wc -l | tr -d ' ')
  if [ "$Q_COUNT" -ge 8 ]; then
    pass "Question count: $Q_COUNT"
  else
    fail "Question count: $Q_COUNT (should be >= 8)" "Add more Question entities"
  fi

  # 8. No file: IRIs
  if echo "$CONTENT" | grep -q 'file://'; then
    fail "file: scheme IRIs found"
  else
    pass "No file: scheme IRIs"
  fi

  # 9. owl:sameAs uses @id
  if echo "$CONTENT" | grep -q '"owl:sameAs".*\n.*@id'; then
    pass "owl:sameAs uses @id"
  elif echo "$CONTENT" | grep -q '"owl:sameAs"' && ! echo "$CONTENT" | grep -q '"owl:sameAs".*@id'; then
    fail "owl:sameAs may have plain literal values" "Use @id for owl:sameAs values"
  else
    pass "No owl:sameAs issues detected"
  fi
fi

# ── Common checks for both formats ──

# Smart quotes check
if echo "$CONTENT" | grep -q $'\xe2\x80\x9c\|\xe2\x80\x9d'; then
  fail "Smart/curly quotes found" "$(echo "$CONTENT" | grep -n $'\xe2\x80\x9c' | head -3)"
else
  pass "No smart/curly quotes"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo "COMPLIANCE: FAIL ($FAIL issue(s) to fix)"
  exit 1
else
  echo "COMPLIANCE: PASS"
  exit 0
fi

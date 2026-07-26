# Using These Skills

These are standard `SKILL.md` folders and ZIP bundles that can be loaded into an AI agent environment that supports Skills. The enablement process is as follows:

1. Ask the host environment to load the skills bundle ZIP (or folder) from its URL (`file:` for local reference) or local path.

2. To install the plugin, place the plugin directory in the `.agents/plugins` directory of your AI agent environment. Activate it by adding its metadata to the `marketplace.json` file in the same directory.
2. Test the skill using the usage example documented in the `SKILL.md` file.
3. Add it to a workflow schedule if the skill needs to run in automated form on a daily, weekly, or monthly basis.

## Quick Start

### 1. Load Skills

Ask your AI agent environment to load each skill from its ZIP or directory path:

```
file:///path/to/ai-agent-skills/<skill-name>.zip
file:///path/to/ai-agent-skills/<skill-name>/
```

### 2. Agent Memory Setup

The `agent-rdf-memory/` directory is the canonical behavioral contract.
Execute this retrieval sequence **before any task**:

1. List `agent-rdf-memory/` and subfolders (`sessions/`, `projects/`, `entities/`)
2. Read `core.ttl` (user identity, output paths)
3. Read `preferences.ttl` (operational rules)
4. Read `preferences.private.ttl` if present (private overlay)
5. Read `ontology.ttl` (prompt-intent routing)
6. Read `index.ttl` (session pointers)
7. Follow `rdfs:seeAlso` references to relevant `howto/*.ttl`
8. Reason over loaded Turtle content
9. Write session memory on trigger events (see `ontology.ttl#MemoryWriteTrigger`)

### 3. Agent Identity Resolution

At session start, resolve:

- **Agent environment**: `{AGENT_ENV_NAME}` (e.g., `claude_code`, `opencode`)
- **LLM model**: `{LLM_MODEL}` from the system prompt
- **Output path**: from `core.ttl` output path entries

These feed artifact routing and `whoami` responses.

### 4. Claude Code Hook (Optional)

For automatic memory injection, set up the SessionStart hook per
`agent-rdf-memory/SESSION-START-HOOK.md`. This reads memory files before
the first user turn.

### 5. Verify

Run `whoami` to confirm identity resolution and output path routing are correct.

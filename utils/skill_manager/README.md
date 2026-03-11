# skill-manager

LLM-driven creator and updater for [agentskills.io](https://agentskills.io/specification)-compliant skills.

## Architecture

```
skill-manager/
├── skill_manager/
│   ├── __init__.py      # Public API
│   ├── models.py        # Skill, SkillFrontmatter, UpdateResult
│   ├── validator.py     # Spec compliance checks
│   ├── backup.py        # Timestamped backup/rollback
│   ├── llm_client.py    # All Anthropic API calls (one place)
│   ├── creator.py       # SkillCreator — new skills from docs or scratch
│   ├── updater.py       # SkillUpdater — update existing skills from context
│   ├── scanner.py       # SkillScanner — scan a directory, update relevant skills
│   └── cli.py           # CLI entry point
├── examples/
│   └── sample-skill/    # Valid sample SKILL.md for testing
├── tests/
│   └── test_skill_manager.py
└── pyproject.toml
```

## Installation

Install core + your chosen provider:

```bash
# Core (required)
pip install langchain langchain-core pyyaml
pip install -e .

# Pick ONE (or more) provider SDK:
pip install langchain-anthropic    # Anthropic Claude  (ANTHROPIC_API_KEY)
pip install langchain-openai       # OpenAI / Azure    (OPENAI_API_KEY)
pip install langchain-google-genai # Google Gemini     (GOOGLE_API_KEY)
pip install langchain-groq         # Groq              (GROQ_API_KEY)
pip install langchain-ollama       # Ollama local      (no key needed)
pip install langchain-mistralai    # Mistral           (MISTRAL_API_KEY)

# Or install all provider extras at once:
pip install "skill-manager[all]"
```

Set your provider API key (LangChain picks it up automatically):

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # for anthropic
export OPENAI_API_KEY=sk-...          # for openai
# etc.
```

Optionally pin provider + model via env vars (useful in Docker/agent deployments):

```bash
export SKILL_MANAGER_PROVIDER=groq
export SKILL_MANAGER_MODEL=llama3-70b-8192
```

## Usage

### Python API

**Create a skill from a document:**
```python
from pathlib import Path
from skill_manager import SkillCreator

# Default provider (anthropic) — reads ANTHROPIC_API_KEY automatically
creator = SkillCreator()

# Or pick any provider/model at construction time:
creator = SkillCreator(provider="openai", model="gpt-4o")
creator = SkillCreator(provider="ollama", model="llama3")        # local, no key
creator = SkillCreator(provider="groq",  model="llama3-70b-8192")

skill_path = creator.from_document(
    document=Path("juniper-mist-api-docs.txt").read_text(),
    skill_name="juniper-mist-wifi-api",
    output_dir=Path("skills"),
    author="my-org",
)
```

**Create a skill from scratch:**
```python
skill_path = creator.from_scratch(
    skill_name="my-noc-runbook",
    description="Step-by-step NOC procedures for common network incidents. "
                "Use when an alert fires or an incident is declared.",
    body_markdown=Path("runbook.md").read_text(),
    output_dir=Path("skills"),
)
```

**Update a skill from agent context:**
```python
from skill_manager import SkillUpdater

updater = SkillUpdater()                                  # uses env defaults
updater = SkillUpdater(provider="openai", model="gpt-4o") # explicit

result = updater.update_from_context(
    skill_path=Path("skills/juniper-mist-wifi-api"),
    context="""
        Agent output: Mist API confirmed.
        Org ID: abc-1234-def
        Base URL: https://api.eu.mist.com/api/v1
        Auth scheme: Token (not Bearer)
    """,
)
print(result)  # Updated 'juniper-mist-wifi-api': Found new org ID and base URL
```

**Dry-run to preview changes:**
```python
result = updater.update_from_context(
    skill_path=Path("skills/my-skill"),
    context="...",
    dry_run=True,
)
# File is NOT written; result.updated tells you if it would have been
```

**Rollback:**
```python
updater.rollback(Path("skills/my-skill"))          # latest backup
updater.rollback(Path("skills/my-skill"), steps=2) # two versions back
```

**Scan a whole skills directory:**
```python
from skill_manager import SkillScanner

scanner = SkillScanner(skills_dir=Path("skills"))
results = scanner.scan_and_update(context=agent_output_text)
print(scanner.report(results))
```

**Validate:**
```python
from skill_manager import validate_skill, SkillValidationError

try:
    validate_skill(Path("skills/my-skill"))
    print("Valid!")
except SkillValidationError as e:
    print(e)
```

### CLI

`--provider` and `--model` are global flags available on every subcommand.
If omitted, values fall back to `SKILL_MANAGER_PROVIDER` / `SKILL_MANAGER_MODEL` env vars,
then the built-in defaults (`anthropic` / `claude-sonnet-4-20250514`).

```bash
# Create from a document — default provider
skill-manager create juniper-mist-wifi-api ./skills --document api-docs.txt

# Same, but using OpenAI
skill-manager --provider openai --model gpt-4o create juniper-mist-wifi-api ./skills --document api-docs.txt

# Local Ollama (no API key needed)
skill-manager --provider ollama --model llama3 create my-skill ./skills --document docs.txt

# Update from a context file
skill-manager update ./skills/my-skill --context-file agent-output.txt

# Dry run with Groq
skill-manager --provider groq --model llama3-70b-8192 update ./skills/my-skill --context-file out.txt --dry-run

# Scan all skills
skill-manager scan ./skills --context-file agent-output.txt

# Validate (no LLM needed)
skill-manager validate ./skills/my-skill

# Rollback
skill-manager rollback ./skills/my-skill
skill-manager rollback ./skills/my-skill --steps 3

# List backups
skill-manager backups ./skills/my-skill
```

## Design decisions

| Concern | Approach |
|---|---|
| Detection | LLM returns JSON `{should_update, reason, extracted_facts}` |
| Extraction | LLM extracts facts generically — no regex per domain |
| Writing | LLM rewrites the relevant section — no surgical line splicing |
| Provider | LangChain `init_chat_model` — swap provider/model with one arg |
| Config | No sidecar YAML — settings in code defaults, env vars, or `metadata:` |
| Frontmatter | Spec-compliant: custom keys live under `metadata:` |
| Portability | Works with any valid agentskills.io SKILL.md |

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```

Tests mock all LLM calls so no API key is needed.

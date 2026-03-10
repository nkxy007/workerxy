"""
LLM client - all model interactions via LangChain init_chat_model.

Provider and model are fully swappable at runtime via constructor args
or environment variables. No hard dependency on any specific provider SDK
beyond what LangChain lazy-loads.

Supported providers (install the matching extras):
  anthropic   pip install langchain-anthropic
  openai      pip install langchain-openai
  google      pip install langchain-google-genai
  ollama      pip install langchain-ollama          (local, no API key needed)
  groq        pip install langchain-groq
  mistralai   pip install langchain-mistralai
  cohere      pip install langchain-cohere
  ... any provider supported by langchain's init_chat_model

Environment variable configuration (all optional):
  SKILL_MANAGER_PROVIDER   e.g. "anthropic", "openai", "ollama"
  SKILL_MANAGER_MODEL      e.g. "claude-sonnet-4-20250514", "gpt-4o", "llama3"
  ANTHROPIC_API_KEY / OPENAI_API_KEY / etc. — picked up automatically by LangChain

Usage:
    # Default (anthropic / claude-sonnet-4-20250514)
    client = LLMClient()

    # Switch provider + model at construction
    client = LLMClient(provider="openai", model="gpt-4o")

    # Local Ollama — no API key needed
    client = LLMClient(provider="ollama", model="llama3")

    # Via env vars (useful for Docker / agent deployments)
    # SKILL_MANAGER_PROVIDER=groq SKILL_MANAGER_MODEL=llama3-70b-8192
    client = LLMClient()
"""

import json
import logging
import os
import re
from typing import Any, Optional

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# ── Defaults (overridable via env or constructor) ─────────────────────────────
DEFAULT_SKILL_PROVIDER = "openai"
DEFAULT_SKILL_MODEL = "gpt-5-mini"

# ── Token / char budgets ──────────────────────────────────────────────────────
MAX_TOKENS_DETECT = 600
MAX_TOKENS_REWRITE = 4096
MAX_TOKENS_CREATE = 4096
MAX_TOKENS_DESCRIBE = 400

BODY_CHAR_LIMIT = 12_000
CONTEXT_CHAR_LIMIT = 8_000
DOC_CHAR_LIMIT = 12_000

# ── agentskills.io spec summary (injected into prompts) ───────────────────────
SKILL_SPEC = """
agentskills.io SKILL.md specification (mandatory fields):

FRONTMATTER (YAML between --- delimiters):
  name        REQUIRED. 1-64 chars. Lowercase a-z, digits, hyphens only.
              No leading/trailing/consecutive hyphens. Must match directory name.
  description REQUIRED. 1-1024 chars. Describe WHAT the skill does AND WHEN to
              use it. Include keywords agents can match against user requests.
  license     Optional. Short string.
  compatibility Optional. 1-500 chars. Describe environment requirements.
  metadata    Optional. Key-value mapping for extra properties.
  allowed-tools Optional. Space-delimited list of pre-approved tools.

BODY (after frontmatter):
  Must not be empty. Should contain: step-by-step instructions, examples,
  common edge cases. Written for an AI agent, not a human.

Non-spec top-level keys are NOT allowed — put custom fields under metadata:
"""


class LLMClient:
    """
    Provider-agnostic LLM wrapper built on LangChain's init_chat_model.

    All public methods accept plain strings and return plain Python objects —
    callers never touch LangChain internals directly.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **model_kwargs,
    ):
        """
        Args:
            provider:     LangChain provider string, e.g. "anthropic", "openai",
                          "ollama", "groq". Falls back to SKILL_MANAGER_PROVIDER
                          env var, then DEFAULT_SKILL_PROVIDER.
            model:        Model name understood by the provider, e.g. "gpt-4o",
                          "claude-sonnet-4-20250514", "llama3".
                          Falls back to SKILL_MANAGER_MODEL env var, then
                          DEFAULT_SKILL_MODEL.
            **model_kwargs: Extra kwargs forwarded to init_chat_model
                          (e.g. temperature=0, timeout=30).
        """
        self._provider = (
            provider
            or os.environ.get("SKILL_MANAGER_PROVIDER")
            or DEFAULT_SKILL_PROVIDER
        )
        self._model = (
            model
            or os.environ.get("SKILL_MANAGER_MODEL")
            or DEFAULT_SKILL_MODEL
        )
        self._model_kwargs = model_kwargs

        logger.debug(f"LLMClient initialised: provider={self._provider!r} model={self._model!r}")
        self._llm = self._build_llm()

    # ── Public API ────────────────────────────────────────────────────────────

    def detect_new_info(self, skill_body: str, context: str) -> dict:
        """
        Ask the LLM whether the context contains new information
        worth adding to this skill.

        Returns dict with keys:
          should_update (bool), reason (str), extracted_facts (list[str])
        """
        prompt = f"""You are a skill document curator. Decide if the context below contains
NEW factual information that is not already in the skill body, and that would make the skill
more useful to future agents.

Only flag an update if the new info is concrete and durable (device names, endpoints,
API patterns, procedures, credentials patterns, tool URLs, config details, etc.).
Ignore conversational filler, already-known facts, or vague statements.

<skill_body>
{skill_body[:BODY_CHAR_LIMIT]}
</skill_body>
Here is the new context from which you can extract info to update the skill body.
<new_context>
{context[:CONTEXT_CHAR_LIMIT]}
</new_context>

Respond with ONLY valid JSON (no markdown fences, no extra text):
{{
  "should_update": true | false,
  "reason": "<one sentence>",
  "extracted_facts": ["<fact 1>", "<fact 2>"]
}}"""

        return self._json_call(
            prompt,
            max_tokens=MAX_TOKENS_DETECT,
            fallback={"should_update": False, "reason": "LLM call failed", "extracted_facts": []},
        )

    def rewrite_body(self, skill_body: str, facts: list[str], skill_name: str) -> str:
        """
        Produce an updated SKILL.md body incorporating the new facts.
        Returns only the markdown body (no frontmatter).
        """
        facts_block = "\n".join(f"- {f}" for f in facts)
        prompt = f"""You are updating the SKILL.md for skill '{skill_name}'.

Current body:
<skill_body>
{skill_body[:BODY_CHAR_LIMIT]}
</skill_body>

New facts to incorporate:
{facts_block}

Rules:
1. Preserve ALL existing content.
2. Add new facts into the most appropriate existing section, or create a new section if none fits.
3. Use clear, concise technical writing — this is read by an AI agent, not a human.
4. Keep the total under 500 lines.
5. Output ONLY the updated markdown body — no frontmatter, no code fences, no explanation."""

        return self._text_call(prompt, max_tokens=MAX_TOKENS_REWRITE)

    def create_skill_body(self, document: str, skill_name: str, description: str) -> str:
        """
        Generate a SKILL.md body from a source document.
        Returns only the markdown body (no frontmatter).
        """
        prompt = f"""Create a SKILL.md body for a skill named '{skill_name}'.
{SKILL_SPEC}
Skill description: {description}

Source document to extract instructions from:
<document>
{document[:DOC_CHAR_LIMIT]}
</document>

Rules:
1. Write clear step-by-step instructions an AI agent can follow.
2. Include: overview, prerequisites (if any), step-by-step instructions, common edge cases.
3. Use concrete examples where helpful.
4. Keep under 500 lines.
5. Output ONLY the markdown body — no frontmatter, no code fences, no explanation."""

        return self._text_call(prompt, max_tokens=MAX_TOKENS_CREATE)

    def suggest_description(self, document: str, skill_name: str) -> str:
        """Generate a spec-compliant description (≤ 1024 chars) from a document."""
        prompt = f"""Write a description for an agentskills.io skill named '{skill_name}'.
{SKILL_SPEC}
Source document excerpt:
<document>
{document[:4000]}
</document>

Rules:
- Max 1024 characters (HARD LIMIT — the system will reject longer descriptions)
- Min 20 characters
- Describe WHAT the skill does and WHEN to use it
- Include specific keywords that help agents identify relevant tasks
- Output ONLY the description text, nothing else"""

        return self._text_call(prompt, max_tokens=MAX_TOKENS_DESCRIBE)[:1024]

    def fix_body(self, bad_body: str, errors: list[str], skill_name: str) -> str:
        """
        Ask the LLM to fix a previously generated body that failed validation.
        Sends the bad output + exact error list back as feedback.
        Returns a corrected markdown body (no frontmatter).
        """
        error_block = "\n".join(f"  • {e}" for e in errors)
        prompt = f"""The SKILL.md body you generated for skill '{skill_name}' failed \
agentskills.io spec validation.
{SKILL_SPEC}
Validation errors found:
{error_block}

Your previous (invalid) output:
<bad_body>
{bad_body[:BODY_CHAR_LIMIT]}
</bad_body>

Fix EVERY error listed above. Produce a corrected body that passes all spec rules.
Output ONLY the corrected markdown body — no frontmatter, no code fences, no explanation."""

        return self._text_call(prompt, max_tokens=MAX_TOKENS_REWRITE)

    def fix_description(self, bad_desc: str, errors: list[str], skill_name: str) -> str:
        """
        Ask the LLM to fix a previously generated description that failed validation.
        Returns a corrected description string (≤ 1024 chars).
        """
        error_block = "\n".join(f"  • {e}" for e in errors)
        prompt = f"""The description you generated for agentskills.io skill '{skill_name}' \
failed spec validation.
{SKILL_SPEC}
Validation errors found:
{error_block}

Your previous (invalid) description:
<bad_description>
{bad_desc[:2000]}
</bad_description>

Write a corrected description that passes all rules.
HARD LIMITS: 20-1024 characters, describes what the skill does AND when to use it.
Output ONLY the description text, nothing else."""

        return self._text_call(prompt, max_tokens=MAX_TOKENS_DESCRIBE)[:1024]

    # ── Provider info ─────────────────────────────────────────────────────────

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def __repr__(self) -> str:
        return f"LLMClient(provider={self._provider!r}, model={self._model!r})"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_llm(self):
        """
        Construct the LangChain chat model.

        init_chat_model signature:
          init_chat_model(model, model_provider, **kwargs)

        It lazy-imports the provider SDK, so only the SDK for the chosen
        provider needs to be installed.
        """
        return init_chat_model(
            self._model,
            model_provider=self._provider,
            **self._model_kwargs,
        )

    def _invoke(self, prompt: str, max_tokens: int) -> str:
        """Send a single human message and return the response text."""
        # Bind max_tokens per-call so different methods can use different limits
        llm = self._llm.bind(max_tokens=max_tokens)
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def _text_call(self, prompt: str, max_tokens: int) -> str:
        """Call the LLM and return plain text. Raises on failure."""
        try:
            return self._invoke(prompt, max_tokens).strip()
        except Exception as exc:
            logger.error(f"LLM text call failed ({self._provider}/{self._model}): {exc}")
            raise

    def _json_call(self, prompt: str, max_tokens: int, fallback: Any) -> Any:
        """Call the LLM, parse JSON response. Returns fallback on any failure."""
        try:
            raw = self._invoke(prompt, max_tokens).strip()
            # Strip accidental markdown fences that some models add
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error(f"JSON parse failed: {exc} — raw response: {raw!r}")
            return fallback
        except Exception as exc:
            logger.error(f"LLM JSON call failed ({self._provider}/{self._model}): {exc}")
            return fallback

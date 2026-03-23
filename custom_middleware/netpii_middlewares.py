"""PII Pseudonymization Middleware.

This middleware masks PII in user input before the LLM sees it, while
saving a reversible mapping so that placeholders can be decoded for tool
invocations after the model step. Inspired by 'PIIMiddleware' in
`middle.py`, but designed for reversible pseudonymization.

Key behaviors:
- before_model: Replace PII in the last HumanMessage with placeholders like
  "<<pii:email:1>>" and store the placeholder-original map in the agent state
  under key `_pii_pseudonym_map`.
- after_model: Keep AI message content masked for logs/UI, but decode any
  tool call arguments to their original values so tools receive accurate input.
- Utilities `pseudonymize_text` and `depseudonymize_text` are exported for use
  in custom tool chains if needed.

Notes:
- If LangChain/LangGraph imports are unavailable at import time, the module
  provides no-op shims to allow running the demo utilities. In agent runtime,
  ensure LangChain and LangGraph are installed so hooks and message types work.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple
import logging

logger = logging.getLogger(__name__)

# --- Optional imports with shims for demo compatibility ---
try:  # Message types (LangChain Core)
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
except Exception:  # pragma: no cover - demo fallback
    @dataclass
    class _Msg:
        content: Any
        id: Optional[str] = None
        name: Optional[str] = None
        tool_calls: Optional[Any] = None
        tool_call_id: Optional[str] = None

    class AIMessage(_Msg):
        pass

    class HumanMessage(_Msg):
        pass

    class ToolMessage(_Msg):
        pass

try:  # Agent middleware base from LangChain agents
    from langchain.agents.middleware import AgentMiddleware  # type: ignore
except Exception:  # pragma: no cover - demo fallback
    class AgentMiddleware:
        def __init__(self) -> None:
            pass

try:  # Runtime from LangGraph
    from langgraph.runtime import Runtime as LangGraphRuntime  # type: ignore
    Runtime = LangGraphRuntime
except Exception:  # pragma: no cover - fallback
    Runtime = Any

# Type aliases to avoid coupling to specific agent state types
AgentState = MutableMapping[str, Any]
Runtime = Any


# ─────────────────────────────────── PII Detectors ──────────────────────────────────

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IP_RE = re.compile(r"\b(?:(?:1\d{2}|2[0-4]\d|25[0-5]|[1-9]?\d)\.){3}(?:1\d{2}|2[0-4]\d|25[0-5]|[1-9]?\d)\b")
# Match both standard format (aa:bb:cc:dd:ee:ff) and Cisco format (aabb.ccdd.eeff)
MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b|\b(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}\b")
URL_RE = re.compile(r"\bhttps?://[^\s]+|www\.[^\s]+")
CC_RE = re.compile(r"\b(?:[0-9]{4}[-\s]?){3}[0-9]{4}\b")


def _valid_ipv4(s: str) -> bool:
    try:
        parts = s.split(".")
        if len(parts) != 4:
            return False
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
    except Exception:
        return False


def _luhn_check(digits: str) -> bool:
    s = 0
    alt = False
    for ch in reversed(digits):
        if not ch.isdigit():
            return False
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        s += n
        alt = not alt
    return s % 10 == 0


def _find_emails(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    return [(m.group(0), (m.start(), m.end())) for m in EMAIL_RE.finditer(text)]


def _find_ips(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    out: List[Tuple[str, Tuple[int, int]]] = []
    for m in IP_RE.finditer(text):
        ip = m.group(0)
        if _valid_ipv4(ip):
            out.append((ip, (m.start(), m.end())))
    return out


def _find_macs(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    return [(m.group(0), (m.start(), m.end())) for m in MAC_RE.finditer(text)]


def _find_urls(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    return [(m.group(0), (m.start(), m.end())) for m in URL_RE.finditer(text)]


def _find_credit_cards(text: str) -> List[Tuple[str, Tuple[int, int]]]:
    out: List[Tuple[str, Tuple[int, int]]] = []
    for m in CC_RE.finditer(text):
        raw = m.group(0)
        digits = re.sub(r"[^0-9]", "", raw)
        if 13 <= len(digits) <= 19 and _luhn_check(digits):
            out.append((raw, (m.start(), m.end())))
    return out


PII_DETECTORS: Mapping[str, Callable[[str], List[Tuple[str, Tuple[int, int]]]]] = {
    "email": _find_emails,
    "ip": _find_ips,
    "mac_address": _find_macs,
    "url": _find_urls,
    "credit_card": _find_credit_cards,
}


def pseudonymize_text(
    text: str,
    pii_types: Sequence[str] | str = "all",
    placeholder_prefix: str = "pii",
    existing_mapping: Optional[Dict[str, str]] = None,
) -> Tuple[str, Dict[str, str]]:
    """Replace PII in text with placeholders and return mapping.

    Returns (masked_text, mapping) where mapping is {placeholder: original}.
    """
    if pii_types == "all":
        types = list(PII_DETECTORS.keys())
    else:
        types = [t for t in pii_types if t in PII_DETECTORS]

    mapping = existing_mapping if existing_mapping is not None else {}
    
    # Invert mapping to check if a value is already masked
    value_to_placeholder = {v: k for k, v in mapping.items()}
    
    # Re-calculate counters based on existing mapping
    counters: Dict[str, int] = {t: 0 for t in types}
    for token in mapping:
        parts = token.strip("<>").split(":")
        if len(parts) >= 3 and parts[1] in counters:
            idx = int(parts[2])
            counters[parts[1]] = max(counters[parts[1]], idx)

    # Collect matches per type with spans to prevent overlapping mishandling
    matches: List[Tuple[int, int, str, str]] = []  # (start, end, type, value)
    for t in types:
        detector = PII_DETECTORS[t]
        for val, (start, end) in detector(text):
            matches.append((start, end, t, val))

    if not matches:
        return text, mapping

    # Sort by start position to replace safely
    matches.sort(key=lambda x: (x[0], x[1]))

    out = []
    last_idx = 0

    # Walk the string to avoid overlaps
    for start, end, t, val in matches:
        # Skip overlaps already covered
        if start < last_idx:
            continue
        # Append gap
        out.append(text[last_idx:start])
        
        if val in value_to_placeholder:
            token = value_to_placeholder[val]
        else:
            counters[t] += 1
            token = f"<<{placeholder_prefix}:{t}:{counters[t]}>>"
            mapping[token] = val
            value_to_placeholder[val] = token
            
        out.append(token)
        last_idx = end

    out.append(text[last_idx:])
    return "".join(out), mapping


def depseudonymize_text(text: str, mapping: Mapping[str, str]) -> str:
    """Replace placeholders back to originals using the provided mapping."""
    if not mapping:
        return text
    # Sort tokens by length desc to avoid partial collisions
    for token in sorted(mapping.keys(), key=len, reverse=True):
        text = text.replace(token, mapping[token])
    return text


def _deep_decode(obj: Any, mapping: Mapping[str, str]) -> Any:
    """Recursively decode placeholders inside common container types."""
    if isinstance(obj, str):
        return depseudonymize_text(obj, mapping)
    if isinstance(obj, list):
        return [_deep_decode(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _deep_decode(v, mapping) for k, v in obj.items()}
    return obj


class PIIPseudonymizationMiddleware(AgentMiddleware):
    """Mask PII before the model and decode placeholders for tool calls.

    - Input side (before_model): replaces PII in the last `HumanMessage` with
      placeholders, stores `_pii_pseudonym_map` in the agent state.
    - Output side (after_model): keeps AI content masked; but decodes any
      `tool_calls` arguments so tools receive accurate parameters.

    Configuration:
    - `pii_types`: Iterable of PII types to mask, or "all" (default).
    - `placeholder_prefix`: Token prefix, default "pii".
    - `apply_to_input`: Whether to mask last HumanMessage (default True).
    - `apply_to_output`: Whether to decode placeholders in last AI message content (default False).
    - `apply_to_tool_results`: Whether to decode placeholders in `ToolMessage` content before the next model call (default False).
    - `decode_tool_calls`: Whether to decode placeholders in AI `tool_calls` (default True).
    """

    def __init__(
        self,
        pii_types: Sequence[str] | str = "all",
        *,
        placeholder_prefix: str = "pii",
        apply_to_input: bool = True,
        apply_to_output: bool = False,
        apply_to_tool_results: bool = False,
        decode_tool_calls: bool = True,
    ) -> None:
        super().__init__()
        self.pii_types = pii_types
        self.placeholder_prefix = placeholder_prefix
        self.apply_to_input = apply_to_input
        self.apply_to_output = apply_to_output
        self.apply_to_tool_results = apply_to_tool_results
        self.decode_tool_calls = decode_tool_calls

    @property
    def name(self) -> str:
        # Unique, safe name derived from configuration without reserved characters.
        # Use a short hash to keep instances distinct while avoiding symbols like '|'.
        try:
            import hashlib
            cfg = {
                "types": self.pii_types if isinstance(self.pii_types, str) else list(self.pii_types),
                "prefix": self.placeholder_prefix,
                "in": bool(self.apply_to_input),
                "out": bool(self.apply_to_output),
                "toolres": bool(self.apply_to_tool_results),
                "decodecalls": bool(self.decode_tool_calls),
            }
            digest = hashlib.sha1(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:8]
            return f"{self.__class__.__name__}_{digest}"
        except Exception:
            # Fallback: class name only
            return f"{self.__class__.__name__}"

    def state_schema(self, input_schema: type) -> type:
        """Augment the agent state schema with middleware-specific keys.

        Returns a TypedDict that extends the provided `input_schema` with:
        - `_pii_pseudonym_map`: Dict[str, str] = mapping of placeholders to originals

        If schema composition fails (e.g., `input_schema` is not a TypedDict),
        the original `input_schema` is returned unchanged.
        """
        try:
            # Prefer typing_extensions for NotRequired support
            from typing_extensions import TypedDict  # type: ignore
        except Exception:
            from typing import TypedDict  # type: ignore

        try:
            class _PIIState(input_schema, TypedDict, total=False):  # type: ignore[misc]
                _pii_pseudonym_map: Dict[str, str]

            return _PIIState
        except Exception:
            # Fallback: return input schema unchanged if TypedDict composition fails
            return input_schema

    def before_model(
        self,
        state: AgentState,
        runtime: Runtime,  # noqa: ARG002
    ) -> Dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        any_modified = False
        new_messages = list(messages)

        # Optionally decode tool result messages using existing mapping
        if self.apply_to_tool_results:
            mapping_existing = state.get("_pii_pseudonym_map", {})
            if mapping_existing:
                # Find last AI message, then process ToolMessages after it
                last_ai_idx = None
                for i in range(len(messages) - 1, -1, -1):
                    if isinstance(messages[i], AIMessage):
                        last_ai_idx = i
                        break

                if last_ai_idx is not None:
                    for i in range(last_ai_idx + 1, len(messages)):
                        if isinstance(messages[i], ToolMessage):
                            msg = messages[i]
                            decoded_content = depseudonymize_text(str(msg.content), mapping_existing)
                            if decoded_content != msg.content:
                                new_messages[i] = ToolMessage(
                                    content=decoded_content,
                                    id=getattr(msg, "id", None),
                                    name=getattr(msg, "name", None),
                                    tool_call_id=getattr(msg, "tool_call_id", None),
                                )
                                any_modified = True

        # Mask HumanMessages if enabled
        if self.apply_to_input:
            mapping_accumulated = state.get("_pii_pseudonym_map", {})
            
            for i in range(len(new_messages)):
                msg = new_messages[i]
                if isinstance(msg, HumanMessage) and getattr(msg, "content", None):
                    content = str(msg.content)
                    masked, mapping_accumulated = pseudonymize_text(
                        content,
                        pii_types=self.pii_types,
                        placeholder_prefix=self.placeholder_prefix,
                        existing_mapping=mapping_accumulated
                    )

                    if masked != content:
                        logger.info(f"\n[PIIPseudonymizationMiddleware - before_model]")
                        logger.info(f"  Index: {i}")
                        logger.info(f"  Original content: {content}")
                        logger.info(f"  Masked content: {masked}")
                        
                        new_messages[i] = HumanMessage(
                            content=masked,
                            id=getattr(msg, "id", None),
                            name=getattr(msg, "name", None),
                        )
                        any_modified = True

            if any_modified:
                return {"messages": new_messages, "_pii_pseudonym_map": mapping_accumulated}

        if any_modified:
            return {"messages": new_messages}

        return None

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime,  # noqa: ARG002
    ) -> Dict[str, Any] | None:
        """Async alias to `before_model` for frameworks expecting async hooks."""
        return self.before_model(state, runtime)

    def after_model(
        self,
        state: AgentState,
        runtime: Runtime,  # noqa: ARG002
    ) -> Dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        logger.info(f"\n[PIIPseudonymizationMiddleware - after_model]")
        # Last AI message
        last_ai_idx = None
        last_ai_msg = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], AIMessage):
                last_ai_idx = i
                last_ai_msg = messages[i]
                break

        if last_ai_idx is None or not last_ai_msg:
            return None

        mapping = state.get("_pii_pseudonym_map", {})
        if not mapping:
            return None

        any_modified = False
        content = getattr(last_ai_msg, "content", None)
        decoded_text = None

        # Optionally decode AI content
        updated_content = content
        if self.apply_to_output and isinstance(content, str):
            decoded_text = depseudonymize_text(content, mapping)
            if decoded_text != content:
                updated_content = decoded_text
                any_modified = True

        # Decode tool calls so tools receive original values
        tool_calls = getattr(last_ai_msg, "tool_calls", None)
        decoded_calls = tool_calls
        if self.decode_tool_calls and tool_calls:
            try:
                logger.info(f"\n[PIIPseudonymizationMiddleware - tools]")
                logger.info(f"  Mapping: {mapping}")
                logger.info(f"  Original tool_calls: {tool_calls}")

                # Deep decode the tool calls structure
                decoded_calls = _deep_decode(tool_calls, mapping)

                print(f"  Decoded tool_calls: {decoded_calls}")

                if decoded_calls != tool_calls:
                    any_modified = True
            except Exception as e:
                # Keep original on error
                print(f"  ERROR during decoding: {e}")
                decoded_calls = tool_calls

        if not any_modified:
            return None

        updated_ai = AIMessage(
            content=updated_content,
            id=getattr(last_ai_msg, "id", None),
            name=getattr(last_ai_msg, "name", None),
            tool_calls=decoded_calls,
        )

        new_messages = list(messages)
        new_messages[last_ai_idx] = updated_ai

        return {"messages": new_messages}

    async def aafter_model(
        self,
        state: AgentState,
        runtime: Runtime,  # noqa: ARG002
    ) -> Dict[str, Any] | None:
        """Async alias to `after_model` for frameworks expecting async hooks."""
        return self.after_model(state, runtime)


# ──────────────────────────────── Minimal Demo/Utilities ─────────────────────────────

def _demo() -> None:  # pragma: no cover
    sample = (
        "Email alice@example.com called from 192.168.1.10 to https://example.com "
        "with card 4111-1111-1111-1111 and MAC aa:bb:cc:dd:ee:ff"
    )
    masked, m = pseudonymize_text(sample, "all")
    print("Original:\n", sample)
    print("\nMasked:\n", masked)
    print("\nMapping:\n", json.dumps(m, indent=2))
    print("\nDecoded:\n", depseudonymize_text(masked, m))


if __name__ == "__main__":  # pragma: no cover
    _demo()
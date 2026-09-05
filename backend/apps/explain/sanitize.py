"""Sanitization for LLM-bound payloads.

Every string that leaves this backend for the AI service passes through
`sanitize_text`: control characters and newlines are stripped (they cannot
carry meaning in these fields but can carry prompt injection), and length is
bounded. The AI service validates the payload shape again (defense in depth).
"""

MAX_FIELD_LEN = 200


def sanitize_text(value, max_len: int = MAX_FIELD_LEN):
    if not isinstance(value, str):
        return value
    cleaned = "".join(ch for ch in value if ch.isprintable() and ch not in "\n\r\t")
    return cleaned[:max_len]


def sanitize_payload(payload):
    """Recursively sanitize every string in a dict/list payload (depth-limited)."""

    def walk(node, depth):
        if depth > 4:
            return node
        if isinstance(node, dict):
            return {k: walk(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, depth + 1) for v in node]
        return sanitize_text(node)

    return walk(payload, 0)

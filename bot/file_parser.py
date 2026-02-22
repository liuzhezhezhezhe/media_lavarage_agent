"""Parse uploaded files into plain text for LLM processing."""
import csv
import io
import json
from pathlib import Path

MAX_OUTPUT_BYTES = 100_000  # 100 KB
_TRUNCATION_NOTICE = "\n\n[Content truncated to 100 KB]"

_JSON_TEXT_KEYS = {"content", "text", "message", "body", "value"}


def parse_file(data: bytes, filename: str) -> str:
    """Parse file bytes into plain text. Raises ValueError on unsupported format."""
    suffix = Path(filename).suffix.lower()

    if suffix in (".txt", ".md"):
        text = _decode(data)
    elif suffix == ".json":
        text = _parse_json(data)
    elif suffix == ".csv":
        text = _parse_csv(data)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .txt / .md / .json / .csv")

    return _truncate(text)


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_json(data: bytes) -> str:
    try:
        obj = json.loads(_decode(data))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {e}") from e

    texts: list[str] = []
    _extract_text_fields(obj, texts)
    if not texts:
        # Fallback: dump the whole thing
        return json.dumps(obj, ensure_ascii=False, indent=2)
    return "\n".join(texts)


def _extract_text_fields(obj, out: list[str]) -> None:
    """Recursively pull text values from known keys."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key.lower() in _JSON_TEXT_KEYS and isinstance(val, str) and val.strip():
                out.append(val.strip())
            else:
                _extract_text_fields(val, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_text_fields(item, out)


def _parse_csv(data: bytes) -> str:
    text = _decode(data)
    reader = csv.reader(io.StringIO(text))
    rows: list[str] = []
    for row in reader:
        line = " | ".join(cell.strip() for cell in row if cell.strip())
        if line:
            rows.append(line)
    return "\n".join(rows)


def _truncate(text: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_OUTPUT_BYTES:
        return text
    truncated = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
    return truncated + _TRUNCATION_NOTICE

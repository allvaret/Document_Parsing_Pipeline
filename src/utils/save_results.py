
import json
from dataclasses import asdict, is_dataclass
from typing import Any

def _default_serializer(obj: Any):
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # Pydantic v1
    if hasattr(obj, "dict"):
        return obj.dict()
    # dataclasses
    if is_dataclass(obj):
        return asdict(obj) # type: ignore
    # sets, tuples "estranhos", etc.
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    raise TypeError(f"Objeto do tipo {type(obj)} não é serializável em JSON")


def save_output(content: Any, pdf_path: str, suffix: str) -> str:
    output_path = pdf_path.replace(".pdf", f"_{suffix}.json")

    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content, ensure_ascii=False, indent=2, default=_default_serializer)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return output_path
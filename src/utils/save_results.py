import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _default_serializer(obj: Any):
    # Pydantic v2
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    # dataclasses
    if is_dataclass(obj):
        return asdict(obj)  # type: ignore
    # sets, tuples "estranhos", etc.
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    raise TypeError(f"Objeto do tipo {type(obj)} não é serializável em JSON")


def save_output(content: Any, pdf_path: str | Path, suffix: str, out_dir: str | Path | None = None) -> Path:
    """Salva <nome-do-pdf>_<suffix>.json.

    Antes: pdf_path.replace(".pdf", ...). Com extensão ".PDF" (maiúscula)
    nada era substituído e o JSON sobrescrevia o próprio PDF.
    """
    pdf_path = Path(pdf_path)
    target_dir = Path(out_dir) if out_dir else pdf_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{pdf_path.stem}_{suffix}.json"

    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content, ensure_ascii=False, indent=2, default=_default_serializer)

    output_path.write_text(text, encoding="utf-8")
    return output_path

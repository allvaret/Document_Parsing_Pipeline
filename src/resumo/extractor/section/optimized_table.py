from __future__ import annotations
import re

import pdfplumber

from resumo.extractor.section.detect_region_text import LineRegion, PageBBox, TableRegion


# ── conversão de coordenadas ───────────────────────────────────────────────────

def _plumber_bbox_to_fitz(
    bbox:        tuple[float, float, float, float],
    page:        int,
    page_height: float,
    page_width:  float,
) -> PageBBox:
    """
    bbox do pdfplumber: (x0, top, x1, bottom)
    onde top < bottom no sistema pdfplumber (y cresce para baixo nessa API).

    Nota: pdfplumber expõe .bbox como (x0, top, x1, bottom) já em coords
    de página com y crescendo para baixo — mesmo sistema do fitz.
    A conversão só é necessária se você usar .y0/.y1 do objeto Table.
    """
    x0, top, x1, bottom = bbox
    return PageBBox(
        page    = page, 
        x_start = 0, # sempre — captura coluna de labels
        x_end   = page_width,
        y_start = max(top,    0),
        y_end   = min(bottom, page_height),
    )


# ── detecção via pdfplumber ────────────────────────────────────────────────────

def _detect_tables_plumber(
    plumber_pdf:  pdfplumber.PDF, # type: ignore
    page_heights: dict[int, float],
) -> list[PageBBox]:
    """
    Varre todas as páginas e coleta bboxes de tabelas detectadas pelo pdfplumber.
    Coordenadas convertidas para o sistema fitz.
    """
    detected: list[PageBBox] = []

    for page_index, page in enumerate(plumber_pdf.pages):
        tables = page.find_tables()
        if not tables:
            continue

        page_height = page_heights.get(page_index, page.height)

        for table in tables:
            bbox = _plumber_bbox_to_fitz(table.bbox, page_index, page_height, page.width)
            detected.append(bbox)

    return detected


# ── intersecção ────────────────────────────────────────────────────────────────

def _intersects(
    region: LineRegion | TableRegion,
    bbox:   PageBBox,
) -> bool:
    """
    Verifica se uma região intersecta uma bbox do pdfplumber.
    Ambas devem estar na mesma página e ter sobreposição vertical mínima de 30%.
    """
    if region.page != bbox.page:
        return False

    overlap_start = max(region.y_start, bbox.y_start)
    overlap_end   = min(region.y_end,   bbox.y_end)
    overlap       = overlap_end - overlap_start

    if overlap <= 0:
        return False

    region_height = region.y_end - region.y_start
    if region_height <= 0:
        return False

    return (overlap / region_height) >= 0.30


def _find_intersecting_bbox(
    region:   LineRegion | TableRegion,
    detected: list[PageBBox],
) -> PageBBox | None:
    """Retorna a primeira bbox do pdfplumber que intersecta a região, ou None."""
    for bbox in detected:
        if _intersects(region, bbox):
            return bbox
    return None


# ── extração e formatação ──────────────────────────────────────────────────────

def _is_coherent_table(rows: list[list[str | None]]) -> bool:
    if not rows or len(rows) < 2:
        return False
    col_count = max(len(row) for row in rows)
    if col_count < 2:
        return False

    total  = sum(len(row) for row in rows)
    filled = sum(1 for row in rows for cell in row if cell and cell.strip())
    if (filled / total) < 0.4:
        return False

    # Checa header financeiro OU densidade numérica suficiente
    NUMBER_RE = re.compile(r'[\d]')
    HEADER_RE = re.compile(r'\d{1}[TM]\d{2}|R\$|20\d{2}|milhões|bilhões', re.IGNORECASE)

    header_text = ' '.join(c for c in rows[0] if c)
    has_financial_header = bool(HEADER_RE.search(header_text))

    data_cells = [c for row in rows[1:] for c in row if c and c.strip()]
    numeric_rate = sum(1 for c in data_cells if NUMBER_RE.search(c)) / max(len(data_cells), 1)

    return has_financial_header or numeric_rate > 0.4


def _rows_to_markdown(rows: list[list[str | None]]) -> str:
    def clean(cell: str | None) -> str:
        return (cell or "").replace("|", "\\|").strip()

    lines: list[str] = []
    for i, row in enumerate(rows):
        lines.append("| " + " | ".join(clean(c) for c in row) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


# ── promoção / rebaixamento ────────────────────────────────────────────────────

def _promote_to_table(
    region:      LineRegion | TableRegion,
    bbox:        PageBBox,
    plumber_pdf: pdfplumber.PDF, # type: ignore
) -> TableRegion | None:
    """
    Tenta extrair o markdown da bbox e construir um TableRegion.
    Retorna None se a extração falhar.
    """
    result = _extract_table_from_bbox(plumber_pdf, bbox)
    if result is None:
        return None

    return TableRegion(
        region_type = "table",
        page_spans  = [bbox],
        page        = region.page,
        y_start     = region.y_start,
        y_end       = region.y_end,
        markdown    = result["markdown"],
        confidence  = result["confidence"],
        note        = result["note"],
    )


def _demote_to_prose(region: LineRegion | TableRegion) -> LineRegion:
    """Rebaixa qualquer região para LineRegion prose."""
    lines = region.lines if isinstance(region, LineRegion) else []
    return LineRegion(
        region_type = "prose",
        lines       = lines,
        page        = region.page,
        y_start     = region.y_start,
        y_end       = region.y_end,
        page_spans  = None,
    )


# ── função principal ───────────────────────────────────────────────────────────

def enrich_line_regions(
    regions:      list[LineRegion | TableRegion],
    pdf_path:     str,
) -> list[LineRegion | TableRegion]:
    """
    Enriquece regiões detectadas usando o pdfplumber como fonte de verdade
    para detecção e extração de tabelas.

    Regras por tipo de entrada:
      - "prose"     → passa direto, nunca tocado
      - "uncertain" → intersecta bbox → TableRegion; senão → prose
      - "table"     → intersecta bbox → TableRegion; senão → prose (falso positivo)
      - TableRegion → revalida; sem intersecção ou extração falha → prose

    Args:
        regions:      lista ordenada por y_start (ordem de leitura)
        pdf_path:     mesmo caminho usado pelo fitz
        page_heights: dict[page_index, height] extraído do fitz

    Returns:
        lista na mesma ordem com regiões promovidas ou rebaixadas
    """
    result: list[LineRegion | TableRegion] = []

    page_heights = {}
    if isinstance(regions, LineRegion):
        page_heights = regions.get_page_heights

    with pdfplumber.open(pdf_path) as plumber_pdf:
        detected = _detect_tables_plumber(plumber_pdf, page_heights) # type: ignore

        for region in regions:
            # prosa nunca é tocada
            if isinstance(region, LineRegion) and region.region_type == "prose":
                result.append(region)
                continue

            bbox = _find_intersecting_bbox(region, detected)

            if bbox is None:
                # sem intersecção → falso positivo, rebaixa para prosa
                result.append(_demote_to_prose(region))
                continue

            promoted = _promote_to_table(region, bbox, plumber_pdf)

            if promoted is None:
                # intersectou mas extração falhou → rebaixa
                result.append(_demote_to_prose(region))
                continue

            result.append(promoted)

    return result


# ── classificação por conteúdo ─────────────────────────────────────────────────

def _word_content_type(text: str) -> str:
    """
    'numeric' → valor financeiro (número, %, p.p., traço placeholder)
    'label'   → texto descritivo ((fees), (capital), nomes, conectores)
    """
    t = text.strip()
    if not t:
        return "label"
    if t in ("-", "−", "—"):          # traço como placeholder de valor
        return "numeric"
    if t == "p.p.":                    # unidade de ponto percentual
        return "numeric"
    cleaned = (t
        .replace(".", "").replace(",", "").replace("%", "")
        .replace("(", "").replace(")", "").replace("-", "").replace("+", "")
        .strip()
    )
    return "numeric" if (cleaned and cleaned.isdigit()) else "label"


def _classify_line_by_content(words: list[dict]) -> str:
    types = {_word_content_type(w["text"]) for w in words if w["text"].strip()}
    has_n = "numeric" in types
    has_l = "label"   in types
    if has_n and has_l: return "data"
    if has_n:           return "values"
    return "label"


# ── espaçamento mediano ────────────────────────────────────────────────────────

def _median_line_spacing(
    lines:       dict[float, list[dict]],
    sorted_tops: list[float],
) -> float:
    numeric_tops = [
        t for t in sorted_tops
        if any(_word_content_type(w["text"]) == "numeric" for w in lines[t])
    ]
    if len(numeric_tops) < 2:
        return 15.0
    deltas = [numeric_tops[i+1] - numeric_tops[i] for i in range(len(numeric_tops)-1)]
    return sorted(deltas)[len(deltas) // 2]


# ── âncoras de coluna ──────────────────────────────────────────────────────────

# palavras de conexão que nunca são cabeçalhos de coluna
_CONNECTOR_WORDS = {"x", "×", "X", "vs", "e", "de"}


def _infer_label_zone_end(header_words: list[dict]) -> float:
    sorted_words = sorted(header_words, key=lambda w: w["x0"])
    positions    = [w["x0"] for w in sorted_words]
    if len(positions) < 2:
        return positions[0] if positions else 0.0
    gaps        = [(positions[i+1] - positions[i], i) for i in range(len(positions)-1)]
    max_gap_idx = max(gaps, key=lambda g: g[0])[1]
    return (positions[max_gap_idx] + positions[max_gap_idx+1]) / 2


def _infer_col_anchors(header_words: list[dict], label_zone_end: float) -> list[float]:
    numeric_words = sorted(
        [w for w in header_words
         if w["x0"] > label_zone_end and w["text"].strip() not in _CONNECTOR_WORDS],
        key=lambda w: w["x0"]
    )
    if not numeric_words:
        return []
    positions = [w["x0"] for w in numeric_words]
    if len(positions) == 1:
        return positions

    deltas        = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
    sorted_deltas = sorted(deltas)

    working = sorted_deltas[:]
    while len(working) > 1:
        gaps     = [(working[i+1] - working[i], i) for i in range(len(working)-1)]
        rel_gaps = [(gap / working[i] if working[i] > 0 else 0.0, i) for gap, i in gaps]
        best_rel, best_idx = max(rel_gaps, key=lambda g: g[0])
        if best_rel < 0.5:
            break
        threshold = (working[best_idx] + working[best_idx+1]) / 2
        working   = [d for d in working if d >= threshold]

    threshold = working[0] if working else sorted_deltas[len(sorted_deltas)//2]

    anchors = [positions[0]]
    for i, delta in enumerate(deltas):
        if delta > threshold:
            anchors.append(positions[i+1])
    return anchors


# ── classificação e mesclagem de linhas ────────────────────────────────────────

def _classify_and_merge_lines(
    lines:       dict[float, list[dict]],
    sorted_tops: list[float],
) -> list[dict]:
    """
    Classifica linhas por CONTEÚDO e mescla linhas adjacentes que formam
    uma única linha lógica.

    Padrões:
      A: label → values → label  (span pequeno → uma linha)
      B: label → values           (label acima dos valores)
      C: values → label           (label abaixo dos valores, mesma linha física)
      D: data completo + values→label adjacentes → duas linhas distintas
      E: label (+ label adjacente) → subheader
    """
    median_sp = _median_line_spacing(lines, sorted_tops)
    threshold = median_sp * 0.5     # linhas dentro de 50% do espaçamento → mesma linha lógica

    classified = [
        {"top": t, "words": lines[t], "type": _classify_line_by_content(lines[t])}
        for t in sorted_tops
    ]

    merged = []
    i = 0
    while i < len(classified):
        cur  = classified[i]
        nxt  = classified[i+1] if i+1 < len(classified) else None
        nxt2 = classified[i+2] if i+2 < len(classified) else None

        d01  = (nxt["top"]  - cur["top"]) if nxt         else 9999.
        d12  = (nxt2["top"] - nxt["top"]) if (nxt and nxt2) else 9999.
        span = (nxt2["top"] - cur["top"]) if (nxt and nxt2) else 9999.

        # A: label → values → label (span pequeno)
        if (cur["type"] == "label" and
                nxt  and nxt["type"]  == "values" and
                nxt2 and nxt2["type"] == "label" and
                span <= threshold * 2):
            merged.append({"words": cur["words"] + nxt["words"] + nxt2["words"],
                           "type": "data", "top": cur["top"]})
            i += 3; continue

        # B: label → values (delta pequeno)
        if (cur["type"] == "label" and
                nxt and nxt["type"] == "values" and d01 <= threshold):
            merged.append({"words": cur["words"] + nxt["words"],
                           "type": "data", "top": cur["top"]})
            i += 2; continue

        # C: values → label (delta pequeno)
        if (cur["type"] == "values" and
                nxt and nxt["type"] == "label" and d01 <= threshold):
            merged.append({"words": cur["words"] + nxt["words"],
                           "type": "data", "top": cur["top"]})
            i += 2; continue

        # D: linha data completa + values+label adjacentes formam outra linha
        # ex: Treasury com valores próprios + Gestão de Patrimônio abaixo
        if (cur["type"] == "data" and
                nxt  and nxt["type"]  == "values" and
                nxt2 and nxt2["type"] == "label" and d12 <= threshold):
            merged.append({"words": cur["words"],
                           "type": "data", "top": cur["top"]})
            merged.append({"words": nxt["words"] + nxt2["words"],
                           "type": "data", "top": nxt["top"]})
            i += 3; continue

        # E: label sem values adjacente → subheader
        if cur["type"] == "label":
            if nxt and nxt["type"] == "label" and d01 <= threshold:
                merged.append({"words": cur["words"] + nxt["words"],
                               "type": "subheader", "top": cur["top"]})
                i += 2; continue
            merged.append({"words": cur["words"], "type": "subheader", "top": cur["top"]})
            i += 1; continue

        merged.append(cur)
        i += 1

    return merged


# ── montagem de linha ──────────────────────────────────────────────────────────

def _build_row(
    words:          list[dict],
    col_anchors:    list[float],
    label_zone_end: float,
    use_position:   bool = False,
) -> list[str]:
    """
    use_position=True  → header: usa x0 para atribuir coluna
    use_position=False → dados: usa tipo de conteúdo da palavra
      texto   → col 0 (label)
      numérico → âncora mais próxima → col 1+
    """
    row = [""] * (len(col_anchors) + 1)

    for w in sorted(words, key=lambda w: w["x0"]):
        text = w["text"].strip()
        if not text:
            continue

        if use_position:
            if w["x0"] < label_zone_end:
                row[0] = (row[0] + " " + text).strip()
            else:
                col = min(range(len(col_anchors)),
                          key=lambda i: abs(col_anchors[i] - w["x0"])) + 1
                row[col] = (row[col] + " " + text).strip()
        else:
            if _word_content_type(text) == "label":
                row[0] = (row[0] + " " + text).strip()
            else:
                col = min(range(len(col_anchors)),
                          key=lambda i: abs(col_anchors[i] - w["x0"])) + 1
                row[col] = (row[col] + " " + text).strip()

    return row


# ── extração principal ─────────────────────────────────────────────────────────

def _extract_financial_table(
    page:        pdfplumber.page.Page, # type: ignore
    bbox:        PageBBox,
    y_threshold: float = 3.0,
) -> list[list[str]] | None:
    cropped = page.crop((
        max(bbox.x_start, 0), max(bbox.y_start, 0),
        min(bbox.x_end, page.width), min(bbox.y_end, page.height),
    ))

    words = [w for w in cropped.extract_words()
             if w["x0"] >= 0 and w["x1"] <= page.width]
    if not words:
        return None

    lines: dict[float, list[dict]] = {}
    for w in words:
        top = round(w["top"] / y_threshold) * y_threshold
        lines.setdefault(top, []).append(w)

    sorted_tops = sorted(lines.keys())

    # header: primeira linha com palavra iniciando em dígito
    def is_numeric_header(lw: list[dict]) -> bool:
        return any(w["text"] and w["text"][0].isdigit() for w in lw)

    header_top     = next((t for t in sorted_tops if is_numeric_header(lines[t])), sorted_tops[0])
    label_zone_end = _infer_label_zone_end(lines[header_top])
    col_anchors    = _infer_col_anchors(lines[header_top], label_zone_end)

    if not col_anchors:
        return None

    # classifica e mescla apenas as linhas de conteúdo (sem o header)
    non_header_tops = [t for t in sorted_tops if t != header_top]
    logical_lines   = _classify_and_merge_lines(lines, non_header_tops)

    n_cols    = len(col_anchors) + 1
    rows:     list[list[str]] = []

    # header (posição)
    rows.append(_build_row(lines[header_top], col_anchors, label_zone_end, use_position=True))

    # conteúdo (conteúdo semântico)
    for line in logical_lines:
        if line["type"] == "subheader":
            text = " ".join(
                w["text"] for w in sorted(line["words"], key=lambda w: w["x0"])
                if w["text"].strip()
            )
            rows.append([text] + [""] * (n_cols - 1))
        else:
            rows.append(_build_row(line["words"], col_anchors, label_zone_end))

    return rows if len(rows) >= 2 else None


import re

def _score_table_confidence(
    rows:      list[list[str]],
    row_types: list[str],
) -> tuple[str, str | None]:
    """
    Avalia a qualidade da tabela extraída.

    Retorna:
      ("high" | "low", note | None)

    Critérios:
      fill_rate  < 0.5  → low  (muitas células vazias)
      leak_count > 0    → note (valores no label)
      fill_rate >= 0.5 e leak_count == 0 → high
    """
    data_rows = [
        row for row, t in zip(rows, row_types)
        if t == "data"
    ]
    if not data_rows:
        return ("low", "sem linhas de dados")

    # fill rate apenas nas colunas numéricas (ignora col 0)
    numeric_cells = [cell for row in data_rows for cell in row[1:]]
    if not numeric_cells:
        return ("low", "sem colunas numéricas")

    filled    = sum(1 for c in numeric_cells if c.strip())
    fill_rate = filled / len(numeric_cells)

    # detecta linhas onde o label termina com número — vazamento
    _ends_with_number = re.compile(r"[\d,\.]+\s*[\)\%]?\s*$")
    leak_rows = [
        row[0] for row in data_rows
        if row[0].strip() and _ends_with_number.search(row[0])
    ]
    leak_count = len(leak_rows)

    note = None
    if leak_count > 0:
        note = f"{leak_count} célula(s) com possível vazamento de valor para coluna de label"

    confidence = "high" if fill_rate >= 0.5 and leak_count == 0 else "low"
    return (confidence, note)


def _extract_table_from_bbox(
    plumber_pdf: pdfplumber.PDF, # type: ignore
    bbox:        "PageBBox",
) -> dict | None:
    """
    Retorna:
      {
        "markdown":   str,
        "confidence": "high" | "low",
        "note":       str | None,
      }
    ou None se a extração for incoerente.
    """
    page = plumber_pdf.pages[bbox.page]

    x0 = max(bbox.x_start, 0)
    y0 = max(bbox.y_start, 0)
    x1 = min(bbox.x_end,   page.width)
    y1 = min(bbox.y_end,   page.height)

    if x1 <= x0 or y1 <= y0:
        return None

    clipped = PageBBox(
        page    = bbox.page,
        x_start = x0, x_end = x1,
        y_start = y0, y_end = y1,
    )

    rows = _extract_financial_table(page, clipped)
    if not rows or not _is_coherent_table(rows): # type: ignore
        return None

    # reconstrói row_types para o scorer
    row_types = ["header"] + ["data"] * (len(rows) - 1)

    confidence, note = _score_table_confidence(rows, row_types)

    return {
        "markdown":   _rows_to_markdown(rows), # type: ignore
        "confidence": confidence,
        "note":       note,
    }

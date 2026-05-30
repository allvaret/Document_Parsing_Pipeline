import json
import requests

from extractor.group_text_line import group_atoms_into_lines
from extractor.parsers import decomp_pdf
from extractor.parsers.detect_region_text import LineRegion, detect_regions
from extractor.parsers.title_block import consolidate_title_blocks
from extractor.section.section_builder import build_sections
from extractor.section.section_json import sections_to_json
from utils.text_size import get_text_size
from utils.title.candidate_filter import candidate_filter, is_disqualified
from utils.title.is_title import calculate_title_score
from utils.title.remove_repeated_title import remove_repeated


path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"


# ─────────────────────────────────────────────
# 1. FILTROS DE REGIÃO
# ─────────────────────────────────────────────

def is_footer_region(region: LineRegion, page_height: float) -> bool:
    return (region.y_start / page_height) > 0.85 and len(region.lines) <= 5


def filter_regions(regions: list, page_height: float) -> list:
    before = len(regions)
    filtered = [r for r in regions if not is_footer_region(r, page_height)]
    print(f"Regiões após filtro de rodapé: {len(filtered)} / {before}")
    return filtered


# ─────────────────────────────────────────────
# 2. CHAMADA AO LLM (Ollama local)
# ─────────────────────────────────────────────

def call_llm(sections_json: str, model: str = "llama3.2") -> str:
    prompt = f"""Você é um analista financeiro especializado em empresas brasileiras listadas na B3.

Abaixo está o conteúdo estruturado de um documento financeiro em JSON.
Cada entrada contém: título da seção, página, corpo de texto e tabelas associadas.

Sua tarefa é produzir um resumo executivo em português com exatamente estas seções:

1. RESULTADO DO PERÍODO
   - Receita total, lucro líquido, margem, e variações relevantes vs período anterior

2. PONTOS DE ATENÇÃO
   - Mudanças significativas, riscos mencionados, ou tendências preocupantes

3. DESTAQUES POSITIVOS
   - Crescimentos, conquistas ou eventos favoráveis mencionados no documento

4. CONTEXTO DE MERCADO
   - Cenário econômico descrito que afeta a empresa


Seja objetivo e use os números do documento. Se uma seção não tiver informação suficiente, escreva "Não mencionado".

Documento:
{sections_json}

Resumo executivo:"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model":   model,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": 0.2,   # baixo para respostas mais factuais
                    "num_ctx":     8192,  # contexto máximo
                }
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]

    except requests.exceptions.ConnectionError:
        return "[ERRO] Ollama não está rodando. Execute: ollama serve"
    except requests.exceptions.Timeout:
        return "[ERRO] Timeout — documento muito longo para o modelo. Tente reduzir o JSON."
    except Exception as e:
        return f"[ERRO] {e}"


# ─────────────────────────────────────────────
# 3. PIPELINE COMPLETA
# ─────────────────────────────────────────────

def test_full_pipeline():
    print("=" * 60)
    print("PIPELINE COMPLETA: PDF → JSON → LLM")
    print("=" * 60)
    print(f"Arquivo: {path}")
    print()

    # ── Extração ──────────────────────────────
    print("[ 1/6 ] Extraindo átomos...")
    atoms = decomp_pdf.extract_text_atoms(path)
    page_height = atoms[0].page_height
    print(f"        {len(atoms)} átomos extraídos")

    # ── Limpeza ───────────────────────────────
    print("[ 2/6 ] Limpando e agrupando em linhas...")
    body_size = get_text_size(atoms)
    lines = group_atoms_into_lines(atoms)
    print(f"        body_size={body_size}  linhas={len(lines)}")

    # ── Títulos ───────────────────────────────
    print("[ 3/6 ] Detectando títulos...")
    survivors = candidate_filter(atoms, body_size)
    titles_list = [
        {
            "text":       a.text.strip(),
            "page":       a.page,
            "relative_y": a.y0 / a.page_height,
            "size":       a.size,
            "bold":       a.bold,
            "score":      score,
        }
        for a in survivors
        if (score := calculate_title_score(a, body_size, a.page_height))
    ]

    # Passagem 1: remove repetições estruturais
    cleaned_titles = remove_repeated(titles_list)

    # Passagem 2: consolida fragmentos em blocos
    title_blocks = consolidate_title_blocks(cleaned_titles, lines)

    # O section_builder agora usa TitleBlock em vez de string simples
    title_texts = {block.text for block in title_blocks}

    print(f"Títulos individuais : {len(titles_list)}")
    print(f"Após deduplicação   : {len(cleaned_titles)}")
    print(f"Após consolidação   : {len(title_blocks)}")
    print()
    print("=== Blocos de título consolidados ===")
    for block in title_blocks:
        if len(block.lines) > 1:
            print(f"  [Pág {block.page}] BLOCO: {block.text[:70]}")
            for ln in block.lines:
                print(f"    └─ {ln}")
        else:
            print(f"  [Pág {block.page}] {block.text[:70]}")
            
    # ── Regiões ───────────────────────────────
    print("[ 4/6 ] Detectando regiões...")
    regions = detect_regions(lines, title_texts)
    regions = filter_regions(regions, page_height)
    prose  = sum(1 for r in regions if r.region_type == "prose")
    tables = sum(1 for r in regions if r.region_type == "table")
    unc    = sum(1 for r in regions if r.region_type == "uncertain")
    print(f"        prose={prose}  table={tables}  uncertain={unc}")

    # ── Section builder ───────────────────────
    print("[ 5/6 ] Construindo seções...")
    sections = build_sections(regions, title_texts)
    print(f"        {len(sections)} seções montadas")
    print()

    # Prévia das seções para inspecionar antes de mandar ao LLM
    print("── Prévia das seções ──────────────────────")
    for s in sections:
        preview_body = s.body[:120].replace("\n", " ")
        print(
            f"  [Pág {s.page:>3}] {s.title[:50]:<50} "
            f"| corpo={len(s.body):>5} chars  "
            f"tabelas={len(s.tables)}"
        )
        if preview_body:
            print(f"           └─ {preview_body}...")
    print()

    # ── LLM ───────────────────────────────────
    print("[ 6/6 ] Enviando ao LLM...")

    # Monta JSON apenas com seções que têm conteúdo relevante
    # (descarta seções de capa/assinatura com corpo muito curto)
    sections_for_llm = [
        s for s in sections
        if len(s.body) > 100 or len(s.tables) > 0
    ]
    print(f"        {len(sections_for_llm)} seções com conteúdo suficiente enviadas")

    sections_json = sections_to_json(sections_for_llm)

    # Salva JSON para inspeção
    json_path = path.replace(".pdf", "_sections.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(sections_json)
    print(f"        JSON salvo em: {json_path}")
    print()

    print("── Aguardando resposta do LLM... ──────────")
    resumo = call_llm(sections_json)

    print()
    print("=" * 60)
    print("RESUMO EXECUTIVO")
    print("=" * 60)
    print(resumo)

    return sections, resumo


test_full_pipeline()
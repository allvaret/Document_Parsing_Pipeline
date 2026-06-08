import json
import requests
import spacy

from LLM.NLP.feature_extractor_nlp import extract_features_batch
from LLM.NLP.semantic_scorer import calc_semantic_score_nlp
from extractor.group_text_line import group_atoms_into_lines
from extractor.parsers import decomp_pdf
from extractor.parsers.detect_region_text import LineRegion, detect_regions
from extractor.section.section_builder import build_sections, combine_scores
from extractor.section.section_json import sections_to_json
from utils.text_size import get_text_size
from utils.title.candidate_filter import TitleCandidate, best_title_candidates, candidate_filter
from utils.title.is_title import calculate_title_score, normalize_title_score
from utils.title.remove_repeated_title import remove_repeated


path = "assets/Earnings Release 3T25.pdf"


# ─────────────────────────────────────────────
# 2. CHAMADA AO LLM (Ollama local)
# ─────────────────────────────────────────────

def call_llm(sections_json: str, model: str = "qwen3.5:9b") -> str:
    prompt = f"""Você é um analista financeiro especializado em empresas brasileiras listadas na B3.

Abaixo está o conteúdo estruturado de um relatório financeiro em JSON.
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
"""

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
    # Build title list
    survivors = candidate_filter(atoms, body_size)
    candidates = [
        TitleCandidate(
            text=a.text.strip(),
            page=a.page +1,  # pages are 0-indexed internally, +1 for human-friendly
            relative_y=a.y0 / a.page_height,
            h_score=normalize_title_score(calculate_title_score(a, body_size, a.page_height)),
            nlp_score=0.0,  # Será preenchido posteriormente
            combined_score=0.0,  # Será preenchido posteriormente

        )
        for a in survivors
    ]
    print(f"        {len(candidates)} candidatos a título após filtragem inicial")

    # Filtra candidatos por pontuação, para cada pagina pega o de menor relative_y
    best_candidates = best_title_candidates(candidates, min_score=0.3)
    print(f"        {len(best_candidates)} candidatos a título após seleção final")

    # Passagem 1: remove repetições estruturais
    cleaned_titles = remove_repeated(best_candidates, debug=True)
    #print(f" {cleaned_titles} \n")

    for c in cleaned_titles:
        
        # Passagem 2: extrai features NLP em lote para os títulos limpos 
        np_features = extract_features_batch([t.text for t in cleaned_titles])  # teste da função de extração em lote

        # Passagem 3: classifica títulos como candidatos a títulos usando o modelo NLP
        sematic_scores = [calc_semantic_score_nlp(f) for f in np_features]
        c.nlp_score = sematic_scores[cleaned_titles.index(c)]  # atribui a pontuação semântica ao título
        print(f"'{c.text[:30]:<30}' | h_score={c.h_score:.3f} nlp_score={c.nlp_score:.3f}")

    for c in cleaned_titles:
        c.combined_score = combine_scores(c.h_score, c.nlp_score)

    print(f"Títulos individuais : {len(best_candidates)}")
    print(f"Após deduplicação   : {len(cleaned_titles)}")
    print()


    # ── Regiões ───────────────────────────────
    print("[ 4/6 ] Detectando regiões...")

    # ── Section builder ───────────────────────
    print("[ 5/6 ] Construindo seções...")
    sections = build_sections(lines, cleaned_titles)
    print(f"        {len(sections)} seções montadas")
    print()

    # Prévia das seções para inspecionar antes de mandar ao LLM
    print("── Prévia das seções ──────────────────────")
    # for s in sections:
    #     preview_body = s.regions[:120]
    #     print(
    #         f"  [Pág {s.pages[0]}] {s.title[:50]:<50} "
    #         f"| corpo={len(s.regions):>5} chars  "
    #     )
    #     if preview_body:
    #         print(f"           └─ {preview_body}...")
    # print()

    # ── LLM ───────────────────────────────────
    print("[ 6/6 ] Enviando ao LLM...")

    # Monta JSON apenas com seções que têm conteúdo relevante
    # (descarta seções de capa/assinatura com corpo muito curto)

    sections_json = sections_to_json(sections)

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

    return sections, #resumo


test_full_pipeline()
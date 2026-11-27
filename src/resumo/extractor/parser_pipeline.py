

from resumo.extractor.group_text_line import group_atoms_into_lines
from resumo.extractor.parsers import decomp_pdf
from resumo.extractor.section.build_section import build_sections
from resumo.extractor.section.detect_region_text import detect_regions
from resumo.extractor.section.optimized_table import enrich_line_regions
from utils.text_size import get_text_size
from resumo.extractor.title.title_pipeline import detect_titles


def parse_document(path):
    
    atoms = decomp_pdf.extract_text_atoms(path)

    body_size = get_text_size(atoms)

    lines = group_atoms_into_lines(atoms)

    titles = detect_titles(atoms, body_size)

    regions = detect_regions(lines, titles)

    enriched_lines = enrich_line_regions(regions, path) 
    
    sections = build_sections(enriched_lines, titles)

    return sections
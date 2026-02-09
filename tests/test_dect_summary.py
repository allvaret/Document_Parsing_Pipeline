import extractor.summary_detector
from extractor.summary_detector import detect_summary
from extractor.parsers.decomp_pdf import extract_text_atoms

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"
result = extract_text_atoms(path)

atacht = detect_summary(result)
print(atacht)
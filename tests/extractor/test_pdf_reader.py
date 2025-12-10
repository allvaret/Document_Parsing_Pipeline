from extractor import PdfReader

reader = PdfReader.PdfReader("assets/BR_PT Demonstrações Financeiras 3T25.pdf")
texto = reader.extract_text()
print(texto)
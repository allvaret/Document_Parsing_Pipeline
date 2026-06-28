import fitz # PyMuPDF

def read_pdf(text:str):
    return fitz.open(text)

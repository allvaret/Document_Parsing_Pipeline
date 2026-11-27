import pymupdf

def read_pdf(text:str):
    return pymupdf.open(text)

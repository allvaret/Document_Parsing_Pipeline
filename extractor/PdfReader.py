import fitz # PyMuPDF

class PdfReader:
    def __init__(self, path):
        self.doc = fitz.open(path)

    def extract_text(self):
            text = ""
            for page in self.doc:
                text += page.get_text()
            return text

    def extract_pages(self):
            return [page.get_text() for page in self.doc]



def save_output(content: str, pdf_path: str, suffix: str):
    output_path = pdf_path.replace(".pdf", f"_{suffix}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


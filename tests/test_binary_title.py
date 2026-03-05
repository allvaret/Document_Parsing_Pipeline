from extractor.parsers.decomp_pdf import extract_text_atoms
from extractor.parsers.remove_repeated import remove_repeated
from utils.title.is_title import is_title
from utils.title.is_title import calculate_title_score
from utils.text_size import get_text_size

def test_binary_title():
    """Test if all functions work well together

    Rules: The test need to perform well all the three mains functions of extracting
    information from this pdf, they are: extract_text_atoms (just extract, already validated);
    remove_repeated (should remove repeated str, which 'is_title' detected in a wrong way),
    and is_title (working well too, but getting some non really titles in his output)
    - Debug information, to analyze and upgrade
    """

    path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"

    print("=== Integration Test: PDF Processing Pipeline ===")
    print(f"Testing PDF: {path}")
    print()

    # 1. extract_text_atoms - Extração de átomos de texto
    print("1. Extracting text atoms...")
    atoms = extract_text_atoms(path)
    print(f"   Total text atoms extracted: {len(atoms)}")

    if not atoms:
        print("   ERROR: No atoms extracted!")
        return None

    # 2. get_text_size - Determinar tamanho do corpo do texto
    print("2. Determining body text size...")
    body_size = get_text_size(atoms)
    print(f"   Detected body text size: {body_size}")

    # 3. is_title - Identificar títulos
    print("3. Identifying titles...")
    titles = []
    title_count = 0

    for i, atom in enumerate(atoms):
        is_title_result = is_title(atom, body_size, atom.page_height)

        if is_title_result:
            title_count += 1
            titles.append({
                'page': atom.page,
                'text': atom.text,
                'size': atom.size,
                'bold': atom.bold,
                'relative_y': atom.y0 / atom.page_height,
                'atom_index': i
            })

    print(f"   Total titles detected: {title_count}")
    # Could be useful to debug
    for i in titles:
        print(i)

    # Debug: Mostrar alguns títulos detectados
    print("   Sample detected titles:")
    for i, title in enumerate(titles[:5]):
        print(f"     {i+1}. Page {title['page']}: '{title['text'][:50]}...' (Size: {title['size']}, Bold: {title['bold']})")

    if len(titles) > 5:
        print(f"     ... and {len(titles) - 5} more")

    # 4. remove_repeated - Remover títulos repetidos
    print("4. Removing repeated titles...")
    filtered_titles = remove_repeated(titles)

    #debug time
    for i in filtered_titles:
        print(i)

    print(f"   Titles before filtering: {len(titles)}")
    print(f"   Titles after filtering: {len(filtered_titles)}")
    print(f"   Removed titles: {len(titles) - len(filtered_titles)}")

    # Debug: Análise das repetições
    from collections import Counter
    text_counts = Counter(title['text'] for title in titles)
    repeated_texts = {text: count for text, count in text_counts.items() if count > 2}

    if repeated_texts:
        print("   Texts repeated more than 2 times (removed):")
        for text, count in repeated_texts.items():
            print(f"     '{text[:50]}...' - {count} times")

    # 5. Resultados finais e validações
    print("\n=== FINAL RESULTS ===")
    print(f"✓ Text atoms extracted: {len(atoms)}")
    print(f"✓ Titles detected: {len(titles)}")
    print(f"✓ Titles after removing repetitions: {len(filtered_titles)}")

    # Validações básicas
    if len(filtered_titles) <= len(titles):
        print("✓ Filtering working correctly (no increase in titles)")
    else:
        print("✗ ERROR: Filtering increased number of titles!")

    if len(atoms) > 0 and len(titles) > 0:
        print("✓ Pipeline completed successfully")
    else:
        print("✗ ERROR: Pipeline failed - no data extracted")

    # Retornar resultados para análise
    return {
        'atoms_count': len(atoms),
        'titles_detected': titles,
        'titles_filtered': filtered_titles,
        'removed_count': len(titles) - len(filtered_titles),
        'repeated_texts': repeated_texts
    }


if __name__ == "__main__":
    results = test_binary_title()
    if results:
        print(f"\nTest completed. Results available for analysis.")


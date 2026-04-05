from extractor.parsers import decomp_pdf
from utils.title.is_title import calculate_title_score
from utils.text_size import get_text_size
from utils.title.candidate_filter import candidate_filter

path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/BR_PT Demonstrações Financeiras 3T25.pdf"

def test_title_detection():
    """Test the is_title function with detailed output and validation"""
    print("=== Title Detection Test ===")
    print(f"Testing PDF: {path}")
    print()
    
    # Extract text atoms from PDF
    atoms = decomp_pdf.extract_text_atoms(path)
    body_size = get_text_size(atoms)
    
    print(f"Total text atoms: {len(atoms)}")
    print(f"Detected body text size: {body_size}")
    print()
    
    # Track detected titles
    titles = []
    title_count = 0

    cf = candidate_filter(atoms)

    for i, atom in enumerate(cf):
        is_title_result = calculate_title_score(atom, body_size, atom.page_height)
        
        if is_title_result:
            title_count += 1
            titles.append({
                'page': atom.page,
                'text': atom.text,
                'size': atom.size,
                'bold': atom.bold,
                'relative_y': atom.y0 / atom.page_height,
                'score': is_title_result
            })
    
    # Print detailed results
    print(f"Total titles detected: {title_count}")
    print()
    
    print("=== Detected Titles ===")
    for i, title in enumerate(titles, 1):
        print(f"{i}. Page {title['page']}: '{title['text'][:50]}{'...' if len(title['text']) > 50 else ''}'")
        print(f"   Size: {title['size']:.1f} ({title['size']/body_size:.1f}x body size)")
        print(f"   Bold: {title['bold']}")
        print(f"   Position: {title['relative_y']:.2f} from top")
        print(f"   Score: {title['score']}")
        print()
    
    # Analysis
    print("=== Analysis ===")
    if title_count == 0:
        print("⚠️  No titles detected! Consider:")
        print("   - Checking if PDF has actual titles")
        print("   - Adjusting scoring thresholds")
        print("   - Verifying text extraction is working")
    elif title_count > len(atoms) * 0.3:  # More than 30% of atoms are titles
        print("⚠️  Too many titles detected! Consider:")
        print("   - Increasing the score threshold")
        print("   - Adjusting size or position criteria")
    else:
        print("✅ Title detection seems reasonable")
    
    return titles

def test_edge_cases():
    """Test edge cases for the is_title function"""
    print("\n=== Edge Case Tests ===")
    
    # Mock TextAtom for testing
    from extractor.TextAtom import TextAtom
    
    test_cases = [
        {
            'name': 'Large bold text at top',
            'atom': TextAtom("TEST TITLE", 0, 50, 70, 18.0, True, 800),
            'expected': True,
            'body_size': 12.0
        },
        {
            'name': 'Small regular text at top',
            'atom': TextAtom("regular text", 0, 50, 70, 10.0, False, 800),
            'expected': False,
            'body_size': 12.0
        },
        {
            'name': 'Large text at bottom',
            'atom': TextAtom("bottom title", 0, 600, 620, 18.0, True, 800),
            'expected': False,  # Position too low
            'body_size': 12.0
        },
        {
            'name': 'Long text at top',
            'atom': TextAtom("This is a very long text that should not be considered a title because it exceeds the character limit", 0, 50, 70, 18.0, True, 800),
            'expected': False,  # Too long
            'body_size': 12.0
        }
    ]
    
    for test in test_cases:
        result = calculate_title_score(test['atom'], test['body_size'], test['atom'].page_height)
        status = "✅" if result == test['expected'] else "❌"
        print(f"{status} {test['name']}: Expected {test['expected']}, Got {result}")

if __name__ == "__main__":
    # Run the main test
    titles = test_title_detection()

    #Run edge case tests


    print(f"\n=== Summary ===")
    print(f"Main test found {len(titles)} titles")
    print("Review the detected titles above to see if they make sense for your PDF")

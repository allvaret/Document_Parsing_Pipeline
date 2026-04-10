from src.extractor.parsers.decomp_pdf import extract_text_atoms
from src.utils.title.is_title import calculate_title_score
from src.utils.title.classify_title_confidence import classify_title_confidence
from src.utils.title.relative_title_importance import get_relative_title_importance
from src.utils import get_text_size
from collections import Counter
import json
import os

def test_probabilistic_system(atoms, body_size):
    """Testa novo sistema probabilístico com scoring 0-100"""
    
    print("=== PROBABILISTIC TITLE SYSTEM TEST ===")
    
    scores = []
    classifications = []
    detailed_results = []
    
    for i, atom in enumerate(atoms):
        # Calcular score do título
        score = calculate_title_score(atom, body_size, atom.page_height)
        
        # Classificar basedo no score
        classification = classify_title_confidence(score)
        
        # Armazenar resultados
        scores.append(score)
        classifications.append(classification)
        
        detailed_results.append({
            'atom_index': i,
            'text': atom.text,
            'page': atom.page,
            'score': score,
            'classification': classification,
            'size': atom.size,
            'bold': atom.bold,
            'relative_y': atom.y0 / atom.page_height
        })
    
    # Análise estatística dos scores
    analyze_score_distribution(scores)
    
    # Análise das classificações
    analyze_classifications(classifications)
    
    # Obter importância relativa
    relative_importance = get_relative_title_importance(scores)
    
    # Adicionar importância relativa aos resultados
    for i, result in enumerate(detailed_results):
        result['relative_importance'] = relative_importance[i]
    
    # Mostrar exemplos por categoria
    show_examples_by_category(detailed_results)
    
    return {
        'scores': scores,
        'classifications': classifications,
        'detailed_results': detailed_results,
        'relative_importance': relative_importance
    }

def analyze_score_distribution(scores):
    """Análise estatística da distribuição de scores"""
    print("\n--- SCORE DISTRIBUTION ANALYSIS ---")
    
    if not scores:
        print("No scores to analyze")
        return
    
    # Estatísticas básicas
    min_score = min(scores)
    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    
    print(f"Score range: {min_score:.1f} - {max_score:.1f}")
    print(f"Average score: {avg_score:.1f}")
    
    # Distribuição por faixas
    ranges = [
        (0, 20, "Very Low"),
        (20, 40, "Low"), 
        (40, 60, "Medium"),
        (60, 80, "High"),
        (80, 100, "Very High")
    ]
    
    print("\nScore distribution:")
    for min_range, max_range, label in ranges:
        count = len([s for s in scores if min_range <= s < max_range])
        percentage = (count / len(scores)) * 100
        print(f"  {label} ({min_range}-{max_range}): {count} atoms ({percentage:.1f}%)")

def analyze_classifications(classifications):
    """Análise das classificações de títulos"""
    print("\n--- CLASSIFICATION ANALYSIS ---")
    
    if not classifications:
        print("No classifications to analyze")
        return
    
    # Contar classificações
    class_counts = Counter(classifications)
    total = len(classifications)
    
    print("Classification distribution:")
    for classification, count in class_counts.items():
        percentage = (count / total) * 100
        print(f"  {classification}: {count} atoms ({percentage:.1f}%)")

def show_examples_by_category(detailed_results):
    """Mostra exemplos de cada categoria de classificação"""
    print("\n--- EXAMPLES BY CATEGORY ---")
    
    # Agrupar por classificação
    by_category = {}
    for result in detailed_results:
        category = result['classification']
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(result)
    
    # Mostrar exemplos para cada categoria
    for category, items in by_category.items():
        if category == "NOT_TITLE":
            continue  # Pular não-títulos para economizar espaço
            
        print(f"\n{category} examples:")
        
        # Ordenar por score (maior primeiro)
        items.sort(key=lambda x: x['score'], reverse=True)
        
        # Mostrar top 3 exemplos
        for i, item in enumerate(items[:3]):
            text_preview = item['text'][:50] + "..." if len(item['text']) > 50 else item['text']
            print(f"  {i+1}. Score: {item['score']:.1f} | Page {item['page']} | '{text_preview}'")
            print(f"     Size: {item['size']:.1f} | Bold: {item['bold']} | Rel. Importance: {item['relative_importance']:.2f}")

def compare_with_binary_system(binary_results, probabilistic_results):
    """Compara sistema binário com probabilístico"""
    print("\n=== BINARY VS PROBABILISTIC COMPARISON ===")
    
    # Converter sistema probabilístico para binário (threshold 60)
    prob_binary = [r for r in probabilistic_results['detailed_results'] if r['score'] >= 60]
    strong_only = [r for r in probabilistic_results['detailed_results'] if r['classification'] == 'STRONG_TITLE']
    
    print(f"Binary system: {len(binary_results['titles_detected'])} titles")
    print(f"Probabilistic (threshold 60): {len(prob_binary)} titles")
    print(f"Probabilistic (STRONG only): {len(strong_only)} titles")
    
    # Análise de diferenças
    print("\nDifferences analysis:")
    
    # Títulos detectados apenas pelo sistema binário
    binary_texts = {t['text'] for t in binary_results['titles_detected']}
    prob_texts = {r['text'] for r in prob_binary}
    
    only_binary = binary_texts - prob_texts
    only_prob = prob_texts - binary_texts
    common = binary_texts & prob_texts
    
    print(f"  Common titles: {len(common)}")
    print(f"  Only in binary: {len(only_binary)}")
    print(f"  Only in probabilistic: {len(only_prob)}")
    
    # Mostrar exemplos das diferenças
    if only_binary:
        print("\nExamples only in binary system:")
        for i, text in enumerate(list(only_binary)[:3]):
            print(f"  {i+1}. '{text[:50]}...'")
    
    if only_prob:
        print("\nExamples only in probabilistic system:")
        for i, text in enumerate(list(only_prob)[:3]):
            print(f"  {i+1}. '{text[:50]}...'")

def store_test_results(results, filename):
    """Armazena resultados para análise posterior"""
    os.makedirs('test_results', exist_ok=True)
    
    # Converter para formato serializável
    serializable_results = {
        'scores': results['scores'],
        'classifications': results['classifications'],
        'detailed_results': results['detailed_results'],
        'relative_importance': results['relative_importance']
    }
    
    with open(f'test_results/{filename}.json', 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults stored in test_results/{filename}.json")

def test_title_evolution():
    """Teste completo da evolução do sistema de títulos"""
    
    path = "D:/Projetos/Projetoes/SmartLazys/finance-data-platform/assets/comunicado_petr3_33064.pdf"
    
    print("=== TITLE EVOLUTION TEST ===")
    print(f"Testing PDF: {path}")
    print()
    
    # 1. Extração de dados
    print("1. Extracting text atoms...")
    atoms = extract_text_atoms(path)
    body_size = get_text_size(atoms)
    
    print(f"   Total atoms: {len(atoms)}")
    print(f"   Body size: {body_size}")
    
    # 2. Testar sistema probabilístico
    print("\n2. Testing probabilistic system...")
    probabilistic_results = test_probabilistic_system(atoms, body_size)
    
    # 3. Comparar com sistema binário (se disponível)
    try:
        from test_binary_title import test_binary_title
        print("\n3. Comparing with binary system...")
        binary_results = test_binary_title()
        compare_with_binary_system(binary_results, probabilistic_results)
    except ImportError:
        print("\n3. Binary system test not available - skipping comparison")
    
    # 4. Armazenar resultados
    store_test_results(probabilistic_results, 'title_evolution_results')
    
    print("\n=== EVOLUTION TEST COMPLETED ===")
    return probabilistic_results

if __name__ == "__main__":
    results = test_title_evolution()
    print(f"\nEvolution test completed with {len(results['detailed_results'])} atoms analyzed")
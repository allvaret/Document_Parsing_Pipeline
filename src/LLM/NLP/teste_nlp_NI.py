import pdfplumber
import spacy
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

# Carregar NLP (spaCy é 3x mais rápido que NLTK) [web:14]
nlp = spacy.load("pt_core_news_sm")

def extrair_features_para_linha(texto, font_size=12, is_bold=False, whitespace_acima=0):
    """Extrai TODAS as features para uma linha de texto"""
    doc = nlp(texto)
    
    features = {
        # === HEURÍSTICAS ===
        'font_size': font_size,
        'is_bold': 1 if is_bold else 0,
        'whitespace_acima': whitespace_acima,
        'comprimento': len(texto),
        'num_palavras': len(texto.split()),
        'is_uppercase': 1 if texto.isupper() else 0,
        'termina_pontuacao': 1 if texto and texto[-1] in '.!?:;' else 0,
        
        # === NLP FEATURES (spaCy) === [web:14]
        'num_entidades': len(doc.ents),
        'proporcao_substantivos': sum(1 for t in doc if t.pos_ in ['NOUN', 'PROPN']) / max(len(doc), 1),
        'proporcao_verbos': sum(1 for t in doc if t.pos_ == 'VERB') / max(len(doc), 1),
        'proporcao_adjetivos': sum(1 for t in doc if t.pos_ == 'ADJ') / max(len(doc), 1),
        'densidade_conteudo': sum(1 for t in doc if not t.is_stop and not t.is_punct) / max(len(doc), 1),
        'tem_artigo_inicio': 1 if len(doc) > 0 and doc[0].pos_ == 'DET' else 0,
    }
    
    return features

def criar_dataset_treino():
    """
    Crie este dataset marcando ~50-100 exemplos do SEU PDF
    Label: 1 = título real, 0 = falso positivo
    """
    dados = {
        'texto': [
            # Títulos reais (label=1)
            "Introdução", "MÉTODOS E TECNOLOGIAS", "Resultados da Pesquisa",
            "Conclusão Final", "Capítulo 3: Análise de Dados", "REFERÊNCIAS"
            # Falsos positivos (label=0)
            "O estudo foi realizado em 2024.",
            "A empresa tem 150 funcionários.",
            "João Silva foi o responsável.",
            "Este documento contém 30 páginas.",
        ],
        'font_size': [18, 16, 14, 14, 16, 12, 11, 11, 11, 11, 11],
        'is_bold': [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0],
        'whitespace_acima': [12, 12, 10, 10, 12, 4, 2, 2, 4, 2, 2],
        'label': [1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0]
    }
    return pd.DataFrame(dados)

def treinar_classificador(df):
    """Treina o classificador Random Forest"""
    X = []
    y = []
    
    for _, row in df.iterrows():
        features = extrair_features_para_linha(
            row['texto'],
            font_size=row['font_size'],
            is_bold=row['is_bold'],
            whitespace_acima=row['whitespace_acima']
        )
        X.append(list(features.values()))
        y.append(row['label'])
    
    feature_names = list(features.keys())
    
    # Treinar Random Forest (funciona bem com poucos dados) [web:25]
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)
    
    # Mostrar importância das features
    importancia = pd.DataFrame({
        'feature': feature_names,
        'importancia': clf.feature_importances_
    }).sort_values('importancia', ascending=False)
    
    print("Top 5 features mais importantes:")
    print(importancia.head(5))
    
    return clf, feature_names

def detectar_titulos_no_pdf(clf, feature_names, pdf_path):
    """Aplica o classificador no PDF"""
    with pdfplumber.open(pdf_path) as pdf:
        titulos = []
        
        for page in pdf.pages:
            # Extrair texto COM formatação
            texto_com_format = page.extract_text()
            
            if texto_com_format:
                for linha in texto_com_format.split('\n'):
                    if linha.strip():
                        features = extrair_features_para_linha(linha.strip())
                        X = [[features[feat] for feat in feature_names]]
                        
                        predicao = clf.predict(X)[0]
                        confianca = clf.predict_proba(X)[0][1]
                        
                        if predicao == 1 and confianca > 0.7:
                            titulos.append({
                                'texto': linha.strip(),
                                'confianca': confianca,
                                'pagina': page.page_number
                            })
    
    return titulos

# === USO ===
if __name__ == "__main__":
    # 1. Criar dataset (faça com exemplos REAIS do seu PDF)
    df = criar_dataset_treino()
    
    # 2. Treinar
    clf, feature_names = treinar_classificador(df)
    
    # 3. Salvar
    joblib.dump(clf, "modelo_titulos.pkl")
    joblib.dump(feature_names, "feature_names.pkl")
    
    # 4. Usar
    clf = joblib.load("modelo_titulos.pkl")
    feature_names = joblib.load("feature_names.pkl")
    titulos = detectar_titulos_no_pdf(clf, feature_names, "seu_documento.pdf")
    
    print(f"Detectados {len(titulos)} títulos:")
    for t in titulos:
        print(f"  - {t['texto']} (confiança: {t['confianca']:.2%})")
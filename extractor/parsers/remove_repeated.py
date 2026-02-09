from collections import Counter

def remove_repeated(titles: list):
    # Contar repetições de cada texto
    repeticoes = {}
    for titulo in titles:
        texto = titulo["text"]
        if texto in repeticoes:
            repeticoes[texto] += 1
        else:
            repeticoes[texto] = 1

    # Filtrar títulos baseado nas repetições
    titulos_filtrados = []
    for titulo in titles:
        texto = titulo["text"]
        if repeticoes[texto] <= 2:  # Mantém se repetiu 1 ou 2 vezes
            titulos_filtrados.append(titulo)
        # Se repetiu > 2 vezes, não adiciona (remove)

    return titulos_filtrados

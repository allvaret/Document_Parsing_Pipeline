from collections import Counter

def remove_repeated(titles: list):
    # Contar repetições de cada texto
    repeticoes = {}
    qtd_titulo = 0
    for titulo in titles:
        qtd_titulo += 1
        texto = titulo["text"]
        if texto in repeticoes:
            repeticoes[texto] += 1
        else:
            repeticoes[texto] = 1
    print(qtd_titulo)

    # Filtrar títulos baseado nas repetições
    titulos_filtrados = []
    particao = qtd_titulo * 0.1
    print(particao)

    for titulo in titles:
        texto = titulo["text"]
        if repeticoes[texto] <= particao:  # Mantém se repetiu menos de 20% das aparições
            titulos_filtrados.append(titulo)

    return titulos_filtrados


def detect_same_y(titles: list, page_height=None):
    # Nao deve repetir o relative_y na mesma pagina, do contrario, e um paragrafo
    """Vou pegar um relative_y e olhar pra pagina dele, se tiver outro item no mesmo relative_y, entao nao e um titulo;
    se eu olhei pra frente, e encontrei outros relatives_ys, nao preciso olhar denovo quando chegar na iteracao deles, posso adicionar em um """
    # Contar repetições de cada y0
    repeticoes_pagina = {}
    qtd_y = 0

    for titulo in titles:
        repeticoes = {}

        page0 = titulo.page
        page1 = page0
        page5 = page1
        if page5 == page1:



        repeticoes = page0

        y0 = titulo.y0

        for y in page:
            print(y0)




"""        if y0 in page:
            repeticoes[texto] += 1
        else:
            repeticoes[texto] = 1
    print(qtd_titulo)

    # Filtrar títulos baseado nas repetições
    titulos_filtrados = []
    particao = qtd_titulo * 0.1
    print(particao)

    for titulo in titles:
        texto = titulo["text"]
        if repeticoes[texto] <= particao:  # Mantém se repetiu menos de 20% das aparições
            titulos_filtrados.append(titulo)

    return titulos_filtrados
"""


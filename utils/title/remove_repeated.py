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


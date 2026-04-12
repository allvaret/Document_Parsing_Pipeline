import statistics
import math


def _page_distribution_score(pages: list[int]) -> dict:
    """
    Analisa a distribuição de páginas de um título para classificar
    se é estrutural (cabeçalho/rodapé) ou legítimo (seção real).

    Retorna um dict com os sinais individuais para rastreabilidade.
    """
    n = len(pages)

    if n == 1:
        return {"structural": False, "reason": "single_occurrence"}

    gaps = [pages[i + 1] - pages[i] for i in range(n - 1)]
    mean_gap = statistics.mean(gaps)

    # ── Sinal 1: regularidade dos gaps (coeficiente de variação) ──────────
    # CV baixo = gaps quase iguais = periódico = estrutural
    # CV alto  = gaps irregulares  = esparso   = legítimo
    if len(gaps) > 1:
        cv_gap = statistics.stdev(gaps) / mean_gap if mean_gap > 0 else 999
    else:
        cv_gap = 1.0  # só 2 páginas, não dá pra calcular periodicidade

    # ── Sinal 2: densidade absoluta ───────────────────────────────────────
    # Span = diferença entre primeira e última página
    # n / span alto = muito denso = estrutural
    span = pages[-1] - pages[0] + 1
    density = n / span if span > 0 else 1.0

    # ── Sinal 3: gap médio pequeno ────────────────────────────────────────
    # Cabeçalhos aparecem a cada 1-3 páginas
    # Seções legítimas costumam ter gaps maiores
    small_gap = mean_gap <= 3.0

    # ── Sinal 4: entropia da distribuição ─────────────────────────────────
    # Entropia alta = distribuição uniforme ao longo do doc = estrutural
    # Entropia baixa = concentrado em poucas regiões = legítimo
    if span > 1:
        # Normaliza posição de cada página no span [0, 1]
        normalized = [(p - pages[0]) / span for p in pages]
        # Divide em 5 buckets e calcula entropia
        buckets = [0] * 5
        for pos in normalized:
            idx = min(int(pos * 5), 4)
            buckets[idx] += 1
        total = sum(buckets)
        entropy = -sum(
            (b / total) * math.log2(b / total)
            for b in buckets if b > 0
        )
        max_entropy = math.log2(5)
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
    else:
        normalized_entropy = 0.0

    high_entropy = normalized_entropy > 0.7

    return {
        "cv_gap":              round(cv_gap, 3),
        "density":             round(density, 3),
        "mean_gap":            round(mean_gap, 2),
        "normalized_entropy":  round(normalized_entropy, 3),
        "small_gap":           small_gap,
        "high_entropy":        high_entropy,
        "n_occurrences":       n,
    }


def remove_repeated(titles: list, debug: bool = False) -> list:
    """
    Remove títulos estruturais (cabeçalhos/rodapés) sem usar threshold fixo.

    Classificação baseada em comportamento de distribuição de páginas:
    - Periódico + denso + uniforme → estrutural → mantém só primeira ocorrência
    - Esparso + irregular           → legítimo   → mantém todas ocorrências
    """
    if not titles:
        return []

    # Agrupar por texto
    grupos: dict[str, list] = {}
    for t in titles:
        grupos.setdefault(t["text"], []).append(t)

    resultado = []

    for texto, ocorrencias in grupos.items():
        if len(ocorrencias) == 1:
            resultado.append(ocorrencias[0])
            continue

        pages = sorted([o["page"] for o in ocorrencias])
        stats = _page_distribution_score(pages)

        # ── Decisão por comportamento, não por threshold ───────────────────
        #
        # É estrutural se pelo menos 2 de 3 sinais independentes concordam:
        #
        # A) CV baixo (< 0.4)  → gaps muito regulares → periódico
        # B) Densidade alta (> 0.4) + gap pequeno     → aparece em quase toda página
        # C) Entropia alta (> 0.7)                    → distribuição uniforme no doc
        #
        signal_a = stats["cv_gap"] < 0.4
        signal_b = stats["density"] > 0.4 and stats["small_gap"]
        signal_c = stats["high_entropy"]

        vote = sum([signal_a, signal_b, signal_c])
        is_structural = vote >= 2

        if debug:
            print(
                f"  {'STRUCT' if is_structural else 'LEGIT ':6} "
                f"[{vote}/3] {repr(texto[:50]):<55} "
                f"n={stats['n_occurrences']:>3}  "
                f"cv={stats['cv_gap']:.2f}  "
                f"dens={stats['density']:.2f}  "
                f"gap={stats['mean_gap']:.1f}  "
                f"ent={stats['normalized_entropy']:.2f}"
            )

        if is_structural:
            first = min(ocorrencias, key=lambda o: o["page"])
            resultado.append(first)
        else:
            resultado.extend(ocorrencias)

    resultado.sort(key=lambda o: (o["page"], o["relative_y"]))
    return resultado
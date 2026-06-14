from dataclasses import dataclass
from typing import List

from extractor import TextAtom


def calculate_vertical_spacing(atoms: List[TextAtom]) -> List[TextAtom]:
    """
    Calcula as distâncias verticais entre átomos consecutivos.
    
    - vertical_whitespace_up: distância do topo do átomo atual até a base do átomo anterior.
      Para o primeiro átomo da página, é a distância do topo do átomo até o topo da página.
    - vertical_whitespace_down: distância da base do átomo atual até o topo do próximo átomo.
      Para o último átomo da página, permanece 0.0.
    
    O cálculo é feito página por página, assumindo que os átomos estão ordenados
    por posição vertical (y decrescente = mais próximo do topo).
    """
    if not atoms:
        return atoms
    
    # Agrupa átomos por página
    pages = {}
    for atom in atoms:
        if atom.page not in pages:
            pages[atom.page] = []
        pages[atom.page].append(atom)
    
    result = []
    
    for page_num in sorted(pages.keys()):
        page_atoms = pages[page_num]
        
        # Ordena por y0 decrescente (coordenadas PDF: maior y = mais próximo do topo)
        page_atoms.sort(key=lambda a: a.y0, reverse=True)
        
        for i, current in enumerate(page_atoms):
            # Calcula vertical_whitespace_up
            if i == 0:
                # Primeiro átomo: distância do topo da página até o topo do átomo
                current.vertical_whitespace_up = current.page_height - current.y0
            else:
                # Distância do topo do átomo atual até a base do átomo anterior
                previous = page_atoms[i - 1]
                current.vertical_whitespace_up = previous.y1 - current.y0
            
            # Calcula vertical_whitespace_down
            if i < len(page_atoms) - 1:
                # Distância da base do átomo atual até o topo do próximo átomo
                next_atom = page_atoms[i + 1]
                current.vertical_whitespace_down = current.y1 - next_atom.y0
            else:
                current.vertical_whitespace_down = 0.0
            
            result.append(current)
    
    return result


def calcular_vertical_space(atom: TextAtom, atoms_pagina: List[TextAtom]) -> tuple[float, float]:
    """
    Calcula vertical_space_above e vertical_space_below
    ATENÇÃO: Apenas para atoms da MESMA página
    """
    # Pega todos os atoms da mesma página ordenados por y0 (topo → fundo)
    atoms_ordenados = sorted(
        [a for a in atoms_pagina if a.page == atom.page],
        key=lambda a: a.y0
    )
    
    # Encontrar índice deste atom
    idx = next(i for i, a in enumerate(atoms_ordenados) if a is atom)
    
    # Vertical space ACIMA (próximo atom acima)
    space_above = 0.0
    if idx > 0:
        atom_acima = atoms_ordenados[idx - 1]
        space_above = atom.y0 - atom_acima.y1  # gap entre y1 do acima e y0 deste
    
    # Vertical space ABAIXO (próximo atom abaixo)
    space_below = 0.0
    if idx < len(atoms_ordenados) - 1:
        atom_abaixo = atoms_ordenados[idx + 1]
        space_below = atom_abaixo.y0 - atom.y1  # gap entre y1 deste e y0 do abaixo
    
    return space_above, space_below

def normalizar_vertical_space(space: float, page_height: float) -> float:
    """Normaliza para 0-1 (independente do tamanho da página)"""
    return space / page_height if page_height > 0 else 0.0
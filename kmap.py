"""
Logi — Truth Table & Karnaugh Map Module (kmap.py)
"""

import itertools
from typing import List, Tuple, Set


def generate_combinations(num_vars: int) -> List[Tuple[int, ...]]:
    """
    Generates the binary combinations sequence for `num_vars` variables.
    Example for num_vars=2: [(0, 0), (0, 1), (1, 0), (1, 1)]
    """
    return list(itertools.product([0, 1], repeat=num_vars))


def display_truth_table(variables: List[str], truth_table: List[List[int]]) -> None:
    """
    Formats and prints the complete truth table to the console.
    """
    header = " | ".join(variables) + " || F"
    sep = "-" * len(header)
    print(header)
    print(sep)
    for row in truth_table:
        inputs_str = " | ".join(str(b) for b in row[:-1])
        print(f"{inputs_str} || {row[-1]}")


def _count_ones(n: int) -> int:
    return bin(n).count("1")


def _combine_terms(t1: Tuple[int, int], t2: Tuple[int, int]) -> Tuple[int, int] | None:
    val1, mask1 = t1
    val2, mask2 = t2
    if mask1 != mask2:
        return None
    diff = val1 ^ val2
    if diff != 0 and (diff & (diff - 1)) == 0:
        return (val1 & ~diff, mask1 | diff)
    return None


def _term_covers(term: Tuple[int, int], minterm: int) -> bool:
    val, mask = term
    return (minterm & ~mask) == val


def _term_to_expr(term: Tuple[int, int], variables: List[str]) -> str:
    val, mask = term
    n = len(variables)
    literals = []
    for i, var in enumerate(variables):
        bit_pos = n - 1 - i
        if not (mask & (1 << bit_pos)):
            if val & (1 << bit_pos):
                literals.append(var)
            else:
                literals.append(f"{var}'")
    return "".join(literals) if literals else "1"


def _minimize_sop(variables: List[str], minterms: List[int]) -> List[Tuple[int, int]]:
    """Finds minimal prime implicant cover using Quine-McCluskey + Petrick/greedy reduction."""
    if not minterms:
        return []

    current_groups: Set[Tuple[int, int]] = {(m, 0) for m in minterms}
    prime_implicants: Set[Tuple[int, int]] = set()

    while current_groups:
        next_groups: Set[Tuple[int, int]] = set()
        used: Set[Tuple[int, int]] = set()
        terms_list = sorted(current_groups, key=lambda x: (_count_ones(x[0]), x[0], x[1]))

        for i in range(len(terms_list)):
            for j in range(i + 1, len(terms_list)):
                combined = _combine_terms(terms_list[i], terms_list[j])
                if combined is not None:
                    used.add(terms_list[i])
                    used.add(terms_list[j])
                    next_groups.add(combined)

        for term in current_groups:
            if term not in used:
                prime_implicants.add(term)

        current_groups = next_groups

    uncovered = set(minterms)
    selected: List[Tuple[int, int]] = []
    pi_list = sorted(prime_implicants, key=lambda t: (-_count_ones(t[1]), t[0]))

    # Essential prime implicants first
    for m in list(uncovered):
        covering = [pi for pi in pi_list if _term_covers(pi, m)]
        if len(covering) == 1 and covering[0] not in selected:
            selected.append(covering[0])

    for pi in selected:
        for m in list(uncovered):
            if _term_covers(pi, m):
                uncovered.discard(m)

    # Greedy cover for remaining minterms
    while uncovered:
        best_pi = max(
            pi_list,
            key=lambda pi: (sum(1 for m in uncovered if _term_covers(pi, m)), _count_ones(pi[1])),
        )
        selected.append(best_pi)
        for m in list(uncovered):
            if _term_covers(best_pi, m):
                uncovered.discard(m)

    return selected


def _print_kmap_grid(variables: List[str], truth_table: List[List[int]]) -> None:
    """Prints a formatted Gray-code K-Map grid for 2, 3, or 4 variables."""
    n = len(variables)
    out_map = {idx: row[-1] for idx, row in enumerate(truth_table)}

    if n == 2:
        row_vars, col_vars = variables[0], variables[1]
        row_codes = [(0, "0"), (1, "1")]
        col_codes = [(0, "0"), (1, "1")]
    elif n == 3:
        row_vars, col_vars = variables[0], "".join(variables[1:])
        row_codes = [(0, "0"), (1, "1")]
        col_codes = [(0, "00"), (1, "01"), (3, "11"), (2, "10")]
    elif n == 4:
        row_vars, col_vars = "".join(variables[:2]), "".join(variables[2:])
        row_codes = [(0, "00"), (1, "01"), (3, "11"), (2, "10")]
        col_codes = [(0, "00"), (1, "01"), (3, "11"), (2, "10")]
    else:
        return

    col_shift = n - len(row_codes[0][1])
    header_cells = " | ".join(f"{lbl:^4}" for _, lbl in col_codes)
    label_pad = f"{row_vars}\\{col_vars}"
    header_line = f"  {label_pad:<5} || {header_cells}"
    print("K-Map Grid (Gray Code):")
    print(header_line)
    print("  " + "-" * (len(header_line) - 2))
    for r_val, r_lbl in row_codes:
        cells = []
        for c_val, _ in col_codes:
            m_idx = (r_val << col_shift) | c_val
            cells.append(f"{out_map.get(m_idx, 0):^4}")
        print(f"  {r_lbl:<5} || " + " | ".join(cells))
    print()


def simplify_kmap(variables: List[str], truth_table: List[List[int]]) -> str:
    """
    Performs K-Map reduction and returns the simplified logic expression as a string.
    """
    minterms = [idx for idx, row in enumerate(truth_table) if row[-1] == 1]
    if not minterms:
        print("All outputs are 0 -> Constant 0.")
        return "0"
    if len(minterms) == len(truth_table):
        print("All outputs are 1 -> Constant 1.")
        return "1"

    _print_kmap_grid(variables, truth_table)

    selected_pis = _minimize_sop(variables, minterms)
    print("Prime Implicant Groups:")
    terms = []
    for idx, pi in enumerate(selected_pis, start=1):
        covered = [m for m in minterms if _term_covers(pi, m)]
        term_str = _term_to_expr(pi, variables)
        terms.append(term_str)
        print(f"  Group {idx}: m{tuple(covered)} -> {term_str}")

    expr = " + ".join(terms)
    return expr

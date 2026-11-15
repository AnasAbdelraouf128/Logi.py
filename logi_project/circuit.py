"""
circuit.py -- Boolean Algebra Simplification & Logic Circuit Module

Implements:
    - simplify_boolean(variables: list[str], truth_table: list[list[int]]) -> str
    - draw_logic_circuit(expression: str) -> None
"""

from typing import List, Tuple, Optional


def simplify_boolean(variables: List[str], truth_table: List[List[int]]) -> str:
    """
    Simplifies logic using Boolean algebraic laws (Absorption, Adjacency/Combining
    XY + XY' = X, Idempotence, and Essential Implicant Reduction), prints the
    canonical and simplified SOP expressions, and returns the simplified expression string.
    """
    n = len(variables)
    if not truth_table or n == 0:
        return "0"

    on_indices = [i for i, row in enumerate(truth_table) if row[-1] == 1]
    print("=" * 45)
    print("BOOLEAN ALGEBRA SIMPLIFICATION".center(45))
    print("=" * 45)

    if not on_indices:
        print("Canonical SOP : F = 0")
        print("Simplified SOP: F = 0")
        print("=" * 45)
        return "0"

    if len(on_indices) == (1 << n):
        print("Canonical SOP : F = 1 (Identity / Tautology Law)")
        print("Simplified SOP: F = 1")
        print("=" * 45)
        return "1"

    canonical_terms = []
    for row in truth_table:
        if row[-1] == 1:
            lits = [
                v if bit == 1 else f"{v}'"
                for v, bit in zip(variables, row[:n])
            ]
            canonical_terms.append("".join(lits))

    print(f"Active Minterms: Σm({', '.join(map(str, on_indices))})")
    print(f"Canonical SOP  : F = {' + '.join(canonical_terms)}\n")

    current = [(frozenset({m}), format(m, f"0{n}b")) for m in on_indices]
    step_num = 1
    while True:
        used = set()
        nxt = []
        for i in range(len(current)):
            for j in range(i + 1, len(current)):
                p1, b1 = current[i]
                p2, b2 = current[j]
                diffs = [k for k in range(n) if b1[k] != b2[k]]
                if len(diffs) == 1 and b1[diffs[0]] != "-" and b2[diffs[0]] != "-":
                    k = diffs[0]
                    cand = (frozenset(p1 | p2), b1[:k] + "-" + b1[k + 1:])
                    if cand not in nxt:
                        nxt.append(cand)
                    used.add(i)
                    used.add(j)
        for i in range(len(current)):
            if i not in used and current[i] not in nxt:
                nxt.append(current[i])
        if not used:
            break
        current = nxt
        step_num += 1

    prime_implicants = current
    selected = []
    for m in on_indices:
        coverers = [pi for pi in prime_implicants if m in pi[0]]
        if len(coverers) == 1 and coverers[0] not in selected:
            selected.append(coverers[0])

    covered = set().union(*(pi[0] for pi in selected)) if selected else set()
    remaining = set(on_indices) - covered
    while remaining:
        best = max(prime_implicants, key=lambda pi: len(pi[0] & remaining))
        if best not in selected:
            selected.append(best)
        remaining -= best[0]

    def render(pattern: str) -> str:
        parts = []
        for v, bit in zip(variables, pattern):
            if bit == "1":
                parts.append(v)
            elif bit == "0":
                parts.append(v + "'")
        return "".join(parts) if parts else "1"

    print("Algebraic Reduction (Adjacency X·Y + X·Y' = X & Absorption):")
    for idx, (mset, pat) in enumerate(selected, start=1):
        print(f"  Term {idx}: m{sorted(mset)} -> {render(pat)}")

    terms = sorted((render(pi[1]) for pi in selected), key=lambda t: (len(t), t))
    reduced_expr = " + ".join(terms) if terms else "0"
    print(f"\nSimplified SOP : F = {reduced_expr}")
    print("=" * 45)
    return reduced_expr


def _parse_term(term: str) -> List[str]:
    """Split a product term like "A'BC" into literals ["A'", "B", "C"]."""
    literals: List[str] = []
    for ch in term:
        if ch == "'" and literals:
            literals[-1] += "'"
        elif ch.isalpha():
            literals.append(ch)
    return literals


def _parse_products(expression: str) -> Optional[List[List[Tuple[str, bool]]]]:
    """Parses a SOP expression into a list of [(var, is_negated), ...] product terms."""
    expr = expression.strip()
    if expr.startswith("F") and "=" in expr:
        expr = expr.split("=", 1)[1].strip()
    if not expr or expr == "0":
        return []
    if expr == "1":
        return None

    products: List[List[Tuple[str, bool]]] = []
    for raw in expr.split("+"):
        t = raw.strip()
        if not t:
            continue
        if t == "1":
            return None
        lits = _parse_term(t)
        if lits:
            products.append([(lit[0], lit.endswith("'")) for lit in lits])
    return products


def draw_logic_circuit(expression: str) -> None:
    """
    Generates and prints the two-level logic gate circuit diagram and breakdown.
    """
    expression = expression.strip()
    if expression.startswith("F") and "=" in expression:
        expression = expression.split("=", 1)[1].strip()

    print("=" * 45)
    print("LOGIC CIRCUIT".center(45))
    print("=" * 45)
    print(f"F = {expression}\n")

    if expression in ("0", "1", ""):
        val = expression if expression else "0"
        print(f"Constant output: F is always {val} (no gates needed).")
        print("=" * 45)
        return

    terms = [_parse_term(t.strip()) for t in expression.split("+") if t.strip()]
    if not terms:
        print("Constant output: F is always 0 (no gates needed).")
        print("=" * 45)
        return

    # 1. NOT gates for every complemented variable
    inverted = sorted({lit[0] for term in terms for lit in term if lit.endswith("'")})
    if inverted:
        print("NOT gates:")
        for v in inverted:
            print(f"  {v} ----[NOT]---- {v}'")
        print()

    # 2. AND gates (one per term with 2+ literals)
    print("AND gates:")
    names = []
    for i, literals in enumerate(terms, start=1):
        name = f"T{i}"
        names.append(name)
        if len(literals) == 1:
            print(f"  {literals[0]} ------------------- {name}   (single literal, wire only)")
            continue
        width = max(len(l) for l in literals)
        mid = len(literals) // 2
        for j, lit in enumerate(literals):
            gate = "[AND]---- " + name if j == mid else "|"
            print(f"  {lit.ljust(width)} ----{gate}")
    print()

    # 3. OR gate combining all the terms
    if len(names) == 1:
        print(f"Output: F = {names[0]}")
    else:
        print("OR gate:")
        width = max(len(n) for n in names)
        mid = len(names) // 2
        for j, name in enumerate(names):
            gate = "[OR]---- F" if j == mid else "|"
            print(f"  {name.ljust(width)} ----{gate}")
    print("=" * 45)

"""
Logi — Boolean Algebra & Logic Circuit Module (circuit.py)
"""

from typing import List, Tuple, Optional


def simplify_boolean(variables: List[str], truth_table: List[List[int]]) -> str:
    """
    Simplifies logic using Boolean algebraic reduction, prints the canonical and
    simplified SOP forms, and returns the simplified expression string.
    """
    n = len(variables)
    if not truth_table:
        return "0"
    on_indices = [i for i, row in enumerate(truth_table) if row[-1] == 1]
    if not on_indices:
        print("Canonical SOP : F = 0")
        return "0"
    if len(on_indices) == 2 ** n:
        print("Canonical SOP : F = 1")
        return "1"

    canonical_terms = []
    for row in truth_table:
        if row[-1] == 1:
            lits = [
                v if bit == 1 else f"{v}'"
                for v, bit in zip(variables, row[:-1])
            ]
            canonical_terms.append("".join(lits))
    print("Canonical SOP : F = " + " + ".join(canonical_terms))

    current = [(frozenset({m}), format(m, "0{}b".format(n))) for m in on_indices]
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

    terms = sorted((render(pi[1]) for pi in selected), key=lambda t: (len(t), t))
    reduced_expr = " + ".join(terms) if terms else "0"
    print("Reduced SOP   : F = " + reduced_expr)
    return reduced_expr


def _parse_products(expression: str) -> Optional[List[List[Tuple[str, bool]]]]:
    products: List[List[Tuple[str, bool]]] = []
    expr = expression.strip()
    if expr.startswith("F") and "=" in expr:
        expr = expr.split("=", 1)[1].strip()
    for raw in expr.split("+"):
        term = raw.strip()
        if not term:
            continue
        if term == "1":
            return None
        lits: List[Tuple[str, bool]] = []
        i = 0
        while i < len(term):
            ch = term[i]
            if not ch.isalpha():
                i += 1
                continue
            neg = i + 1 < len(term) and term[i + 1] == "'"
            lits.append((ch, neg))
            i += 2 if neg else 1
        products.append(lits)
    return products


def draw_logic_circuit(expression: str) -> None:
    """
    Generates and prints the logic gate circuit diagram and gate netlist legend.
    """
    print("\n" + "=" * 64)
    print(" Logic Circuit Diagram ")
    print("=" * 64)
    expr = expression.strip()
    if expr.startswith("F") and "=" in expr:
        expr = expr.split("=", 1)[1].strip()
    if expr in ("0", ""):
        print(" Output: constant 0 (no gates needed) ")
        print("=" * 64 + "\n")
        return
    if expr == "1":
        print(" Output: constant 1 (no gates needed) ")
        print("=" * 64 + "\n")
        return
    products = _parse_products(expr)
    if products is None or any(len(p) == 0 for p in products):
        print(" Output: constant 1 (no gates needed)")
        print("=" * 64 + "\n")
        return
    print(" Expression : " + expr)
    print("-" * 64)
    rows = []
    for t, lits in enumerate(products):
        for r, (v, neg) in enumerate(lits):
            rows.append((v, neg, t, r, len(lits)))
    H = len(rows)
    label_w = max(len(v + ("'" if neg else "")) for v, neg, *_ in rows)
    SEG_W, GATE_W, WIRE_W = 8, 6, 5
    mid = H // 2
    lines = []
    for r, (v, neg, t, ri, m) in enumerate(rows):
        label = v + ("'" if neg else "")
        seg = "--[NOT]-" if neg else "-" * SEG_W
        line = "{:<{w}} {}".format(label, seg, w=label_w)
        if m > 1:
            gmid = r - ri + m // 2
            if r == gmid:
                line += ">|AND" + " " * (GATE_W - 4)
            else:
                line += ">|" + " " * (GATE_W - 2)
            line += "-" * WIRE_W if r == gmid else " " * WIRE_W
        else:
            line += "-" * (GATE_W + WIRE_W)
        if len(products) > 1:
            if r == 0:
                line += "|"
            elif r == H - 1:
                line += "|"
            elif r == mid:
                line += "|OR--> F"
            else:
                line += "|"
        else:
            if r == mid:
                line += "--> F"
        lines.append(line.rstrip())
    print("\n".join(lines))
    gates = []
    for t, lits in enumerate(products):
        ins = " . ".join(v + ("'" if neg else "") for v, neg in lits)
        gates.append(
            "G{}=AND({})".format(t + 1, ins)
            if len(lits) > 1
            else "G{}={}".format(t + 1, ins)
        )
    legend = "  ".join(gates)
    if len(products) > 1:
        legend += "  |  F = OR({})".format(
            ", ".join("G" + str(i + 1) for i in range(len(products)))
        )
    else:
        legend += "  |  F = G1"
    print("-" * 64)
    print(" " + legend)
    not_vars = sorted({v for lits in products for v, neg in lits if neg})
    if not_vars:
        print(" NOT gates used for: " + ", ".join(not_vars))
    print("=" * 64 + "\n")
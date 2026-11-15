"""
kmap.py -- Truth Table & Karnaugh Map Simplification Module

Shared data format (the "bridge"):
    variables   : list[str]         e.g. ['A', 'B', 'C']
    combos      : list[tuple[int]]  all 2^N binary rows in counting order
    truth_table : list[list[int]]   each row = N input bits + 1 output bit

Expression notation returned by simplify_kmap:
    NOT -> A'      AND -> AB (juxtaposition)      OR -> +
    Constant functions return "0" or "1".
"""

from itertools import product

MAX_VARS = 4  # K-Map grid visualization officially supported for 1..4 variables


# ----------------------------------------------------------------------
# Function 1
# ----------------------------------------------------------------------
def generate_combinations(num_vars: int) -> list[tuple]:
    """Generates all 2^N binary combinations for num_vars variables."""
    return list(product([0, 1], repeat=num_vars))


# ----------------------------------------------------------------------
# Function 2
# ----------------------------------------------------------------------
def display_truth_table(variables: list, truth_table: list) -> None:
    """Formats and prints the complete truth table to the console."""
    header_vars = " | ".join(variables)
    header = f" {header_vars} || Output (F)"
    width = max(len(header), 29)

    print("=" * width)
    print("TRUTH TABLE".center(width))
    print("=" * width)
    print(header)
    left = "-" * (len(header_vars) + 2)
    print(left + "++" + "-" * (len(header) - len(left) - 2))

    out_width = len("Output (F)")
    for row in truth_table:
        inputs = " | ".join(str(b) for b in row[:-1])
        print(f" {inputs} || {str(row[-1]).center(out_width)}".rstrip())
    print("=" * width)


# ----------------------------------------------------------------------
# Helpers for K-Map
# ----------------------------------------------------------------------
def _gray_code(n_bits: int) -> list[tuple]:
    """Gray code sequence of n_bits bits, e.g. 2 -> 00, 01, 11, 10."""
    if n_bits == 0:
        return [()]
    seq = [(0,), (1,)]
    for _ in range(n_bits - 1):
        seq = [(0,) + s for s in seq] + [(1,) + s for s in reversed(seq)]
    return seq


def _bits_to_index(bits: tuple) -> int:
    value = 0
    for b in bits:
        value = (value << 1) | b
    return value


def _layout(num_vars: int):
    """Split variables between rows and columns of the K-Map."""
    row_vars = num_vars // 2
    col_vars = num_vars - row_vars
    return row_vars, col_vars


def _print_kmap(variables, grid, row_gray, col_gray, row_vars):
    """Pretty-prints the K-Map grid."""
    row_names = "".join(variables[:row_vars])
    col_names = "".join(variables[row_vars:])
    corner = f"{row_names}\\{col_names}" if row_names else f"\\{col_names}"
    label_w = max(len(corner), max(len("".join(map(str, r))) for r in row_gray)) + 1
    cell_w = max(len("".join(map(str, c))) for c in col_gray) + 2

    print("=" * 29)
    print("K-MAP".center(29))
    print("=" * 29)
    print(
        corner.ljust(label_w)
        + "|"
        + "".join("".join(map(str, c)).center(cell_w) for c in col_gray)
    )
    print("-" * label_w + "+" + "-" * (cell_w * len(col_gray)))
    for r, rbits in enumerate(row_gray):
        rlabel = "".join(map(str, rbits)) or "-"
        print(
            rlabel.ljust(label_w)
            + "|"
            + "".join(str(v).center(cell_w) for v in grid[r])
        )
    print("=" * 29)


def _find_prime_groups(grid, rows, cols):
    """
    All maximal rectangles of 1s whose height and width are powers of two,
    including wrap-around (the K-Map is a torus). Returns a list of
    frozensets of (row, col) cells.
    """
    def sizes(n):
        s, k = [], 1
        while k <= n:
            s.append(k)
            k *= 2
        return s

    groups = set()
    for h in sizes(rows):
        for w in sizes(cols):
            for r0 in range(rows):
                for c0 in range(cols):
                    cells = frozenset(
                        ((r0 + i) % rows, (c0 + j) % cols)
                        for i in range(h)
                        for j in range(w)
                    )
                    if len(cells) == h * w and all(grid[r][c] == 1 for r, c in cells):
                        groups.add(cells)

    return [g for g in groups if not any(g < other for other in groups)]


def _choose_cover(groups, ones):
    """Pick a minimal set of groups covering every 1 (essentials first)."""
    chosen = []
    remaining = set(ones)

    for cell in sorted(ones):
        covering = [g for g in groups if cell in g]
        if len(covering) == 1 and covering[0] not in chosen:
            chosen.append(covering[0])
    for g in chosen:
        remaining -= g

    if remaining:
        rest = [g for g in groups if g not in chosen and g & remaining]
        if len(rest) <= 18:
            from itertools import combinations
            best = None
            for k in range(1, len(rest) + 1):
                for combo in combinations(rest, k):
                    if remaining <= frozenset().union(*combo):
                        score = (k, -sum(len(g) for g in combo))
                        if best is None or score < best[0]:
                            best = (score, combo)
                if best:
                    break
            chosen.extend(best[1])
        else:
            while remaining:
                g = max(rest, key=lambda x: len(x & remaining))
                chosen.append(g)
                remaining -= g
    return chosen


def _group_to_term(group, variables, row_gray, col_gray, row_vars) -> str:
    """Convert a group of K-Map cells into a product term like A'BC."""
    n = len(variables)
    cell_bits = []
    for r, c in group:
        cell_bits.append(row_gray[r] + col_gray[c])

    term = ""
    for i in range(n):
        values = {bits[i] for bits in cell_bits}
        if len(values) == 1:
            term += variables[i] + ("" if values.pop() == 1 else "'")
    return term


def _qm_fallback_simplify(variables: list, truth_table: list) -> str:
    """Quine-McCluskey fallback when N > 4 so 5-6 variable tables still simplify."""
    n = len(variables)
    on_indices = [i for i, row in enumerate(truth_table) if row[-1] == 1]
    if not on_indices:
        return "0"
    if len(on_indices) == (1 << n):
        return "1"

    current = [(frozenset({m}), format(m, f"0{n}b")) for m in on_indices]
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

    terms = []
    for mset, pat in selected:
        parts = [v if bit == "1" else f"{v}'" for v, bit in zip(variables, pat) if bit in ("0", "1")]
        t_str = "".join(parts) if parts else "1"
        terms.append((sorted(mset), t_str))

    terms.sort(key=lambda x: x[0])
    print("Groups chosen (tabular K-Map extension):")
    for mlist, t_str in terms:
        print(f"  size {len(mlist)}: m{mlist} -> {t_str}")
    return " + ".join(t for _, t in terms)


# ----------------------------------------------------------------------
# Function 3
# ----------------------------------------------------------------------
def simplify_kmap(variables: list, truth_table: list) -> str:
    """
    Displays the K-Map grid, performs K-Map simplification,
    prints the result, and returns the simplified SOP expression string.
    """
    n = len(variables)
    if n < 1 or not truth_table:
        print("Error: nothing to simplify.")
        return "0"

    if n > MAX_VARS:
        print(f"Note: 2D K-Map grid is for 1..{MAX_VARS} variables (using {n}-variable tabular grouping).\n")
        result = _qm_fallback_simplify(variables, truth_table)
        print(f"\nSimplified expression: F = {result}")
        return result

    row_vars, col_vars = _layout(n)
    row_gray = _gray_code(row_vars)
    col_gray = _gray_code(col_vars)
    rows, cols = len(row_gray), len(col_gray)

    lookup = {_bits_to_index(tuple(row[:-1])): row[-1] for row in truth_table}
    grid = [
        [lookup.get(_bits_to_index(rb + cb), 0) for cb in col_gray]
        for rb in row_gray
    ]

    _print_kmap(variables, grid, row_gray, col_gray, row_vars)

    ones = {(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 1}
    if not ones:
        result = "0"
    elif len(ones) == rows * cols:
        result = "1"
    else:
        groups = _find_prime_groups(grid, rows, cols)
        cover = _choose_cover(groups, ones)

        print("Groups chosen:")
        entries = []
        for g in cover:
            minterms = sorted(_bits_to_index(row_gray[r] + col_gray[c]) for r, c in g)
            term = _group_to_term(g, variables, row_gray, col_gray, row_vars)
            key = (
                [variables.index(v) for v in variables if v in term.replace("'", "")]
                if all(len(v) == 1 for v in variables)
                else [],
                minterms,
            )
            entries.append((key, len(g), minterms, term))
        entries.sort(key=lambda e: e[0])
        terms = []
        for _, size, minterms, term in entries:
            terms.append(term)
            print(f"  size {size}: m{minterms} -> {term}")
        result = " + ".join(terms)

    print(f"\nSimplified expression: F = {result}")
    return result

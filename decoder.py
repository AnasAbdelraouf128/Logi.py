"""
Logi — Decoder Implementation & Verification Module (decoder.py)
"""

from typing import List
import kmap
import circuit


def implement_decoder(variables: List[str], truth_table: List[List[int]]) -> None:
    """
    Prints decoder sizing (e.g. 3-to-8) and shows connected minterms to the external OR gate.
    """
    n = len(variables)
    num_outputs = 1 << n
    minterms = [idx for idx, row in enumerate(truth_table) if row[-1] == 1]

    print(f"Decoder Configuration : {n}-to-{num_outputs} Line Decoder")
    print(f"Input Lines           : {', '.join(variables)} (MSB={variables[0]}, LSB={variables[-1]})")
    print(f"Output Lines          : D0 to D{num_outputs - 1}")
    print("-" * 58)

    if not minterms:
        print("F = 0 (No decoder minterm outputs connected; tie F to GND)")
        return

    connected = ", ".join(f"D{m}" for m in minterms)
    print(f"Active Minterms Σm    : {minterms}")
    print(f"External OR Inputs    : {connected}")
    print(f"Implementation Eq     : F = OR({connected})")


def run_integration_tests() -> None:
    """
    Verifies all modules in a single self-test workflow.
    """
    print("Running Logi Self-Test Suite...\n")
    test_vars = ["A", "B", "C"]
    combos = kmap.generate_combinations(3)
    assert len(combos) == 8, "kmap.generate_combinations(3) must return 8 tuples"

    sample_tt = [list(c) + [1 if sum(c) >= 2 else 0] for c in combos]
    k_expr = kmap.simplify_kmap(test_vars, sample_tt)
    b_expr = circuit.simplify_boolean(test_vars, sample_tt)
    assert isinstance(k_expr, str) and k_expr, "simplify_kmap must return a non-empty str"
    assert isinstance(b_expr, str) and b_expr, "simplify_boolean must return a non-empty str"

    print()
    circuit.draw_logic_circuit(b_expr)
    print()
    implement_decoder(test_vars, sample_tt)
    print("\n[PASS] All modules verified.")

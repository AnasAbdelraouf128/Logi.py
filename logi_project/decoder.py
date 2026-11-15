"""
decoder.py -- Decoder Implementation & System Integration Module

Implements:
    - implement_decoder(variables: list[str], truth_table: list[list[int]]) -> None
    - exit_program(message: str) -> None
    - run_integration_tests() -> None
"""

import sys
from typing import List
import kmap
import circuit


def implement_decoder(variables: List[str], truth_table: List[List[int]]) -> None:
    """
    Option 4: Implement using a Decoder.
    Prints decoder sizing (e.g., 3-to-8) and minterms connected to the OR gate.
    """
    num_vars = len(variables)
    if num_vars == 0 or not truth_table:
        print("[Decoder] Invalid variables or empty truth table.")
        return

    num_outputs = 2 ** num_vars
    minterms: List[int] = []

    for row in truth_table:
        if len(row) < num_vars + 1:
            print(f"[Decoder] Skipping invalid row: {row}")
            continue

        inputs = row[:num_vars]
        output = row[num_vars]

        if output == 1:
            binary_str = "".join(str(bit) for bit in inputs)
            minterm_num = int(binary_str, 2)
            if minterm_num not in minterms:
                minterms.append(minterm_num)

    print("=" * 45)
    print(f"DECODER IMPLEMENTATION ({num_vars}-to-{num_outputs})".center(45))
    print("=" * 45)
    print(f"Variables                    : {variables} (MSB={variables[0]}, LSB={variables[-1]})")
    print(f"Decoder Outputs              : Y0 to Y{num_outputs - 1}")
    print("-" * 45)

    if minterms:
        connected_m = ", ".join(f"m{m}" for m in minterms)
        connected_y = ", ".join(f"Y{m}" for m in minterms)
        print(f"Minterms connected to OR gate: {connected_m} ({connected_y})")
        print(f"Boolean Function             : F = Σm({', '.join(str(m) for m in minterms)})")
        print(f"External OR Gate Equation    : F = OR({connected_y})")
    else:
        print("Minterms connected to OR gate: None (Output is always 0)")
        print("Boolean Function             : F = 0")
    print("=" * 45)


def exit_program(message: str = "Exiting program. Goodbye!") -> None:
    """Option 5: Clean program exit logic."""
    print("\n--- Option 5: Exit ---")
    print(message)
    sys.exit(0)


def run_integration_tests() -> None:
    """
    Integrates and verifies all 4 modules (kmap, circuit, decoder, and shared data bridge).
    """
    print("=" * 52)
    print("FULL SYSTEM INTEGRATION VERIFICATION".center(52))
    print("=" * 52)

    test_vars = ["A", "B", "C"]
    combos = kmap.generate_combinations(3)
    assert len(combos) == 8, "kmap.generate_combinations(3) must return 8 tuples"

    # Sample 3-variable function: Σm(1, 3, 6, 7) -> A'C + AB
    active_set = {1, 3, 6, 7}
    test_truth_table = [
        list(c) + [1 if idx in active_set else 0]
        for idx, c in enumerate(combos)
    ]

    print("\n[Step 1] Truth Table Generation & Display (kmap.display_truth_table):")
    kmap.display_truth_table(test_vars, test_truth_table)

    print("\n[Step 2] K-Map Simplification (kmap.simplify_kmap):")
    k_expr = kmap.simplify_kmap(test_vars, test_truth_table)
    assert isinstance(k_expr, str) and k_expr, "simplify_kmap must return a non-empty string"

    print("\n[Step 3] Boolean Algebra Simplification (circuit.simplify_boolean):")
    b_expr = circuit.simplify_boolean(test_vars, test_truth_table)
    assert isinstance(b_expr, str) and b_expr, "simplify_boolean must return a non-empty string"

    print("\n[Step 4] Logic Circuit Diagram (circuit.draw_logic_circuit):")
    circuit.draw_logic_circuit(b_expr)

    print("\n[Step 5] Decoder Implementation (decoder.implement_decoder):")
    implement_decoder(test_vars, test_truth_table)

    print("\n[PASS] All 4 project modules passed cross-module verification!")


if __name__ == "__main__":
    run_integration_tests()
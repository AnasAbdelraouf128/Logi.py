# Logi — Digital Logic Design Studio

## Quick Start

```bash
# 1. Install PyQt6
pip install -r requirements.txt

# 2. Launch the GUI
python logi.py

# Optional: Run in terminal CLI mode
python logi.py --cli
```

## Architecture & Module Signatures

| Module | Functions |
| :--- | :--- |
| `logi.py` | `get_num_variables() -> int`<br>`get_user_outputs(variables: list, combos: list) -> list[int]`<br>`display_menu() -> int`<br>`main()` |
| `kmap.py` | `generate_combinations(num_vars: int) -> list[tuple]`<br>`display_truth_table(variables: list, truth_table: list) -> None`<br>`simplify_kmap(variables: list, truth_table: list) -> str` |
| `circuit.py` | `simplify_boolean(variables: list, truth_table: list) -> str`<br>`draw_logic_circuit(expression: str) -> None` |
| `decoder.py` | `implement_decoder(variables: list, truth_table: list) -> None`<br>`run_integration_tests() -> None` |

#!/usr/bin/env python3
"""
Logi — Digital Logic Design Studio
Core UI & System Flow Module (logi.py)
"""

from __future__ import annotations
import sys
import io
import math
import random
import string
import traceback
import contextlib
from typing import List, Tuple, Callable, Any

import kmap
import circuit
import decoder


# =====================================================================
# SHARED DATA HELPERS & SELF-HEALING MODULE BRIDGE
# =====================================================================

def make_variable_names(num_vars: int) -> List[str]:
    """Generates variable names ['A', 'B', 'C', ...] for N variables."""
    return list(string.ascii_uppercase[:num_vars])


def build_truth_table(combos: List[Tuple[int, ...]], outputs: List[int]) -> List[List[int]]:
    """
    Constructs the shared truth_table format:
    truth_table = [[0, 0, 0, 1], [0, 0, 1, 0], ...]
    where each inner list has N input bits followed by 1 output bit.
    """
    return [[int(b) for b in combo] + [int(out_bit)] for combo, out_bit in zip(combos, outputs)]


def _builtin_simplify_boolean(variables: List[str], truth_table: List[List[int]]) -> str:
    """
    Built-in Boolean Algebra simplifier so Option 2 and Option 3 work even if
    an older `circuit.py` without `simplify_boolean` is present on disk.
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
            lits = [v if bit == 1 else f"{v}'" for v, bit in zip(variables, row[:n])]
            canonical_terms.append("".join(lits))

    print(f"Active Minterms: Σm({', '.join(map(str, on_indices))})")
    print(f"Canonical SOP  : F = {' + '.join(canonical_terms)}\n")

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


if not hasattr(circuit, "simplify_boolean"):
    circuit.simplify_boolean = _builtin_simplify_boolean  # type: ignore[attr-defined]


def safe_simplify_boolean(variables: List[str], truth_table: List[List[int]]) -> str:
    """Calls circuit.simplify_boolean if present, or falls back to _builtin_simplify_boolean."""
    fn = getattr(circuit, "simplify_boolean", _builtin_simplify_boolean)
    return fn(variables, truth_table)


def parse_sop_expression(expression: str) -> List[List[Tuple[str, bool]]]:
    """
    Parses a SOP Boolean expression (e.g. "A'B + BC'") into a list of product terms
    of (variable_name, is_negated) tuples.
    """
    expr = expression.strip()
    if expr.startswith("F") and "=" in expr:
        expr = expr.split("=", 1)[1].strip()
    if not expr or expr in ("0", "1"):
        return []

    if hasattr(circuit, "_parse_products"):
        parsed = circuit._parse_products(expr)
        if parsed:
            return parsed

    terms: List[List[Tuple[str, bool]]] = []
    for raw_term in expr.split("+"):
        t = raw_term.strip()
        if not t:
            continue
        literals: List[Tuple[str, bool]] = []
        i = 0
        while i < len(t):
            ch = t[i]
            if ch.isalpha():
                neg = i + 1 < len(t) and t[i + 1] == "'"
                literals.append((ch, neg))
                i += 2 if neg else 1
            else:
                i += 1
        if literals:
            terms.append(literals)
    return terms


def execute_module_function(func: Callable[..., Any], *args: Any) -> Tuple[bool, str, Any]:
    """
    Executes a logic module function safely while capturing both its return value
    and anything printed via `print()` to stdout.
    """
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            result = func(*args)
        printed_output = buffer.getvalue().strip()
        if printed_output:
            print(printed_output)
        if result is not None and str(result).strip():
            combined = (
                f"{printed_output}\n\nResult:\n  F = {result}".strip()
                if printed_output
                else f"F = {result}"
            )
        else:
            combined = printed_output if printed_output else "Operation completed."
        return True, combined, result
    except Exception as exc:
        err_msg = f"Execution Error in {func.__module__}.{func.__name__}(): {exc}\n\n{traceback.format_exc()}"
        return False, err_msg, None


# =====================================================================
# PROJECT REQUIREMENTS CLI FUNCTIONS
# =====================================================================

def get_num_variables() -> int:
    """
    Prompts the user for input size, validates and returns integer N.
    Handles invalid inputs gracefully without terminating the program.
    """
    while True:
        raw = input("\nEnter the number of input variables (2 to 4 recommended, 1 to 6 supported): ").strip()
        try:
            num_vars = int(raw)
            if 1 <= num_vars <= 6:
                return num_vars
            print("  [!] Invalid input: Please enter an integer between 1 and 6.")
        except ValueError:
            print(f"  [!] Invalid input: '{raw}' is not a valid integer. Please try again.")


def get_user_outputs(variables: List[str], combos: List[Tuple[int, ...]]) -> List[int]:
    """
    Prompts user to input 0 or 1 for each combination, returning the output list.
    Validates every input so invalid characters never crash the program.
    """
    outputs: List[int] = []
    header = " ".join(variables)
    print(f"\n--- Enter Output Value (0 or 1) for Each Input Combination ({header}) ---")
    print("Tip: Type 'all0', 'all1', or 'rand' at the first prompt to auto-fill.")

    for idx, combo in enumerate(combos):
        combo_str = " ".join(str(bit) for bit in combo)
        while True:
            raw = input(f"  Row {idx:2d} ({combo_str}) -> F = ").strip().lower()
            if idx == 0 and raw in ("all0", "all1", "rand"):
                if raw == "all0":
                    return [0] * len(combos)
                if raw == "all1":
                    return [1] * len(combos)
                return [random.choice([0, 1]) for _ in combos]
            if raw in ("0", "1"):
                outputs.append(int(raw))
                break
            print("  [!] Invalid input! Output value must be 0 or 1.")
    return outputs


def display_menu() -> int:
    """
    Displays the required 5-option menu, validates user input, and handles
    invalid menu choices without terminating the program.
    """
    menu_text = """
==================================================
          DIGITAL LOGIC DESIGN — MENU             
==================================================
  1. Simplify using K-Map
  2. Simplify using Boolean Algebra
  3. Draw the logic circuit
  4. Implement using a Decoder
  5. Exit
=================================================="""
    while True:
        print(menu_text)
        choice_raw = input("Select an option (1-5): ").strip()
        try:
            choice = int(choice_raw)
            if 1 <= choice <= 5:
                return choice
            print("  [!] Invalid menu choice! Please enter a number between 1 and 5.")
        except ValueError:
            print(f"  [!] Invalid input '{choice_raw}'! Please enter a number between 1 and 5.")


def run_cli_loop() -> None:
    """
    Runs the continuous interactive CLI loop required by the project specification.
    """
    print("==================================================")
    print("         LOGI — DIGITAL LOGIC DESIGN              ")
    print("==================================================")
    num_vars = get_num_variables()
    variables = make_variable_names(num_vars)

    combos = kmap.generate_combinations(num_vars)
    if not combos:
        combos = [
            tuple((i >> shift) & 1 for shift in range(num_vars - 1, -1, -1))
            for i in range(1 << num_vars)
        ]

    outputs = get_user_outputs(variables, combos)
    truth_table = build_truth_table(combos, outputs)

    print()
    kmap.display_truth_table(variables, truth_table)

    last_expression: str = ""

    while True:
        choice = display_menu()
        if choice == 1:
            print("\n[Option 1] Simplify using K-Map:")
            _, _, res = execute_module_function(kmap.simplify_kmap, variables, truth_table)
            if isinstance(res, str) and res.strip():
                last_expression = res.strip()
        elif choice == 2:
            print("\n[Option 2] Simplify using Boolean Algebra:")
            _, _, res = execute_module_function(safe_simplify_boolean, variables, truth_table)
            if isinstance(res, str) and res.strip():
                last_expression = res.strip()
        elif choice == 3:
            print("\n[Option 3] Draw the logic circuit:")
            if not last_expression:
                _, _, res = execute_module_function(safe_simplify_boolean, variables, truth_table)
                if isinstance(res, str) and res.strip():
                    last_expression = res.strip()
                else:
                    _, _, res_k = execute_module_function(kmap.simplify_kmap, variables, truth_table)
                    last_expression = str(res_k) if res_k else "0"
            execute_module_function(circuit.draw_logic_circuit, last_expression)
        elif choice == 4:
            print("\n[Option 4] Implement using a Decoder:")
            execute_module_function(decoder.implement_decoder, variables, truth_table)
        elif choice == 5:
            if hasattr(decoder, "exit_program"):
                decoder.exit_program("Exiting Logi. Goodbye!")
            else:
                print("\nExiting Logi. Goodbye!")
                break


# =====================================================================
# 3-COLUMN GLASSMORPHIC GUI WITH HIGH-LEGIBILITY TYPOGRAPHY (PyQt6)
# =====================================================================

def launch_glass_gui() -> int:
    from PyQt6.QtCore import (
        Qt,
        QTimer,
        QVariantAnimation,
        QEasingCurve,
        QPointF,
        QRectF,
        QSize,
    )
    from PyQt6.QtGui import (
        QColor,
        QPainter,
        QLinearGradient,
        QRadialGradient,
        QPen,
        QFont,
        QFontMetrics,
        QBrush,
        QPainterPath,
        QShortcut,
        QKeySequence,
    )
    from PyQt6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QLineEdit,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QTextEdit,
        QFrame,
        QSplitter,
        QStackedWidget,
        QScrollArea,
        QSizePolicy,
    )

    class GlassPanel(QFrame):
        """
        Frosted glass card painted directly via QPainter without offscreen
        QGraphicsEffect buffers so maximizing/minimizing never glitches.
        """

        def __init__(
            self,
            tint: QColor = QColor(17, 24, 39, 205),
            border_color: QColor = QColor(255, 255, 255, 38),
            radius: int = 15,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self.tint = tint
            self.border_color = border_color
            self.radius = radius

        def paintEvent(self, event) -> None:
            w, h = float(self.width()), float(self.height())
            if w <= 2.0 or h <= 2.0:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            shadow_rect = QRectF(1.0, 2.0, w - 2.0, h - 2.0)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, self.radius, self.radius)
            painter.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 70)))

            rect = QRectF(1.0, 1.0, w - 2.0, h - 3.0)
            path = QPainterPath()
            path.addRoundedRect(rect, self.radius, self.radius)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(
                0.0,
                QColor(
                    min(255, self.tint.red() + 14),
                    min(255, self.tint.green() + 18),
                    min(255, self.tint.blue() + 26),
                    self.tint.alpha(),
                ),
            )
            grad.setColorAt(0.5, self.tint)
            grad.setColorAt(
                1.0,
                QColor(
                    max(0, self.tint.red() - 6),
                    max(0, self.tint.green() - 6),
                    max(0, self.tint.blue() - 6),
                    min(255, self.tint.alpha() + 15),
                ),
            )
            painter.fillPath(path, QBrush(grad))

            border_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            border_grad.setColorAt(0.0, QColor(255, 255, 255, 72))
            border_grad.setColorAt(0.5, self.border_color)
            border_grad.setColorAt(1.0, QColor(0, 245, 212, 42))

            painter.setPen(QPen(QBrush(border_grad), 1.2))
            painter.drawPath(path)

    class MenuOptionButton(QPushButton):
        """
        Proficient Left-Sidebar Menu Button with active selection glow,
        numbered step badge, shortcut pill, and subtitle.
        """

        def __init__(
            self,
            step_num: str,
            title: str,
            subtitle: str,
            shortcut_text: str = "",
            accent_hex: str = "#00f5d4",
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(title, parent)
            self.step_num = step_num
            self.subtitle = subtitle
            self.shortcut_text = shortcut_text
            self.accent = QColor(accent_hex)
            self._hover_progress = 0.0
            self._is_active = False
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setMinimumHeight(56)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

            self._anim = QVariantAnimation(self)
            self._anim.setDuration(160)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.valueChanged.connect(self._on_anim_value)

        def set_active(self, active: bool) -> None:
            if self._is_active != active:
                self._is_active = active
                self.update()

        def _on_anim_value(self, val: float) -> None:
            self._hover_progress = float(val)
            self.update()

        def enterEvent(self, event) -> None:
            self._anim.stop()
            self._anim.setStartValue(self._hover_progress)
            self._anim.setEndValue(1.0)
            self._anim.start()
            super().enterEvent(event)

        def leaveEvent(self, event) -> None:
            self._anim.stop()
            self._anim.setStartValue(self._hover_progress)
            self._anim.setEndValue(0.0)
            self._anim.start()
            super().leaveEvent(event)

        def paintEvent(self, event) -> None:
            if self.width() <= 4 or self.height() <= 4:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            p = max(self._hover_progress, 0.90 if self._is_active else 0.0)
            rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
            rect.translate(0, -1.0 * self._hover_progress)

            path = QPainterPath()
            path.addRoundedRect(rect, 11, 11)

            bg_r = int(20 + (self.accent.red() - 20) * (0.25 * p))
            bg_g = int(29 + (self.accent.green() - 29) * (0.25 * p))
            bg_b = int(48 + (self.accent.blue() - 48) * (0.25 * p))
            bg_a = int(185 + 55 * p)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(min(255, bg_r + 14), min(255, bg_g + 14), min(255, bg_b + 18), bg_a))
            grad.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, max(0, bg_a - 20)))
            painter.fillPath(path, QBrush(grad))

            border_r = int(255 + (self.accent.red() - 255) * p)
            border_g = int(255 + (self.accent.green() - 255) * p)
            border_b = int(255 + (self.accent.blue() - 255) * p)
            border_a = int(45 + 195 * p)
            pen_w = 1.9 if self._is_active else (1.2 + 0.5 * p)
            painter.setPen(QPen(QColor(border_r, border_g, border_b, border_a), pen_w))
            painter.drawPath(path)

            # Left accent bar
            bar_rect = QRectF(rect.left() + 6.0, rect.top() + 9.0, 3.8, rect.height() - 18.0)
            bar_path = QPainterPath()
            bar_path.addRoundedRect(bar_rect, 1.9, 1.9)
            bar_col = QColor(self.accent)
            bar_col.setAlpha(255 if self._is_active else int(125 + 120 * p))
            painter.fillPath(bar_path, QBrush(bar_col))

            # Step number badge
            badge_rect = QRectF(rect.left() + 16.0, rect.center().y() - 13.0, 26.0, 26.0)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 7.0, 7.0)
            badge_bg = QColor(self.accent)
            badge_bg.setAlpha(230 if self._is_active else int(55 + 115 * p))
            painter.fillPath(badge_path, QBrush(badge_bg))

            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#090d18") if self._is_active else QColor("#f8fafc"))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.step_num)

            # Shortcut chip on right
            right_pad = 12.0
            if self.shortcut_text:
                chip_w = 48.0
                chip_rect = QRectF(rect.right() - chip_w - 10.0, rect.top() + 10.0, chip_w, 18.0)
                painter.setBrush(QBrush(QColor(15, 23, 42, 180)))
                painter.setPen(QPen(QColor(148, 163, 184, 80), 1.0))
                painter.drawRoundedRect(chip_rect, 5.0, 5.0)
                painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#cbd5e1"))
                painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, self.shortcut_text)
                right_pad = chip_w + 18.0

            text_x = rect.left() + 50.0
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff") if self._is_active else QColor("#f1f5f9"))
            painter.drawText(
                QRectF(text_x, rect.top() + 7.0, rect.width() - 50.0 - right_pad, 21.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.text(),
            )

            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(185, 205, 230, 235 if self._is_active else int(180 + 60 * p)))
            painter.drawText(
                QRectF(text_x, rect.top() + 28.0, rect.width() - 58.0, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.subtitle,
            )

    class AnimatedGlassButton(QPushButton):
        """Auto-sizing utility button that never clips its label text."""

        def __init__(
            self,
            text: str,
            accent_hex: str = "#00f5d4",
            compact: bool = True,
            active: bool = False,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(text, parent)
            self.accent = QColor(accent_hex)
            self._hover_progress = 0.0
            self._is_active = active
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setMinimumHeight(34 if compact else 38)

            font = QFont("Segoe UI", 9, QFont.Weight.Bold)
            fm = QFontMetrics(font)
            text_w = fm.horizontalAdvance(text)
            self.setMinimumWidth(max(64, text_w + 28))

            self._anim = QVariantAnimation(self)
            self._anim.setDuration(150)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.valueChanged.connect(self._on_anim_value)

        def set_active(self, active: bool) -> None:
            if self._is_active != active:
                self._is_active = active
                self.update()

        def _on_anim_value(self, val: float) -> None:
            self._hover_progress = float(val)
            self.update()

        def enterEvent(self, event) -> None:
            self._anim.stop()
            self._anim.setStartValue(self._hover_progress)
            self._anim.setEndValue(1.0)
            self._anim.start()
            super().enterEvent(event)

        def leaveEvent(self, event) -> None:
            self._anim.stop()
            self._anim.setStartValue(self._hover_progress)
            self._anim.setEndValue(0.0)
            self._anim.start()
            super().leaveEvent(event)

        def paintEvent(self, event) -> None:
            if self.width() <= 2 or self.height() <= 2:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            p = max(self._hover_progress, 0.88 if self._is_active else 0.0)
            rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)

            path = QPainterPath()
            path.addRoundedRect(rect, 9, 9)

            bg_r = int(22 + (self.accent.red() - 22) * (0.28 * p))
            bg_g = int(32 + (self.accent.green() - 32) * (0.28 * p))
            bg_b = int(52 + (self.accent.blue() - 52) * (0.28 * p))
            bg_a = int(175 + 60 * p)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(min(255, bg_r + 14), min(255, bg_g + 14), min(255, bg_b + 18), bg_a))
            grad.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, max(0, bg_a - 18)))
            painter.fillPath(path, QBrush(grad))

            border_r = int(255 + (self.accent.red() - 255) * p)
            border_g = int(255 + (self.accent.green() - 255) * p)
            border_b = int(255 + (self.accent.blue() - 255) * p)
            border_a = int(50 + 185 * p)

            painter.setPen(QPen(QColor(border_r, border_g, border_b, border_a), 1.6 if self._is_active else 1.2))
            painter.drawPath(path)

            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if self._is_active else QFont.Weight.DemiBold))
            painter.setPen(QColor("#ffffff") if self._is_active else QColor(240, 248, 255))
            painter.drawText(
                rect.adjusted(6, 0, -6, 0),
                Qt.AlignmentFlag.AlignCenter,
                self.text(),
            )

    class LogicSchematicCanvas(QWidget):
        """
        Resize-resilient, opaque-painted graphical schematic renderer for
        IEEE/ANSI NOT, AND, OR, and Decoder logic gate networks.
        """

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.mode: str = "circuit"
            self.variables: List[str] = ["A", "B", "C"]
            self.expression: str = "AB + AC + BC"
            self.minterms: List[int] = [3, 5, 6, 7]
            self._required_height: int = 440
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.MinimumExpanding,
            )

        def sizeHint(self) -> QSize:
            return QSize(540, self._required_height)

        def minimumSizeHint(self) -> QSize:
            return QSize(360, self._required_height)

        def set_circuit_data(self, variables: List[str], expression: str) -> None:
            self.mode = "circuit"
            self.variables = list(variables)
            self.expression = expression.strip() if expression.strip() else "0"
            terms = parse_sop_expression(self.expression)
            self._required_height = max(420, 150 + len(terms) * 86)
            self.setMinimumHeight(self._required_height)
            self.updateGeometry()
            self.update()

        def set_decoder_data(self, variables: List[str], minterms: List[int]) -> None:
            self.mode = "decoder"
            self.variables = list(variables)
            self.minterms = list(minterms)
            num_out = 1 << len(self.variables)
            self._required_height = max(420, 130 + num_out * 26)
            self.setMinimumHeight(self._required_height)
            self.updateGeometry()
            self.update()

        def _draw_grid_background(self, painter: QPainter, w: float, h: float) -> None:
            bg = QLinearGradient(0, 0, w, h)
            bg.setColorAt(0.0, QColor(9, 13, 24))
            bg.setColorAt(1.0, QColor(13, 20, 36))
            painter.fillRect(QRectF(0, 0, w, h), QBrush(bg))

            grid_pen = QPen(QColor(255, 255, 255, 12), 1.0)
            painter.setPen(grid_pen)
            step = 24
            for x in range(0, int(w), step):
                painter.drawLine(x, 0, x, int(h))
            for y in range(0, int(h), step):
                painter.drawLine(0, y, int(w), y)

        @staticmethod
        def _draw_and_gate(
            painter: QPainter,
            x: float,
            y: float,
            gw: float,
            gh: float,
            label: str = "AND",
        ) -> QPointF:
            top = y - gh / 2.0
            path = QPainterPath()
            path.moveTo(x, top)
            path.lineTo(x + gw * 0.5, top)
            path.arcTo(QRectF(x, top, gw, gh), 90.0, -180.0)
            path.lineTo(x, top + gh)
            path.closeSubpath()

            grad = QLinearGradient(x, top, x + gw, top + gh)
            grad.setColorAt(0.0, QColor(16, 185, 129, 85))
            grad.setColorAt(1.0, QColor(6, 95, 70, 145))
            painter.fillPath(path, QBrush(grad))
            painter.setPen(QPen(QColor("#10b981"), 2.0))
            painter.drawPath(path)

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#d1fae5"))
            painter.drawText(
                QRectF(x, top, gw * 0.88, gh),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
            return QPointF(x + gw, y)

        @staticmethod
        def _draw_or_gate(
            painter: QPainter,
            x: float,
            y: float,
            gw: float,
            gh: float,
            label: str = "OR",
        ) -> QPointF:
            top = y - gh / 2.0
            bottom = y + gh / 2.0
            path = QPainterPath()
            path.moveTo(x, top)
            path.quadTo(x + gw * 0.58, top, x + gw, y)
            path.quadTo(x + gw * 0.58, bottom, x, bottom)
            path.quadTo(x + gw * 0.28, y, x, top)
            path.closeSubpath()

            grad = QLinearGradient(x, top, x + gw, bottom)
            grad.setColorAt(0.0, QColor(139, 92, 246, 95))
            grad.setColorAt(1.0, QColor(76, 29, 149, 150))
            painter.fillPath(path, QBrush(grad))
            painter.setPen(QPen(QColor("#a78bfa"), 2.2))
            painter.drawPath(path)

            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor("#ede9fe"))
            painter.drawText(
                QRectF(x + gw * 0.14, top, gw * 0.68, gh),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
            return QPointF(x + gw, y)

        @staticmethod
        def _draw_not_gate_mini(painter: QPainter, x: float, y: float) -> None:
            tri = QPainterPath()
            tri.moveTo(x, y - 6)
            tri.lineTo(x, y + 6)
            tri.lineTo(x + 10, y)
            tri.closeSubpath()
            painter.fillPath(tri, QBrush(QColor(244, 63, 94, 110)))
            painter.setPen(QPen(QColor("#fb7185"), 1.5))
            painter.drawPath(tri)
            painter.setBrush(QBrush(QColor("#0f172a")))
            painter.drawEllipse(QPointF(x + 12.5, y), 2.5, 2.5)

        @staticmethod
        def _draw_buffer_gate(
            painter: QPainter,
            x: float,
            y: float,
            gw: float,
            gh: float,
            negated: bool = False,
            label_prefix: str = "",
        ) -> QPointF:
            top = y - gh / 2.0
            bottom = y + gh / 2.0
            path = QPainterPath()
            path.moveTo(x, top)
            path.lineTo(x + gw, y)
            path.lineTo(x, bottom)
            path.closeSubpath()

            grad = QLinearGradient(x, top, x + gw, bottom)
            grad.setColorAt(0.0, QColor(0, 245, 212, 80))
            grad.setColorAt(1.0, QColor(14, 116, 144, 140))
            painter.fillPath(path, QBrush(grad))
            painter.setPen(QPen(QColor("#00f5d4"), 2.0))
            painter.drawPath(path)

            out_x = x + gw
            if negated:
                painter.setBrush(QBrush(QColor("#0f172a")))
                painter.setPen(QPen(QColor("#fb7185"), 2.0))
                painter.drawEllipse(QPointF(x + gw + 5.0, y), 4.5, 4.5)
                out_x = x + gw + 10.0

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#ccfbf1"))
            gate_text = label_prefix if label_prefix else ("NOT" if negated else "BUF")
            painter.drawText(
                QRectF(x, top, gw * 0.72, gh),
                Qt.AlignmentFlag.AlignCenter,
                gate_text,
            )
            return QPointF(out_x, y)

        def paintEvent(self, event) -> None:
            w, h = float(self.width()), float(self.height())
            if w <= 10.0 or h <= 10.0:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            self._draw_grid_background(painter, w, h)

            if self.mode == "decoder":
                self._paint_decoder_schematic(painter, w, h)
            else:
                self._paint_logic_circuit(painter, w, h)

        def _paint_logic_circuit(self, painter: QPainter, w: float, h: float) -> None:
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(
                QRectF(18, 12, w - 36, 26),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"Graphical Gate Schematic   •   F = {self.expression}",
            )

            expr_clean = self.expression.strip()
            if expr_clean in ("0", "1"):
                cy = h * 0.5
                painter.setPen(QPen(QColor("#00f5d4"), 2.5))
                painter.drawLine(QPointF(100, cy), QPointF(max(180.0, w - 120.0), cy))
                painter.setBrush(QBrush(QColor(0, 245, 212, 45)))
                painter.drawRoundedRect(QRectF(40, cy - 22, 60, 44), 8, 8)
                painter.setFont(QFont("Consolas", 14, QFont.Weight.Bold))
                painter.setPen(QColor("#00f5d4"))
                painter.drawText(
                    QRectF(40, cy - 22, 60, 44),
                    Qt.AlignmentFlag.AlignCenter,
                    expr_clean,
                )
                self._draw_output_probe(painter, QPointF(max(180.0, w - 120.0), cy), f"F = {expr_clean}")
                return

            terms = parse_sop_expression(expr_clean)
            if not terms:
                return

            n_vars = max(1, len(self.variables))
            bus_start_x = 28.0
            bus_spacing = min(34.0, max(20.0, (w * 0.22) / n_vars))
            bus_top_y = 66.0
            bus_bot_y = h - 44.0

            rail_colors = [
                QColor("#00f5d4"),
                QColor("#38bdf8"),
                QColor("#a78bfa"),
                QColor("#f472b6"),
                QColor("#fbbf24"),
                QColor("#34d399"),
            ]

            bus_x_map = {}
            for idx, var in enumerate(self.variables):
                bx = bus_start_x + idx * bus_spacing
                bus_x_map[var] = bx
                col = rail_colors[idx % len(rail_colors)]

                pill_rect = QRectF(bx - 12, bus_top_y - 26, 24, 21)
                painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 48)))
                painter.setPen(QPen(col, 1.4))
                painter.drawRoundedRect(pill_rect, 5, 5)

                painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                painter.setPen(QColor("#f8fafc"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, var)

                rail_pen = QPen(QColor(col.red(), col.green(), col.blue(), 145), 1.7)
                painter.setPen(rail_pen)
                painter.drawLine(QPointF(bx, bus_top_y - 5), QPointF(bx, bus_bot_y))

            last_bus_x = bus_start_x + (n_vars - 1) * bus_spacing
            avail_w = max(240.0, w - last_bus_x - 95.0)
            and_x = last_bus_x + max(42.0, avail_w * 0.18)
            and_w, and_h = 62.0, 46.0

            or_x = max(and_x + and_w + 52.0, last_bus_x + avail_w * 0.62)
            or_w, or_h = 70.0, 60.0

            usable_h = max(120.0, bus_bot_y - bus_top_y - 16.0)
            num_terms = len(terms)
            gate_outputs: List[QPointF] = []
            gate_equations: List[str] = []

            for t_idx, literals in enumerate(terms):
                cy = bus_top_y + 8.0 + usable_h * ((t_idx + 0.5) / num_terms)
                term_label = "".join(f"{v}'" if neg else v for v, neg in literals)
                ins_dot = "·".join(f"{v}'" if neg else v for v, neg in literals)
                gate_id = f"T{t_idx + 1}"
                gate_equations.append(
                    f"{gate_id}=AND({ins_dot})" if len(literals) > 1 else f"{gate_id}={ins_dot}"
                )

                num_lits = len(literals)
                in_span = min(and_h - 12.0, max(10.0, (num_lits - 1) * 9.0))
                for l_idx, (var_name, is_neg) in enumerate(literals):
                    if num_lits == 1:
                        iy = cy
                    else:
                        iy = (cy - in_span / 2.0) + in_span * (l_idx / (num_lits - 1))

                    bx = bus_x_map.get(var_name, bus_start_x)
                    v_idx = self.variables.index(var_name) if var_name in self.variables else 0
                    wire_col = rail_colors[v_idx % len(rail_colors)]

                    painter.setBrush(QBrush(wire_col))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(bx, iy), 3.4, 3.4)

                    painter.setPen(QPen(wire_col, 1.7))
                    if is_neg and num_lits > 1:
                        inv_x = and_x - 20.0
                        painter.drawLine(QPointF(bx, iy), QPointF(inv_x, iy))
                        self._draw_not_gate_mini(painter, inv_x, iy)
                        painter.setPen(QPen(QColor("#fb7185"), 1.7))
                        painter.drawLine(QPointF(inv_x + 15.0, iy), QPointF(and_x, iy))
                    else:
                        painter.drawLine(QPointF(bx, iy), QPointF(and_x, iy))

                if num_lits == 1:
                    _, is_neg_single = literals[0]
                    out_pt = self._draw_buffer_gate(
                        painter, and_x, cy, 52.0, 40.0, negated=is_neg_single, label_prefix=gate_id
                    )
                else:
                    out_pt = self._draw_and_gate(painter, and_x, cy, and_w, and_h, label=gate_id)

                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                painter.setPen(QColor("#6ee7b7"))
                painter.drawText(
                    QRectF(out_pt.x() + 5, out_pt.y() - 18, 65, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    term_label,
                )
                gate_outputs.append(out_pt)

            if len(gate_outputs) == 1:
                single_out = gate_outputs[0]
                end_x = min(w - 75.0, single_out.x() + 80.0)
                painter.setPen(QPen(QColor("#00f5d4"), 2.2))
                painter.drawLine(single_out, QPointF(end_x, single_out.y()))
                self._draw_output_probe(painter, QPointF(end_x, single_out.y()), "F")
            else:
                or_cy = sum(pt.y() for pt in gate_outputs) / len(gate_outputs)
                or_in_span = min(or_h - 16.0, max(14.0, len(gate_outputs) * 7.5))

                for idx, pt in enumerate(gate_outputs):
                    target_y = (
                        or_cy - or_in_span / 2.0
                        + or_in_span * (idx / (len(gate_outputs) - 1))
                    )
                    mid_x = pt.x() + (or_x - pt.x()) * (0.42 + 0.08 * (idx % 3))

                    wire_path = QPainterPath(pt)
                    wire_path.lineTo(mid_x, pt.y())
                    wire_path.lineTo(mid_x, target_y)
                    wire_path.lineTo(or_x + 7.0, target_y)

                    painter.setPen(QPen(QColor("#10b981"), 1.9))
                    painter.drawPath(wire_path)

                or_out = self._draw_or_gate(painter, or_x, or_cy, or_w, or_h, label="OR")
                end_x = min(w - 72.0, or_out.x() + 34.0)
                painter.setPen(QPen(QColor("#00f5d4"), 2.3))
                painter.drawLine(or_out, QPointF(end_x, or_out.y()))
                self._draw_output_probe(painter, QPointF(end_x, or_out.y()), "F")

            legend_str = "  ".join(gate_equations)
            if len(gate_outputs) > 1:
                t_list = ", ".join(f"T{i + 1}" for i in range(len(gate_outputs)))
                legend_str += f"   |   F = OR({t_list})"
            else:
                legend_str += "   |   F = T1"

            painter.setFont(QFont("Consolas", 9, QFont.Weight.DemiBold))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                QRectF(18, h - 30, w - 36, 22),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                legend_str,
            )

        def _paint_decoder_schematic(self, painter: QPainter, w: float, h: float) -> None:
            n = len(self.variables)
            num_out = 1 << n

            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(
                QRectF(18, 12, w - 36, 26),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"Graphical {n}-to-{num_out} Line Decoder   •   Σm = {self.minterms}",
            )

            dec_x = 92.0
            dec_w = 126.0
            dec_top = 58.0
            dec_h = max(220.0, h - 88.0)

            dec_rect = QRectF(dec_x, dec_top, dec_w, dec_h)
            grad = QLinearGradient(dec_rect.topLeft(), dec_rect.bottomRight())
            grad.setColorAt(0.0, QColor(30, 58, 138, 130))
            grad.setColorAt(1.0, QColor(15, 23, 42, 195))
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor("#38bdf8"), 2.1))
            painter.drawRoundedRect(dec_rect, 12, 12)

            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#bae6fd"))
            painter.drawText(
                QRectF(dec_x, dec_top + 8, dec_w, 22),
                Qt.AlignmentFlag.AlignCenter,
                f"{n}-to-{num_out}",
            )
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.setPen(QColor("#7dd3fc"))
            painter.drawText(
                QRectF(dec_x, dec_top + 26, dec_w, 16),
                Qt.AlignmentFlag.AlignCenter,
                "DECODER",
            )

            for idx, var in enumerate(self.variables):
                py = dec_top + 56.0 + (dec_h - 82.0) * ((idx + 0.5) / max(1, n))
                painter.setPen(QPen(QColor("#00f5d4"), 1.9))
                painter.drawLine(QPointF(44.0, py), QPointF(dec_x, py))

                pill = QRectF(16.0, py - 10.0, 28.0, 20.0)
                painter.setBrush(QBrush(QColor(0, 245, 212, 42)))
                painter.setPen(QPen(QColor("#00f5d4"), 1.4))
                painter.drawRoundedRect(pill, 5, 5)
                painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                painter.setPen(QColor("#f8fafc"))
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, var)

            or_x = max(dec_x + dec_w + 80.0, w * 0.62)
            or_w, or_h = 70.0, 62.0
            or_cy = dec_top + dec_h * 0.5

            active_pts: List[QPointF] = []
            for m in range(num_out):
                oy = dec_top + 22.0 + (dec_h - 44.0) * ((m + 0.5) / num_out)
                is_active = m in self.minterms

                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                painter.setPen(QColor("#00f5d4") if is_active else QColor("#64748b"))
                painter.drawText(
                    QRectF(dec_x + dec_w - 36, oy - 8, 30, 16),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"Y{m}",
                )

                pin_start = QPointF(dec_x + dec_w, oy)
                if is_active:
                    active_pts.append(pin_start)
                else:
                    painter.setPen(QPen(QColor(100, 116, 139, 90), 1.1))
                    painter.drawLine(pin_start, QPointF(dec_x + dec_w + 14.0, oy))

            if not active_pts:
                painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                painter.setPen(QColor("#94a3b8"))
                painter.drawText(
                    QRectF(dec_x + dec_w + 24, or_cy - 20, 200, 40),
                    Qt.AlignmentFlag.AlignCenter,
                    "F = 0 (Grounded)",
                )
                return

            or_in_span = min(or_h - 14.0, max(12.0, len(active_pts) * 6.5))
            for idx, pt in enumerate(active_pts):
                if len(active_pts) == 1:
                    ty = or_cy
                else:
                    ty = or_cy - or_in_span / 2.0 + or_in_span * (idx / (len(active_pts) - 1))

                mid_x = pt.x() + (or_x - pt.x()) * (0.34 + 0.07 * (idx % 5))
                wpath = QPainterPath(pt)
                wpath.lineTo(mid_x, pt.y())
                wpath.lineTo(mid_x, ty)
                wpath.lineTo(or_x + 7.0, ty)

                painter.setPen(QPen(QColor("#00f5d4"), 1.6))
                painter.drawPath(wpath)

            or_out = self._draw_or_gate(painter, or_x, or_cy, or_w, or_h, label="OR")
            end_x = min(w - 72.0, or_out.x() + 34.0)
            painter.setPen(QPen(QColor("#00f5d4"), 2.3))
            painter.drawLine(or_out, QPointF(end_x, or_out.y()))
            self._draw_output_probe(painter, QPointF(end_x, or_out.y()), "F")

        @staticmethod
        def _draw_output_probe(painter: QPainter, pt: QPointF, label: str) -> None:
            badge = QRectF(pt.x(), pt.y() - 15.0, 52.0, 30.0)
            painter.setBrush(QBrush(QColor(0, 245, 212, 48)))
            painter.setPen(QPen(QColor("#00f5d4"), 1.9))
            painter.drawRoundedRect(badge, 7, 7)
            painter.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)

    class AmbientGlassCanvas(QWidget):
        """Opaque-painted ambient backdrop that pauses automatically when minimized."""

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._phase = 0.0
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(50)

        def _tick(self) -> None:
            if not self.isVisible() or self.window().isMinimized():
                return
            self._phase = (self._phase + 0.02) % (2.0 * math.pi)
            self.update()

        def paintEvent(self, event) -> None:
            w, h = float(self.width()), float(self.height())
            if w <= 2.0 or h <= 2.0:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            rect = QRectF(0, 0, w, h)

            base_grad = QLinearGradient(0, 0, w, h)
            base_grad.setColorAt(0.0, QColor(9, 13, 24))
            base_grad.setColorAt(0.5, QColor(13, 19, 34))
            base_grad.setColorAt(1.0, QColor(8, 11, 20))
            painter.fillRect(rect, QBrush(base_grad))

            span = min(w, h)
            orbs = (
                (
                    w * (0.20 + 0.06 * math.sin(self._phase)),
                    h * (0.24 + 0.05 * math.cos(self._phase)),
                    span * 0.42,
                    QColor(0, 245, 212, 38),
                ),
                (
                    w * (0.80 + 0.05 * math.cos(self._phase)),
                    h * (0.30 + 0.06 * math.sin(self._phase)),
                    span * 0.44,
                    QColor(139, 92, 246, 40),
                ),
                (
                    w * (0.50 + 0.06 * math.sin(self._phase + 1.2)),
                    h * (0.82 + 0.05 * math.cos(self._phase)),
                    span * 0.38,
                    QColor(16, 185, 129, 32),
                ),
            )

            for cx, cy, radius, color in orbs:
                rad = QRadialGradient(QPointF(cx, cy), radius)
                rad.setColorAt(0.0, color)
                rad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
                painter.fillRect(rect, QBrush(rad))

    class LogiMainWindow(QMainWindow):
        """
        Balanced 3-Column Studio Window:
          - Left Column   : Input Variables Setup + Proficient 5-Option Menu Dock
          - Center Column : Interactive Truth Table (with vertically centered rows)
          - Right Column  : Large 15pt Output Console & Graphical IEEE Circuit Canvas
        """

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Logi — Digital Logic Design Studio")
            self.resize(1280, 800)
            self.setMinimumSize(980, 620)

            self.num_vars: int = 3
            self.variables: List[str] = make_variable_names(self.num_vars)
            self.combos: List[Tuple[int, ...]] = []
            self.outputs: List[int] = []
            self.truth_table: List[List[int]] = []
            self.last_simplified_expr: str = ""
            self.active_option: int = 1
            self.menu_buttons: List[MenuOptionButton] = []
            self.var_pills: dict[int, AnimatedGlassButton] = {}

            self.canvas = AmbientGlassCanvas(self)
            self.setCentralWidget(self.canvas)

            root_layout = QVBoxLayout(self.canvas)
            root_layout.setContentsMargins(18, 14, 18, 16)
            root_layout.setSpacing(12)

            root_layout.addWidget(self._build_header_panel())

            self.banner_label = QLabel("")
            self.banner_label.setVisible(False)
            self.banner_label.setWordWrap(True)
            root_layout.addWidget(self.banner_label)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setChildrenCollapsible(False)
            splitter.setStyleSheet("QSplitter::handle { background: transparent; width: 12px; }")

            splitter.addWidget(self._build_left_sidebar())
            splitter.addWidget(self._build_center_truth_table_panel())
            splitter.addWidget(self._build_right_output_panel())
            splitter.setStretchFactor(0, 26)
            splitter.setStretchFactor(1, 35)
            splitter.setStretchFactor(2, 39)

            root_layout.addWidget(splitter, 1)

            self._bind_shortcuts()
            self._regenerate_truth_table(initial=True)

        def changeEvent(self, event) -> None:
            super().changeEvent(event)
            if hasattr(self, "schematic_canvas"):
                self.schematic_canvas.updateGeometry()
                self.schematic_canvas.update()
            if hasattr(self, "right_stack"):
                self.right_stack.update()

        def resizeEvent(self, event) -> None:
            super().resizeEvent(event)
            if hasattr(self, "schematic_canvas") and self.schematic_canvas.isVisible():
                self.schematic_canvas.update()

        def _bind_shortcuts(self) -> None:
            QShortcut(QKeySequence("Ctrl+1"), self, activated=self._run_option_1_kmap)
            QShortcut(QKeySequence("Ctrl+2"), self, activated=self._run_option_2_boolean)
            QShortcut(QKeySequence("Ctrl+3"), self, activated=self._run_option_3_circuit)
            QShortcut(QKeySequence("Ctrl+4"), self, activated=self._run_option_4_decoder)
            QShortcut(QKeySequence("Ctrl+T"), self, activated=self._run_integration_check)
            QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

        def _build_header_panel(self) -> GlassPanel:
            header = GlassPanel(tint=QColor(15, 23, 40, 210), radius=14)
            layout = QHBoxLayout(header)
            layout.setContentsMargins(20, 12, 20, 12)

            title_col = QVBoxLayout()
            title_col.setSpacing(2)
            title_lbl = QLabel("LOGI — DIGITAL LOGIC DESIGN STUDIO")
            title_lbl.setStyleSheet(
                "color: #f8fafc; font-size: 19px; font-weight: 800; letter-spacing: 1.5px;"
            )
            sub_lbl = QLabel(
                "Truth Table Generator  •  K-Map Simplification  •  Boolean Algebra  •  Logic Gate Circuit  •  Decoder Synthesis"
            )
            sub_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            title_col.addWidget(title_lbl)
            title_col.addWidget(sub_lbl)

            self.expr_badge = QLabel("F = —")
            self.expr_badge.setStyleSheet(
                """
                QLabel {
                    background-color: rgba(0, 245, 212, 0.14);
                    border: 1px solid rgba(0, 245, 212, 0.45);
                    border-radius: 10px;
                    color: #00f5d4;
                    padding: 8px 16px;
                    font-family: 'Consolas', monospace;
                    font-size: 14px;
                    font-weight: 800;
                }
                """
            )

            layout.addLayout(title_col)
            layout.addStretch()
            layout.addWidget(self.expr_badge)
            return header

        def _build_left_sidebar(self) -> QWidget:
            container = QWidget()
            container.setMinimumWidth(295)
            col = QVBoxLayout(container)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(12)

            # Card 1: Input Variables Setup
            var_card = GlassPanel()
            var_layout = QVBoxLayout(var_card)
            var_layout.setContentsMargins(16, 14, 16, 14)
            var_layout.setSpacing(10)

            step1_title = QLabel("1. INPUT VARIABLES (N)")
            step1_title.setStyleSheet(
                "color: #00f5d4; font-size: 12px; font-weight: 800; letter-spacing: 1px;"
            )
            var_layout.addWidget(step1_title)

            quick_row = QHBoxLayout()
            quick_row.setSpacing(6)
            for n_val in (2, 3, 4, 5):
                pill = AnimatedGlassButton(
                    f"{n_val} Vars",
                    accent_hex="#00f5d4",
                    compact=True,
                    active=(n_val == self.num_vars),
                )
                pill.clicked.connect(lambda checked=False, v=n_val: self._set_quick_vars(v))
                self.var_pills[n_val] = pill
                quick_row.addWidget(pill)
            var_layout.addLayout(quick_row)

            input_row = QHBoxLayout()
            input_row.setSpacing(8)
            self.var_input = QLineEdit("3")
            self.var_input.setPlaceholderText("Enter N (1 to 6)...")
            self.var_input.setStyleSheet(
                """
                QLineEdit {
                    background-color: rgba(15, 23, 42, 0.85);
                    border: 1px solid rgba(148, 163, 184, 0.38);
                    border-radius: 9px;
                    color: #f8fafc;
                    padding: 7px 12px;
                    font-size: 14px;
                    font-weight: 700;
                }
                QLineEdit:focus {
                    border: 1.5px solid #00f5d4;
                }
                """
            )
            self.var_input.returnPressed.connect(self._on_apply_variables)

            apply_btn = AnimatedGlassButton("Generate Table", accent_hex="#00f5d4", compact=False)
            apply_btn.clicked.connect(self._on_apply_variables)

            input_row.addWidget(self.var_input, 1)
            input_row.addWidget(apply_btn)
            var_layout.addLayout(input_row)

            col.addWidget(var_card)

            # Card 2: Operations Menu Dock
            menu_card = GlassPanel()
            menu_layout = QVBoxLayout(menu_card)
            menu_layout.setContentsMargins(16, 14, 16, 14)
            menu_layout.setSpacing(9)

            step2_title = QLabel("2. OPERATIONS MENU")
            step2_title.setStyleSheet(
                "color: #a78bfa; font-size: 12px; font-weight: 800; letter-spacing: 1px;"
            )
            menu_layout.addWidget(step2_title)

            self.btn_opt1 = MenuOptionButton(
                "1",
                "Simplify using K-Map",
                "Gray-code K-Map grid & prime implicants",
                "Ctrl+1",
                accent_hex="#00f5d4",
            )
            self.btn_opt1.clicked.connect(self._run_option_1_kmap)

            self.btn_opt2 = MenuOptionButton(
                "2",
                "Simplify using Boolean Algebra",
                "Canonical SOP & algebraic reduction",
                "Ctrl+2",
                accent_hex="#8b5cf6",
            )
            self.btn_opt2.clicked.connect(self._run_option_2_boolean)

            self.btn_opt3 = MenuOptionButton(
                "3",
                "Draw the Logic Circuit",
                "Graphical IEEE gate network + ASCII",
                "Ctrl+3",
                accent_hex="#10b981",
            )
            self.btn_opt3.clicked.connect(self._run_option_3_circuit)

            self.btn_opt4 = MenuOptionButton(
                "4",
                "Implement using a Decoder",
                "N-to-2^N line decoder & external OR",
                "Ctrl+4",
                accent_hex="#38bdf8",
            )
            self.btn_opt4.clicked.connect(self._run_option_4_decoder)

            self.btn_opt_test = MenuOptionButton(
                "✓",
                "Verify All Team Modules",
                "Run full cross-module test suite",
                "Ctrl+T",
                accent_hex="#f59e0b",
            )
            self.btn_opt_test.clicked.connect(self._run_integration_check)

            self.btn_opt5 = MenuOptionButton(
                "5",
                "Exit Program",
                "Close session safely",
                "Ctrl+Q",
                accent_hex="#f43f5e",
            )
            self.btn_opt5.clicked.connect(self.close)

            self.menu_buttons = [
                self.btn_opt1,
                self.btn_opt2,
                self.btn_opt3,
                self.btn_opt4,
                self.btn_opt_test,
                self.btn_opt5,
            ]
            for b in self.menu_buttons:
                menu_layout.addWidget(b)

            menu_layout.addStretch()
            col.addWidget(menu_card, 1)
            return container

        def _set_active_option(self, opt_index: int) -> None:
            self.active_option = opt_index
            mapping = {
                1: self.btn_opt1,
                2: self.btn_opt2,
                3: self.btn_opt3,
                4: self.btn_opt4,
                99: self.btn_opt_test,
            }
            target = mapping.get(opt_index)
            for b in self.menu_buttons:
                b.set_active(b is target)

        def _build_center_truth_table_panel(self) -> GlassPanel:
            panel = GlassPanel()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)

            top_row = QHBoxLayout()
            title = QLabel("INTERACTIVE TRUTH TABLE")
            title.setStyleSheet(
                "color: #10b981; font-size: 12px; font-weight: 800; letter-spacing: 1px;"
            )
            self.var_summary_lbl = QLabel("Variables: A, B, C (8 rows)")
            self.var_summary_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
            top_row.addWidget(title)
            top_row.addStretch()
            top_row.addWidget(self.var_summary_lbl)
            layout.addLayout(top_row)

            hint_lbl = QLabel("Click any cell in column F to toggle 0 ↔ 1, or choose a preset:")
            hint_lbl.setStyleSheet("color: #cbd5e1; font-size: 12px;")
            layout.addWidget(hint_lbl)

            preset_row = QHBoxLayout()
            preset_row.setSpacing(6)
            for label, mode in (
                ("All 0s", "zeros"),
                ("All 1s", "ones"),
                ("Random", "random"),
                ("XOR", "xor"),
                ("Majority", "majority"),
            ):
                p_btn = AnimatedGlassButton(label, accent_hex="#10b981", compact=True)
                p_btn.clicked.connect(lambda checked=False, m=mode: self._apply_output_preset(m))
                preset_row.addWidget(p_btn)
            layout.addLayout(preset_row)

            bulk_row = QHBoxLayout()
            bulk_row.setSpacing(8)
            self.bulk_bits_input = QLineEdit()
            self.bulk_bits_input.setPlaceholderText("Custom output bits (e.g. 00010111)...")
            self.bulk_bits_input.setStyleSheet(
                """
                QLineEdit {
                    background-color: rgba(15, 23, 42, 0.80);
                    border: 1px solid rgba(148, 163, 184, 0.32);
                    border-radius: 8px;
                    color: #e2e8f0;
                    padding: 6px 10px;
                    font-family: 'Consolas', monospace;
                    font-size: 13px;
                }
                QLineEdit:focus { border: 1.5px solid #10b981; }
                """
            )
            self.bulk_bits_input.returnPressed.connect(self._on_apply_bulk_outputs)
            bulk_btn = AnimatedGlassButton("Apply Vector", accent_hex="#10b981", compact=True)
            bulk_btn.clicked.connect(self._on_apply_bulk_outputs)
            bulk_row.addWidget(self.bulk_bits_input, 1)
            bulk_row.addWidget(bulk_btn)
            layout.addLayout(bulk_row)

            self.table = QTableWidget()
            self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.table.verticalHeader().setVisible(False)
            self.table.setStyleSheet(
                """
                QTableWidget {
                    background-color: rgba(11, 17, 30, 0.82);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 10px;
                    gridline-color: rgba(255, 255, 255, 0.08);
                    color: #f1f5f9;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 14px;
                }
                QHeaderView::section {
                    background-color: rgba(30, 41, 59, 0.95);
                    color: #00f5d4;
                    font-size: 13px;
                    font-weight: 800;
                    border: none;
                    border-bottom: 1.5px solid rgba(0, 245, 212, 0.45);
                    padding: 9px;
                }
                """
            )
            self.table.cellClicked.connect(self._on_table_cell_clicked)
            layout.addWidget(self.table, 1)

            return panel

        def _build_right_output_panel(self) -> GlassPanel:
            panel = GlassPanel()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)

            header_row = QHBoxLayout()
            header_row.setSpacing(8)
            self.output_title_lbl = QLabel("OPTION 1 — K-MAP SIMPLIFICATION")
            self.output_title_lbl.setStyleSheet(
                "color: #38bdf8; font-size: 12px; font-weight: 800; letter-spacing: 1px;"
            )
            self.view_graphic_btn = AnimatedGlassButton("Schematic View", accent_hex="#10b981", compact=True)
            self.view_graphic_btn.clicked.connect(lambda: self._switch_output_subview(1))

            self.view_text_btn = AnimatedGlassButton("Text Report", accent_hex="#f59e0b", compact=True)
            self.view_text_btn.clicked.connect(lambda: self._switch_output_subview(0))

            copy_btn = AnimatedGlassButton("Copy", accent_hex="#8b5cf6", compact=True)
            copy_btn.clicked.connect(self._copy_output_to_clipboard)

            table_btn = AnimatedGlassButton("Bridge Data", accent_hex="#38bdf8", compact=True)
            table_btn.clicked.connect(self._show_shared_data_snapshot)

            header_row.addWidget(self.output_title_lbl)
            header_row.addStretch()
            header_row.addWidget(self.view_graphic_btn)
            header_row.addWidget(self.view_text_btn)
            header_row.addWidget(copy_btn)
            header_row.addWidget(table_btn)
            layout.addLayout(header_row)

            self.right_stack = QStackedWidget()

            self.output_console = QTextEdit()
            self.output_console.setReadOnly(True)
            self.output_console.setStyleSheet(
                """
                QTextEdit {
                    background-color: #090d18;
                    border: 1px solid rgba(255, 255, 255, 0.14);
                    border-radius: 10px;
                    color: #f1f5f9;
                    padding: 16px;
                    font-family: 'Consolas', 'Fira Code', 'Courier New', monospace;
                    font-size: 15px;
                    line-height: 1.45;
                }
                """
            )

            self.schematic_scroll = QScrollArea()
            self.schematic_scroll.setWidgetResizable(True)
            self.schematic_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.schematic_scroll.setStyleSheet(
                """
                QScrollArea {
                    background-color: #090d18;
                    border: 1px solid rgba(255, 255, 255, 0.14);
                    border-radius: 10px;
                }
                QWidget {
                    background-color: #090d18;
                }
                """
            )
            self.schematic_canvas = LogicSchematicCanvas()
            self.schematic_scroll.setWidget(self.schematic_canvas)

            self.right_stack.addWidget(self.output_console)
            self.right_stack.addWidget(self.schematic_scroll)

            layout.addWidget(self.right_stack, 1)
            return panel

        def _switch_output_subview(self, index: int) -> None:
            self.right_stack.setCurrentIndex(index)
            self.view_graphic_btn.set_active(index == 1)
            self.view_text_btn.set_active(index == 0)
            if index == 1:
                self.schematic_canvas.updateGeometry()
                self.schematic_canvas.update()
                self.schematic_scroll.viewport().update()
            else:
                self.output_console.update()

        def _copy_output_to_clipboard(self) -> None:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self.output_console.toPlainText())
                self._show_banner("Copied output report to clipboard.", is_error=False)

        def _show_banner(self, message: str, is_error: bool = True) -> None:
            if is_error:
                self.banner_label.setStyleSheet(
                    """
                    QLabel {
                        background-color: rgba(239, 68, 68, 0.24);
                        border: 1px solid rgba(248, 113, 113, 0.75);
                        border-radius: 9px;
                        color: #fecaca;
                        padding: 8px 14px;
                        font-size: 13px;
                        font-weight: 600;
                    }
                    """
                )
            else:
                self.banner_label.setStyleSheet(
                    """
                    QLabel {
                        background-color: rgba(16, 185, 129, 0.22);
                        border: 1px solid rgba(52, 211, 153, 0.75);
                        border-radius: 9px;
                        color: #a7f3d0;
                        padding: 8px 14px;
                        font-size: 13px;
                        font-weight: 600;
                    }
                    """
                )
            self.banner_label.setText(message)
            self.banner_label.setVisible(True)

        def _update_expr_badge(self, expr: str) -> None:
            display = expr if len(expr) <= 42 else expr[:39] + "..."
            self.expr_badge.setText(f"F = {display}" if display else "F = —")

        def _show_output_text(self, title: str, content: str) -> None:
            self.output_title_lbl.setText(title)
            self.output_console.setPlainText(content)
            self._switch_output_subview(0)

        def _show_schematic_view(self, title: str, text_backup: str) -> None:
            self.output_title_lbl.setText(title)
            self.output_console.setPlainText(text_backup)
            self._switch_output_subview(1)

        def _set_quick_vars(self, n_val: int) -> None:
            self.var_input.setText(str(n_val))
            self._on_apply_variables()

        def _on_apply_variables(self) -> None:
            raw = self.var_input.text().strip()
            if not raw:
                self.var_input.setText(str(self.num_vars))
                self.banner_label.setVisible(False)
                self._regenerate_truth_table()
                return
            try:
                val = int(raw)
                if not (1 <= val <= 6):
                    self._show_banner(
                        f"Invalid input: Number of variables ({val}) must be between 1 and 6.",
                        is_error=True,
                    )
                    return
                self.num_vars = val
                for k, pill in self.var_pills.items():
                    pill.set_active(k == val)
                self.banner_label.setVisible(False)
                self._regenerate_truth_table()
            except ValueError:
                self._show_banner(
                    f"Invalid input: '{raw}' is not a valid integer. Please enter a number from 1 to 6.",
                    is_error=True,
                )

        def _regenerate_truth_table(self, initial: bool = False) -> None:
            self.variables = make_variable_names(self.num_vars)

            ok, _, combos = execute_module_function(kmap.generate_combinations, self.num_vars)
            if not ok or not isinstance(combos, list) or len(combos) != (1 << self.num_vars):
                combos = [
                    tuple((i >> shift) & 1 for shift in range(self.num_vars - 1, -1, -1))
                    for i in range(1 << self.num_vars)
                ]
            self.combos = combos

            self.outputs = [
                1 if sum(row) >= (self.num_vars / 2.0) else 0 for row in self.combos
            ]
            self.truth_table = build_truth_table(self.combos, self.outputs)
            self.last_simplified_expr = ""
            self._update_expr_badge("—")
            self._populate_table_full()

            if not initial:
                self._show_banner(
                    f"Generated {len(self.combos)}-row truth table for {', '.join(self.variables)}.",
                    is_error=False,
                )
            self._refresh_active_option()

        def _refresh_active_option(self) -> None:
            if self.active_option == 1:
                self._run_option_1_kmap()
            elif self.active_option == 2:
                self._run_option_2_boolean()
            elif self.active_option == 3:
                self._run_option_3_circuit()
            elif self.active_option == 4:
                self._run_option_4_decoder()
            elif self.active_option == 99:
                self._run_integration_check()
            else:
                self._show_shared_data_snapshot()

        def _style_output_cell(self, item: QTableWidgetItem, out_bit: int) -> None:
            item.setText(f"  {out_bit}  ")
            if out_bit == 1:
                item.setForeground(QBrush(QColor("#00f5d4")))
                item.setBackground(QBrush(QColor(0, 245, 212, 42)))
            else:
                item.setForeground(QBrush(QColor("#94a3b8")))
                item.setBackground(QBrush(QColor(30, 41, 59, 95)))

        def _populate_table_full(self) -> None:
            self.table.setUpdatesEnabled(False)
            try:
                num_rows = len(self.combos)
                num_cols = self.num_vars + 2

                self.table.setRowCount(num_rows)
                self.table.setColumnCount(num_cols)
                headers = ["m#"] + self.variables + ["F (Output)"]
                self.table.setHorizontalHeaderLabels(headers)
                self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

                # Stretch rows for 2..4 variables so the truth table fills the vertical card cleanly
                v_header = self.table.verticalHeader()
                if num_rows <= 16:
                    v_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                else:
                    v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                    v_header.setDefaultSectionSize(34)

                self.var_summary_lbl.setText(f"Variables: {', '.join(self.variables)} ({num_rows} rows)")
                self.bulk_bits_input.setText("".join(str(b) for b in self.outputs))

                out_font = QFont("Consolas", 14, QFont.Weight.Bold)
                for r_idx, row_data in enumerate(self.truth_table):
                    m_item = QTableWidgetItem(f"m{r_idx}")
                    m_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    m_item.setForeground(QBrush(QColor("#64748b")))
                    m_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    self.table.setItem(r_idx, 0, m_item)

                    for c_idx in range(self.num_vars):
                        bit_val = row_data[c_idx]
                        inp_item = QTableWidgetItem(str(bit_val))
                        inp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        inp_item.setForeground(
                            QBrush(QColor("#f1f5f9") if bit_val == 1 else QColor("#64748b"))
                        )
                        inp_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        self.table.setItem(r_idx, c_idx + 1, inp_item)

                    out_bit = row_data[-1]
                    out_item = QTableWidgetItem()
                    out_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    out_item.setFont(out_font)
                    out_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    self._style_output_cell(out_item, out_bit)
                    self.table.setItem(r_idx, self.num_vars + 1, out_item)
            finally:
                self.table.setUpdatesEnabled(True)

        def _update_output_column_only(self) -> None:
            self.table.setUpdatesEnabled(False)
            try:
                out_col = self.num_vars + 1
                for r_idx, out_bit in enumerate(self.outputs):
                    item = self.table.item(r_idx, out_col)
                    if item is not None:
                        self._style_output_cell(item, out_bit)
                self.bulk_bits_input.setText("".join(str(b) for b in self.outputs))
            finally:
                self.table.setUpdatesEnabled(True)

        def _on_table_cell_clicked(self, row: int, col: int) -> None:
            new_bit = 1 - self.outputs[row]
            self.outputs[row] = new_bit
            self.truth_table[row][-1] = new_bit
            self.last_simplified_expr = ""
            self._update_expr_badge("—")

            item = self.table.item(row, self.num_vars + 1)
            if item is not None:
                self._style_output_cell(item, new_bit)
            self.bulk_bits_input.setText("".join(str(b) for b in self.outputs))
            self._refresh_active_option()

        def _apply_output_preset(self, mode: str) -> None:
            n_rows = len(self.combos)
            if mode == "zeros":
                self.outputs = [0] * n_rows
            elif mode == "ones":
                self.outputs = [1] * n_rows
            elif mode == "random":
                self.outputs = [random.choice([0, 1]) for _ in range(n_rows)]
            elif mode == "xor":
                self.outputs = [sum(c) % 2 for c in self.combos]
            elif mode == "majority":
                self.outputs = [1 if sum(c) >= (self.num_vars / 2.0) else 0 for c in self.combos]

            self.truth_table = build_truth_table(self.combos, self.outputs)
            self.last_simplified_expr = ""
            self._update_expr_badge("—")
            self._update_output_column_only()
            self.banner_label.setVisible(False)
            self._refresh_active_option()

        def _on_apply_bulk_outputs(self) -> None:
            raw = self.bulk_bits_input.text().strip().replace(" ", "")
            expected_len = len(self.combos)
            if len(raw) != expected_len or any(ch not in ("0", "1") for ch in raw):
                self._show_banner(
                    f"Invalid input: Output vector must contain {expected_len} binary digits ('0' or '1').",
                    is_error=True,
                )
                return
            self.outputs = [int(ch) for ch in raw]
            self.truth_table = build_truth_table(self.combos, self.outputs)
            self.last_simplified_expr = ""
            self._update_expr_badge("—")
            self._update_output_column_only()
            self._show_banner("Applied custom output vector.", is_error=False)
            self._refresh_active_option()

        def _show_shared_data_snapshot(self) -> None:
            _, console_table, _ = execute_module_function(
                kmap.display_truth_table, self.variables, self.truth_table
            )
            minterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 1]
            maxterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 0]
            lines = [
                console_table,
                "",
                f"Active Minterms Σm : {minterms}",
                f"Active Maxterms ΠM : {maxterms}",
                f"variables          = {self.variables}",
                "truth_table        = [",
            ]
            for idx, r in enumerate(self.truth_table):
                lines.append(f"    {r},  # m{idx}")
            lines.append("]")
            self._show_output_text("TRUTH TABLE & SHARED DATA BRIDGE", "\n".join(lines))

        def _run_option_1_kmap(self) -> None:
            self._set_active_option(1)
            _, output_text, result = execute_module_function(
                kmap.simplify_kmap, self.variables, self.truth_table
            )
            if isinstance(result, str) and result.strip():
                self.last_simplified_expr = result.strip()
                self._update_expr_badge(self.last_simplified_expr)
                self.schematic_canvas.set_circuit_data(self.variables, self.last_simplified_expr)
            minterms = [i for i, r in enumerate(self.truth_table) if r[-1] == 1]
            header = (
                f"Variables   : {', '.join(self.variables)}\n"
                f"Minterms Σm : {minterms}\n"
                + "-" * 45
                + "\n\n"
            )
            self._show_output_text("OPTION 1 — K-MAP SIMPLIFICATION", header + output_text)

        def _run_option_2_boolean(self) -> None:
            self._set_active_option(2)
            _, output_text, result = execute_module_function(
                safe_simplify_boolean, self.variables, self.truth_table
            )
            if isinstance(result, str) and result.strip():
                self.last_simplified_expr = result.strip()
                self._update_expr_badge(self.last_simplified_expr)
                self.schematic_canvas.set_circuit_data(self.variables, self.last_simplified_expr)
            self._show_output_text("OPTION 2 — BOOLEAN ALGEBRA SIMPLIFICATION", output_text)

        def _run_option_3_circuit(self) -> None:
            self._set_active_option(3)
            if not self.last_simplified_expr:
                _, _, res = execute_module_function(
                    safe_simplify_boolean, self.variables, self.truth_table
                )
                if isinstance(res, str) and res.strip():
                    self.last_simplified_expr = res.strip()
                else:
                    _, _, res_k = execute_module_function(
                        kmap.simplify_kmap, self.variables, self.truth_table
                    )
                    self.last_simplified_expr = (
                        res_k.strip() if isinstance(res_k, str) and res_k.strip() else "0"
                    )
                self._update_expr_badge(self.last_simplified_expr)

            _, output_text, _ = execute_module_function(
                circuit.draw_logic_circuit, self.last_simplified_expr
            )
            self.schematic_canvas.set_circuit_data(self.variables, self.last_simplified_expr)
            self._show_schematic_view("OPTION 3 — LOGIC CIRCUIT SCHEMATIC", output_text)

        def _run_option_4_decoder(self) -> None:
            self._set_active_option(4)
            _, output_text, _ = execute_module_function(
                decoder.implement_decoder, self.variables, self.truth_table
            )
            minterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 1]
            self.schematic_canvas.set_decoder_data(self.variables, minterms)
            self._show_schematic_view("OPTION 4 — DECODER IMPLEMENTATION", output_text)

        def _run_integration_check(self) -> None:
            self._set_active_option(99)
            _, output_text, _ = execute_module_function(decoder.run_integration_tests)
            self._show_output_text("CROSS-MODULE INTEGRATION VERIFICATION", output_text)

    app = QApplication(sys.argv)
    window = LogiMainWindow()
    window.show()
    return app.exec()


def main() -> None:
    """
    Entry point for Logi.
    Launches the PyQt6 GUI by default, or falls back to the CLI menu if `--cli` is passed
    or PyQt6 is unavailable.
    """
    if "--cli" in sys.argv:
        run_cli_loop()
        return

    try:
        sys.exit(launch_glass_gui())
    except ImportError:
        print("[Notice] PyQt6 is not installed (`pip install PyQt6`). Starting CLI mode...")
        run_cli_loop()


if __name__ == "__main__":
    main()
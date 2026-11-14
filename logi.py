#!/usr/bin/env python3
"""
Logi — Digital Logic Design Studio
Core UI & System Flow Module
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
# SHARED DATA HELPERS & MODULE BRIDGE
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


def parse_sop_expression(expression: str) -> List[List[Tuple[str, bool]]]:
    """
    Uses circuit._parse_products when available to parse a SOP Boolean expression
    (e.g. "A'B + BC'") into a list of product terms of (variable_name, is_negated) tuples.
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
# CORE CLI FUNCTIONS
# =====================================================================

def get_num_variables() -> int:
    """
    Prompts the user for input size, validates and returns integer N.
    Handles invalid inputs gracefully without terminating the program.
    """
    while True:
        raw = input("\nEnter the number of input variables (2 to 6): ").strip()
        try:
            num_vars = int(raw)
            if 1 <= num_vars <= 8:
                return num_vars
            print("  [!] Please enter an integer between 1 and 8.")
        except ValueError:
            print(f"  [!] '{raw}' is not a valid integer. Please try again.")


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
            raw = input(f"  Row {idx:2d} | {combo_str} -> F = ").strip().lower()
            if idx == 0 and raw in ("all0", "all1", "rand"):
                if raw == "all0":
                    return [0] * len(combos)
                if raw == "all1":
                    return [1] * len(combos)
                return [random.choice([0, 1]) for _ in combos]
            if raw in ("0", "1"):
                outputs.append(int(raw))
                break
            print("  [!] Invalid input. Output value must be 0 or 1.")
    return outputs


def display_menu() -> int:
    """
    Shows options 1-5, validates and returns user's selection without terminating on bad input.
    """
    menu_text = """
==================================================
                     LOGI MENU                    
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
            print("  [!] Please select a number from 1 to 5.")
        except ValueError:
            print(f"  [!] Invalid input '{choice_raw}'. Please enter a number from 1 to 5.")


def run_cli_loop() -> None:
    """Runs the interactive CLI flow."""
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

    print("\n--- Truth Table ---")
    kmap.display_truth_table(variables, truth_table)

    last_expression: str = ""

    while True:
        choice = display_menu()
        if choice == 1:
            print("\n[1] Simplifying using K-Map...")
            _, _, res = execute_module_function(kmap.simplify_kmap, variables, truth_table)
            if isinstance(res, str) and res.strip():
                last_expression = res.strip()
                print(f"Simplified Expression (K-Map): F = {last_expression}")
        elif choice == 2:
            print("\n[2] Simplifying using Boolean Algebra...")
            _, _, res = execute_module_function(circuit.simplify_boolean, variables, truth_table)
            if isinstance(res, str) and res.strip():
                last_expression = res.strip()
                print(f"Simplified Expression (Boolean Algebra): F = {last_expression}")
        elif choice == 3:
            print("\n[3] Drawing Logic Circuit...")
            if not last_expression:
                _, _, res = execute_module_function(circuit.simplify_boolean, variables, truth_table)
                if isinstance(res, str) and res.strip():
                    last_expression = res.strip()
                else:
                    _, _, res_k = execute_module_function(kmap.simplify_kmap, variables, truth_table)
                    last_expression = str(res_k) if res_k else "0"
            execute_module_function(circuit.draw_logic_circuit, last_expression)
        elif choice == 4:
            print("\n[4] Implementing with Decoder...")
            execute_module_function(decoder.implement_decoder, variables, truth_table)
        elif choice == 5:
            print("\nExiting Logi. Goodbye!")
            break


# =====================================================================
# GLITCH-FREE HARDWARE-ACCELERATED GUI & CIRCUIT CANVAS (PyQt6)
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
        Frosted glass container painted directly via QPainter without
        QGraphicsEffect offscreen buffers (eliminates resize/maximize/minimize glitches).
        """

        def __init__(
            self,
            tint: QColor = QColor(17, 24, 39, 195),
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

            # Soft outer shadow ring painted directly (no QGraphicsDropShadowEffect buffer loss)
            shadow_rect = QRectF(1.0, 2.0, w - 2.0, h - 2.0)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, self.radius, self.radius)
            painter.fillPath(shadow_path, QBrush(QColor(0, 0, 0, 65)))

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

    class AnimatedGlassButton(QPushButton):
        """Interactive glassmorphic button with smooth hover and press animations."""

        def __init__(
            self,
            text: str,
            accent_hex: str = "#00f5d4",
            subtitle: str = "",
            compact: bool = False,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(text, parent)
            self.accent = QColor(accent_hex)
            self.subtitle = subtitle
            self._hover_progress = 0.0
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if subtitle:
                self.setMinimumHeight(48)
            elif compact:
                self.setMinimumHeight(32)
            else:
                self.setMinimumHeight(36)

            self._anim = QVariantAnimation(self)
            self._anim.setDuration(160)
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.valueChanged.connect(self._on_anim_value)

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

            p = self._hover_progress
            rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
            rect.translate(0, -1.0 * p)

            path = QPainterPath()
            path.addRoundedRect(rect, 10, 10)

            bg_r = int(22 + (self.accent.red() - 22) * (0.25 * p))
            bg_g = int(32 + (self.accent.green() - 32) * (0.25 * p))
            bg_b = int(52 + (self.accent.blue() - 52) * (0.25 * p))
            bg_a = int(165 + 55 * p)

            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, QColor(min(255, bg_r + 14), min(255, bg_g + 14), min(255, bg_b + 18), bg_a))
            grad.setColorAt(1.0, QColor(bg_r, bg_g, bg_b, max(0, bg_a - 18)))
            painter.fillPath(path, QBrush(grad))

            border_r = int(255 + (self.accent.red() - 255) * p)
            border_g = int(255 + (self.accent.green() - 255) * p)
            border_b = int(255 + (self.accent.blue() - 255) * p)
            border_a = int(40 + 180 * p)

            painter.setPen(QPen(QColor(border_r, border_g, border_b, border_a), 1.2 + 0.5 * p))
            painter.drawPath(path)

            if self.subtitle:
                bar_rect = QRectF(rect.left() + 8, rect.top() + 9, 3.2, rect.height() - 18)
                bar_path = QPainterPath()
                bar_path.addRoundedRect(bar_rect, 1.6, 1.6)
                bar_col = QColor(self.accent)
                bar_col.setAlpha(int(140 + 115 * p))
                painter.fillPath(bar_path, QBrush(bar_col))

                text_x = int(rect.left() + 20)
                painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                painter.setPen(QColor(245, 250, 255))
                painter.drawText(
                    QRectF(text_x, rect.top() + 5, rect.width() - 28, 20),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    self.text(),
                )
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor(160, 180, 210, int(185 + 60 * p)))
                painter.drawText(
                    QRectF(text_x, rect.top() + 24, rect.width() - 28, 17),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    self.subtitle,
                )
            else:
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                painter.setPen(QColor(245, 250, 255))
                painter.drawText(
                    rect.adjusted(8, 0, -8, 0),
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
            self.mode: str = "circuit"  # "circuit" or "decoder"
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
            return QSize(560, self._required_height)

        def minimumSizeHint(self) -> QSize:
            return QSize(380, self._required_height)

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

            grid_pen = QPen(QColor(255, 255, 255, 11), 1.0)
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
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(
                QRectF(18, 10, w - 36, 24),
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
            bus_top_y = 62.0
            bus_bot_y = h - 42.0

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

                pill_rect = QRectF(bx - 11, bus_top_y - 24, 22, 19)
                painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 48)))
                painter.setPen(QPen(col, 1.4))
                painter.drawRoundedRect(pill_rect, 5, 5)

                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                painter.setPen(QColor("#f8fafc"))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, var)

                rail_pen = QPen(QColor(col.red(), col.green(), col.blue(), 145), 1.7)
                painter.setPen(rail_pen)
                painter.drawLine(QPointF(bx, bus_top_y - 5), QPointF(bx, bus_bot_y))

            last_bus_x = bus_start_x + (n_vars - 1) * bus_spacing
            # Responsive horizontal coordinates that clamp safely on any window width
            avail_w = max(240.0, w - last_bus_x - 95.0)
            and_x = last_bus_x + max(42.0, avail_w * 0.18)
            and_w, and_h = 60.0, 44.0

            or_x = max(and_x + and_w + 52.0, last_bus_x + avail_w * 0.62)
            or_w, or_h = 68.0, 58.0

            usable_h = max(120.0, bus_bot_y - bus_top_y - 16.0)
            num_terms = len(terms)
            gate_outputs: List[QPointF] = []
            gate_equations: List[str] = []

            for t_idx, literals in enumerate(terms):
                cy = bus_top_y + 8.0 + usable_h * ((t_idx + 0.5) / num_terms)
                term_label = "".join(f"{v}'" if neg else v for v, neg in literals)
                ins_dot = "·".join(f"{v}'" if neg else v for v, neg in literals)
                gate_id = f"G{t_idx + 1}"
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
                    painter.drawEllipse(QPointF(bx, iy), 3.2, 3.2)

                    painter.setPen(QPen(wire_col, 1.6))
                    if is_neg and num_lits > 1:
                        inv_x = and_x - 20.0
                        painter.drawLine(QPointF(bx, iy), QPointF(inv_x, iy))
                        self._draw_not_gate_mini(painter, inv_x, iy)
                        painter.setPen(QPen(QColor("#fb7185"), 1.6))
                        painter.drawLine(QPointF(inv_x + 15.0, iy), QPointF(and_x, iy))
                    else:
                        painter.drawLine(QPointF(bx, iy), QPointF(and_x, iy))

                if num_lits == 1:
                    _, is_neg_single = literals[0]
                    out_pt = self._draw_buffer_gate(
                        painter, and_x, cy, 50.0, 38.0, negated=is_neg_single, label_prefix=gate_id
                    )
                else:
                    out_pt = self._draw_and_gate(painter, and_x, cy, and_w, and_h, label=gate_id)

                painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#6ee7b7"))
                painter.drawText(
                    QRectF(out_pt.x() + 4, out_pt.y() - 17, 62, 15),
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

                    painter.setPen(QPen(QColor("#10b981"), 1.8))
                    painter.drawPath(wire_path)

                or_out = self._draw_or_gate(painter, or_x, or_cy, or_w, or_h, label="OR")
                end_x = min(w - 72.0, or_out.x() + 34.0)
                painter.setPen(QPen(QColor("#00f5d4"), 2.3))
                painter.drawLine(or_out, QPointF(end_x, or_out.y()))
                self._draw_output_probe(painter, QPointF(end_x, or_out.y()), "F")

            # Bottom Member 3 netlist legend bar
            legend_str = "  ".join(gate_equations)
            if len(gate_outputs) > 1:
                g_list = ", ".join(f"G{i + 1}" for i in range(len(gate_outputs)))
                legend_str += f"   |   F = OR({g_list})"
            else:
                legend_str += "   |   F = G1"

            painter.setFont(QFont("Consolas", 8))
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(
                QRectF(18, h - 28, w - 36, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                legend_str,
            )

        def _paint_decoder_schematic(self, painter: QPainter, w: float, h: float) -> None:
            n = len(self.variables)
            num_out = 1 << n

            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.setPen(QColor("#f8fafc"))
            painter.drawText(
                QRectF(18, 10, w - 36, 24),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"Graphical {n}-to-{num_out} Line Decoder   •   Σm = {self.minterms}",
            )

            dec_x = 92.0
            dec_w = 122.0
            dec_top = 56.0
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
                painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
                painter.setPen(QColor("#f8fafc"))
                painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, var)

            or_x = max(dec_x + dec_w + 80.0, w * 0.62)
            or_w, or_h = 68.0, 60.0
            or_cy = dec_top + dec_h * 0.5

            active_pts: List[QPointF] = []
            for m in range(num_out):
                oy = dec_top + 22.0 + (dec_h - 44.0) * ((m + 0.5) / num_out)
                is_active = m in self.minterms

                painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#00f5d4") if is_active else QColor("#64748b"))
                painter.drawText(
                    QRectF(dec_x + dec_w - 34, oy - 8, 28, 16),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"D{m}",
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
            badge = QRectF(pt.x(), pt.y() - 15.0, 50.0, 30.0)
            painter.setBrush(QBrush(QColor(0, 245, 212, 48)))
            painter.setPen(QPen(QColor("#00f5d4"), 1.9))
            painter.drawRoundedRect(badge, 7, 7)
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
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
        """Main application window for Logi with glitch-free window state handling."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Logi — Digital Logic Design Studio")
            self.resize(1220, 760)
            self.setMinimumSize(920, 580)

            self.num_vars: int = 3
            self.variables: List[str] = make_variable_names(self.num_vars)
            self.combos: List[Tuple[int, ...]] = []
            self.outputs: List[int] = []
            self.truth_table: List[List[int]] = []
            self.last_simplified_expr: str = ""

            self.canvas = AmbientGlassCanvas(self)
            self.setCentralWidget(self.canvas)

            root_layout = QVBoxLayout(self.canvas)
            root_layout.setContentsMargins(18, 16, 18, 16)
            root_layout.setSpacing(12)

            root_layout.addWidget(self._build_header_panel())

            self.banner_label = QLabel("")
            self.banner_label.setVisible(False)
            self.banner_label.setWordWrap(True)
            root_layout.addWidget(self.banner_label)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setChildrenCollapsible(False)
            splitter.setStyleSheet("QSplitter::handle { background: transparent; width: 10px; }")

            splitter.addWidget(self._build_left_control_column())
            splitter.addWidget(self._build_center_truth_table_panel())
            splitter.addWidget(self._build_right_output_panel())
            splitter.setStretchFactor(0, 25)
            splitter.setStretchFactor(1, 35)
            splitter.setStretchFactor(2, 40)

            root_layout.addWidget(splitter, 1)

            self._bind_shortcuts()
            self._regenerate_truth_table(initial=True)

        def changeEvent(self, event) -> None:
            """Ensures immediate clean repaint when restoring from minimize or maximizing."""
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
            QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

        def _build_header_panel(self) -> GlassPanel:
            header = GlassPanel(tint=QColor(15, 23, 40, 200), radius=14)
            layout = QHBoxLayout(header)
            layout.setContentsMargins(18, 10, 18, 10)

            title_col = QVBoxLayout()
            title_col.setSpacing(2)
            title_lbl = QLabel("LOGI")
            title_lbl.setStyleSheet(
                "color: #f8fafc; font-size: 20px; font-weight: 800; letter-spacing: 2px;"
            )
            sub_lbl = QLabel("Digital Logic Synthesis, K-Map Reduction, Gate Schematics & Decoder Design")
            sub_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
            title_col.addWidget(title_lbl)
            title_col.addWidget(sub_lbl)

            self.expr_badge = QLabel("F = —")
            self.expr_badge.setStyleSheet(
                """
                QLabel {
                    background-color: rgba(0, 245, 212, 0.12);
                    border: 1px solid rgba(0, 245, 212, 0.40);
                    border-radius: 10px;
                    color: #00f5d4;
                    padding: 6px 14px;
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                    font-weight: 700;
                }
                """
            )

            layout.addLayout(title_col)
            layout.addStretch()
            layout.addWidget(self.expr_badge)
            return header

        def _build_left_control_column(self) -> QWidget:
            container = QWidget()
            col = QVBoxLayout(container)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(12)

            var_card = GlassPanel()
            var_layout = QVBoxLayout(var_card)
            var_layout.setContentsMargins(16, 14, 16, 14)
            var_layout.setSpacing(8)

            step1_title = QLabel("INPUT VARIABLES")
            step1_title.setStyleSheet(
                "color: #00f5d4; font-size: 11px; font-weight: 800; letter-spacing: 1px;"
            )
            var_layout.addWidget(step1_title)

            input_row = QHBoxLayout()
            self.var_input = QLineEdit("3")
            self.var_input.setPlaceholderText("Variables (1-6)")
            self.var_input.setStyleSheet(
                """
                QLineEdit {
                    background-color: rgba(15, 23, 42, 0.82);
                    border: 1px solid rgba(148, 163, 184, 0.35);
                    border-radius: 9px;
                    color: #f8fafc;
                    padding: 6px 10px;
                    font-size: 13px;
                    font-weight: 700;
                }
                QLineEdit:focus {
                    border: 1.5px solid #00f5d4;
                    background-color: rgba(15, 23, 42, 0.98);
                }
                """
            )
            self.var_input.returnPressed.connect(self._on_apply_variables)

            apply_btn = AnimatedGlassButton("Apply", accent_hex="#00f5d4", compact=True)
            apply_btn.clicked.connect(self._on_apply_variables)

            input_row.addWidget(self.var_input, 1)
            input_row.addWidget(apply_btn, 1)
            var_layout.addLayout(input_row)

            quick_row = QHBoxLayout()
            quick_row.setSpacing(6)
            for n_val in (2, 3, 4, 5):
                pill = AnimatedGlassButton(f"{n_val} Vars", accent_hex="#8b5cf6", compact=True)
                pill.clicked.connect(lambda checked=False, v=n_val: self._set_quick_vars(v))
                quick_row.addWidget(pill)
            var_layout.addLayout(quick_row)

            col.addWidget(var_card)

            menu_card = GlassPanel()
            menu_layout = QVBoxLayout(menu_card)
            menu_layout.setContentsMargins(16, 14, 16, 14)
            menu_layout.setSpacing(8)

            step2_title = QLabel("SYNTHESIS & ANALYSIS")
            step2_title.setStyleSheet(
                "color: #a78bfa; font-size: 11px; font-weight: 800; letter-spacing: 1px;"
            )
            menu_layout.addWidget(step2_title)

            btn_kmap = AnimatedGlassButton(
                "1. Simplify using K-Map",
                accent_hex="#00f5d4",
                subtitle="Karnaugh Map minimization (Ctrl+1)",
            )
            btn_kmap.clicked.connect(self._run_option_1_kmap)

            btn_bool = AnimatedGlassButton(
                "2. Simplify using Boolean Algebra",
                accent_hex="#8b5cf6",
                subtitle="Algebraic SOP reduction (Ctrl+2)",
            )
            btn_bool.clicked.connect(self._run_option_2_boolean)

            btn_circuit = AnimatedGlassButton(
                "3. Draw Logic Circuit",
                accent_hex="#10b981",
                subtitle="Graphical IEEE gate schematic (Ctrl+3)",
            )
            btn_circuit.clicked.connect(self._run_option_3_circuit)

            btn_decoder = AnimatedGlassButton(
                "4. Implement with Decoder",
                accent_hex="#38bdf8",
                subtitle="Graphical N-to-2^N decoder & OR gate (Ctrl+4)",
            )
            btn_decoder.clicked.connect(self._run_option_4_decoder)

            btn_test = AnimatedGlassButton(
                "Run System Self-Test",
                accent_hex="#f59e0b",
                subtitle="Verify all logic modules",
            )
            btn_test.clicked.connect(self._run_integration_check)

            btn_exit = AnimatedGlassButton(
                "5. Exit",
                accent_hex="#f43f5e",
                subtitle="Close application (Ctrl+Q)",
            )
            btn_exit.clicked.connect(self.close)

            for b in (btn_kmap, btn_bool, btn_circuit, btn_decoder, btn_test, btn_exit):
                menu_layout.addWidget(b)

            menu_layout.addStretch()
            col.addWidget(menu_card, 1)
            return container

        def _build_center_truth_table_panel(self) -> GlassPanel:
            panel = GlassPanel()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(8)

            top_row = QHBoxLayout()
            title = QLabel("TRUTH TABLE")
            title.setStyleSheet(
                "color: #10b981; font-size: 11px; font-weight: 800; letter-spacing: 1px;"
            )
            self.var_summary_lbl = QLabel("A, B, C (8 rows)")
            self.var_summary_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
            top_row.addWidget(title)
            top_row.addStretch()
            top_row.addWidget(self.var_summary_lbl)
            layout.addLayout(top_row)

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
            self.bulk_bits_input = QLineEdit()
            self.bulk_bits_input.setPlaceholderText("Output vector (e.g. 00010111)...")
            self.bulk_bits_input.setStyleSheet(
                """
                QLineEdit {
                    background-color: rgba(15, 23, 42, 0.78);
                    border: 1px solid rgba(148, 163, 184, 0.30);
                    border-radius: 8px;
                    color: #e2e8f0;
                    padding: 5px 10px;
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                }
                QLineEdit:focus { border: 1.5px solid #10b981; }
                """
            )
            self.bulk_bits_input.returnPressed.connect(self._on_apply_bulk_outputs)
            bulk_btn = AnimatedGlassButton("Set Outputs", accent_hex="#10b981", compact=True)
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
                    background-color: rgba(11, 17, 30, 0.75);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 10px;
                    gridline-color: rgba(255, 255, 255, 0.06);
                    color: #e2e8f0;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 13px;
                }
                QHeaderView::section {
                    background-color: rgba(30, 41, 59, 0.92);
                    color: #00f5d4;
                    font-weight: 800;
                    border: none;
                    border-bottom: 1px solid rgba(0, 245, 212, 0.35);
                    padding: 7px;
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
            layout.setSpacing(8)

            header_row = QHBoxLayout()
            self.output_title_lbl = QLabel("OUTPUT VIEW")
            self.output_title_lbl.setStyleSheet(
                "color: #38bdf8; font-size: 11px; font-weight: 800; letter-spacing: 1px;"
            )
            diagram_btn = AnimatedGlassButton("Circuit View", accent_hex="#10b981", compact=True)
            diagram_btn.clicked.connect(self._run_option_3_circuit)
            text_btn = AnimatedGlassButton("ASCII / Text", accent_hex="#f59e0b", compact=True)
            text_btn.clicked.connect(lambda: self.right_stack.setCurrentIndex(0))
            copy_btn = AnimatedGlassButton("Copy", accent_hex="#8b5cf6", compact=True)
            copy_btn.clicked.connect(self._copy_output_to_clipboard)
            inspect_btn = AnimatedGlassButton("Table Summary", accent_hex="#38bdf8", compact=True)
            inspect_btn.clicked.connect(self._show_shared_data_snapshot)

            header_row.addWidget(self.output_title_lbl)
            header_row.addStretch()
            header_row.addWidget(diagram_btn)
            header_row.addWidget(text_btn)
            header_row.addWidget(copy_btn)
            header_row.addWidget(inspect_btn)
            layout.addLayout(header_row)

            # QStackedWidget without QGraphicsOpacityEffect so maximize/restore never drops the canvas texture
            self.right_stack = QStackedWidget()

            self.output_console = QTextEdit()
            self.output_console.setReadOnly(True)
            self.output_console.setStyleSheet(
                """
                QTextEdit {
                    background-color: #090d18;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 10px;
                    color: #e2e8f0;
                    padding: 12px;
                    font-family: 'Consolas', 'Fira Code', 'Courier New', monospace;
                    font-size: 13px;
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
                    border: 1px solid rgba(255, 255, 255, 0.12);
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

        def _copy_output_to_clipboard(self) -> None:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self.output_console.toPlainText())
                self._show_banner("Copied output text to clipboard.", is_error=False)

        def _show_banner(self, message: str, is_error: bool = True) -> None:
            if is_error:
                self.banner_label.setStyleSheet(
                    """
                    QLabel {
                        background-color: rgba(239, 68, 68, 0.24);
                        border: 1px solid rgba(248, 113, 113, 0.75);
                        border-radius: 9px;
                        color: #fecaca;
                        padding: 7px 12px;
                        font-size: 12px;
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
                        padding: 7px 12px;
                        font-size: 12px;
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
            self.right_stack.setCurrentIndex(0)
            self.output_console.update()

        def _show_schematic_view(self, title: str, text_backup: str) -> None:
            self.output_title_lbl.setText(title)
            self.output_console.setPlainText(text_backup)
            self.right_stack.setCurrentIndex(1)
            self.schematic_canvas.updateGeometry()
            self.schematic_canvas.update()
            self.schematic_scroll.viewport().update()

        def _set_quick_vars(self, n_val: int) -> None:
            self.var_input.setText(str(n_val))
            self._on_apply_variables()

        def _on_apply_variables(self) -> None:
            raw = self.var_input.text().strip()
            try:
                val = int(raw)
                if not (1 <= val <= 6):
                    self._show_banner(
                        f"Number of variables ({val}) must be between 1 and 6.",
                        is_error=True,
                    )
                    return
                self.num_vars = val
                self.banner_label.setVisible(False)
                self._regenerate_truth_table()
            except ValueError:
                self._show_banner(
                    f"'{raw}' is not a valid integer. Please enter an integer between 1 and 6.",
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

            _, console_table, _ = execute_module_function(
                kmap.display_truth_table, self.variables, self.truth_table
            )
            if not initial:
                self._show_banner(
                    f"Generated {len(self.combos)}-row truth table for {', '.join(self.variables)}.",
                    is_error=False,
                )
            self._show_shared_data_snapshot(extra_note=console_table)

        def _style_output_cell(self, item: QTableWidgetItem, out_bit: int) -> None:
            item.setText(f"  {out_bit}  ")
            if out_bit == 1:
                item.setForeground(QBrush(QColor("#00f5d4")))
                item.setBackground(QBrush(QColor(0, 245, 212, 38)))
            else:
                item.setForeground(QBrush(QColor("#94a3b8")))
                item.setBackground(QBrush(QColor(30, 41, 59, 90)))

        def _populate_table_full(self) -> None:
            self.table.setUpdatesEnabled(False)
            try:
                num_rows = len(self.combos)
                num_cols = self.num_vars + 2

                self.table.setRowCount(num_rows)
                self.table.setColumnCount(num_cols)
                headers = ["m#"] + self.variables + ["F"]
                self.table.setHorizontalHeaderLabels(headers)
                self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

                self.var_summary_lbl.setText(f"{', '.join(self.variables)} ({num_rows} rows)")
                self.bulk_bits_input.setText("".join(str(b) for b in self.outputs))

                out_font = QFont("Consolas", 13, QFont.Weight.Bold)
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
                            QBrush(QColor("#e2e8f0") if bit_val == 1 else QColor("#64748b"))
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

            if self.right_stack.currentIndex() == 1:
                if self.schematic_canvas.mode == "circuit":
                    self._run_option_3_circuit()
                else:
                    self._run_option_4_decoder()

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

            if self.right_stack.currentIndex() == 1:
                if self.schematic_canvas.mode == "circuit":
                    self._run_option_3_circuit()
                else:
                    self._run_option_4_decoder()

        def _on_apply_bulk_outputs(self) -> None:
            raw = self.bulk_bits_input.text().strip().replace(" ", "")
            expected_len = len(self.combos)
            if len(raw) != expected_len or any(ch not in ("0", "1") for ch in raw):
                self._show_banner(
                    f"Output vector must contain {expected_len} binary digits ('0' or '1').",
                    is_error=True,
                )
                return
            self.outputs = [int(ch) for ch in raw]
            self.truth_table = build_truth_table(self.combos, self.outputs)
            self.last_simplified_expr = ""
            self._update_expr_badge("—")
            self._update_output_column_only()
            self._show_banner("Applied custom output vector.", is_error=False)

            if self.right_stack.currentIndex() == 1:
                if self.schematic_canvas.mode == "circuit":
                    self._run_option_3_circuit()
                else:
                    self._run_option_4_decoder()

        def _show_shared_data_snapshot(self, extra_note: str = "") -> None:
            minterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 1]
            maxterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 0]
            lines = [
                f"Variables       : {self.variables}",
                f"Minterms Σm     : {minterms}",
                f"Maxterms ΠM     : {maxterms}",
                "",
                "truth_table = [",
            ]
            for idx, r in enumerate(self.truth_table):
                lines.append(f"    {r},  # m{idx}")
            lines.append("]")
            if extra_note:
                lines.append("\n--- Formatted Truth Table ---")
                lines.append(extra_note)
            self._show_output_text("TRUTH TABLE SUMMARY", "\n".join(lines))

        def _run_option_1_kmap(self) -> None:
            _, output_text, result = execute_module_function(
                kmap.simplify_kmap, self.variables, self.truth_table
            )
            if isinstance(result, str) and result.strip():
                self.last_simplified_expr = result.strip()
                self._update_expr_badge(self.last_simplified_expr)
            minterms = [i for i, r in enumerate(self.truth_table) if r[-1] == 1]
            header = (
                f"Variables   : {', '.join(self.variables)}\n"
                f"Minterms Σm : {minterms}\n"
                + "-" * 58
                + "\n\n"
            )
            self._show_output_text("K-MAP SIMPLIFICATION", header + output_text)

        def _run_option_2_boolean(self) -> None:
            _, output_text, result = execute_module_function(
                circuit.simplify_boolean, self.variables, self.truth_table
            )
            if isinstance(result, str) and result.strip():
                self.last_simplified_expr = result.strip()
                self._update_expr_badge(self.last_simplified_expr)
            minterms = [i for i, r in enumerate(self.truth_table) if r[-1] == 1]
            header = (
                f"Variables   : {', '.join(self.variables)}\n"
                f"Minterms Σm : {minterms}\n"
                + "-" * 58
                + "\n\n"
            )
            self._show_output_text("BOOLEAN ALGEBRA SIMPLIFICATION", header + output_text)

        def _run_option_3_circuit(self) -> None:
            if not self.last_simplified_expr:
                _, _, res = execute_module_function(
                    circuit.simplify_boolean, self.variables, self.truth_table
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
            self._show_schematic_view("GRAPHICAL LOGIC CIRCUIT SCHEMATIC", output_text)

        def _run_option_4_decoder(self) -> None:
            _, output_text, _ = execute_module_function(
                decoder.implement_decoder, self.variables, self.truth_table
            )
            minterms = [idx for idx, row in enumerate(self.truth_table) if row[-1] == 1]
            self.schematic_canvas.set_decoder_data(self.variables, minterms)
            self._show_schematic_view("GRAPHICAL DECODER IMPLEMENTATION", output_text)

        def _run_integration_check(self) -> None:
            _, output_text, _ = execute_module_function(decoder.run_integration_tests)
            self._show_output_text("SYSTEM SELF-TEST", output_text)

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
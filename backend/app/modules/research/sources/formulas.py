"""Small, closed Excel interpreter. No eval, cache, I/O or provider calls.

Numbers, + - * /, unary signs, parentheses, A1 ranges and same-workbook
references; AVERAGE/SUM/MIN/MAX/COUNT over numbers; named-table #This Row
column ranges. Everything else fails closed. See sources/README.md.
"""

import math
import re
from dataclasses import dataclass

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import TokenizerError
from openpyxl.utils.cell import get_column_letter, range_boundaries

VERSION = "excel-subset-1"
ERROR_PREFIX = "#C01!"
ERROR_MESSAGES = {
    "UNSUPPORTED": "fórmula no admitida por el cálculo acotado",
    "REFERENCE": "referencia no encontrada o fuera de la tabla",
    "VALUE": "la operación requiere un número y encontró texto o una celda sin valor",
    "SOURCE_ERROR": "la celda de origen contiene un error de Excel",
    "DIV_ZERO": "división por cero",
    "CYCLE": "referencia circular entre fórmulas",
    "NON_FINITE": "resultado fuera del rango numérico finito",
    "NO_NUMBERS": "el agregado no contiene números",
    "LIMIT": "se excedió un límite del cálculo acotado",
}


class FormulaError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass
class ExcelTable:
    sheet: str
    rectangle: str
    columns: list[str]


class Calculator:
    def __init__(self, sheets, tables):
        self.sheets = {s.name.casefold(): s for s in sheets}
        self.tables = {k.casefold(): v for k, v in tables.items()}
        self.memo = {}
        self.active = set()
        self.steps = 0

    def cell(self, sheet_name, row, col, depth=0):
        self.steps += 1
        if self.steps > 1_000_000 or depth > 64:
            raise FormulaError("LIMIT")
        sheet = self.sheets.get(sheet_name.casefold())
        if sheet is None or not (1 <= row <= 1048576 and 1 <= col <= 16384):
            raise FormulaError("REFERENCE")
        key = (sheet.name, row, col)
        if key in self.active:
            raise FormulaError("CYCLE")
        if key in self.memo:
            result = self.memo[key]
            if isinstance(result, FormulaError):
                raise result
            return result
        value = (
            sheet.rows[row - 1][col - 1]
            if row <= len(sheet.rows) and col <= len(sheet.rows[row - 1])
            else None
        )
        kind = sheet.cell_types.get((row, col), "blank")
        if kind == "error":
            raise FormulaError("SOURCE_ERROR")
        if kind == "date":
            raise FormulaError("UNSUPPORTED")
        if (row, col) not in sheet.formula_cells:
            if kind == "number":
                return self.finite(float(value))
            return value  # Text and blanks remain distinguishable from numeric cells.
        self.active.add(key)
        dependencies = []
        try:
            if (row, col) in sheet.unsupported_formula_cells:
                raise FormulaError("UNSUPPORTED")
            if not isinstance(value, str) or len(value) > 8192:
                raise FormulaError("UNSUPPORTED")
            tokens = Tokenizer(value).items
            if len(tokens) > 1024:
                raise FormulaError("LIMIT")
            parser = Parser(self, sheet.name, row, tokens, dependencies, depth)
            result = self.number(parser.expression())
            if parser.pos != len(parser.tokens):
                raise FormulaError("UNSUPPORTED")
        except (
            TokenizerError,
            ValueError,
            OverflowError,
            ZeroDivisionError,
            RecursionError,
        ) as exc:
            result = FormulaError(
                "DIV_ZERO" if isinstance(exc, ZeroDivisionError) else "UNSUPPORTED"
            )
        except FormulaError as exc:
            result = exc
        finally:
            self.active.remove(key)
        self.memo[key] = result
        sheet.formula_results[(row, col)] = {
            "coordinate": f"{get_column_letter(col)}{row}",
            "formula": value if isinstance(value, str) else "[unsupported formula object]",
            "value": None if isinstance(result, FormulaError) else str(result),
            "status": "error" if isinstance(result, FormulaError) else "calculated",
            "error": result.code if isinstance(result, FormulaError) else None,
            "dependencies": dependencies,
        }
        if isinstance(result, FormulaError):
            raise result
        return result

    @staticmethod
    def finite(value):
        if not math.isfinite(value):
            raise FormulaError("NON_FINITE")
        return value

    def number(self, value):
        if not isinstance(value, float):
            raise FormulaError("VALUE")
        return self.finite(value)

    def reference(self, text, sheet, row, dependencies, depth):
        # Explicitly reject workbook URLs, external books, defined names and 3D refs.
        structured = re.fullmatch(
            r"([^\[\]!]+)\[\[#This Row\],\[([^\]]+)\](?::\[([^\]]+)\])?\]", text
        )
        if structured:
            name, first, last = structured.groups()
            table = self.tables.get(name.casefold())
            if table is None:
                raise FormulaError("REFERENCE")
            left, top, right, bottom = range_boundaries(table.rectangle)
            if not top < row <= bottom:
                raise FormulaError("REFERENCE")
            names = [c.casefold() for c in table.columns]
            try:
                start, end = names.index(first.casefold()), names.index((last or first).casefold())
            except ValueError as exc:
                raise FormulaError("REFERENCE") from exc
            if start > end or left + end > right:
                raise FormulaError("REFERENCE")
            sheet, bounds = table.sheet, (left + start, row, left + end, row)
        else:
            match = re.fullmatch(
                r"(?:(?:'((?:[^']|'')+)'|([^'!\[\]:]+))!)?(\$?[A-Za-z]{1,3}\$?[1-9][0-9]*(?::\$?[A-Za-z]{1,3}\$?[1-9][0-9]*)?)",
                text,
            )
            if not match:
                raise FormulaError("UNSUPPORTED")
            quoted, plain, address = match.groups()
            sheet = quoted.replace("''", "'") if quoted else plain or sheet
            if any(c in sheet for c in "[]:/\\"):
                raise FormulaError("UNSUPPORTED")
            bounds = range_boundaries(address.upper())
        left, top, right, bottom = bounds
        if right < left or bottom < top or (right - left + 1) * (bottom - top + 1) > 10000:
            raise FormulaError("LIMIT")
        values = []
        for r in range(top, bottom + 1):
            for c in range(left, right + 1):
                dependencies.append(
                    f"'{sheet.replace(chr(39), chr(39) * 2)}'!{get_column_letter(c)}{r}"
                )
                values.append(self.cell(sheet, r, c, depth + 1))
        return values[0] if ":" not in text and not structured else values

    def resolve(self):
        for sheet in self.sheets.values():
            for row, col in sorted(sheet.formula_cells):
                try:
                    self.cell(sheet.name, row, col)
                except FormulaError as exc:
                    if (row, col) not in sheet.formula_results:
                        sheet.formula_results[(row, col)] = {
                            "coordinate": f"{get_column_letter(col)}{row}",
                            "formula": sheet.rows[row - 1][col - 1],
                            "value": None,
                            "status": "error",
                            "error": exc.code,
                            "dependencies": [],
                        }
        # Replace only after every formula has been interpreted against original cells.
        for sheet in self.sheets.values():
            for (row, col), result in sheet.formula_results.items():
                sheet.rows[row - 1][col - 1] = (
                    result["value"]
                    if result["status"] == "calculated"
                    else ERROR_PREFIX + result["error"]
                )
            for (row, col), kind in sheet.cell_types.items():
                if kind == "error":
                    sheet.rows[row - 1][col - 1] = ERROR_PREFIX + "SOURCE_ERROR"


class Parser:
    def __init__(self, calculator, sheet, row, tokens, dependencies, depth):
        self.calc, self.sheet, self.row = calculator, sheet, row
        # Whitespace intersection is not supported, and is not silently interpreted.
        self.tokens = [t for t in tokens if t.type != "WHITE-SPACE"]
        self.pos, self.dependencies, self.depth = 0, dependencies, depth

    def expression(self, minimum=0):
        if self.pos >= len(self.tokens):
            raise FormulaError("UNSUPPORTED")
        token = self.tokens[self.pos]
        self.pos += 1
        if token.type == "OPERAND" and token.subtype == "NUMBER":
            value = self.calc.finite(float(token.value))
        elif token.type == "OPERAND" and token.subtype == "RANGE":
            value = self.calc.reference(
                token.value, self.sheet, self.row, self.dependencies, self.depth
            )
        elif token.type == "OPERATOR-PREFIX" and token.value in {"+", "-"}:
            value = self.calc.number(self.expression(30)) * (-1 if token.value == "-" else 1)
        elif token.type == "PAREN" and token.subtype == "OPEN":
            value = self.expression()
            self.close("PAREN")
        elif token.type == "FUNC" and token.subtype == "OPEN":
            name = token.value[:-1].upper()
            if name not in {"AVERAGE", "SUM", "MIN", "MAX", "COUNT"}:
                raise FormulaError("UNSUPPORTED")
            args = []
            while True:
                arg = self.expression()
                args.extend(arg if isinstance(arg, list) else [arg])
                if (
                    self.pos < len(self.tokens)
                    and self.tokens[self.pos].type == "SEP"
                    and self.tokens[self.pos].subtype == "ARG"
                ):
                    self.pos += 1
                    continue
                break
            self.close("FUNC")
            numbers = [v for v in args if isinstance(v, float)]
            if name == "COUNT":
                value = float(len(numbers))
            elif not numbers:
                raise FormulaError("NO_NUMBERS")
            elif name == "AVERAGE":
                value = sum(numbers) / len(numbers)
            elif name == "SUM":
                value = sum(numbers)
            elif name == "MIN":
                value = min(numbers)
            else:
                value = max(numbers)
            value = self.calc.finite(value)
        else:
            raise FormulaError("UNSUPPORTED")
        precedence = {"+": 10, "-": 10, "*": 20, "/": 20}
        while self.pos < len(self.tokens):
            operator = self.tokens[self.pos]
            rank = precedence.get(operator.value, -1)
            if operator.type != "OPERATOR-INFIX" or rank < minimum:
                break
            self.pos += 1
            right = self.calc.number(self.expression(rank + 1))
            left = self.calc.number(value)
            if operator.value == "+":
                value = left + right
            elif operator.value == "-":
                value = left - right
            elif operator.value == "*":
                value = left * right
            else:
                value = left / right
            value = self.calc.finite(value)
        return value

    def close(self, kind):
        if (
            self.pos >= len(self.tokens)
            or self.tokens[self.pos].type != kind
            or self.tokens[self.pos].subtype != "CLOSE"
        ):
            raise FormulaError("UNSUPPORTED")
        self.pos += 1

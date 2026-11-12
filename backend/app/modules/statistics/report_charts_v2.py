"""Shared vector geometry and PNG drawing over authorized figure data only."""

from io import BytesIO
from textwrap import shorten

from app.modules.statistics.presentation_v2 import format_number

WIDTH = 540


def chart_geometry(figure):
    bars = figure.kind in {"bars", "metric"}
    height = max(180, 75 + len(figure.y) * 28) if bars else 300
    commands = []

    def line(x1, y1, x2, y2, color="#d9e1e8"):
        commands.append(("line", (x1, y1, x2, y2), color))

    def text(x, y, label, size=9):
        commands.append(("text", (x, y, str(label), size), "#172b3a"))

    lo = figure.axis_min if figure.axis_min is not None else min([0, *figure.y])
    hi = figure.axis_max if figure.axis_max is not None else max([0, *figure.y])
    if lo == hi:
        hi = lo + 1

    # Divide before subtracting so finite values near float limits remain drawable.
    def fraction(v, low, high):
        return (v / 2 - low / 2) / (high / 2 - low / 2) if high != low else 0.5

    if bars:
        x0, x1 = 235, 485

        def pos(value):
            return x0 + fraction(value, lo, hi) * (x1 - x0)

        for n in range(5):
            value = lo * (1 - n / 4) + hi * (n / 4)
            x = pos(value)
            line(x, 15, x, height - 45)
            text(x - 10, height - 32, format_number(value), 8)
        line(pos(0), 15, pos(0), height - 45, "#526775")
        for n, value in enumerate(figure.y):
            y = 22 + n * 28
            label = figure.labels[n] if n < len(figure.labels) else figure.x_label
            text(4, y + 10, shorten(label, width=43, placeholder="…"), 8)
            a, b = sorted((pos(0), pos(value)))
            if b > a:
                commands.append(("rect", (a, y, b, y + 15), "#376d8c"))
            text(b + 4, y + 10, format_number(value), 8)
        text(235, height - 8, shorten(figure.y_label, width=65, placeholder="…"), 8)
    else:
        xlow, xhigh = min(figure.x), max(figure.x)

        def px(value):
            return 60 + fraction(value, xlow, xhigh) * 440

        def py(value):
            return 245 - fraction(value, lo, hi) * 210

        for n in range(5):
            value = lo * (1 - n / 4) + hi * (n / 4)
            line(60, py(value), 500, py(value))
            text(4, py(value) + 3, format_number(value), 8)
            xvalue = xlow * (1 - n / 4) + xhigh * (n / 4)
            text(52 + 110 * n, 263, format_number(xvalue), 8)
        line(60, 25, 60, 245, "#526775")
        line(60, 245, 500, 245, "#526775")
        text(60, 14, shorten(figure.y_label, width=85, placeholder="…"), 9)
        text(60, 287, shorten(figure.x_label, width=85, placeholder="…"), 9)
        for x, y in zip(figure.x, figure.y, strict=True):
            commands.append(("circle", (px(x), py(y), 2.4), "#376d8c"))
    return height, commands


def chart_drawing(figure):
    from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
    from reportlab.lib.colors import HexColor

    height, commands = chart_geometry(figure)
    drawing = Drawing(WIDTH, height)
    for kind, args, color in commands:
        color = HexColor(color)
        if kind == "text":
            x, y, label, size = args
            shape = String(
                x, height - y, label, fontName="Helvetica", fontSize=size, fillColor=color
            )
        elif kind == "line":
            a, b, c, d = args
            shape = Line(a, height - b, c, height - d, strokeColor=color, strokeWidth=0.6)
        elif kind == "rect":
            a, b, c, d = args
            shape = Rect(a, height - d, c - a, d - b, fillColor=color, strokeColor=None)
        else:
            x, y, radius = args
            shape = Circle(x, height - y, radius, fillColor=color, strokeColor=None)
        drawing.add(shape)
    return drawing


def chart_png(figure):
    from PIL import Image, ImageDraw, ImageFont

    height, commands = chart_geometry(figure)
    scale = 3
    canvas = Image.new("RGB", (WIDTH * scale, height * scale), "white")
    pen = ImageDraw.Draw(canvas)
    for kind, args, color in commands:
        if kind == "text":
            x, y, label, size = args
            font = ImageFont.load_default(size=size * scale)
            pen.text((x * scale, (y - size) * scale), label, fill=color, font=font)
        elif kind == "circle":
            x, y, radius = args
            pen.ellipse(
                tuple(v * scale for v in (x - radius, y - radius, x + radius, y + radius)),
                fill=color,
            )
        elif kind == "line":
            pen.line(tuple(v * scale for v in args), fill=color, width=2)
        else:
            pen.rectangle(tuple(v * scale for v in args), fill=color)
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

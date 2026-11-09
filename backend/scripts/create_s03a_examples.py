"""Small, deterministic, exclusively synthetic multi-source examples."""

import argparse
import io
import zipfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook


def workbook_bytes() -> bytes:
    book = Workbook()
    book.properties.creator = "Ejemplo sintético TesisStat"
    book.properties.created = book.properties.modified = datetime(2026, 1, 1)
    instructions = book.active
    instructions.title = "Instrucciones"
    instructions.append(["Datos ficticios: revisar cada fuente antes de analizar."])
    instructions.append(["No combinar mediciones en S03A."])
    for name in ("Antes", "Después", "Instrumento"):
        sheet = book.create_sheet(name)
        sheet.append(["codigo", "nota" if name != "Instrumento" else "item_1", "grupo"])
        for index in range(1, 124):
            sheet.append(
                [f"{index:04d}", None if index == 7 else (index % 5) + 1, "A" if index % 2 else "B"]
            )
        if name == "Después":
            sheet["B3"] = "=1+2"
        if name == "Instrumento":
            sheet.sheet_state = "hidden"
    book.create_sheet("Vacía")
    titled = book.create_sheet("Con título")
    titled.append(["Notas de una muestra completamente ficticia"])
    titled.append([])
    titled.append(["codigo", "valor"])
    for index in range(1, 38):
        titled.append([f"T{index:03d}", index])
    buffer = io.BytesIO()
    book.save(buffer)
    book.close()
    # openpyxl updates modified time and ZIP timestamps. Freeze both for reproducibility.
    stable = io.BytesIO()
    with (
        zipfile.ZipFile(buffer) as original,
        zipfile.ZipFile(stable, "w", compression=zipfile.ZIP_DEFLATED) as output,
    ):
        import re

        for name in sorted(original.namelist()):
            data = original.read(name)
            if name == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>).*?(</dcterms:modified>)",
                    rb"\g<1>2026-01-01T00:00:00Z\g<2>",
                    data,
                )
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)
    return stable.getvalue()


def csv_bytes():
    return (
        "codigo,otra_medicion\n" + "".join(f"{index:04d},{index + 10}\n" for index in range(1, 28))
    ).encode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parents[2] / "fixtures/data/s03a"
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "mediciones-sinteticas.xlsx").write_bytes(workbook_bytes())
    (args.output / "medicion-independiente.csv").write_bytes(csv_bytes())


if __name__ == "__main__":
    main()

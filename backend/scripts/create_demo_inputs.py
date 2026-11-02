"""Create fictitious local files for the application demonstration, without AI."""

from pathlib import Path

from docx import Document


def main():
    output = Path(".cache/application-demo")
    output.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading("Estudio sintético de horas y rendimiento", 0)
    document.add_paragraph("Objetivo general: analizar horas y rendimiento ficticios.")
    document.add_paragraph("Hipótesis general: existe relación entre horas y rendimiento.")
    document.add_paragraph("Diseño observacional con observaciones independientes.")
    document.add_paragraph("Variables: Horas de estudio y Rendimiento, ambas de razón.")
    document.add_paragraph(
        "Todos los datos de este documento son inventados para una demostración local."
    )
    document.save(output / "metodologia-sintetica.docx")
    (output / "datos-sinteticos.csv").write_text(
        "horas_estudio,rendimiento\n1,2\n2,4\n3,6\n4,8\n4,8\n", encoding="utf-8"
    )
    print(output.resolve())


if __name__ == "__main__":
    main()

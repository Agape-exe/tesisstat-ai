# Ejemplos sintéticos S03A

`mediciones-sinteticas.xlsx`: seis hojas, primera de instrucciones; Antes/Después/Instrumento
con 123 observaciones cada una; Instrumento oculta; una hoja vacía; «Con título» con encabezado
en fila 3 y 37 observaciones (rango **A3:B40**). Código textual con ceros, faltante XLSX null
y fórmula de ejemplo en Después (`=1+2`), conservada como texto sin calcular.

`medicion-independiente.csv`: otra fuente de 27 observaciones. No reemplaza al libro.
Ningún nombre/código corresponde a personas reales. Los valores no acreditan un diseño.

Regenerar desde backend: `python -m scripts.create_s03a_examples`. Los bytes del XLSX se
normalizan con fechas ZIP/core fijas para obtener el mismo SHA-256 al repetir el generador.
Excluir Instrucciones/Vacía y confirmar A3:B40 deja el libro con cuatro tablas listas.
La combinación por identificadores queda para S03B.

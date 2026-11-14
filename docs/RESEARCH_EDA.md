# Research EDA — Sesión 9

## Alcance

El perfilador lee todas las filas del CSV UTF-8 o de la primera hoja XLSX mediante el mismo lector validado que genera la vista previa. No modifica registros ni ejecuta fórmulas. No usa IA ni servicios externos. La vista previa conserva su límite de 20 filas.

## Criterios y fórmulas

- Filas: registros después de la cabecera. Columnas: cabeceras validadas. Celdas: filas × columnas.
- Faltante: celda XLSX `None`, cadena vacía, solo espacios, o (sin distinguir mayúsculas y tras quitar espacios) `NA`, `N/A`, `null`, `none`. Estos marcadores pueden ser categorías legítimas; el reporte conserva el archivo original y la política puede cambiarse en `ProfilePolicy` en una sesión futura. Faltantes % = faltantes / celdas × 100; en columna = faltantes / filas × 100. Denominador cero produce 0%.
- Duplicado exacto: fila cuyo vector de valores crudos ya apareció. Se cuentan las apariciones posteriores a la primera. Duplicados % = duplicados / filas × 100. Una repetición puede ser legítima.
- Distintos: número de valores crudos no faltantes diferentes. Unicidad % = distintos / presentes × 100. Constante: un solo valor observado y al menos uno presente. Vacía: cero presentes.
- Numérico: `Decimal` finito tras quitar espacios externos. El texto original se conserva. Si todos los presentes son numéricos, se sugiere categórico cuando hay pocos valores distintos (`<= min(10, max(1, presentes // 2))`); de otro modo numérico. La categoría numérica codificada requiere revisión humana.
- Temporal: todos los presentes deben usar una fecha ISO válida `AAAA-MM-DD` o fecha y hora ISO compatible. Fechas con barras o formato día/mes/año se marcan ambiguas. Mínimo y máximo solo se muestran cuando toda la columna es interpretable de forma consistente.
- Mixto: coexistencia de números y no números, o de fechas ISO y otros formatos. Texto/categórico se decide por cardinalidad, de forma conservadora. Identificador posible: cabecera con `id`, `codigo`, `code`, `uuid`, `dni`, o valores únicos y completos de longitud mínima 6 en al menos tres filas. Es una sugerencia, no una escala de medición estadística.
- Advertencia de faltantes altos: `>= 30%`; mayoría numérica con incompatibles: `>= 80%` de los presentes. `ProfilePolicy` permite cambiar ambos umbrales y el tope de frecuencias (1–20, valor predeterminado 10). La versión del reporte incluye estos parámetros y los marcadores para invalidar la caché.
- Frecuencias: valores crudos categóricos, ordenados por frecuencia descendente; el porcentaje usa valores presentes. Se devuelven hasta 10 categorías, cada etiqueta truncada a 120 caracteres. Los ejemplos incompatibles se limitan a cinco y 120 caracteres. El reporte incluye severidad `info`, `quality` o `blocking`; no asigna puntuación global.

## Reporte y API

`POST /api/research/projects/{project_id}/datasets/{dataset_id}/eda` calcula o devuelve la caché. `?force=true` recalcula. `GET` en la misma ruta consulta el reporte o responde 404 si falta o está invalidado. Ambos comprueban pertenencia al proyecto. El reporte incluye `project_id`, `dataset_id`, `processed_at`, `content_sha256`, `rule_version`, `summary`, `columns` y `warnings`. No incluye filas completas.

SQLite guarda un reporte por dataset. El hash SHA-256 del archivo y la versión de reglas controlan la vigencia. La eliminación del dataset elimina el reporte en la misma transacción SQLite. Los reportes sobreviven reinicios.

## Límites y uso

Se conservan los límites de subida: 10 MiB, 50 000 filas, 200 columnas, XLSX descomprimido hasta 50 MiB y 1000 entradas ZIP. El lector XLSX itera en modo de solo lectura; las fórmulas se muestran como expresiones y producen advertencias. El cálculo de distintos y duplicados mantiene conjuntos exactos en memoria hasta esos límites. No hay muestreo.

Inicia el backend de desarrollo y la demo Research según `docs/RESEARCH_DATASETS.md`. Abre un proyecto, sube un dataset sintético y pulsa **Analizar calidad de datos**. La misma sección muestra resumen, perfil por columna, detalle, advertencias y reanálisis. El reporte guardado se consulta al volver a la pantalla.

## Verificación y límites

Las pruebas unitarias de analizador y caché cubren CSV completo, XLSX con fórmula, faltantes, duplicados, cero filas y reinicio. Los tests HTTP comprueban rutas, pertenencia y borrado. Los tipos son sugerencias técnicas: no confirman escala nominal, ordinal, intervalo ni razón. La sesión 10 puede usar el reporte como diagnóstico para ofrecer operaciones con decisión explícita del usuario; esta sesión no transforma datos.

Verificación de la sesión: `pytest` 126/126; `ruff check .`, `ruff format --check .` y exportación de contratos sin diferencias; Vitest 50/50, ESLint, Prettier, TypeScript, build principal y build de demo Research correctos.

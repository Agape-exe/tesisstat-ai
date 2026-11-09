# Familia v2: contexto, fuentes e intención/snapshot

Canónicos: `backend/app/shared/analysis_v2.py` y `data_sources_v2.py`. S02 habilita C2;
S03A habilita archivos, hojas, tablas y contexto C3. C4 es estructura preparada para S04.
Los seis contratos v1 y sus ejemplos permanecen intactos.

Desde backend: `python -m scripts.export_contracts` regenera ambas familias;
`--check` comprueba actualidad. Desde frontend: `npm run contracts:generate` genera tipos
v1 y subcarpeta `generated/v2`. No editar los JSON Schema ni TypeScript generados a mano.
Schema `2.0.0`, revisión de recurso y versión de algoritmo son conceptos separados.

`python -m scripts.export_v2_examples` regenera ejemplos deterministas sintéticos. Los ejemplos
de C4 solo validan la estructura: sus fuentes están declaradas en `examples/sources.json`,
con un CSV ficticio verificable. Son fixtures estáticos; no se insertan en la aplicación,
no son recursos operativos C3 ni acreditan perfil, diagnóstico o ejecución real. El test
verifica pertenencia, revisiones, hashes y conteos del CSV. No hay materialización de
snapshots durante la creación de proyectos o guardado de contexto.

Decisiones compatibles de S02 y consumidores:

- `AnalysisIntentV2.observations` es Fact del enum C2: explicita la procedencia y confirmación
  exigidas por C4. S04/Orchestration consumirá `.value`; no inferir independencia por defecto.
- `Provenance.algorithm_version` opcional hace verificable la regla derived requiere
  fuente/algoritmo. Obligatorio solo cuando kind=derived; S03/S04 lo completarán.
- SourceRef de contexto usa `id=project_id` porque C2 no tiene un ID distinto. La revisión
  identifica el histórico. UI y futuro resolver deben usar esa identidad canónica.
- `SnapshotVariableV2` es proyección de variables elegidas (id, columnas, nombre y escala),
  no un diccionario editable completo. S03B prepara el recurso de diccionario y S04 construye
  esta proyección al resolver las fuentes. No se habilitan endpoints C3 en S02.
- `source_refs` enumera las referencias nombradas del snapshot. El validador verifica tipo,
  pertenencia a esa lista, revisión/hash de intención congelada y variables seleccionadas.
  Resolver otras fuentes/columnas y permisos sigue siendo responsabilidad del servidor S04.
- `canonical_hash` implementa json-sort-v1; excluye fechas, confirmaciones y hash propio del
  recurso editable. Conserva hashes anidados de SourceRef. Para un DatasetRef futuro se
  mantiene research-dataset-v1 según S00; no sustituirlo por el hash del manifiesto de ejemplo.

No hay lectura heurística de v2 por consumidores v1 ni reutilización de aprobaciones.

## Fuentes C3 de S03A

`SourceFileV2` agrupa `SourceSheetV2`; cada hoja lista apunta a `ImportedTableV2`, con
original_hash, extracción, columnas UUID y content_hash independiente de `TableContextV2`.
`TablePreviewV2` contiene una ventana de esa misma extracción; no materializa otra tabla.
Las fórmulas son texto, los faltantes se conservan y ninguna fila llega al proveedor IA.

`python -m scripts.export_source_examples` regenera los cinco ejemplos C3 y el CSV real
enlazado; tests verifican modelos/esquemas y hashes/conteos/referencias con sus bytes.
`python -m scripts.create_s03a_examples` regenera el Excel multihoja y CSV de demostración
en `fixtures/data/s03a`. No se insertan recursos ficticios al abrir proyectos anteriores.

El enum SourceRef v2 añade `source_file|source_sheet|table|table_context`.
`SourceService.source_refs` los resuelve en servidor; contexto usa id=table_id y su propia
revisión. La futura construcción de AnalysisSnapshot adaptará esta evidencia C3 a su
dataset/diccionario elegido; no hay consumidor ejecutable nuevo en esta entrega.
Lectura completa, límites, selección y recuperación:
[API C3](../../backend/app/modules/research/sources/README.md).

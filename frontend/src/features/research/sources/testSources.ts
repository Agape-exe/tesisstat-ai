import type { SourceFile, Table, TableContext } from './api';

export const table: Table = {
  schema_version: '2.0.0',
  id: 'table',
  project_id: 'project',
  file_id: 'file',
  sheet_id: 'sheet',
  revision: 1,
  created_at: '2026-11-09T12:00:00Z',
  original_hash: 'a'.repeat(64),
  content_hash: 'b'.repeat(64),
  hash_algorithm: 'table-json-v1',
  extraction: {
    header_row: 1,
    range: 'A1:B124',
    algorithm_version: 'tabular-v1',
    confirmation: null,
  },
  row_count: 123,
  column_count: 2,
  columns: [
    { id: 'id-column', name: 'codigo', position: 0 },
    { id: 'value-column', name: 'valor', position: 1 },
  ],
  warnings: [],
};
export function context(
  revision = 0,
  name: string | null = null,
): TableContext {
  const fact = (value: string | null = null) => ({
    value,
    provenance: { kind: 'manual' as const, source_refs: [] },
    confirmation: null,
  });
  return {
    schema_version: '2.0.0',
    project_id: 'project',
    table_id: 'table',
    revision,
    hash: 'c'.repeat(64),
    updated_at: revision ? '2026-11-09T12:00:00Z' : null,
    name: fact(name),
    description: fact(),
    purpose: fact(),
    row_meaning: fact(),
    population: fact(),
    identifier_column_id: fact(),
    related_tables_notes: fact(),
    measurement_moment: {
      value: 'unknown',
      provenance: { kind: 'unknown', source_refs: [] },
      confirmation: null,
    },
  };
}
export function source(): SourceFile {
  return {
    schema_version: '2.0.0',
    id: 'file',
    project_id: 'project',
    revision: 1,
    name: 'mediciones.xlsx',
    format: 'xlsx',
    size: 5000,
    hash: 'a'.repeat(64),
    hash_algorithm: 'sha256-bytes',
    created_at: '2026-11-09T12:00:00Z',
    updated_at: '2026-11-09T12:00:00Z',
    state: 'needs_clarification',
    sheets: [
      {
        id: 'sheet',
        project_id: 'project',
        file_id: 'file',
        revision: 1,
        index: 0,
        name: 'Antes',
        visibility: 'visible',
        row_count: 124,
        column_count: 2,
        state: 'ready',
        explanation: 'Reconocida automáticamente',
        hash: 'a'.repeat(64),
        table_id: 'table',
        extraction: table.extraction,
      },
      {
        id: 'pending',
        project_id: 'project',
        file_id: 'file',
        revision: 1,
        index: 1,
        name: 'Con título',
        visibility: 'hidden',
        row_count: 40,
        column_count: 2,
        state: 'pending',
        explanation: 'Confirma encabezado y rango',
        hash: 'd'.repeat(64),
        table_id: null,
        extraction: null,
      },
    ],
  };
}

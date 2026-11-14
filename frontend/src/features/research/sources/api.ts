import type { SourceFileV2 } from '../../../shared/contracts/generated/v2/SourceFileV2';
import type { SourceSheetV2 } from '../../../shared/contracts/generated/v2/SourceSheetV2';
import type { ImportedTableV2 } from '../../../shared/contracts/generated/v2/ImportedTableV2';
import type { TableContextV2 } from '../../../shared/contracts/generated/v2/TableContextV2';
import type { TablePreviewV2 } from '../../../shared/contracts/generated/v2/TablePreviewV2';
import { resourcesChanged } from '../projects/resourceEvents';

export type Sheet = Required<SourceSheetV2>;
export type SourceFile = Omit<
  Required<SourceFileV2>,
  'sheets' | 'reimported_from'
> & {
  sheets: Sheet[];
  reimported_from?: string | null;
};
export type Table = Omit<
  Required<ImportedTableV2>,
  'omitted_columns' | 'calculation_version'
> &
  Pick<ImportedTableV2, 'omitted_columns' | 'calculation_version'>;
export type TableContext = Required<TableContextV2>;
export type ContextField =
  | 'name'
  | 'description'
  | 'purpose'
  | 'row_meaning'
  | 'measurement_moment'
  | 'population'
  | 'identifier_column_id'
  | 'related_tables_notes';
export type ContextChanges = Partial<Record<ContextField, string | null>>;
export interface ContextPatch {
  expected_revision: number;
  changes: ContextChanges;
  confirm_fields: string[];
}
export interface SheetPatch {
  expected_revision: number;
  action: 'exclude' | 'include' | 'extract';
  header_row?: number;
  range?: string;
}
export class SourcesError extends Error {
  constructor(
    message: string,
    public status: number,
    public revision: number | null = null,
  ) {
    super(message);
  }
}
export function createSourcesApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  function root(projectId: string) {
    return `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(projectId)}`;
  }
  async function request<T>(
    projectId: string,
    path: string,
    init?: RequestInit,
  ) {
    let response: Response;
    try {
      response = await fetch(root(projectId) + path, {
        ...init,
        signal: AbortSignal.timeout(60000),
      });
    } catch {
      throw new SourcesError(
        'No se pudo contactar con el servidor. Reintenta.',
        0,
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new SourcesError(
        body?.error?.message ?? 'No se pudo consultar o guardar la fuente.',
        response.status,
        body?.error?.current_revision ?? null,
      );
    }
    const data = (await response.json()) as T;
    if (init?.method && init.method !== 'GET') resourcesChanged(projectId);
    return data;
  }
  const patch = (body: object): RequestInit => ({
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return {
    files: (id: string) => request<SourceFile[]>(id, '/files'),
    contexts: (id: string) => request<TableContext[]>(id, '/table-contexts'),
    upload: (id: string, file: File) =>
      request<SourceFile>(id, '/files', {
        method: 'POST',
        headers: { 'X-File-Name': encodeURIComponent(file.name) },
        body: file,
      }),
    reimport: (id: string, fileId: string) =>
      request<SourceFile>(id, `/files/${encodeURIComponent(fileId)}/reimport`, {
        method: 'POST',
      }),
    calculationUrl: (id: string, tableId: string) =>
      `${root(id)}/tables/${encodeURIComponent(tableId)}/calculation`,
    sheet: (id: string, fileId: string, sheetId: string, body: SheetPatch) =>
      request<SourceFile>(
        id,
        `/files/${encodeURIComponent(fileId)}/sheets/${encodeURIComponent(sheetId)}`,
        patch(body),
      ),
    originalUrl: (id: string, fileId: string) =>
      `${root(id)}/files/${encodeURIComponent(fileId)}/original`,
    preview: (id: string, tableId: string) =>
      request<TablePreviewV2>(
        id,
        `/tables/${encodeURIComponent(tableId)}/preview`,
      ),
    context: (id: string, tableId: string) =>
      request<TableContext>(
        id,
        `/tables/${encodeURIComponent(tableId)}/context`,
      ),
    patchContext: (id: string, tableId: string, body: ContextPatch) =>
      request<TableContext>(
        id,
        `/tables/${encodeURIComponent(tableId)}/context`,
        patch(body),
      ),
  };
}
export type SourcesApi = ReturnType<typeof createSourcesApi>;

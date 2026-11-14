import type { DatasetRefV2 } from '../../../shared/contracts/generated/v2/DatasetRefV2';
import type { VariableDictionaryV2 } from '../../../shared/contracts/generated/v2/VariableDictionaryV2';
import type { TableProfileV2 } from '../../../shared/contracts/generated/v2/TableProfileV2';
import type { TableRecipeV2 } from '../../../shared/contracts/generated/v2/TableRecipeV2';
import type { PreparationPreviewV2 } from '../../../shared/contracts/generated/v2/PreparationPreviewV2';
import type { DerivedTableV2 } from '../../../shared/contracts/generated/v2/DerivedTableV2';
import { SourcesError } from '../sources/api';
import { resourcesChanged } from '../projects/resourceEvents';

export type Dataset = Required<DatasetRefV2>;
export type Dictionary = Required<VariableDictionaryV2>;
export type Variable = Required<Dictionary['variables'][number]>;
export type Profile = Required<TableProfileV2>;
export type Recipe = TableRecipeV2;
export type Preview = Required<PreparationPreviewV2>;
export type Derived = Required<DerivedTableV2>;
export type VariableChanges = Partial<{
  name: string | null;
  description: string | null;
  measurement_scale: 'nominal' | 'ordinal' | 'interval' | 'ratio' | 'unknown';
  column_ids: string[];
  category_order: string[];
  missing_markers: string[];
  identifier_confirmed: boolean | null;
}>;
export interface Summary {
  tables: {
    id: string;
    name: string;
    kind: string;
    profile: 'current' | 'stale' | 'absent';
    variables: number;
    confirmed_variables: number;
    usable: boolean;
  }[];
  derived: number;
}
export function createDataApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    project: string,
    path: string,
    body?: object,
    method = 'POST',
  ) {
    let response: Response;
    try {
      response = await fetch(
        `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(project)}${path}`,
        {
          ...(body
            ? {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
              }
            : {}),
          signal: AbortSignal.timeout(60000),
        },
      );
    } catch {
      throw new SourcesError('No se pudo contactar con el servidor.', 0);
    }
    if (!response.ok) {
      const value = await response.json().catch(() => null);
      throw new SourcesError(
        value?.error?.message ?? 'No se pudo consultar o guardar los datos.',
        response.status,
        value?.error?.current_revision ?? null,
      );
    }
    const data = (await response.json()) as T;
    if (body) resourcesChanged(project);
    return data;
  }
  const table = (id: string) => `/data-tables/${encodeURIComponent(id)}`;
  return {
    tables: (p: string) => request<Dataset[]>(p, '/data-tables'),
    summary: (p: string) => request<Summary>(p, '/data-summary'),
    preview: (p: string, id: string) =>
      request<{ dataset_ref: Dataset; rows: (string | null)[][] }>(
        p,
        `${table(id)}/preview`,
      ),
    dictionary: (p: string, id: string) =>
      request<Dictionary>(p, `${table(id)}/dictionary`),
    saveDictionary: (
      p: string,
      d: Dictionary,
      changes: Record<string, VariableChanges>,
      confirm_fields: string[],
      expected_revision = d.revision,
    ) =>
      request<Dictionary>(
        p,
        `${table(d.dataset_ref.id)}/dictionary`,
        {
          expected_revision,
          dataset_revision: d.dataset_ref.revision,
          dataset_hash: d.dataset_ref.hash,
          changes,
          confirm_fields,
        },
        'PATCH',
      ),
    profile: async (p: string, id: string) => {
      try {
        return await request<Profile>(p, `${table(id)}/profile`);
      } catch (error) {
        if (error instanceof SourcesError && error.status === 404) return null;
        throw error;
      }
    },
    compute: (p: string, d: Dataset) =>
      request<Profile>(p, `${table(d.id)}/profile`, {
        dataset_revision: d.revision,
        dataset_hash: d.hash,
        confirm: true,
      }),
    prepare: (p: string, recipe: Recipe) =>
      request<Preview>(p, '/table-preparations/preview', recipe),
    apply: (p: string, preview: Preview) =>
      request<Derived>(p, '/table-preparations/apply', {
        preview_id: preview.id,
        recipe_hash: preview.recipe_hash,
        confirm: true,
      }),
    derived: (p: string, id: string) =>
      request<Derived>(p, `/derived-tables/${encodeURIComponent(id)}`),
  };
}
export type DataApi = ReturnType<typeof createDataApi>;

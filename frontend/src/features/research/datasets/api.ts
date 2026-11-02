export interface ResearchDataset {
  id: string;
  project_id: string;
  name: string;
  format: 'csv' | 'xlsx';
  size: number;
  row_count: number;
  column_count: number;
  columns: string[];
  sheet: string | null;
  uploaded_at: string;
  active: boolean;
  warnings: string[];
}

export interface DatasetPreview {
  columns: string[];
  rows: (string | null)[][];
  row_count: number;
  column_count: number;
  format: 'csv' | 'xlsx';
  sheet: string | null;
  warnings: string[];
}

export interface DatasetApi {
  list(projectId: string, signal?: AbortSignal): Promise<ResearchDataset[]>;
  upload(projectId: string, file: File): Promise<ResearchDataset>;
  preview(projectId: string, id: string): Promise<DatasetPreview>;
  activate(projectId: string, id: string): Promise<ResearchDataset>;
  delete(projectId: string, id: string): Promise<void>;
}

export function createDatasetApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
): DatasetApi {
  const root = `${baseUrl.replace(/\/$/, '')}/api/research/projects`;
  const path = (projectId: string) =>
    `${root}/${encodeURIComponent(projectId)}/datasets`;
  async function request<T>(
    url: string,
    options: RequestInit = {},
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        signal: options.signal
          ? AbortSignal.any([options.signal, AbortSignal.timeout(30000)])
          : AbortSignal.timeout(30000),
      });
    } catch {
      throw new Error('No se pudo contactar con Research. Intenta nuevamente.');
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        typeof body?.detail === 'string'
          ? body.detail
          : 'No se pudo completar la operación. Intenta nuevamente.',
      );
    }
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  }
  const item = (projectId: string, id: string) =>
    `${path(projectId)}/${encodeURIComponent(id)}`;
  return {
    list: (projectId, signal) => request(path(projectId), { signal }),
    upload: (projectId, file) =>
      request(path(projectId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-File-Name': encodeURIComponent(file.name),
        },
        body: file,
      }),
    preview: (projectId, id) => request(`${item(projectId, id)}/preview`),
    activate: (projectId, id) =>
      request(`${item(projectId, id)}/activate`, { method: 'POST' }),
    delete: (projectId, id) =>
      request(item(projectId, id), { method: 'DELETE' }),
  };
}

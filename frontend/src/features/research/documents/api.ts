export interface ResearchDocument {
  id: string;
  project_id: string;
  name: string;
  format: 'pdf' | 'docx';
  size: number;
  uploaded_at: string;
}

export interface DocumentApi {
  list(projectId: string, signal?: AbortSignal): Promise<ResearchDocument[]>;
  upload(projectId: string, file: File): Promise<ResearchDocument>;
  delete(projectId: string, documentId: string): Promise<void>;
}

export class DocumentApiError extends Error {}

export function createDocumentApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
): DocumentApi {
  const root = `${baseUrl.replace(/\/$/, '')}/api/research/projects`;
  async function request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${root}${path}`, {
        ...options,
        signal: options.signal
          ? AbortSignal.any([options.signal, AbortSignal.timeout(30000)])
          : AbortSignal.timeout(30000),
      });
    } catch (error) {
      if (options.signal?.aborted) throw error;
      throw new DocumentApiError(
        'No se pudo contactar con Research. Intenta nuevamente.',
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new DocumentApiError(
        typeof body?.detail === 'string'
          ? body.detail
          : 'No se pudo completar la operación. Intenta nuevamente.',
      );
    }
    return response.status === 204
      ? (undefined as T)
      : ((await response.json()) as T);
  }
  const path = (projectId: string) =>
    `/${encodeURIComponent(projectId)}/documents`;
  return {
    list: (projectId, signal) =>
      request<ResearchDocument[]>(path(projectId), { signal }),
    upload: (projectId, file) =>
      request<ResearchDocument>(path(projectId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'X-File-Name': encodeURIComponent(file.name),
        },
        body: file,
      }),
    delete: (projectId, documentId) =>
      request<void>(`${path(projectId)}/${encodeURIComponent(documentId)}`, {
        method: 'DELETE',
      }),
  };
}

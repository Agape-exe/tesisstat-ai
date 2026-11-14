import type { Project, ProjectDraft, ProjectService } from './types';

export class ProjectApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

export function createProjectApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
): ProjectService {
  const url = `${baseUrl.replace(/\/$/, '')}/api/research/projects`;

  async function request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${url}${path}`, {
        ...options,
        headers: options.body
          ? { 'Content-Type': 'application/json' }
          : undefined,
        signal: options.signal
          ? AbortSignal.any([options.signal, AbortSignal.timeout(10000)])
          : AbortSignal.timeout(10000),
      });
    } catch (error) {
      if (options.signal?.aborted) throw error;
      throw new ProjectApiError(
        'No se pudo contactar con Research. Comprueba la conexión e intenta nuevamente.',
        0,
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const fields: Record<string, string> = {};
      if (body?.errors && typeof body.errors === 'object') {
        for (const [key, value] of Object.entries(body.errors)) {
          if (typeof value === 'string') fields[key] = value;
        }
      }
      throw new ProjectApiError(
        typeof body?.detail === 'string'
          ? body.detail
          : 'No se pudo completar la operación. Intenta nuevamente.',
        response.status,
        fields,
      );
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  return {
    list: (signal) => request<Project[]>('', { signal }),
    get: (id, signal) =>
      request<Project>(`/${encodeURIComponent(id)}`, { signal }),
    create: (draft: ProjectDraft) =>
      request<Project>('', { method: 'POST', body: JSON.stringify(draft) }),
    update: (id, draft) =>
      request<Project>(`/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: JSON.stringify(draft),
      }),
    delete: (id) =>
      request<void>(`/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  };
}

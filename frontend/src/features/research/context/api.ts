import type { ProjectContextV2 } from '../../../shared/contracts/generated/v2/ProjectContextV2';

export type Context = Required<ProjectContextV2>;
export type ContextFact = Context['main_objective'];
export class ContextApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: string[] = [],
    public currentRevision: number | null = null,
  ) {
    super(message);
  }
}
export interface ContextMutation {
  expected_revision: number;
  changes: Record<string, unknown>;
  confirm_fields: string[];
}
export function createContextApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    projectId: string,
    suffix = '',
    body?: ContextMutation,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(
        `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(projectId)}/context${suffix}`,
        {
          method: body ? 'PATCH' : 'GET',
          headers: body ? { 'Content-Type': 'application/json' } : undefined,
          body: body ? JSON.stringify(body) : undefined,
          signal: AbortSignal.timeout(10000),
        },
      );
    } catch {
      throw new ContextApiError(
        'No se pudo contactar con el servidor. Tu borrador sigue aquí.',
        0,
      );
    }
    if (!response.ok) {
      const result = await response.json().catch(() => null);
      throw new ContextApiError(
        result?.error?.message ?? 'No se pudo consultar o guardar el contexto.',
        response.status,
        result?.error?.fields ?? [],
        result?.error?.current_revision ?? null,
      );
    }
    return response.json() as Promise<T>;
  }
  return {
    get: (id: string) => request<Context>(id),
    patch: (id: string, body: ContextMutation) =>
      request<Context>(id, '', body),
    revisions: (id: string) => request<Context[]>(id, '/revisions'),
  };
}

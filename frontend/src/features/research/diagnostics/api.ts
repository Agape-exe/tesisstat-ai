import type { AnalysisIntentV2 } from '../../../shared/contracts/generated/v2/AnalysisIntentV2';
import type { DiagnosticV2 } from '../../../shared/contracts/generated/v2/DiagnosticV2';
import type { IntentPatch } from '../../../shared/contracts/generated/v2/IntentPatch';
import type { DiagnosticRequest } from '../../../shared/contracts/generated/v2/DiagnosticRequest';
import { SourcesError } from '../sources/api';
import { resourcesChanged } from '../projects/resourceEvents';

export type Intent = Required<AnalysisIntentV2>;
export type Diagnostic = Required<DiagnosticV2>;
export type Changes = IntentPatch['changes'];
export type Check = DiagnosticRequest['checks'][number];

export function createDiagnosticsApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    project: string,
    path: string,
    body?: object,
    method = 'POST',
  ): Promise<T> {
    const response = await fetch(
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
    if (!response.ok) {
      const value = await response.json().catch(() => null);
      throw new SourcesError(
        value?.error?.message ?? 'No se pudo consultar o guardar el análisis.',
        response.status,
        value?.error?.current_revision ?? null,
      );
    }
    const data = await response.json();
    if (body) resourcesChanged(project);
    return data;
  }
  return {
    list: (p: string) => request<Intent[]>(p, '/intents'),
    save: (p: string, id: string | null, body: IntentPatch) =>
      request<Intent>(
        p,
        `/intents${id ? `/${encodeURIComponent(id)}` : ''}`,
        body,
        id ? 'PATCH' : 'POST',
      ),
    history: (p: string, id: string) =>
      request<Diagnostic[]>(
        p,
        `/diagnostics?intent_id=${encodeURIComponent(id)}`,
      ),
    compute: (p: string, body: DiagnosticRequest) =>
      request<Diagnostic>(p, '/diagnostics', body),
  };
}

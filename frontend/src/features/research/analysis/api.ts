import type { AnalysisPlan } from '../../../shared/contracts/generated/AnalysisPlan';
import type { AnalysisResult } from '../../../shared/contracts/generated/AnalysisResult';

export interface AnalysisRecord {
  project_id: string;
  source_version: string;
  proposal_token: string;
  plan: AnalysisPlan;
  created_at: string;
  approved_at: string | null;
  invalidated_at: string | null;
  stale_reason: string | null;
  executable: boolean;
  limitation: string | null;
  result: AnalysisResult | null;
}

export function createAnalysisApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
) {
  async function request<T>(
    project: string,
    suffix: string,
    body?: object,
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(
        `${baseUrl.replace(/\/$/, '')}/api/research/projects/${encodeURIComponent(project)}/analysis${suffix}`,
        {
          method: body ? 'POST' : 'GET',
          ...(body
            ? {
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
              }
            : {}),
          signal: AbortSignal.timeout(30000),
        },
      );
    } catch {
      throw new Error(
        'No se pudo contactar con Research. Recarga para recuperar el estado antes de reintentar.',
      );
    }
    const value = await response.json().catch(() => null);
    if (!response.ok)
      throw new Error(
        typeof value?.detail === 'string'
          ? value.detail
          : 'No se pudo completar el análisis. Recarga y revisa la propuesta.',
      );
    return value as T;
  }
  return {
    plans: (project: string) => request<AnalysisRecord[]>(project, '/plans'),
    results: (project: string) =>
      request<AnalysisRecord[]>(project, '/results'),
    propose: (project: string, packageId: string, hypothesisId: string) =>
      request<AnalysisRecord>(project, '/plan', {
        package_id: packageId,
        hypothesis_id: hypothesisId,
      }),
    approve: (project: string, record: AnalysisRecord) =>
      request<AnalysisRecord>(
        project,
        `/plans/${encodeURIComponent(record.plan.id)}/approve`,
        { confirm: true, proposal_token: record.proposal_token },
      ),
    execute: (project: string, planId: string) =>
      request<AnalysisResult>(
        project,
        `/plans/${encodeURIComponent(planId)}/execute`,
        {},
      ),
  };
}

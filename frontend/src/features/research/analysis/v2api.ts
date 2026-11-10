import type { AnalysisPlanV2 } from '../../../shared/contracts/generated/v2/AnalysisPlanV2';
import type { AnalysisResultV2 } from '../../../shared/contracts/generated/v2/AnalysisResultV2';
import type { PlanRequest } from '../../../shared/contracts/generated/v2/PlanRequest';
import { SourcesError } from '../sources/api';
export type Plan = Required<AnalysisPlanV2>;
export type Result = Required<AnalysisResultV2>;
export function createAnalysisV2Api(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    p: string,
    path: string,
    body?: object,
  ): Promise<T> {
    const response = await fetch(
      `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(p)}/analysis${path}`,
      {
        method: body ? 'POST' : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(90000),
      },
    );
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new SourcesError(
        data?.error?.message ?? 'No se pudo completar la operación.',
        response.status,
        null,
      );
    }
    const data = await response.json();
    if (!body && ['/plans', '/results'].includes(path) && !Array.isArray(data))
      throw new Error('Respuesta de evidencia no válida. Reintenta.');
    return data;
  }
  return {
    plans: (p: string) => request<Plan[]>(p, '/plans'),
    propose: (p: string, body: PlanRequest) => request<Plan>(p, '/plans', body),
    authorize: (p: string, plan: Plan) =>
      request<Plan>(p, `/plans/${encodeURIComponent(plan.id)}/authorize-data`, {
        proposal_token: plan.proposal_token,
        confirm: true,
      }),
    approve: (p: string, plan: Plan) =>
      request<Plan>(p, `/plans/${encodeURIComponent(plan.id)}/approve`, {
        proposal_token: plan.proposal_token,
        confirm: true,
      }),
    execute: (p: string, plan: Plan, request_id: string) =>
      request<Result>(p, `/plans/${encodeURIComponent(plan.id)}/execute`, {
        proposal_token: plan.proposal_token,
        request_id,
      }),
    results: (p: string) => request<Result[]>(p, '/results'),
  };
}
export const techniqueLabels: Record<string, string> = {
  descriptive_summary: 'Resumen descriptivo',
  pearson: 'Correlación de Pearson',
  spearman: 'Correlación de Spearman',
  t_welch: 't de Welch',
  t_independent: 't de Student agrupada',
  mann_whitney: 'Mann–Whitney',
  t_paired: 't pareada',
  wilcoxon: 'Wilcoxon',
  cronbach_alpha: 'Alfa de Cronbach',
};

import type { AnalysisPlanV2 } from '../../../shared/contracts/generated/v2/AnalysisPlanV2';
import type { AnalysisResultV2 } from '../../../shared/contracts/generated/v2/AnalysisResultV2';
import type { PlanRequest } from '../../../shared/contracts/generated/v2/PlanRequest';
import { SourcesError } from '../sources/api';
import type { ResultPresentationV2 } from '../../../shared/contracts/generated/v2/ResultPresentationV2';
import type { ResultFiguresV2 } from '../../../shared/contracts/generated/v2/ResultFiguresV2';
import type { ResultExplanationV2 } from '../../../shared/contracts/generated/v2/ResultExplanationV2';
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
    presentation: (p: string, id: string) =>
      request<ResultPresentationV2>(
        p,
        `/results/${encodeURIComponent(id)}/presentation`,
      ),
    figures: (p: string, id: string) =>
      request<ResultFiguresV2>(p, `/results/${encodeURIComponent(id)}/figures`),
    interpretations: (p: string, id: string) =>
      request<ResultExplanationV2[]>(
        p,
        `/results/${encodeURIComponent(id)}/interpretations`,
      ),
    interpretationHistory: (p: string, id: string, explanationId: string) =>
      request<ResultExplanationV2[]>(
        p,
        `/results/${encodeURIComponent(id)}/interpretations/${encodeURIComponent(explanationId)}/revisions`,
      ),
    review: (
      p: string,
      id: string,
      explanation: ResultExplanationV2,
      text: string,
    ) =>
      request<ResultExplanationV2>(
        p,
        `/results/${encodeURIComponent(id)}/interpretations/${encodeURIComponent(explanation.id)}/review`,
        { expected_revision: explanation.revision, text, confirm: true },
      ),
    download: async (p: string, id: string, format: 'txt' | 'docx' | 'pdf') => {
      const response = await fetch(
        `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(p)}/analysis/results/${encodeURIComponent(id)}/export?format=${format}`,
        { signal: AbortSignal.timeout(90000) },
      );
      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(
          data?.error?.message ?? 'No se pudo generar el informe vigente.',
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `resultado-${id}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
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

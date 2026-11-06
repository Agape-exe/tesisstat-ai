import type { AnalysisPlan } from '../../../shared/contracts/generated/AnalysisPlan';
import type { AnalysisResult } from '../../../shared/contracts/generated/AnalysisResult';
import type { AuthorizedScatterData } from '../../statistics/AuthorizedScatterPlot';
import type { AuthorizedResidualData } from '../../statistics/AuthorizedResidualPlot';
import type { AuthorizedGroupData } from '../../statistics/AuthorizedGroupPlot';

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

export interface RealDataAuthorizationReceipt {
  package_id: string;
  dataset_id: string;
  source_version: string;
  status: 'authorized';
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
    download: async (
      project: string,
      record: AnalysisRecord,
      format: 'docx' | 'pdf',
    ) => {
      if (!record.result)
        throw new Error('No existe un resultado para exportar.');
      const response = await fetch(
        `${baseUrl.replace(/\/$/, '')}/api/research/projects/${encodeURIComponent(project)}/analysis/plans/${encodeURIComponent(record.plan.id)}/results/${encodeURIComponent(record.result.id)}/report.${format}`,
        { signal: AbortSignal.timeout(30000) },
      );
      if (!response.ok) {
        const value = await response.json().catch(() => null);
        throw new Error(
          typeof value?.detail === 'string'
            ? value.detail
            : 'No se pudo descargar el informe.',
        );
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `analysis-${record.plan.id}.${format}`;
      document.body.append(link);
      link.click();
      link.remove();
      // Give the browser time to start the download before releasing the blob.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    plans: (project: string) => request<AnalysisRecord[]>(project, '/plans'),
    results: (project: string) =>
      request<AnalysisRecord[]>(project, '/results'),
    authorizeRealDataset: (
      project: string,
      packageId: string,
      datasetId: string,
    ) =>
      request<RealDataAuthorizationReceipt>(
        project,
        '/authorization/real-dataset',
        { package_id: packageId, dataset_id: datasetId, confirm: true },
      ),
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
    scatter: (project: string, record: AnalysisRecord) => {
      if (!record.result)
        throw new Error('No existe un resultado para visualizar.');
      return request<AuthorizedScatterData>(
        project,
        `/plans/${encodeURIComponent(record.plan.id)}/results/${encodeURIComponent(record.result.id)}/observations/scatter`,
      );
    },
    residuals: (project: string, record: AnalysisRecord) => {
      if (!record.result)
        throw new Error('No existe un resultado para visualizar.');
      return request<AuthorizedResidualData>(
        project,
        `/plans/${encodeURIComponent(record.plan.id)}/results/${encodeURIComponent(record.result.id)}/observations/residuals`,
      );
    },
    groups: (project: string, record: AnalysisRecord) => {
      if (!record.result)
        throw new Error('No existe un resultado para visualizar.');
      return request<AuthorizedGroupData>(
        project,
        `/plans/${encodeURIComponent(record.plan.id)}/results/${encodeURIComponent(record.result.id)}/observations/groups`,
      );
    },
  };
}

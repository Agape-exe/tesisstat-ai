import type { MethodologyReview } from '../methodology/api';
import type { ResearchDataset } from '../datasets/api';

export interface VariableLink {
  variable_id: string;
  columns: string[];
  role: 'independent' | 'dependent' | 'covariate' | 'descriptive' | 'unknown';
  measurement_scale: 'nominal' | 'ordinal' | 'interval' | 'ratio' | 'unknown';
}
export interface HypothesisLink {
  id: string;
  source: string;
  objective: string;
  variable_ids: string[];
  kind: 'association' | 'comparison' | 'prediction' | 'descriptive' | 'unknown';
  alternative: 'two-sided' | 'greater' | 'less' | 'unspecified';
  null_statement: string | null;
}
export interface PackageConfiguration {
  version: number;
  document_id: string | null;
  review_version: number | null;
  review_hash: string | null;
  dataset_id: string | null;
  dataset_hash: string | null;
  design: 'experimental' | 'quasi_experimental' | 'observational' | 'unknown';
  observations: 'independent' | 'paired' | 'repeated' | 'unknown';
  sampling_notes: string;
  variables: VariableLink[];
  hypotheses: HypothesisLink[];
  updated_at: string | null;
}
export interface PackageStatus {
  state: 'incomplete' | 'warnings' | 'ready' | 'generated' | 'stale';
  errors: string[];
  warnings: string[];
  configuration: PackageConfiguration;
  documents: {
    id: string;
    name: string;
    review_status: string;
    review_version: number | null;
  }[];
  dataset: ResearchDataset | null;
  review: MethodologyReview | null;
  package_id: string | null;
}
export interface ResearchPackageSummary {
  id: string;
  schema_version: '1.0.0';
  title: string;
  variables: VariableLink[];
  hypotheses: HypothesisLink[];
  dataset: { id: string; columns: string[]; synthetic: boolean };
  pending_questions: string[];
}

export function createPackageApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
) {
  const root = `${baseUrl.replace(/\/$/, '')}/api/research/projects`;
  async function request<T>(
    projectId: string,
    suffix: string,
    method = 'GET',
    body?: object,
  ): Promise<T> {
    const response = await fetch(
      `${root}/${encodeURIComponent(projectId)}/package${suffix}`,
      {
        method,
        ...(body
          ? {
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
            }
          : {}),
      },
    );
    const value = await response.json().catch(() => null);
    if (!response.ok)
      throw new Error(
        typeof value?.detail === 'string'
          ? value.detail
          : JSON.stringify(value?.detail ?? 'No se pudo procesar el paquete.'),
      );
    return value as T;
  }
  return {
    status: (projectId: string) => request<PackageStatus>(projectId, '/status'),
    save: (projectId: string, config: PackageConfiguration) =>
      request<PackageConfiguration>(projectId, '/configuration', 'PUT', config),
    validate: (projectId: string) =>
      request<PackageStatus>(projectId, '/validate', 'POST'),
    build: (projectId: string) =>
      request<ResearchPackageSummary>(projectId, '/build', 'POST'),
    get: (projectId: string) => request<ResearchPackageSummary>(projectId, ''),
  };
}

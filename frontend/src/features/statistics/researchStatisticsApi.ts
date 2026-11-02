export type RuntimeHypothesis = {
  id: string;
  statement: string;
  variable_ids: string[];
};

export type RuntimePlan = {
  id: string;
  hypothesis_id: string;
  dataset_id: string;
  status: 'needs_clarification' | 'proposed' | 'approved';
  technique: string | null;
  rationale: string;
  pending_questions: string[];
};

export type RuntimeResult = {
  status: 'completed' | 'failed' | 'not_executed';
  metrics: { name: string; value: number }[];
  warnings: string[];
  interpretation: string | null;
};

export function createResearchStatisticsApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
) {
  const root = `${baseUrl.replace(/\/$/, '')}/api/research/projects`;
  async function request<T>(
    projectId: string,
    suffix: string,
    body: object,
  ): Promise<T> {
    const response = await fetch(
      `${root}/${encodeURIComponent(projectId)}/statistics${suffix}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    );
    const value = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(
        typeof value?.detail === 'string'
          ? value.detail
          : 'No se pudo ejecutar Statistics.',
      );
    }
    return value as T;
  }
  return {
    plan: (projectId: string, packageId: string, hypothesisId: string) =>
      request<RuntimePlan>(projectId, '/plan', {
        package_id: packageId,
        hypothesis_id: hypothesisId,
      }),
    execute: (projectId: string, packageId: string, hypothesisId: string) =>
      request<RuntimeResult>(projectId, '/analysis', {
        package_id: packageId,
        hypothesis_id: hypothesisId,
        approve: true,
      }),
  };
}

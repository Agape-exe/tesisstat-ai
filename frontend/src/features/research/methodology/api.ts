export interface Finding {
  value: string | null;
  kind: 'unknown' | 'quotation' | 'inference';
  evidence: string[];
}

export interface MethodologyContent {
  title: Finding;
  general_problem: Finding;
  general_objective: Finding;
  specific_objectives: Finding[];
  general_hypothesis: Finding;
  specific_hypotheses: Finding[];
  variables: {
    name: Finding;
    role: Finding;
    measurement_scale: Finding;
    dimensions: Finding[];
    indicators: Finding[];
    instrument_items: Finding[];
  }[];
  research_design: Finding;
  observation_design: Finding;
  additional_methodology: Finding[];
  warnings: string[];
  questions: string[];
}

export interface MethodologyDraft {
  project_id: string;
  document_id: string;
  review_status: 'unreviewed';
  content: MethodologyContent;
  pending_fields: string[];
  evidence: {
    field: string;
    document_id: string;
    quote: string;
    start: number;
    end: number;
  }[];
  warnings: string[];
  model: string;
  source_hash: string;
  schema_version: '1';
  created_at: string;
}

export interface MethodologyState {
  project_id: string;
  document_id: string;
  status: 'not_started' | 'processing' | 'completed' | 'failed';
  provider_configured: boolean;
  attempts: number;
  error_code: string | null;
  message: string | null;
  retry_after: string | null;
  draft: MethodologyDraft | null;
}

export interface ReviewFinding {
  value: string | null;
  kind: Finding['kind'] | 'manual';
  evidence: string[];
}

export interface ReviewVariable {
  id: string;
  name: ReviewFinding;
  role: ReviewFinding;
  measurement_scale: ReviewFinding;
  dimensions: ReviewFinding[];
  indicators: ReviewFinding[];
  instrument_items: ReviewFinding[];
}

export interface ReviewContent {
  title: ReviewFinding;
  general_problem: ReviewFinding;
  general_objective: ReviewFinding;
  specific_objectives: ReviewFinding[];
  general_hypothesis: ReviewFinding;
  specific_hypotheses: ReviewFinding[];
  variables: ReviewVariable[];
  research_design: ReviewFinding;
  observation_design: ReviewFinding;
  additional_methodology: ReviewFinding[];
  clarifications: ReviewFinding[];
}

export interface MethodologyReview {
  project_id: string;
  document_id: string;
  origin: 'ai' | 'manual';
  content: ReviewContent;
  pending_fields: string[];
  review_status: 'unreviewed' | 'reviewed';
  version: number;
  updated_at: string;
  reviewed_at: string | null;
}

export interface MethodologyApi {
  status(
    project: string,
    document: string,
    signal?: AbortSignal,
  ): Promise<MethodologyState>;
  analyze(
    project: string,
    document: string,
    signal?: AbortSignal,
  ): Promise<MethodologyState>;
  reviewStatus?(
    project: string,
    document: string,
    signal?: AbortSignal,
  ): Promise<MethodologyReview | null>;
  createReview?(project: string, document: string): Promise<MethodologyReview>;
  saveReview?(
    project: string,
    document: string,
    version: number,
    content: ReviewContent,
  ): Promise<MethodologyReview>;
  confirmReview?(
    project: string,
    document: string,
    version: number,
  ): Promise<MethodologyReview>;
}

export function createMethodologyApi(
  baseUrl = import.meta.env.VITE_RESEARCH_API_BASE_URL ??
    'http://127.0.0.1:8001',
): MethodologyApi {
  async function request(
    project: string,
    document: string,
    analyze: boolean,
    signal?: AbortSignal,
  ) {
    const url = `${baseUrl.replace(/\/$/, '')}/api/research/projects/${encodeURIComponent(project)}/documents/${encodeURIComponent(document)}/methodology`;
    let response: Response;
    try {
      response = await fetch(`${url}/${analyze ? 'extract' : 'status'}`, {
        method: analyze ? 'POST' : 'GET',
        ...(analyze
          ? {
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ send_to_external_ai: true }),
            }
          : {}),
        signal: signal
          ? AbortSignal.any([signal, AbortSignal.timeout(150000)])
          : AbortSignal.timeout(150000),
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new Error(
        'No se pudo contactar con Research. Consulta el estado antes de reintentar.',
        { cause: error },
      );
    }
    const body = await response.json().catch(() => null);
    if (!response.ok)
      throw new Error(
        typeof body?.detail === 'string'
          ? body.detail
          : 'No se pudo consultar la metodología.',
      );
    return body as MethodologyState;
  }
  async function reviewRequest(
    project: string,
    document: string,
    suffix: string,
    method = 'GET',
    body?: object,
    signal?: AbortSignal,
  ) {
    const url = `${baseUrl.replace(/\/$/, '')}/api/research/projects/${encodeURIComponent(project)}/documents/${encodeURIComponent(document)}/methodology/review${suffix}`;
    const response = await fetch(url, {
      method,
      ...(body
        ? {
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          }
        : {}),
      signal,
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = result?.detail;
      throw new Error(
        typeof detail === 'string'
          ? `${detail}${
              result?.errors
                ? ` ${Object.entries(result.errors)
                    .map(([field, message]) => `${field}: ${message}`)
                    .join(' ')}`
                : ''
            }`
          : JSON.stringify(
              detail ?? result?.errors ?? 'Revisa los campos de metodología.',
            ),
      );
    }
    return result as MethodologyReview | null;
  }
  return {
    status: (project, document, signal) =>
      request(project, document, false, signal),
    analyze: (project, document, signal) =>
      request(project, document, true, signal),
    reviewStatus: (project, document, signal) =>
      reviewRequest(project, document, '/status', 'GET', undefined, signal),
    createReview: (project, document) =>
      reviewRequest(
        project,
        document,
        '',
        'POST',
      ) as Promise<MethodologyReview>,
    saveReview: (project, document, version, content) =>
      reviewRequest(project, document, '', 'PUT', {
        version,
        content,
      }) as Promise<MethodologyReview>,
    confirmReview: (project, document, version) =>
      reviewRequest(project, document, '/confirm', 'POST', {
        version,
      }) as Promise<MethodologyReview>,
  };
}

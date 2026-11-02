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
  return {
    status: (project, document, signal) =>
      request(project, document, false, signal),
    analyze: (project, document, signal) =>
      request(project, document, true, signal),
  };
}

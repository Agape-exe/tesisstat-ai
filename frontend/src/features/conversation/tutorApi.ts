import type {
  TutorContextV2,
  TutorActionV2,
} from '../../shared/contracts/generated/v2/TutorContextV2';
import type { TutorSelectionV2 } from '../../shared/contracts/generated/v2/TutorSelectionV2';
import type { MessageDraftV2 } from '../../shared/contracts/generated/v2/MessageDraftV2';
import type { Message } from './api';
import type { GuidedDescriptiveRequestV2 } from '../../shared/contracts/generated/v2/GuidedDescriptiveRequestV2';
export type Selection = TutorSelectionV2;
export type Action = TutorActionV2;
export class TutorApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export type TutorTrace = {
  snapshot: string;
  stage: string;
  sources: {
    kind: string;
    id: string;
    revision?: number;
    hash?: string;
    version?: string;
    status?: string;
  }[];
  historical_refs: {
    kind: string;
    id: string;
    revision: number;
    hash: string;
  }[];
  evidence_refs?: {
    key: string;
    kind: 'detected' | 'confirmed' | 'calculated';
    text: string;
    source_ref: { kind: string; id: string; revision: number; hash: string };
  }[];
  metric_refs: { result_id: string; key: string }[];
  actions: Action[];
  suggestion_id?: string;
  error?: string;
  prose_source?:
    | 'template'
    | 'ai_draft'
    | 'ai_concepts'
    | 'ai_guidance'
    | 'ai_grounded_draft';
  context_changed_during_response?: boolean;
};
export type TutorMessage = Omit<Message, 'context'> & {
  context?: TutorTrace | null;
};
type Choice = { id: string; label: string; validity?: string };
export interface TutorStatus {
  guidance?: {
    table_count: number;
    selected_table: {
      id: string;
      name: string;
      rows: number;
      columns: number;
      identical_rows?: number;
      recommended_normality_test?: string;
    } | null;
    variables: {
      variable_id: string;
      name: string;
      detected_type: string;
      missing: number;
      formula_errors: number;
      possible_identifier: boolean;
      scale_confirmed: boolean;
      suggested_scale: 'nominal' | 'ordinal' | 'interval' | 'ratio';
      constant?: boolean;
      selected: boolean;
    }[];
    warnings?: string[];
  };
  provider_kind?: 'cloudflare_workers_ai' | 'controlled_test';
  provider_configured: boolean;
  consent: {
    revision: number;
    granted: boolean;
    consent_scope: 'tutor_context_v5';
    renewal_required?: boolean;
  };
  context: Required<TutorContextV2>;
  static_help: string;
  privacy: string;
  max_message_characters: number;
  choices: {
    datasets: Choice[];
    intents: Choice[];
    plans: Choice[];
    results: Choice[];
  };
}
export function createTutorApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    project: string,
    path: string,
    method = 'GET',
    body?: object,
    signal?: AbortSignal,
  ): Promise<T> {
    const response = await fetch(
      `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(project)}/conversations${path}`,
      {
        method,
        signal: signal
          ? AbortSignal.any([signal, AbortSignal.timeout(135000)])
          : AbortSignal.timeout(135000),
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      },
    );
    const data = await response.json().catch(() => null);
    if (!response.ok)
      throw new TutorApiError(
        data?.error?.message ??
          data?.detail ??
          'No se pudo completar la operación del tutor.',
        response.status,
      );
    return data;
  }
  return {
    prepareDescriptive: (p: string, body: GuidedDescriptiveRequestV2) =>
      request<{ intent_id: string; dataset_id: string; replayed: boolean }>(
        p,
        '/actions',
        'POST',
        body,
      ),
    status: async (p: string, selection: Selection, signal?: AbortSignal) => {
      const query = new URLSearchParams(
        Object.entries(selection).filter(([, v]) => v != null) as [
          string,
          string,
        ][],
      );
      const data = await request<TutorStatus>(
        p,
        `/status?${query}`,
        'GET',
        undefined,
        signal,
      );
      if (
        !data?.context?.context_fingerprint ||
        !data?.consent ||
        !data?.choices ||
        !Array.isArray(data.context.allowed_actions)
      )
        throw new Error(
          'No se pudo verificar el contexto del tutor. El historial y los formularios siguen disponibles.',
        );
      return data;
    },
    consent: (p: string, revision: number, granted: boolean) =>
      request<TutorStatus['consent']>(p, '/consent', 'PUT', {
        expected_revision: revision,
        granted,
        consent_scope: 'tutor_context_v5',
      }),
    send: (p: string, cid: string, body: MessageDraftV2) =>
      request<{ messages: TutorMessage[] }>(
        p,
        `/${encodeURIComponent(cid)}/messages`,
        'POST',
        body,
      ),
    executeAnalysis: async (
      p: string,
      body: {
        proposal_type: string;
        technique?: string;
        variable_names?: string[];
        dataset_id?: string;
      },
    ) => {
      const response = await fetch(
        `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(p)}/executions`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: AbortSignal.timeout(90000),
        },
      );
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new TutorApiError(
          err?.detail ??
            err?.error?.message ??
            'No se pudo ejecutar el análisis determinista.',
          response.status,
        );
      }
      return response.json();
    },
    downloadReport: async (
      p: string,
      resultId: string,
      format: 'txt' | 'docx' | 'pdf',
    ) => {
      const response = await fetch(
        `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(p)}/analysis/results/${encodeURIComponent(resultId)}/export?format=${format}`,
        { signal: AbortSignal.timeout(90000) },
      );
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw new Error(
          err?.error?.message ??
            err?.detail ??
            'No se pudo generar el informe para descarga.',
        );
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `reporte-academico-${resultId}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
  };
}

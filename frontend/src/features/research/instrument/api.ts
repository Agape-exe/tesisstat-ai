import type { InstrumentContextV2 } from '../../../shared/contracts/generated/v2/InstrumentContextV2';
import type { InstrumentMappingV2 } from '../../../shared/contracts/generated/v2/InstrumentMappingV2';
import type { InstrumentEdit } from '../../../shared/contracts/generated/v2/InstrumentEdit';
import type { MappingEdit } from '../../../shared/contracts/generated/v2/MappingEdit';
import type { ScorePreviewRequest } from '../../../shared/contracts/generated/v2/ScorePreviewRequest';
import type { ScorePreviewV2 } from '../../../shared/contracts/generated/v2/ScorePreviewV2';
import type { ScoreRecordV2 } from '../../../shared/contracts/generated/v2/ScoreRecordV2';
import { SourcesError } from '../sources/api';

export type Instrument = Required<InstrumentContextV2>;
export type Mapping = Required<InstrumentMappingV2>;
type CanonicalStructure = Required<InstrumentEdit['structure']>;
// A local editor can temporarily contain incomplete collections. The canonical
// request is validated when saving; generated contract types remain unmodified.
export type Structure = {
  variables: CanonicalStructure['variables'][number][];
  dimensions: CanonicalStructure['dimensions'][number][];
  indicators: CanonicalStructure['indicators'][number][];
  items: CanonicalStructure['items'][number][];
  scoring_rules: (Omit<
    CanonicalStructure['scoring_rules'][number],
    'item_ids'
  > & { item_ids: string[] })[];
};
export type ScorePreview = Required<ScorePreviewV2>;
export type Score = Required<ScoreRecordV2>;
export type Edit = InstrumentEdit;

export function createInstrumentApi(
  base = import.meta.env.VITE_RESEARCH_API_BASE_URL ?? 'http://127.0.0.1:8001',
) {
  async function request<T>(
    p: string,
    path: string,
    body?: object,
    method = 'POST',
  ): Promise<T> {
    const response = await fetch(
      `${base.replace(/\/$/, '')}/api/v2/research/projects/${encodeURIComponent(p)}/instruments${path}`,
      {
        method: body ? method : 'GET',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(90000),
      },
    );
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new SourcesError(
        data?.error?.message ??
          'Revisa la estructura, opciones y referencias del instrumento.',
        response.status,
        data?.error?.current_revision ?? null,
      );
    }
    return response.json();
  }
  const path = (id: string) => `/${encodeURIComponent(id)}`;
  return {
    list: (p: string) => request<Instrument[]>(p, ''),
    get: (p: string, id: string) => request<Instrument>(p, path(id)),
    save: (
      p: string,
      id: string | null,
      body: Omit<InstrumentEdit, 'structure'> & { structure: Structure },
    ) =>
      request<Instrument>(p, id ? path(id) : '', body, id ? 'PATCH' : 'POST'),
    confirm: (p: string, i: Instrument) =>
      request<Instrument>(p, `${path(i.instrument_id)}/confirm`, {
        expected_revision: i.revision,
        confirm: true,
      }),
    history: (p: string, id: string) =>
      request<Instrument[]>(p, `${path(id)}/revisions`),
    mapping: (p: string, id: string) =>
      request<Mapping>(p, `${path(id)}/mapping`),
    map: (p: string, id: string, body: MappingEdit) =>
      request<Mapping>(p, `${path(id)}/mapping`, body, 'PUT'),
    preview: (p: string, id: string, body: ScorePreviewRequest) =>
      request<ScorePreview>(p, `${path(id)}/score-previews`, body),
    scores: (p: string, id: string) =>
      request<Score[]>(p, `${path(id)}/scores`),
    score: (p: string, id: string, preview: ScorePreview, requestId: string) =>
      request<Score>(p, `${path(id)}/scores`, {
        preview_id: preview.id,
        fingerprint: preview.fingerprint,
        confirm: true,
        request_id: requestId,
      }),
  };
}

export function fromInstrument(i: Instrument): Structure {
  return {
    variables: i.variables,
    dimensions: i.dimensions,
    indicators: i.indicators,
    items: i.items,
    scoring_rules: i.scoring_rules,
  };
}
export function blank(): Structure {
  const v = crypto.randomUUID(),
    d = crypto.randomUUID(),
    indicator = crypto.randomUUID();
  return {
    variables: [
      { variable_id: v, name: '', scale: 'unknown', context_variable_id: null },
    ],
    dimensions: [{ dimension_id: d, variable_id: v, name: '' }],
    indicators: [{ indicator_id: indicator, dimension_id: d, name: '' }],
    items: [],
    scoring_rules: [],
  };
}

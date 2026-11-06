import { useEffect, useRef, useState } from 'react';
import { createMethodologyApi } from './api';
import type { Finding, MethodologyApi, MethodologyState } from './api';
import type { MethodologyReview } from './api';
import { ReviewEditor } from './ReviewEditor';

const defaultApi = createMethodologyApi();
const labels: Record<string, string> = {
  title: 'Título',
  general_problem: 'Problema general',
  general_objective: 'Objetivo general',
  specific_objectives: 'Objetivos específicos',
  general_hypothesis: 'Hipótesis general',
  specific_hypotheses: 'Hipótesis específicas',
  variables: 'Variables',
  name: 'Nombre',
  role: 'Rol',
  measurement_scale: 'Escala de medición',
  dimensions: 'Dimensiones',
  indicators: 'Indicadores',
  instrument_items: 'Preguntas o ítems',
  research_design: 'Diseño de investigación',
  observation_design: 'Tipo de observaciones o comparación',
  additional_methodology: 'Metodología adicional',
};
function fieldLabel(path: string) {
  return path
    .split('.')
    .map((part) => labels[part] ?? part)
    .join(' · ');
}

function FindingView({ label, finding }: { label: string; finding: Finding }) {
  return (
    <div className="rp-methodology-finding">
      <strong>{label}: </strong>
      {finding.value ?? 'No identificado'}
      {finding.kind !== 'unknown' && (
        <small>
          {finding.kind === 'inference'
            ? 'Inferencia pendiente de revisión'
            : 'Cita textual'}
        </small>
      )}
      {finding.evidence.map((quote, i) => (
        <blockquote key={i}>{quote}</blockquote>
      ))}
    </div>
  );
}

function FindingsView({ label, items }: { label: string; items: Finding[] }) {
  return (
    <div>
      <h5>{label}</h5>
      {items.length ? (
        items.map((finding, i) => (
          <FindingView key={i} label={`${i + 1}`} finding={finding} />
        ))
      ) : (
        <p>No identificado</p>
      )}
    </div>
  );
}

export function DocumentMethodology({
  projectId,
  documentId,
  hasText,
  api = defaultApi,
  reviewMode = 'inline',
}: {
  projectId: string;
  documentId: string;
  hasText: boolean;
  api?: MethodologyApi;
  reviewMode?: 'inline' | 'external';
}) {
  const [state, setState] = useState<MethodologyState | null>(null);
  const [review, setReview] = useState<MethodologyReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [consent, setConsent] = useState(false);
  const [now, setNow] = useState(Date.now);
  const inFlight = useRef(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const read = new AbortController();
    api
      .status(projectId, documentId, read.signal)
      .then((result) => {
        if (!read.signal.aborted) {
          setState(result);
          setLoading(false);
        }
      })
      .catch((caught) => {
        if (!read.signal.aborted) {
          setError(
            caught instanceof Error
              ? caught.message
              : 'No se pudo consultar el estado.',
          );
          setLoading(false);
        }
      });
    return () => {
      read.abort();
      controller.current?.abort();
    };
  }, [api, projectId, documentId]);

  useEffect(() => {
    if (!api.reviewStatus) return;
    const read = new AbortController();
    api
      .reviewStatus(projectId, documentId, read.signal)
      .then((result) => {
        if (!read.signal.aborted) setReview(result);
      })
      .catch((caught) => {
        if (!read.signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : 'No se pudo consultar la revisión.',
          );
      });
    return () => read.abort();
  }, [api, projectId, documentId]);

  async function createReview() {
    if (!api.createReview) return;
    setBusy(true);
    setError('');
    try {
      setReview(await api.createReview(projectId, documentId));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo crear la metodología.',
      );
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!state?.retry_after) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [state?.retry_after]);

  async function act(analyze: boolean) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    const request = new AbortController();
    controller.current = request;
    try {
      const result = await (analyze ? api.analyze : api.status)(
        projectId,
        documentId,
        request.signal,
      );
      if (!request.signal.aborted) {
        setState(result);
        setNow(Date.now());
      }
    } catch (caught) {
      if (!request.signal.aborted)
        setError(
          caught instanceof Error
            ? caught.message
            : 'No se pudo analizar la metodología.',
        );
    } finally {
      inFlight.current = false;
      if (!request.signal.aborted) setBusy(false);
    }
  }

  const draft = state?.draft;
  const waiting = !!state?.retry_after && Date.parse(state.retry_after) > now;
  return (
    <section
      className="rp-methodology"
      aria-label="Metodología con IA"
      aria-busy={loading || busy}
    >
      <h4>Metodología con IA</h4>
      {loading ? (
        <p role="status">Consultando metodología…</p>
      ) : (
        <>
          <p>
            Al analizar se enviarán fragmentos del texto a Cloudflare Workers
            AI, un proveedor externo. Usa solo documentos ficticios en esta
            demo.
          </p>
          {state && !state.provider_configured && (
            <p role="status">
              La extracción con IA no está configurada. Configura Cloudflare en
              el backend.
            </p>
          )}
          {!hasText && <p>Primero extrae texto legible del documento.</p>}
          {!draft && (
            <>
              <label>
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                  disabled={busy}
                />{' '}
                Autorizo enviar fragmentos del documento a Cloudflare para este
                análisis.
              </label>
              <button
                disabled={
                  busy ||
                  !hasText ||
                  !consent ||
                  !state?.provider_configured ||
                  waiting
                }
                onClick={() => void act(true)}
              >
                {busy
                  ? 'Procesando metodología…'
                  : state?.status === 'failed'
                    ? 'Reintentar análisis con IA'
                    : 'Analizar metodología con IA'}
              </button>
            </>
          )}
          <button
            className="rp-secondary"
            disabled={busy}
            onClick={() => void act(false)}
          >
            Consultar estado de IA
          </button>
          {state?.status === 'processing' && (
            <p role="status">
              Análisis en curso. Consulta el estado para recuperar el resultado.
            </p>
          )}
          {state?.message && (
            <p role={state.status === 'failed' ? 'alert' : 'status'}>
              {state.message}
            </p>
          )}
          {waiting && (
            <p>
              Espera hasta{' '}
              {new Date(state!.retry_after!).toLocaleTimeString('es-PE')} antes
              de reintentar.
            </p>
          )}
          {draft && (
            <>
              <p role="status">Borrador original de IA · {draft.model}</p>
              {(
                [
                  'title',
                  'general_problem',
                  'general_objective',
                  'general_hypothesis',
                  'research_design',
                  'observation_design',
                ] as const
              ).map((key) => (
                <FindingView
                  key={key}
                  label={labels[key]}
                  finding={draft.content[key]}
                />
              ))}
              {(
                [
                  'specific_objectives',
                  'specific_hypotheses',
                  'additional_methodology',
                ] as const
              ).map((key) => (
                <FindingsView
                  key={key}
                  label={labels[key]}
                  items={draft.content[key]}
                />
              ))}
              <h5>Variables</h5>
              {draft.content.variables.length === 0 && <p>No identificado</p>}
              {draft.content.variables.map((variable, i) => (
                <div key={i}>
                  {(['name', 'role', 'measurement_scale'] as const).map(
                    (key) => (
                      <FindingView
                        key={key}
                        label={labels[key]}
                        finding={variable[key]}
                      />
                    ),
                  )}
                  {(
                    ['dimensions', 'indicators', 'instrument_items'] as const
                  ).map((key) => (
                    <FindingsView
                      key={key}
                      label={labels[key]}
                      items={variable[key]}
                    />
                  ))}
                </div>
              ))}
              <h5>Información pendiente</h5>
              <ul>
                {draft.pending_fields.map((field) => (
                  <li key={field}>{fieldLabel(field)}</li>
                ))}
              </ul>
              <h5>Advertencias</h5>
              <ul>
                {[...draft.warnings, ...draft.content.warnings].map(
                  (warning, i) => (
                    <li key={i}>{warning}</li>
                  ),
                )}
              </ul>
              <h5>Preguntas pendientes</h5>
              {draft.content.questions.length ? (
                <ul>
                  {draft.content.questions.map((question, i) => (
                    <li key={i}>{question}</li>
                  ))}
                </ul>
              ) : (
                <p>Sin preguntas propuestas por la IA.</p>
              )}
              <details>
                <summary>Referencias verificadas al texto original</summary>
                {draft.evidence.map((item, i) => (
                  <p key={i}>
                    {fieldLabel(item.field)} · Documento {item.document_id} ·
                    Caracteres {item.start}–{item.end}: «{item.quote}»
                  </p>
                ))}
              </details>
            </>
          )}
          {reviewMode === 'inline' && !review && api.createReview && (
            <button
              type="button"
              disabled={busy || state?.status === 'processing'}
              onClick={() => void createReview()}
            >
              {draft
                ? 'Revisar metodología de IA'
                : 'Crear metodología manualmente'}
            </button>
          )}
          {reviewMode === 'inline' && review && (
            <ReviewEditor
              review={review}
              api={api}
              projectId={projectId}
              documentId={documentId}
              onChange={setReview}
            />
          )}
        </>
      )}
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
    </section>
  );
}

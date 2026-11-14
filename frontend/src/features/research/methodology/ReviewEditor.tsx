import { useEffect, useState } from 'react';
import type {
  MethodologyApi,
  MethodologyReview,
  ReviewContent,
  ReviewFinding,
  ReviewVariable,
} from './api';

const names: Record<string, string> = {
  title: 'Título',
  general_problem: 'Problema general',
  general_objective: 'Objetivo general',
  specific_objectives: 'Objetivos específicos',
  general_hypothesis: 'Hipótesis general',
  specific_hypotheses: 'Hipótesis específicas',
  research_design: 'Diseño de investigación',
  observation_design: 'Tipo de observaciones o comparación',
  additional_methodology: 'Metodología adicional',
  clarifications: 'Aclaraciones necesarias',
  variables: 'Variables',
  dimensions: 'Dimensiones',
  indicators: 'Indicadores',
  instrument_items: 'Preguntas o ítems del instrumento',
  name: 'Nombre',
  role: 'Rol',
  measurement_scale: 'Escala de medición',
};
const single = [
  'title',
  'general_problem',
  'general_objective',
  'general_hypothesis',
  'research_design',
  'observation_design',
] as const;
const lists = [
  'specific_objectives',
  'specific_hypotheses',
  'additional_methodology',
  'clarifications',
] as const;
const variableLists = ['dimensions', 'indicators', 'instrument_items'] as const;
const empty = (): ReviewFinding => ({
  value: null,
  kind: 'unknown',
  evidence: [],
});
const manual = (value: string): ReviewFinding =>
  value.trim() ? { value, kind: 'manual', evidence: [] } : empty();
const clone = (content: ReviewContent) => structuredClone(content);
const pathLabel = (path: string) =>
  path
    .split('.')
    .map(
      (part) =>
        names[part] ??
        (Number.isNaN(Number(part)) ? part : String(Number(part) + 1)),
    )
    .join(' · ');

export function ReviewEditor({
  review,
  api,
  projectId,
  documentId,
  onChange,
  initialEditing = false,
}: {
  review: MethodologyReview;
  api: MethodologyApi;
  projectId: string;
  documentId: string;
  onChange: (review: MethodologyReview) => void;
  initialEditing?: boolean;
}) {
  const [content, setContent] = useState(() => clone(review.content));
  const [editing, setEditing] = useState(initialEditing);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const dirty = JSON.stringify(content) !== JSON.stringify(review.content);

  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty]);

  function change(mutator: (next: ReviewContent) => void) {
    setContent((current) => {
      const next = clone(current);
      mutator(next);
      return next;
    });
    setError('');
  }
  function scalar(key: (typeof single)[number]) {
    const item = content[key];
    return (
      <label key={key}>
        {names[key]}
        <textarea
          maxLength={2000}
          value={item.value ?? ''}
          onChange={(event) =>
            change((next) => {
              next[key] = manual(event.target.value);
            })
          }
        />
        <small>
          {item.kind === 'manual'
            ? 'Editado manualmente'
            : item.kind === 'unknown'
              ? 'Desconocido'
              : 'Valor inicial de IA; al editar se registra como manual'}
        </small>
      </label>
    );
  }
  function itemList(
    label: string,
    items: ReviewFinding[],
    set: (next: ReviewFinding[]) => void,
  ) {
    return (
      <fieldset key={label}>
        <legend>{label}</legend>
        {items.map((item, index) => (
          <div className="rp-review-row" key={index}>
            <label>
              {label} {index + 1}
              <input
                maxLength={2000}
                value={item.value ?? ''}
                onChange={(event) => {
                  const next = [...items];
                  next[index] = manual(event.target.value);
                  set(next);
                }}
              />
            </label>
            <small>
              {item.kind === 'manual'
                ? 'Manual'
                : item.kind === 'unknown'
                  ? 'Desconocido'
                  : 'IA'}
            </small>
            <button
              type="button"
              className="rp-secondary"
              onClick={() => set(items.filter((_, i) => i !== index))}
            >
              Eliminar
            </button>
          </div>
        ))}
        <button
          type="button"
          className="rp-secondary"
          onClick={() => set([...items, empty()])}
        >
          Agregar
        </button>
      </fieldset>
    );
  }
  function variable(index: number, item: ReviewVariable) {
    return (
      <fieldset key={item.id}>
        <legend>Variable {index + 1}</legend>
        <label>
          Nombre
          <input
            maxLength={2000}
            value={item.name.value ?? ''}
            onChange={(event) =>
              change((next) => {
                next.variables[index].name = manual(event.target.value);
              })
            }
          />
        </label>
        {(['role', 'measurement_scale'] as const).map((key) => (
          <label key={key}>
            {names[key]}
            <select
              value={item[key].value ?? 'unknown'}
              onChange={(event) =>
                change((next) => {
                  next.variables[index][key] = manual(event.target.value);
                })
              }
            >
              {(key === 'role'
                ? [
                    'unknown',
                    'independent',
                    'dependent',
                    'covariate',
                    'descriptive',
                  ]
                : ['unknown', 'nominal', 'ordinal', 'interval', 'ratio']
              ).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        ))}
        {variableLists.map((key) =>
          itemList(names[key], item[key], (values) =>
            change((next) => {
              next.variables[index][key] = values;
            }),
          ),
        )}
        <button
          type="button"
          className="rp-secondary"
          onClick={() =>
            change((next) => {
              next.variables.splice(index, 1);
            })
          }
        >
          Eliminar variable
        </button>
      </fieldset>
    );
  }
  async function save() {
    if (!api.saveReview) return;
    setBusy(true);
    setError('');
    try {
      const saved = await api.saveReview(
        projectId,
        documentId,
        review.version,
        content,
      );
      onChange(saved);
      setContent(clone(saved.content));
      setEditing(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar.');
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!api.confirmReview) return;
    setBusy(true);
    setError('');
    try {
      onChange(await api.confirmReview(projectId, documentId, review.version));
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'No se pudo confirmar.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="rp-review" aria-label="Revisión metodológica">
      <p role="status">
        {review.review_status === 'reviewed'
          ? 'Revisado por una persona'
          : 'Pendiente de revisión'}{' '}
        · Origen: {review.origin === 'ai' ? 'IA' : 'manual'} · Versión{' '}
        {review.version}
      </p>
      {review.reviewed_at && (
        <p>
          Confirmado: {new Date(review.reviewed_at).toLocaleString('es-PE')}
        </p>
      )}
      {!editing ? (
        <>
          <button type="button" onClick={() => setEditing(true)}>
            Editar metodología
          </button>
          <button
            type="button"
            className="rp-secondary"
            disabled={busy || review.review_status === 'reviewed'}
            onClick={() => void confirm()}
          >
            Confirmar revisión
          </button>
          <h5>Contenido editable guardado</h5>
          {single.map((key) => (
            <p key={key}>
              <strong>{names[key]}:</strong>{' '}
              {review.content[key].value ?? 'Desconocido'}{' '}
              <small>({review.content[key].kind})</small>
            </p>
          ))}
          {lists.map((key) => (
            <div key={key}>
              <h5>{names[key]}</h5>
              {review.content[key].length ? (
                <ol>
                  {review.content[key].map((item, index) => (
                    <li key={index}>
                      {item.value ?? 'Desconocido'} <small>({item.kind})</small>
                    </li>
                  ))}
                </ol>
              ) : (
                <p>Sin datos</p>
              )}
            </div>
          ))}
          <h5>Variables</h5>
          {review.content.variables.map((item) => (
            <div key={item.id}>
              <strong>{item.name.value ?? 'Sin nombre'}</strong>{' '}
              <small>({item.name.kind})</small>
              <p>
                Rol: {item.role.value ?? 'Desconocido'} · Escala:{' '}
                {item.measurement_scale.value ?? 'Desconocida'}
              </p>
              {variableLists.map((key) => (
                <div key={key}>
                  <strong>{names[key]}</strong>
                  <ul>
                    {item[key].map((value, index) => (
                      <li key={index}>
                        {value.value ?? 'Desconocido'}{' '}
                        <small>({value.kind})</small>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </>
      ) : (
        <>
          {dirty && <p role="status">Hay cambios sin guardar.</p>}
          <h5>Información general</h5>
          {single.slice(0, 4).map(scalar)}
          {lists.slice(0, 2).map((key) =>
            itemList(names[key], content[key], (values) =>
              change((next) => {
                next[key] = values;
              }),
            ),
          )}
          <h5>Variables</h5>
          {content.variables.map((item, index) => variable(index, item))}
          <button
            type="button"
            className="rp-secondary"
            onClick={() =>
              change((next) => {
                next.variables.push({
                  id: crypto.randomUUID(),
                  name: empty(),
                  role: empty(),
                  measurement_scale: empty(),
                  dimensions: [],
                  indicators: [],
                  instrument_items: [],
                });
              })
            }
          >
            Agregar variable
          </button>
          <h5>Información metodológica</h5>
          {single.slice(4).map(scalar)}
          {lists.slice(2).map((key) =>
            itemList(names[key], content[key], (values) =>
              change((next) => {
                next[key] = values;
              }),
            ),
          )}
          <div className="rp-review-actions">
            <button
              type="button"
              disabled={busy || !dirty}
              onClick={() => void save()}
            >
              Guardar borrador
            </button>
            <button
              type="button"
              className="rp-secondary"
              disabled={busy}
              onClick={() => {
                if (
                  dirty &&
                  !window.confirm('¿Descartar los cambios sin guardar?')
                )
                  return;
                setContent(clone(review.content));
                setEditing(false);
                setError('');
              }}
            >
              Cancelar
            </button>
          </div>
        </>
      )}
      <h5>Campos pendientes</h5>
      {review.pending_fields.length ? (
        <ul>
          {review.pending_fields.map((field) => (
            <li key={field}>{pathLabel(field)}</li>
          ))}
        </ul>
      ) : (
        <p>Sin campos pendientes.</p>
      )}
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
    </section>
  );
}

import { useState } from 'react';
import {
  createContextApi,
  ContextApiError,
  type Context,
  type ImportProposal,
  type Suggestion,
} from './api';
import { textFields } from './draft';
import { navigateProject } from '../projects/navigation';

const api = createContextApi();
const labels: Record<string, string> = {
  ...textFields,
  design: 'Diseño',
  observations: 'Relación entre observaciones',
  specific_objectives: 'Objetivo específico',
  hypotheses: 'Hipótesis',
  complementary_notes: 'Nota complementaria',
};
const designs = {
  unknown: 'No consta',
  observational: 'Observacional',
  experimental: 'Experimental',
  quasi_experimental: 'Cuasiexperimental',
};
const observations = {
  unknown: 'No consta',
  independent: 'Independientes',
  paired: 'Pareadas',
  repeated: 'Repetidas',
};
type Entry = {
  key: string;
  field: string;
  value: string;
  current: string;
  duplicate: boolean;
};
const states = {
  pending: 'Pendiente de revisión',
  applied: 'Aplicada',
  rejected: 'Cancelada',
  stale: 'Desactualizada',
};

function importEntries(
  proposal: ImportProposal,
  current: Context,
  original: ImportProposal = proposal,
): Entry[] {
  const entries: Entry[] = [];
  for (const field of [
    ...Object.keys(textFields),
    'design',
    'observations',
  ] as (keyof typeof textFields | 'design' | 'observations')[]) {
    const value = proposal[field];
    if (original[field] && original[field] !== 'unknown')
      entries.push({
        key: field,
        field,
        value: value ?? '',
        current: current[field].value ?? '',
        duplicate: false,
      });
  }
  for (const item of proposal.specific_objectives)
    entries.push({
      key: `specific_objectives/${item.ref}`,
      field: 'specific_objectives',
      value: item.text,
      current: current.specific_objectives.map((o) => o.text.value).join('\n'),
      duplicate: current.specific_objectives.some(
        (o) =>
          o.text.value?.toLocaleLowerCase() === item.text.toLocaleLowerCase(),
      ),
    });
  for (const item of proposal.hypotheses)
    entries.push({
      key: `hypotheses/${item.ref}`,
      field: 'hypotheses',
      value: item.statement,
      current: current.hypotheses.map((h) => h.statement.value).join('\n'),
      duplicate: current.hypotheses.some(
        (h) =>
          h.statement.value?.toLocaleLowerCase() ===
          item.statement.toLocaleLowerCase(),
      ),
    });
  for (const [i, note] of proposal.complementary_notes.entries())
    entries.push({
      key: `complementary_notes/${i}`,
      field: 'complementary_notes',
      value: note,
      current: current.complementary_notes.map((n) => n.value).join('\n'),
      duplicate: current.complementary_notes.some(
        (n) => n.value?.toLocaleLowerCase() === note.toLocaleLowerCase(),
      ),
    });
  return entries;
}

export function AssistedContext({
  projectId,
  current,
  title,
  disabled,
  onSaved,
}: {
  projectId: string;
  current: Context;
  title: string;
  disabled: boolean;
  onSaved: (context: Context) => void;
}) {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [proposal, setProposal] = useState<ImportProposal | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [stale, setStale] = useState(false);
  const entries = proposal
    ? importEntries(proposal, current, suggestion?.proposal as ImportProposal)
    : [];
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message +
              (cause instanceof ContextApiError && cause.fields.length
                ? ` Campos: ${cause.fields.join(', ')}`
                : '')
          : 'No se pudo completar la acción.',
      );
      if (cause instanceof ContextApiError && cause.status === 409)
        setStale(true);
    } finally {
      setBusy(false);
    }
  }
  function preview(item: Suggestion) {
    setSuggestion(item);
    setProposal(item.proposal as ImportProposal);
    setConfirm(false);
    setStale(item.state === 'stale');
    setSelected(
      importEntries(item.proposal as ImportProposal, current)
        .filter((e) => !e.current || e.current === 'unknown')
        .map((e) => e.key),
    );
  }
  function edit(entry: Entry, value: string) {
    if (!proposal) return;
    const [field, ref] = entry.key.split('/');
    if (field === 'specific_objectives')
      setProposal({
        ...proposal,
        specific_objectives: proposal.specific_objectives.map((o) =>
          o.ref === ref ? { ...o, text: value } : o,
        ),
      });
    else if (field === 'hypotheses')
      setProposal({
        ...proposal,
        hypotheses: proposal.hypotheses.map((h) =>
          h.ref === ref ? { ...h, statement: value } : h,
        ),
      });
    else if (field === 'complementary_notes')
      setProposal({
        ...proposal,
        complementary_notes: proposal.complementary_notes.map((n, i) =>
          i === Number(ref) ? value : n,
        ),
      });
    else setProposal({ ...proposal, [field]: value });
    if (!value.trim() || value === 'unknown')
      setSelected((previous) => previous.filter((key) => key !== entry.key));
    setConfirm(false);
  }
  return (
    <details className="rc-assisted">
      <summary>Completar con ayuda de otro chat</summary>
      <p>
        Copia el prompt y úsalo con tu tesis en el chat que prefieras. Pega aquí
        su respuesta, revisa y elige qué guardar. No enviamos el contenido a
        ningún proveedor ni necesitas credenciales de IA.
      </p>
      {disabled && (
        <p>Guarda o descarta primero los cambios del formulario manual.</p>
      )}
      <fieldset disabled={busy || disabled}>
        <legend>1. Llevar el prompt a otro chat</legend>
        <button
          type="button"
          onClick={() =>
            void run(async () => {
              const result = await api.prompt(projectId);
              setPrompt(result.prompt);
              try {
                await navigator.clipboard.writeText(result.prompt);
                setNotice('Prompt copiado.');
              } catch {
                setNotice(
                  'No se pudo copiar. Selecciona el texto del prompt y cópialo con Ctrl+C.',
                );
              }
            })
          }
        >
          Copiar prompt
        </button>
        {prompt && (
          <label>
            Prompt para seleccionar y copiar
            <textarea
              readOnly
              value={prompt}
              rows={6}
              onFocus={(e) => e.currentTarget.select()}
            />
          </label>
        )}
        <h4>2. Revisar la respuesta</h4>
        <label htmlFor="assisted-response">Respuesta del otro chat</label>
        <textarea
          id="assisted-response"
          rows={8}
          maxLength={120000}
          value={response}
          onChange={(e) => setResponse(e.target.value)}
        />
        <p>
          Solo la respuesta estructurada solicitada; no pegues la tesis
          completa. Analizar no modifica el contexto.
        </p>
        <div className="rp-actions">
          <button
            type="button"
            disabled={!response.trim() || suggestion?.state === 'pending'}
            onClick={() =>
              void run(async () => {
                preview(
                  await api.suggest(projectId, response, current.revision),
                );
              })
            }
          >
            Revisar respuesta
          </button>
          <button
            type="button"
            className="rp-secondary"
            onClick={() =>
              void run(async () => {
                const items = await api.suggestions(projectId);
                const item = items.find(
                  (s) => s.state === 'pending' || s.state === 'stale',
                );
                if (item) preview(item);
                else
                  setNotice(
                    'No hay borradores pendientes. Los resultados aplicados están en el contexto y su historial.',
                  );
              })
            }
          >
            Recuperar borrador guardado
          </button>
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {stale && !suggestion && (
        <button
          type="button"
          disabled={busy || disabled}
          onClick={() =>
            void run(async () => {
              onSaved(await api.get(projectId));
              setStale(false);
              setNotice(
                'Contexto actualizado. Puedes volver a revisar la respuesta.',
              );
            })
          }
        >
          Consultar contexto actual
        </button>
      )}
      {suggestion && proposal && (
        <fieldset disabled={busy || disabled}>
          <legend>3. Comparar y elegir campos</legend>
          <p>
            Origen: respuesta de IA · Estado: {states[suggestion.state]} ·
            Revisión base: {suggestion.base_revision}. Los elementos elegidos se
            añaden a las listas existentes.
          </p>
          {proposal.title && (
            <p>
              Título propuesto: {proposal.title}. Nombre actual: {title}.{' '}
              <button
                className="rp-link"
                type="button"
                onClick={() => navigateProject(projectId, 'home', 'edit')}
              >
                Revisar nombre del proyecto
              </button>{' '}
              (no se cambia al importar).
            </p>
          )}
          <p>
            Campos reconocidos: {entries.length}. Sin información:{' '}
            {Object.keys(labels)
              .filter((k) => !entries.some((e) => e.field === k))
              .map((k) => labels[k])
              .join(', ') || 'ninguno'}
            .
          </p>
          {!!suggestion.additional_fields.length && (
            <p>
              Información adicional propuesta como notas revisables:{' '}
              {suggestion.additional_fields.join(', ')}. No se usará como
              parámetros estadísticos.
            </p>
          )}
          {entries.map((entry) => (
            <div className="rc-import-item" key={entry.key}>
              <label className="rc-check">
                <input
                  type="checkbox"
                  checked={selected.includes(entry.key)}
                  disabled={
                    entry.duplicate ||
                    !entry.value.trim() ||
                    entry.value === 'unknown' ||
                    stale ||
                    suggestion.state !== 'pending'
                  }
                  onChange={(e) =>
                    setSelected((previous) =>
                      e.target.checked
                        ? [...previous, entry.key]
                        : previous.filter((k) => k !== entry.key),
                    )
                  }
                />
                <span>Incorporar {labels[entry.field]}</span>
              </label>
              <p>
                Actual:{' '}
                <span className="rc-import-current">
                  {entry.field === 'design'
                    ? designs[entry.current as keyof typeof designs] ||
                      'Sin información'
                    : entry.field === 'observations'
                      ? observations[
                          entry.current as keyof typeof observations
                        ] || 'Sin información'
                      : entry.current || 'Sin información'}
                </span>
              </p>
              {entry.duplicate && (
                <p role="status">
                  Posible duplicado: ya existe este texto. Se conservará el
                  existente; corrige o desmarca el propuesto.
                </p>
              )}
              {entry.current &&
                entry.current !== 'unknown' &&
                !entry.key.includes('/') && (
                  <p>Reemplazará este valor solo si lo seleccionas.</p>
                )}
              <label>
                Valor propuesto: {labels[entry.field]}
                {entry.field === 'design' || entry.field === 'observations' ? (
                  <select
                    value={entry.value}
                    onChange={(e) => edit(entry, e.target.value)}
                  >
                    {Object.entries(
                      entry.field === 'design' ? designs : observations,
                    ).map(([v, label]) => (
                      <option value={v} key={v}>
                        {label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <textarea
                    rows={3}
                    maxLength={2000}
                    value={entry.value}
                    onChange={(e) => edit(entry, e.target.value)}
                  />
                )}
              </label>
              {entry.field === 'hypotheses' &&
                (() => {
                  const h = proposal.hypotheses.find(
                    (x) => `hypotheses/${x.ref}` === entry.key,
                  )!;
                  return (
                    <>
                      <label>
                        Objetivo vinculado
                        <select
                          value={h.objective_ref ?? ''}
                          onChange={(e) => {
                            setProposal({
                              ...proposal,
                              hypotheses: proposal.hypotheses.map((x) =>
                                x.ref === h.ref
                                  ? {
                                      ...x,
                                      objective_ref: e.target.value || null,
                                    }
                                  : x,
                              ),
                            });
                            setConfirm(false);
                          }}
                        >
                          <option value="">Sin vínculo</option>
                          {proposal.specific_objectives.map((o) => (
                            <option key={o.ref} value={o.ref}>
                              {o.text}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Dirección de la hipótesis
                        <select
                          value={h.alternative}
                          onChange={(e) => {
                            setProposal({
                              ...proposal,
                              hypotheses: proposal.hypotheses.map((x) =>
                                x.ref === h.ref
                                  ? {
                                      ...x,
                                      alternative: e.target
                                        .value as typeof h.alternative,
                                    }
                                  : x,
                              ),
                            });
                            setConfirm(false);
                          }}
                        >
                          {Object.entries({
                            unspecified: 'No especificada',
                            'two-sided': 'Bilateral',
                            greater: 'Mayor',
                            less: 'Menor',
                          }).map(([v, l]) => (
                            <option key={v} value={v}>
                              {l}
                            </option>
                          ))}
                        </select>
                      </label>
                    </>
                  );
                })()}
            </div>
          ))}
          <p>
            Resultado: se añadirán{' '}
            {
              selected.filter((k) => k.startsWith('specific_objectives/'))
                .length
            }{' '}
            objetivos,{' '}
            {selected.filter((k) => k.startsWith('hypotheses/')).length}{' '}
            hipótesis y{' '}
            {
              selected.filter((k) => k.startsWith('complementary_notes/'))
                .length
            }{' '}
            notas. Se conservarán los IDs y elementos actuales.
          </p>
          <button
            type="button"
            className="rp-secondary"
            disabled={stale || suggestion.state !== 'pending'}
            onClick={() =>
              setSelected(
                entries
                  .filter(
                    (e) =>
                      !e.duplicate && e.value.trim() && e.value !== 'unknown',
                  )
                  .map((e) => e.key),
              )
            }
          >
            Seleccionar todos los campos válidos (incluye reemplazos)
          </button>
          <label className="rc-check">
            <input
              type="checkbox"
              checked={confirm}
              onChange={(e) => setConfirm(e.target.checked)}
            />
            He revisado y quiero confirmar los campos seleccionados
          </label>
          <p>
            Guardar o confirmar no certifica validez científica ni aprueba un
            análisis. Se conserva el origen de IA.
          </p>
          <div className="rp-actions">
            <button
              type="button"
              disabled={
                !selected.length || stale || suggestion.state !== 'pending'
              }
              onClick={() =>
                void run(async () => {
                  const result = await api.apply(
                    projectId,
                    suggestion,
                    proposal,
                    selected,
                    confirm,
                  );
                  onSaved(result.result as Context);
                  setSuggestion(null);
                  setProposal(null);
                  setSelected([]);
                  setResponse('');
                  setNotice('Campos incorporados y guardados.');
                })
              }
            >
              Aplicar y guardar seleccionados
            </button>
            <button
              type="button"
              className="rp-secondary"
              disabled={suggestion.state === 'applied'}
              onClick={() =>
                void run(async () => {
                  await api.reject(projectId, suggestion);
                  setSuggestion(null);
                  setProposal(null);
                  setSelected([]);
                  setResponse('');
                  setNotice('Borrador cancelado. El contexto se conserva.');
                })
              }
            >
              Cancelar importación
            </button>
            {(stale || suggestion.state === 'stale') && (
              <button
                type="button"
                onClick={() =>
                  void run(async () => {
                    const latest = await api.get(projectId);
                    onSaved(latest);
                    preview(
                      await api.suggest(
                        projectId,
                        JSON.stringify(proposal),
                        latest.revision,
                      ),
                    );
                    setSelected([]);
                    setNotice(
                      'Compara con la versión actual y selecciona de nuevo qué incorporar.',
                    );
                  })
                }
              >
                Revisar de nuevo con contexto actual
              </button>
            )}
          </div>
        </fieldset>
      )}
    </details>
  );
}

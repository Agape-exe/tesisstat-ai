import { useEffect, useState } from 'react';
import { SourcesError } from '../sources/api';
import type { DataApi, Dictionary, Variable, VariableChanges } from './api';

const scales = {
  unknown: 'Desconocida',
  nominal: 'Nominal',
  ordinal: 'Ordinal',
  interval: 'Intervalar',
  ratio: 'Razón',
} as const;
const labels = {
  name: 'Nombre',
  measurement_scale: 'Escala',
  column_ids: 'Columna',
  identifier_confirmed: 'Identificador',
  category_order: 'Orden',
  missing_markers: 'Faltantes',
  description: 'Descripción',
};
type Draft = {
  revision: number;
  changes: Record<string, VariableChanges>;
  confirm: string[];
};

export function DictionaryEditor({
  initial,
  api,
  onSaved,
}: {
  initial: Dictionary;
  api: DataApi;
  onSaved: (d: Dictionary) => void;
}) {
  const project = initial.project_id;
  const key = `tesisstat:dictionary:${project}:${initial.dataset_ref.id}`;
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState<Draft>(() => {
    try {
      const text = sessionStorage.getItem(key);
      if (text) return JSON.parse(text) as Draft;
    } catch {
      /* Storage can be disabled. */
    }
    return { revision: initial.revision, changes: {}, confirm: [] };
  });
  const [remote, setRemote] = useState<Dictionary | null>(
    draft.revision !== initial.revision ? initial : null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(draft));
    } catch {
      /* Keep in memory. */
    }
  }, [draft, key]);
  function edit(id: string, changes: VariableChanges) {
    setDraft((d) => ({
      ...d,
      changes: { ...d.changes, [id]: { ...d.changes[id], ...changes } },
    }));
    setNotice('');
  }
  function effective(v: Variable, field: keyof VariableChanges) {
    const change = draft.changes[v.id];
    if (change && field in change) return change[field];
    if (
      field === 'name' ||
      field === 'description' ||
      field === 'measurement_scale' ||
      field === 'identifier_confirmed'
    )
      return v[field].value;
    return v[field];
  }
  function toggle(path: string) {
    setDraft((d) => ({
      ...d,
      confirm: d.confirm.includes(path)
        ? d.confirm.filter((f) => f !== path)
        : [...d.confirm, path],
    }));
  }
  async function save() {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api.saveDictionary(
        project,
        saved,
        draft.changes,
        draft.confirm,
        draft.revision,
      );
      setSaved(result);
      setDraft({ revision: result.revision, changes: {}, confirm: [] });
      setRemote(null);
      setNotice(
        'Diccionario guardado en el servidor. Solo se confirmaron los campos seleccionados.',
      );
      onSaved(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo guardar.');
      if (cause instanceof SourcesError && cause.status === 409) {
        try {
          setRemote(await api.dictionary(project, initial.dataset_ref.id));
        } catch {
          setError(
            'Tu borrador se conserva. Reintenta para comparar con el servidor.',
          );
        }
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Diccionario de variables">
      <h3>Definir o confirmar variables</h3>
      <p>
        Puedes guardar parcialmente. Cada variable usa una columna. La escala
        describe qué significa el dato: un código numérico puede ser nominal y
        un ítem, ordinal.
      </p>
      <p className="rp-hint">
        Revisión {saved.revision}. Las sugerencias del encabezado no están
        confirmadas. No necesitas describir todas las columnas.
      </p>
      {saved.pending_questions.map((q) => (
        <p className="rp-hint" key={q}>
          {q}
        </p>
      ))}
      <fieldset disabled={busy} className="data-dictionary-fields">
        <button
          className="rp-secondary"
          onClick={() =>
            setDraft((d) => ({
              ...d,
              confirm: [
                ...new Set([
                  ...d.confirm,
                  ...saved.variables.flatMap((raw) => {
                    const v = raw as Variable;
                    return (
                      [
                        'name',
                        'column_ids',
                        'measurement_scale',
                        'identifier_confirmed',
                      ] as const
                    )
                      .filter((field) => {
                        const value = effective(v, field);
                        return (
                          value !== null &&
                          value !== undefined &&
                          value !== '' &&
                          value !== 'unknown' &&
                          (field !== 'column_ids' ||
                            (value as string[]).length > 0)
                        );
                      })
                      .map((field) => `/variables/${v.id}/${field}`);
                  }),
                ]),
              ],
            }))
          }
        >
          Seleccionar campos conocidos de todas las variables
        </button>
        <p className="rp-hint">
          {draft.confirm.length} campos seleccionados para confirmar al guardar.
        </p>
        {saved.variables.map((raw) => {
          const v = raw as Variable;
          const prefix = `/variables/${v.id}/`;
          const scale = effective(v, 'measurement_scale') as
            keyof typeof scales | null;
          const identifier = effective(v, 'identifier_confirmed');
          const ids = effective(v, 'column_ids') as string[];
          return (
            <article
              key={v.id}
              className="rp-surface data-variable"
              aria-label={`Variable ${v.name.value ?? 'pendiente'}`}
            >
              <h4>{v.name.value ?? 'Variable pendiente'}</h4>
              <div className="data-form-grid">
                <label className="rp-field">
                  Nombre de variable
                  <input
                    maxLength={200}
                    value={String(effective(v, 'name') ?? '')}
                    onChange={(e) =>
                      edit(v.id, { name: e.target.value || null })
                    }
                  />
                </label>
                <label className="rp-field">
                  Columna
                  <select
                    value={ids[0] ?? ''}
                    onChange={(e) =>
                      edit(v.id, {
                        column_ids: e.target.value ? [e.target.value] : [],
                      })
                    }
                  >
                    <option value="">Vínculo pendiente</option>
                    {saved.dataset_ref.columns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="rp-field">
                  Escala de medición
                  <select
                    value={scale ?? 'unknown'}
                    onChange={(e) =>
                      edit(v.id, {
                        measurement_scale: e.target
                          .value as keyof typeof scales,
                      })
                    }
                  >
                    {Object.entries(scales).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="rp-field">
                  ¿Es identificador?
                  <select
                    value={
                      identifier === true
                        ? 'yes'
                        : identifier === false
                          ? 'no'
                          : 'unknown'
                    }
                    onChange={(e) =>
                      edit(v.id, {
                        identifier_confirmed:
                          e.target.value === 'unknown'
                            ? null
                            : e.target.value === 'yes',
                      })
                    }
                  >
                    <option value="unknown">Sin decidir</option>
                    <option value="yes">Sí, se usa para identificar</option>
                    <option value="no">No es identificador</option>
                  </select>
                </label>
              </div>
              <p className="rp-hint">
                {v.possible_identifier
                  ? 'El encabezado sugiere un identificador; confirma o descarta esta sugerencia.'
                  : 'El tipo de almacenamiento sugerido no determina la escala.'}
              </p>
              {scale === 'ordinal' && (
                <label className="rp-field">
                  Orden de categorías, una por línea
                  <textarea
                    value={(effective(v, 'category_order') as string[]).join(
                      '\n',
                    )}
                    onChange={(e) =>
                      edit(v.id, {
                        category_order: e.target.value.split('\n'),
                      })
                    }
                  />
                </label>
              )}
              <details>
                <summary>
                  Descripción y marcadores de faltantes (opcional)
                </summary>
                <label className="rp-field">
                  Descripción
                  <textarea
                    maxLength={2000}
                    value={String(effective(v, 'description') ?? '')}
                    onChange={(e) =>
                      edit(v.id, { description: e.target.value || null })
                    }
                  />
                </label>
                <label className="rp-field">
                  Marcadores, uno por línea
                  <textarea
                    value={(effective(v, 'missing_markers') as string[]).join(
                      '\n',
                    )}
                    onChange={(e) =>
                      edit(v.id, {
                        missing_markers: e.target.value.split('\n'),
                      })
                    }
                  />
                </label>
                <p className="rp-hint">
                  Vacíos y null son faltantes. Los marcadores se comparan sin
                  espacios exteriores ni distinción de mayúsculas. Cambiarlos
                  vuelve obsoleto el perfil; no modifica celdas.
                </p>
              </details>
              <div
                className="data-confirmations"
                aria-label={`Confirmaciones de ${v.name.value}`}
              >
                {(Object.keys(labels) as (keyof typeof labels)[]).map(
                  (field) => {
                    const value = effective(v, field);
                    const known =
                      value !== null &&
                      value !== undefined &&
                      value !== '' &&
                      value !== 'unknown' &&
                      (field !== 'column_ids' || ids.length > 0);
                    const confirmation =
                      field in v.field_confirmations
                        ? v.field_confirmations[field]
                        : field === 'name' ||
                            field === 'description' ||
                            field === 'measurement_scale' ||
                            field === 'identifier_confirmed'
                          ? v[field].confirmation
                          : null;
                    return (
                      <label key={field}>
                        <input
                          type="checkbox"
                          disabled={!known}
                          checked={draft.confirm.includes(prefix + field)}
                          onChange={() => toggle(prefix + field)}
                        />{' '}
                        Confirmar {labels[field].toLowerCase()}
                        {confirmation && !(field in (draft.changes[v.id] ?? {}))
                          ? ' · guardado'
                          : ''}
                      </label>
                    );
                  },
                )}
              </div>
              <button
                className="rp-link"
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    confirm: [
                      ...new Set([
                        ...d.confirm,
                        ...(
                          [
                            'name',
                            'column_ids',
                            'measurement_scale',
                            'identifier_confirmed',
                          ] as const
                        )
                          .filter((field) => {
                            const x = effective(v, field);
                            return (
                              x !== null &&
                              x !== undefined &&
                              x !== '' &&
                              x !== 'unknown' &&
                              (field !== 'column_ids' || ids.length > 0)
                            );
                          })
                          .map((f) => prefix + f),
                      ]),
                    ],
                  }))
                }
              >
                Seleccionar campos conocidos de esta variable
              </button>
            </article>
          );
        })}
      </fieldset>
      {remote && (
        <div className="rp-surface" role="alert">
          <h4>Otra revisión fue guardada</h4>
          <p>
            Tu borrador sigue disponible. Compara antes de reaplicar únicamente
            tus cambios.
          </p>
          <p>
            Servidor: revisión {remote.revision}. Tu borrador: revisión{' '}
            {draft.revision}.
          </p>
          {remote.variables
            .filter((v) => v.id in draft.changes)
            .map((v) => (
              <div key={v.id}>
                <h5>{v.name.value ?? 'Variable pendiente'}</h5>
                <ul>
                  {Object.entries(draft.changes[v.id]).map(([key, value]) => {
                    const field = key as keyof VariableChanges;
                    const server =
                      field === 'name' ||
                      field === 'description' ||
                      field === 'measurement_scale' ||
                      field === 'identifier_confirmed'
                        ? v[field]?.value
                        : v[field];
                    const show = (x: unknown) =>
                      x === false
                        ? 'No'
                        : x === true
                          ? 'Sí'
                          : x == null || x === ''
                            ? 'Sin dato'
                            : Array.isArray(x)
                              ? x.join(', ') || 'Lista vacía'
                              : String(x);
                    return (
                      <li key={key}>
                        <strong>{labels[field]}</strong>: servidor «
                        {show(server)}»; tu borrador «{show(value)}».
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          <button
            onClick={() => {
              setSaved(remote);
              setDraft((d) => ({ ...d, revision: remote.revision }));
              setRemote(null);
              setError('');
            }}
          >
            Conservar mi borrador sobre la revisión actual
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="rp-success">
          {notice}
        </p>
      )}
      <button
        disabled={
          busy ||
          !!remote ||
          (!Object.keys(draft.changes).length && !draft.confirm.length)
        }
        onClick={() => void save()}
      >
        {busy
          ? 'Guardando…'
          : 'Guardar diccionario y confirmaciones seleccionadas'}
      </button>
    </section>
  );
}

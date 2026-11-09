import { useEffect, useState } from 'react';
import {
  createContextApi,
  ContextApiError,
  type Context,
  type ContextFact,
} from './api';
import {
  changesFrom,
  facts,
  textFields,
  toDraft,
  type Draft,
  type TextField,
} from './draft';
import { ContextLists } from './ContextLists';
import { AssistedContext } from './AssistedContext';
import { navigateProject } from '../projects/navigation';
import './context.css';

const api = createContextApi();
const contextLabels: Record<string, string> = {
  ...textFields,
  design: 'Diseño del estudio',
  observations: 'Relación entre observaciones',
  specific_objectives: 'Objetivos específicos',
  hypotheses: 'Hipótesis',
  complementary_notes: 'Contexto adicional',
};

function describeField(key: string, draft: Draft): string {
  if (key === 'specific_objectives')
    return (
      draft.specific_objectives
        .map((o, i) => `${i + 1}. ${o.text || 'Sin texto'}`)
        .join('\n') || 'Sin objetivos específicos'
    );
  if (key === 'hypotheses')
    return (
      draft.hypotheses
        .map(
          (h, i) =>
            `${i + 1}. ${h.statement || 'Sin texto'} · Objetivo: ${draft.specific_objectives.find((o) => o.id === h.objective_id)?.text || 'Sin vínculo'} · Dirección: ${h.alternative}`,
        )
        .join('\n') || 'Sin hipótesis'
    );
  if (key === 'complementary_notes')
    return (
      draft.complementary_notes.map((n) => n.text).join('\n') || 'Sin notas'
    );
  return String(draft[key as keyof Draft] || 'Sin información');
}

export function FieldStatus({
  fact,
  changed,
}: {
  fact?: ContextFact;
  changed: boolean;
}) {
  return (
    <span className="rc-field-status">
      {changed
        ? 'Sin guardar · requiere revisión'
        : fact?.confirmation
          ? `Confirmado por ti · revisión ${fact.confirmation.revision}`
          : fact?.value && fact.value !== 'unknown'
            ? 'Guardado · sin confirmar'
            : 'Sin información todavía'}
      {fact?.provenance?.kind === 'ai_suggestion' &&
        ' · Origen: respuesta de IA'}
    </span>
  );
}

export function ContextEditor({
  projectId,
  title,
  initial,
}: {
  projectId: string;
  title: string;
  initial: Context;
}) {
  const [saved, setSaved] = useState(initial);
  const [draft, setDraft] = useState(() => toDraft(initial));
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [notice, setNotice] = useState('');
  const [conflict, setConflict] = useState<Context | null>(null);
  const [conflicted, setConflicted] = useState(false);
  const [history, setHistory] = useState<Context[] | null>(null);
  const changes = changesFrom(saved, draft);
  const dirty = Object.keys(changes).length > 0;
  const confirmable = facts(saved).filter(
    ([, f]) => f.value != null && f.value !== '' && f.value !== 'unknown',
  );

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((previous) => ({ ...previous, [key]: value }));
    setSelected([]);
    setNotice('');
  }
  async function save(confirm = false, expected = saved.revision) {
    if (busy) return;
    setBusy(true);
    setError('');
    setInvalidFields([]);
    setNotice('');
    try {
      const result = await api.patch(projectId, {
        expected_revision: expected,
        changes,
        confirm_fields: confirm ? selected : [],
      });
      setSaved(result);
      setDraft(toDraft(result));
      setSelected([]);
      setHistory(null);
      setConflict(null);
      setConflicted(false);
      setNotice(
        confirm
          ? 'Información seleccionada confirmada por ti.'
          : 'Información guardada. Puedes confirmarla después de revisarla.',
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo guardar. Tu borrador sigue aquí.',
      );
      if (cause instanceof ContextApiError) {
        setInvalidFields(cause.fields);
        if (cause.status === 409) {
          setConflicted(true);
          setSelected([]);
        }
      }
    } finally {
      setBusy(false);
    }
  }
  async function readLatest() {
    setBusy(true);
    try {
      setConflict(await api.get(projectId));
      setError('');
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo consultar la revisión.',
      );
    } finally {
      setBusy(false);
    }
  }
  function downloadDraft() {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { project_id: projectId, base_revision: saved.revision, changes },
            null,
            2,
          ),
        ],
        { type: 'application/json' },
      ),
    );
    const link = document.createElement('a');
    link.href = url;
    link.download = 'borrador-contexto.json';
    link.click();
    URL.revokeObjectURL(url);
  }
  async function showHistory() {
    setBusy(true);
    try {
      setHistory(await api.revisions(projectId));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo consultar el historial.',
      );
    } finally {
      setBusy(false);
    }
  }
  function textField(key: TextField, hint: string) {
    return (
      <div className="rc-field" key={key}>
        <label htmlFor={`context-${key}`}>{textFields[key]}</label>
        <p className="rp-hint" id={`hint-${key}`}>
          {hint}
        </p>
        <textarea
          id={`context-${key}`}
          value={draft[key]}
          maxLength={2000}
          rows={3}
          aria-describedby={`hint-${key}`}
          aria-invalid={invalidFields.some((f) => f.endsWith(`/${key}`))}
          onChange={(e) => update(key, e.target.value)}
        />
        <FieldStatus fact={saved[key]} changed={key in changes} />
      </div>
    );
  }
  return (
    <section className="rc-context" aria-label="Contexto de investigación">
      <header>
        <p className="rp-eyebrow">CONTEXTO DE INVESTIGACIÓN</p>
        <h2>{title}</h2>
        <p>
          Empieza por una pregunta o un objetivo. Guarda lo que sepas y vuelve
          cuando tengas más información. Todos los campos son opcionales.
        </p>
      </header>
      <div className="rc-save-state" role="status" aria-live="polite">
        {busy
          ? 'Consultando o guardando…'
          : dirty
            ? 'Cambios sin guardar'
            : saved.revision
              ? `Información guardada · revisión ${saved.revision}`
              : 'Aún no has guardado información'}
        {notice && <p>{notice}</p>}
      </div>
      {error && (
        <div role="alert" className="rp-error">
          {error}{' '}
          {invalidFields.length > 0 && (
            <p>Campos: {invalidFields.join(', ')}</p>
          )}
        </div>
      )}
      {conflicted && (
        <div className="rc-conflict" aria-label="Resolver conflicto">
          <h3>Hay otra revisión guardada</h3>
          <p>
            Tu borrador sigue en el formulario. Consulta la versión actual antes
            de decidir qué conservar.
          </p>
          <div className="rp-actions">
            <button disabled={busy} onClick={() => void readLatest()}>
              Comparar con versión guardada
            </button>
            <button className="rp-secondary" onClick={downloadDraft}>
              Descargar mi borrador
            </button>
          </div>
          {conflict && (
            <>
              <p>
                Revisión actual: {conflict.revision}. Solo se reaplicarán los
                campos que cambiaste; las listas se sustituyen completas. Las
                confirmaciones deben revisarse de nuevo.
              </p>
              {Object.keys(changes).map((key) => (
                <div key={key}>
                  <h4>{contextLabels[key]}</h4>
                  <p>Tu borrador:</p>
                  <pre>{describeField(key, draft)}</pre>
                  <p>Guardado en el servidor:</p>
                  <pre>{describeField(key, toDraft(conflict))}</pre>
                </div>
              ))}
              <div className="rp-actions">
                <button
                  disabled={busy || !dirty}
                  onClick={() => void save(false, conflict.revision)}
                >
                  Guardar mis cambios sobre revisión {conflict.revision}
                </button>
                <button
                  className="rp-secondary"
                  disabled={busy}
                  onClick={() => {
                    setSaved(conflict);
                    setDraft(toDraft(conflict));
                    setConflict(null);
                    setConflicted(false);
                    setSelected([]);
                  }}
                >
                  Usar versión guardada y descartar mi borrador
                </button>
              </div>
            </>
          )}
        </div>
      )}
      <AssistedContext
        projectId={projectId}
        current={saved}
        title={title}
        disabled={busy || dirty || conflicted}
        onSaved={(result) => {
          setSaved(result);
          setDraft(toDraft(result));
          setSelected([]);
          setHistory(null);
        }}
      />
      <form
        className="rp-form rc-form"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <fieldset disabled={busy}>
          <legend>1. Qué quieres comprender</legend>
          {textField(
            'research_question',
            'La pregunta que te gustaría responder con tu estudio.',
          )}
          {textField(
            'main_objective',
            'Qué buscas conocer o describir. Puedes guardar solo este campo.',
          )}
          <ContextLists draft={draft} saved={saved} update={update} />
          <details>
            <summary>2. Sobre el estudio y los datos</summary>
            {textField(
              'study_description',
              'Qué se estudia, en qué población y en qué entorno.',
            )}
            {textField(
              'data_description',
              'Qué información has recogido o planeas recoger; no necesitas cargar un archivo aún.',
            )}
            {textField(
              'observational_unit',
              'Por ejemplo, una persona, una venta o una visita. Si no lo sabes, déjalo vacío.',
            )}
            <label htmlFor="context-design">Diseño del estudio</label>
            <select
              id="context-design"
              value={draft.design}
              onChange={(e) =>
                update('design', e.target.value as Draft['design'])
              }
            >
              <option value="unknown">No lo sé todavía</option>
              <option value="observational">
                Observacional: se observa sin asignar intervenciones
              </option>
              <option value="experimental">
                Experimental: se asigna una intervención al azar
              </option>
              <option value="quasi_experimental">
                Cuasiexperimental: intervención sin asignación al azar
              </option>
            </select>
            <FieldStatus fact={saved.design} changed={'design' in changes} />
            <label htmlFor="context-observations">
              Relación entre observaciones
            </label>
            <select
              id="context-observations"
              value={draft.observations}
              onChange={(e) =>
                update('observations', e.target.value as Draft['observations'])
              }
            >
              <option value="unknown">No lo sé todavía</option>
              <option value="independent">
                Independientes: cada fila es una unidad distinta sin relación
              </option>
              <option value="paired">
                Pareadas: dos mediciones relacionadas por unidad
              </option>
              <option value="repeated">
                Repetidas: varias mediciones de la misma unidad
              </option>
            </select>
            <FieldStatus
              fact={saved.observations}
              changed={'observations' in changes}
            />
            {textField(
              'sampling_notes',
              'De dónde proceden los casos y cómo se seleccionaron. Puedes indicar que no lo sabes todavía.',
            )}
          </details>
          <details>
            <summary>3. Contexto adicional (opcional)</summary>
            <p className="rp-hint">
              Hasta 20 notas breves que ayuden a entender tu investigación.
            </p>
            {draft.complementary_notes.map((n, i) => (
              <div className="rc-item" key={n.key}>
                <label htmlFor={`note-${n.key}`}>Nota adicional {i + 1}</label>
                <textarea
                  id={`note-${n.key}`}
                  maxLength={2000}
                  rows={2}
                  value={n.text}
                  onChange={(e) =>
                    update(
                      'complementary_notes',
                      draft.complementary_notes.map((x) =>
                        x.key === n.key ? { ...x, text: e.target.value } : x,
                      ),
                    )
                  }
                />
                <FieldStatus
                  fact={saved.complementary_notes[i]}
                  changed={'complementary_notes' in changes}
                />
                <button
                  type="button"
                  className="rp-link"
                  onClick={() =>
                    update(
                      'complementary_notes',
                      draft.complementary_notes.filter((x) => x.key !== n.key),
                    )
                  }
                >
                  Retirar nota {i + 1}
                </button>
              </div>
            ))}
            <button
              type="button"
              className="rp-secondary"
              disabled={draft.complementary_notes.length >= 20}
              onClick={() =>
                update('complementary_notes', [
                  ...draft.complementary_notes,
                  { key: crypto.randomUUID(), text: '' },
                ])
              }
            >
              Añadir nota
            </button>
          </details>
          <div className="rp-actions rc-save-actions">
            <button type="submit" disabled={!dirty || conflicted}>
              Guardar información
            </button>
            <span className="rp-hint">
              Guardar no confirma ni aprueba un análisis.
            </span>
          </div>
        </fieldset>
      </form>
      <section className="rc-confirm" aria-label="Confirmación de información">
        <h3>Revisar y confirmar</h3>
        <p>
          Confirmar significa que revisaste los campos seleccionados. No
          certifica su validez científica ni aprueba un análisis.
        </p>
        {dirty && <p>Guarda los cambios antes de confirmar.</p>}
        <fieldset disabled={busy || dirty || conflicted}>
          <legend>Información guardada para revisar</legend>
          {confirmable.length ? (
            confirmable.map(([path, fact]) => (
              <label className="rc-check" key={path}>
                <input
                  type="checkbox"
                  checked={selected.includes(path)}
                  onChange={(e) =>
                    setSelected((previous) =>
                      e.target.checked
                        ? [...previous, path]
                        : previous.filter((p) => p !== path),
                    )
                  }
                />
                <span>
                  {contextLabels[path.split('/')[1]]}
                  {path.split('/').length > 2
                    ? ` ${Number(path.split('/')[2]) + 1}`
                    : ''}
                  : {fact.value}
                  <small>
                    {fact.confirmation
                      ? 'Confirmado por ti'
                      : 'Guardado · sin confirmar'}
                  </small>
                </span>
              </label>
            ))
          ) : (
            <p>Aún no hay valores conocidos para confirmar.</p>
          )}
          <div className="rp-actions">
            <button
              type="button"
              className="rp-secondary"
              disabled={!confirmable.length}
              onClick={() => setSelected(confirmable.map(([path]) => path))}
            >
              Seleccionar todos los campos conocidos
            </button>
            <button
              type="button"
              disabled={!selected.length}
              onClick={() => void save(true)}
            >
              Confirmar campos seleccionados
            </button>
          </div>
        </fieldset>
      </section>
      <details className="rc-history">
        <summary>Historial de revisiones</summary>
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() => void showHistory()}
        >
          Consultar revisiones guardadas
        </button>
        {history &&
          (history.length ? (
            history.map((revision) => (
              <details key={revision.revision}>
                <summary>
                  Revisión {revision.revision} ·{' '}
                  {revision.updated_at
                    ? new Date(revision.updated_at).toLocaleString()
                    : ''}
                </summary>
                <ul>
                  {facts(revision)
                    .filter(([, f]) => f.value != null && f.value !== 'unknown')
                    .map(([path, f]) => (
                      <li key={path}>
                        {contextLabels[path.split('/')[1]]}: {f.value} ·{' '}
                        {f.confirmation ? 'Confirmado' : 'Sin confirmar'}
                      </li>
                    ))}
                </ul>
              </details>
            ))
          ) : (
            <p>No hay revisiones guardadas.</p>
          ))}
      </details>
      <div className="rp-actions">
        <button onClick={() => navigateProject(projectId, 'datasets')}>
          Continuar a Datos
        </button>
        <button
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'home')}
        >
          Volver a Inicio
        </button>
      </div>
      <p className="rp-hint">
        Puedes explorar los datos con contexto incompleto. El tutor y el
        análisis documental conservan su alcance anterior.
      </p>
      <details>
        <summary>Documentos y herramientas de apoyo</summary>
        <p>
          Son opcionales para guardar el contexto. Sus revisiones no confirman
          automáticamente esta información.
        </p>
        <div className="rp-actions">
          {(
            [
              ['documents', 'Documentos de apoyo'],
              ['methodology', 'Revisión metodológica existente'],
              ['instrument', 'Instrumento'],
            ] as const
          ).map(([section, label]) => (
            <button
              className="rp-secondary"
              key={section}
              onClick={() => navigateProject(projectId, section)}
            >
              {label}
            </button>
          ))}
        </div>
      </details>
    </section>
  );
}

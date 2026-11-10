import { useEffect, useState } from 'react';
import {
  createDataApi,
  type Dataset,
  type Dictionary,
  type Profile,
} from '../data/api';
import { SourcesError } from '../sources/api';
import { navigateProject } from '../projects/navigation';
import {
  createDiagnosticsApi,
  type Intent,
  type Changes,
  type Diagnostic,
  type Check,
} from './api';
import { DiagnosticEvidence } from './DiagnosticEvidence';
import { checkLabels } from './labels';
import './diagnostics.css';

const api = createDiagnosticsApi(),
  dataApi = createDataApi();
const empty: Changes = {
  kind: 'descriptive',
  estimand: 'summary',
  question: '',
  dataset_id: null,
  variable_ids: [],
  roles: [],
  observations: 'unknown',
  observational_unit: '',
  identification: '',
  comparison_notes: '',
  linkage: 'unknown',
  identifier_column_id: null,
  paired_columns: null,
  group_column_id: null,
  alternative: 'unspecified',
  alpha: 0.05,
  missing_policy: 'complete_cases',
};
function fromIntent(i: Intent): Changes {
  return {
    ...empty,
    kind: i.kind,
    estimand: i.estimand,
    question: i.question.value ?? '',
    dataset_id: i.dataset_id,
    variable_ids: i.variable_ids,
    roles: i.roles,
    observations: i.observations.value ?? 'unknown',
    observational_unit: i.observational_unit.value ?? '',
    identification: i.identification.value ?? '',
    comparison_notes: i.comparison_notes.value ?? '',
    linkage: i.linkage.value ?? 'unknown',
    identifier_column_id: i.identifier_column_id,
    paired_columns: i.paired_columns,
    group_column_id: i.group_column_id,
    alternative: i.alternative,
    alpha: i.alpha,
  };
}
function difference(draft: Changes, base: Changes): Changes {
  return Object.fromEntries(
    Object.entries(draft).filter(
      ([key, value]) =>
        JSON.stringify(value) !== JSON.stringify(base[key as keyof Changes]),
    ),
  );
}

export function DiagnosticWorkspace({
  projectId,
  active = true,
}: {
  projectId: string;
  active?: boolean;
}) {
  const [intents, setIntents] = useState<Intent[]>([]),
    [tables, setTables] = useState<Dataset[]>([]);
  const [current, setCurrent] = useState<Intent | null>(null),
    [draft, setDraft] = useState<Changes>(empty);
  const [baseline, setBaseline] = useState<Changes>(empty);
  const [pendingPair, setPendingPair] = useState({
    before_column_id: '',
    after_column_id: '',
  });
  const [dictionary, setDictionary] = useState<Dictionary | null>(null),
    [profile, setProfile] = useState<Profile | null>(null);
  const [history, setHistory] = useState<Diagnostic[]>([]),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const [conflict, setConflict] = useState<Intent | null>(null);
  const [checks, setChecks] = useState<Check[]>([
    'complete_cases',
    'distribution',
  ]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  const selectedTable = tables.find((t) => t.id === draft.dataset_id);
  const key = `s04a:${projectId}:${current?.id ?? 'new'}`;

  useEffect(() => {
    if (!active) return;
    let live = true;
    Promise.all([api.list(projectId), dataApi.tables(projectId)])
      .then(([items, sourceTables]) => {
        if (live) {
          setIntents(items);
          setTables(sourceTables);
        }
      })
      .catch((cause) => {
        if (live) setError(String(cause));
      });
    return () => {
      live = false;
    };
  }, [projectId, active]);

  useEffect(() => {
    if (!active) return;
    let live = true;
    if (draft.dataset_id)
      Promise.all([
        dataApi.dictionary(projectId, draft.dataset_id),
        dataApi.profile(projectId, draft.dataset_id),
      ])
        .then(([d, p]) => {
          if (live) {
            setDictionary(d);
            setProfile(p);
          }
        })
        .catch((cause) => {
          if (live) setError(String(cause));
        });
    return () => {
      live = false;
    };
  }, [projectId, draft.dataset_id, active]);

  useEffect(() => {
    if (!active || !current?.id) return;
    let live = true;
    api
      .history(projectId, current.id)
      .then((h) => {
        if (live) setHistory(h);
      })
      .catch((cause) => {
        if (live) setError(String(cause));
      });
    return () => {
      live = false;
    };
  }, [projectId, current?.id, active]);

  useEffect(() => {
    if (dirty) sessionStorage.setItem(key, JSON.stringify(draft));
  }, [key, draft, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  const update = (change: Changes) => {
    if ('paired_columns' in change)
      setPendingPair(
        change.paired_columns ?? { before_column_id: '', after_column_id: '' },
      );
    setDraft((d) => ({ ...d, ...change }));
    setMessage('');
  };
  function choose(id: string) {
    const item = intents.find((i) => i.id === id) ?? null,
      value = item ? fromIntent(item) : empty;
    setCurrent(item);
    setBaseline(value);
    setDraft(value);
    setPendingPair(
      value.paired_columns ?? { before_column_id: '', after_column_id: '' },
    );
    setHistory([]);
    setConflict(null);
    setMessage('');
    setError('');
    if (value.dataset_id !== draft.dataset_id) {
      setDictionary(null);
      setProfile(null);
    }
  }
  async function work(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await action();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo completar la acción.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function save(confirm: boolean) {
    await work(async () => {
      try {
        const value = await api.save(projectId, current?.id ?? null, {
          expected_revision: current?.revision ?? 0,
          changes: current ? difference(draft, baseline) : draft,
          confirm,
        });
        sessionStorage.removeItem(key);
        setCurrent(value);
        setDraft(fromIntent(value));
        setBaseline(fromIntent(value));
        setIntents(await api.list(projectId));
        setHistory(await api.history(projectId, value.id));
        setConflict(null);
        setMessage(
          confirm
            ? 'Intención revisada y guardada. Esto no aprueba una prueba estadística.'
            : 'Borrador guardado. Puedes completar lo que falta después.',
        );
      } catch (cause) {
        if (cause instanceof SourcesError && cause.status === 409 && current) {
          const latest = (await api.list(projectId)).find(
            (i) => i.id === current.id,
          );
          if (latest) setConflict(latest);
        }
        throw cause;
      }
    });
  }
  const selectedVariables =
    dictionary?.variables.filter((v) => draft.variable_ids?.includes(v.id)) ??
    [];
  const selectedColumns =
    selectedTable?.columns.filter((c) =>
      selectedVariables.some((v) => v.column_ids?.some((id) => id === c.id)),
    ) ?? [];
  const ready =
    !!current &&
    !dirty &&
    !!selectedTable &&
    !!dictionary?.revision &&
    profile?.state === 'current';
  return (
    <section
      className="diagnostic-workspace"
      aria-label="Diagnósticos por análisis"
    >
      <header>
        <h3>¿Qué quieres conocer de tus datos?</h3>
        <p>
          Crea varios análisis con sus propias variables. Puedes empezar sin
          tesis, documento ni hipótesis y guardar lo que aún no sabes.
        </p>
      </header>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <label className="rp-field">
        Análisis guardado
        <select
          disabled={busy}
          value={current?.id ?? ''}
          onChange={(e) => void choose(e.target.value)}
        >
          <option value="">Nuevo análisis</option>
          {intents.map((i) => (
            <option key={i.id} value={i.id}>
              {i.question.value || 'Borrador sin nombre'} · revisión{' '}
              {i.revision}
            </option>
          ))}
        </select>
      </label>
      <div className="diagnostic-actions">
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() => void choose('')}
        >
          Nuevo análisis
        </button>
        <button
          className="rp-secondary"
          disabled={busy}
          onClick={() => {
            const saved = sessionStorage.getItem(key);
            if (saved) {
              try {
                setDraft(JSON.parse(saved));
                setMessage(
                  'Borrador local recuperado; revísalo antes de guardar.',
                );
              } catch {
                setError('No se pudo leer el borrador.');
              }
            } else setMessage('No hay un borrador local pendiente.');
          }}
        >
          Recuperar borrador local
        </button>
      </div>
      <fieldset disabled={busy}>
        <legend>1. Pregunta y datos</legend>
        <label className="rp-field">
          Nombre o pregunta del análisis
          <input
            value={draft.question ?? ''}
            maxLength={2000}
            placeholder="Por ejemplo: describir ventas o comparar dos mediciones"
            onChange={(e) => update({ question: e.target.value })}
          />
        </label>
        <label className="rp-field">
          ¿Qué deseas hacer?
          <select
            value={draft.kind ?? 'unknown'}
            onChange={(e) => {
              const kind = e.target.value as Changes['kind'];
              update({
                kind,
                estimand: kind === 'descriptive' ? 'summary' : 'unknown',
                alternative: 'unspecified',
                paired_columns: null,
                group_column_id: null,
              });
            }}
          >
            <option value="descriptive">Describir datos</option>
            <option value="association">Explorar una relación</option>
            <option value="comparison">Comparar grupos o mediciones</option>
            <option value="reliability">Revisar ítems de un instrumento</option>
            <option value="unknown">Todavía no lo sé</option>
          </select>
        </label>
        <label className="rp-field">
          Tabla de este análisis
          <select
            value={draft.dataset_id ?? ''}
            onChange={(e) => {
              setDictionary(null);
              setProfile(null);
              update({
                dataset_id: e.target.value || null,
                variable_ids: [],
                roles: [],
                group_column_id: null,
                paired_columns: null,
                identifier_column_id: null,
                observations: 'unknown',
                linkage: 'unknown',
              });
            }}
          >
            <option value="">Elegir tabla</option>
            {tables.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} · {t.row_count} filas
              </option>
            ))}
          </select>
        </label>
        <p>
          Una tabla importada o derivada aporta todas sus filas. Si las
          mediciones están en tablas distintas, revisa en Datos si pueden
          combinarse por identificadores; no se emparejan por el orden.
        </p>
        <div className="diagnostic-options">
          {dictionary?.variables.map((v) => (
            <label key={v.id}>
              <input
                type="checkbox"
                checked={draft.variable_ids?.includes(v.id) ?? false}
                onChange={(e) =>
                  update({
                    variable_ids: e.target.checked
                      ? [...(draft.variable_ids ?? []), v.id]
                      : draft.variable_ids?.filter((id) => id !== v.id),
                    roles: [],
                    paired_columns: null,
                    group_column_id: null,
                  })
                }
              />
              {v.name.value ?? 'Variable sin nombre'} · escala{' '}
              {v.measurement_scale?.value === 'unknown'
                ? 'pendiente'
                : v.measurement_scale?.value}
              {!v.measurement_scale?.confirmation && ' (sin confirmar)'}
            </label>
          ))}
        </div>
        <button
          type="button"
          className="rp-secondary"
          onClick={() => navigateProject(projectId, 'datasets')}
        >
          Revisar tablas y escalas en Datos
        </button>
        <p>
          Los códigos 1, 2 o 3 pueden representar categorías. La escala se
          revisa en Datos antes de obtener diagnósticos numéricos.
        </p>
      </fieldset>
      <fieldset disabled={busy}>
        <legend>2. ¿Qué representan estas observaciones?</legend>
        <label className="rp-field">
          Unidad de observación en este análisis
          <textarea
            value={draft.observational_unit ?? ''}
            maxLength={2000}
            placeholder="Una venta, una persona, una parcela…"
            onChange={(e) => update({ observational_unit: e.target.value })}
          />
        </label>
        <label className="rp-field">
          ¿Cómo reconoces cada entidad y sus repeticiones?
          <textarea
            value={draft.identification ?? ''}
            maxLength={2000}
            placeholder="Por ejemplo, código estable; o cuestionarios anónimos que no se pueden vincular"
            onChange={(e) => update({ identification: e.target.value })}
          />
        </label>
        <label className="rp-field">
          Columna identificadora, si existe
          <select
            value={draft.identifier_column_id ?? ''}
            onChange={(e) =>
              update({ identifier_column_id: e.target.value || null })
            }
          >
            <option value="">Sin identificar / no existe</option>
            {selectedTable?.columns.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {draft.kind !== 'descriptive' && (
          <>
            <p>
              Personas distintas pueden pertenecer a una misma familia o aula.
              Medir dos veces no basta para formar pares si no puedes reconocer
              a la misma entidad.
            </p>
            <label className="rp-field">
              Relación entre observaciones de este análisis
              <select
                value={draft.observations ?? 'unknown'}
                onChange={(e) =>
                  update({
                    observations: e.target.value as Changes['observations'],
                    paired_columns: null,
                    group_column_id: null,
                    linkage: 'unknown',
                  })
                }
              >
                <option value="unknown">No está claro todavía</option>
                <option value="independent">
                  Entidades distintas, sin dependencia conocida
                </option>
                <option value="paired">
                  Las mismas entidades en dos mediciones
                </option>
                <option value="repeated">
                  Repeticiones o agrupaciones más complejas
                </option>
              </select>
            </label>
            <label className="rp-field">
              Propósito concreto
              <select
                value={draft.estimand ?? 'unknown'}
                onChange={(e) =>
                  update({ estimand: e.target.value as Changes['estimand'] })
                }
              >
                <option value="unknown">Pendiente de aclarar</option>
                {draft.kind === 'comparison' ? (
                  <>
                    <option value="mean_difference">
                      Comparar promedios de una medida cuantitativa
                    </option>
                    <option value="distribution_difference">
                      Comparar distribuciones o posiciones ordenadas
                    </option>
                  </>
                ) : draft.kind === 'association' ? (
                  <>
                    <option value="linear_association">
                      Explorar una relación lineal entre cantidades
                    </option>
                    <option value="monotonic_association">
                      Explorar si ambas variables tienden a aumentar o disminuir
                      juntas
                    </option>
                  </>
                ) : (
                  <option value="internal_consistency">
                    Explorar consistencia interna de ítems
                  </option>
                )}
              </select>
            </label>
            <label className="rp-field">
              Grupos, mediciones y límites de la comparación
              <textarea
                value={draft.comparison_notes ?? ''}
                maxLength={2000}
                placeholder="Qué se mide, cuándo, en qué grupos y qué dudas quedan sobre su comparación"
                onChange={(e) => update({ comparison_notes: e.target.value })}
              />
            </label>
            {draft.kind === 'comparison' && (
              <>
                <label className="rp-field">
                  Variable de grupo, si corresponde
                  <select
                    value={draft.group_column_id ?? ''}
                    onChange={(e) =>
                      update({ group_column_id: e.target.value || null })
                    }
                  >
                    <option value="">Sin grupo seleccionado</option>
                    {selectedColumns.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="rp-field">
                  ¿Es posible vincular las dos mediciones?
                  <select
                    value={draft.linkage ?? 'unknown'}
                    onChange={(e) =>
                      update({ linkage: e.target.value as Changes['linkage'] })
                    }
                  >
                    <option value="unknown">Aún no se ha verificado</option>
                    <option value="same_row">
                      Cada fila contiene ambas mediciones de la misma entidad
                    </option>
                    <option value="unavailable">
                      No puedo establecer correspondencias entre entidades
                    </option>
                  </select>
                </label>
                {draft.observations === 'paired' && (
                  <div className="diagnostic-options">
                    {(['before_column_id', 'after_column_id'] as const).map(
                      (field, index) => (
                        <label className="rp-field" key={field}>
                          {index ? 'Segunda medición' : 'Primera medición'}
                          <select
                            value={pendingPair[field]}
                            onChange={(e) => {
                              const pair = {
                                ...pendingPair,
                                [field]: e.target.value,
                              };
                              update({
                                paired_columns:
                                  pair.before_column_id && pair.after_column_id
                                    ? pair
                                    : null,
                              });
                              setPendingPair(pair);
                            }}
                          >
                            <option value="">Elegir medición</option>
                            {selectedColumns.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      ),
                    )}
                    <p>
                      Se evaluarán diferencias primera − segunda, solo en pares
                      completos. Unir tablas por ID no demuestra que comparar
                      sus mediciones sea apropiado.
                    </p>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </fieldset>
      <p>
        Guardar como revisado registra tus respuestas para este análisis. Puedes
        mantener dudas explícitas; no confirma normalidad, independencia ni
        aprueba una prueba final.
      </p>
      <div className="diagnostic-actions">
        <button disabled={busy} onClick={() => void save(false)}>
          Guardar borrador
        </button>
        <button
          disabled={busy}
          className="rp-secondary"
          onClick={() => void save(true)}
        >
          Guardar intención revisada
        </button>
      </div>
      {conflict && (
        <aside role="alert">
          <p>
            Otra edición guardó la revisión {conflict.revision}. Tu borrador
            está conservado.
          </p>
          <details>
            <summary>Comparar versión del servidor</summary>
            <pre>{JSON.stringify(fromIntent(conflict), null, 2)}</pre>
          </details>
          <button
            onClick={() => {
              const edits = difference(draft, baseline);
              const latest = fromIntent(conflict);
              setCurrent(conflict);
              setBaseline(latest);
              setDraft({ ...latest, ...edits });
              setConflict(null);
              setMessage('Revisa la combinación y vuelve a guardar.');
            }}
          >
            Recuperar revisión y conservar mis campos editados
          </button>
        </aside>
      )}
      <fieldset disabled={busy}>
        <legend>3. Solicitar diagnósticos</legend>
        <p>
          Se revisarán únicamente las comprobaciones elegidas con todas las
          filas y casos completos conjuntos. Se mostrarán exclusiones, límites y
          gráficos pertinentes. No se ejecutará el contraste final ni se
          enviarán datos a IA.
        </p>
        <div className="diagnostic-options">
          {(Object.keys(checkLabels) as Check[]).map((c) => (
            <label key={c}>
              <input
                type="checkbox"
                checked={checks.includes(c)}
                onChange={(e) =>
                  setChecks(
                    e.target.checked
                      ? [...checks, c]
                      : checks.filter((k) => k !== c),
                  )
                }
              />
              {checkLabels[c]}
            </label>
          ))}
        </div>
        <p>
          Normalidad: Shapiro–Wilk en 3–5000 casos no constantes, por grupo o
          sobre diferencias pareadas. Variabilidad: Brown–Forsythe solo para dos
          grupos independientes revisados. Los checks que no correspondan
          explicarán por qué se omiten.
        </p>
        {dirty && (
          <p className="rp-warning">Guarda tus cambios antes de calcular.</p>
        )}
        {!dictionary?.revision && (
          <p>
            Primero guarda la revisión del diccionario en Datos. No es necesario
            completar todas las variables.
          </p>
        )}
        <p>
          Perfil de la tabla:{' '}
          {profile?.state === 'current'
            ? 'vigente'
            : profile?.state === 'stale'
              ? 'desactualizado'
              : 'pendiente'}
          .
        </p>
        <div className="diagnostic-actions">
          <button
            className="rp-secondary"
            disabled={!selectedTable || !dictionary?.revision}
            onClick={() =>
              void work(async () => {
                setProfile(await dataApi.compute(projectId, selectedTable!));
                if (current)
                  setHistory(await api.history(projectId, current.id));
                setMessage(
                  'Perfil actualizado con todas las filas. Ya puedes solicitar los diagnósticos elegidos.',
                );
              })
            }
          >
            Actualizar perfil de la tabla
          </button>
          <button
            disabled={!ready || !checks.length}
            onClick={() =>
              void work(async () => {
                await api.compute(projectId, {
                  intent_id: current!.id,
                  intent_revision: current!.revision,
                  dataset_id: selectedTable!.id,
                  dataset_revision: selectedTable!.revision,
                  checks:
                    checks as import('../../../shared/contracts/generated/v2/DiagnosticRequest').DiagnosticRequest['checks'],
                  confirm: true,
                });
                setHistory(await api.history(projectId, current!.id));
                setMessage(
                  'Diagnóstico guardado. Revisa los conteos y las advertencias.',
                );
              })
            }
          >
            Calcular diagnósticos seleccionados
          </button>
        </div>
      </fieldset>
      {history.length > 0 && (
        <section aria-label="Historial de diagnósticos">
          <h4>Evidencia de este análisis ({history.length})</h4>
          {[...history].reverse().map((d) => (
            <DiagnosticEvidence key={d.id} value={d} />
          ))}
        </section>
      )}
    </section>
  );
}

import { useEffect, useState } from 'react';
import { createDatasetApi, type ResearchDataset } from '../datasets/api';
import {
  createPackageApi,
  type PackageConfiguration,
  type PackageStatus,
  type ResearchPackageSummary,
} from './api';

const packageApi = createPackageApi();
const datasetApi = createDatasetApi();
const roles = [
  'independent',
  'dependent',
  'covariate',
  'descriptive',
  'unknown',
] as const;
const scales = ['nominal', 'ordinal', 'interval', 'ratio', 'unknown'] as const;
const kinds = [
  'association',
  'comparison',
  'prediction',
  'descriptive',
  'unknown',
] as const;
const directions = ['two-sided', 'greater', 'less', 'unspecified'] as const;
const designs = [
  'experimental',
  'quasi_experimental',
  'observational',
  'unknown',
] as const;
const observations = ['independent', 'paired', 'repeated', 'unknown'] as const;

export function ProjectPackage({ projectId }: { projectId: string }) {
  const [status, setStatus] = useState<PackageStatus | null>(null);
  const [config, setConfig] = useState<PackageConfiguration | null>(null);
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [result, setResult] = useState<ResearchPackageSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([packageApi.status(projectId), datasetApi.list(projectId)])
      .then(async ([next, list]) => {
        if (!cancelled) {
          setStatus(next);
          setConfig(next.configuration);
          setDatasets(list);
          setResult(null);
        }
        if (next.state === 'generated' && next.package_id) {
          const current = await packageApi.get(projectId);
          if (!cancelled) setResult(current);
        }
      })
      .catch((caught) => {
        if (!cancelled) setError(String(caught));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function work(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'No se pudo completar la operación.',
      );
    } finally {
      setBusy(false);
    }
  }
  const review = status?.review;
  const selected = datasets.find((item) => item.id === config?.dataset_id);
  const sourceHypotheses = review
    ? [
        ...(review.content.general_hypothesis.value
          ? [
              {
                source: 'general',
                statement: review.content.general_hypothesis.value,
              },
            ]
          : []),
        ...review.content.specific_hypotheses.flatMap((item, index) =>
          item.value
            ? [{ source: `specific:${index}`, statement: item.value }]
            : [],
        ),
      ]
    : [];
  const objectives = review
    ? [
        review.content.general_objective.value,
        ...review.content.specific_objectives.map((item) => item.value),
      ].filter((item): item is string => !!item)
    : [];

  return (
    <section
      className="rp-package"
      aria-label="Preparar investigación para análisis"
    >
      <h2>Preparar investigación para análisis</h2>
      <p>
        Revisa cada relación antes de generar el paquete. Los valores
        desconocidos se envían como advertencias.
      </p>
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
      {!config ? (
        <p>Cargando configuración…</p>
      ) : (
        <>
          <h3>Metodología</h3>
          <label>
            Documento metodológico{' '}
            <select
              value={config.document_id ?? ''}
              onChange={(event) => {
                const id = event.target.value || null;
                setConfig({
                  ...config,
                  document_id: id,
                  variables: [],
                  hypotheses: [],
                });
              }}
            >
              <option value="">Selecciona un documento</option>
              {status?.documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.name} · {doc.review_status} · v
                  {doc.review_version ?? '—'}
                </option>
              ))}
            </select>
          </label>
          {config.document_id &&
            status?.documents.find((doc) => doc.id === config.document_id)
              ?.review_status !== 'reviewed' && (
              <p>Confirma la revisión metodológica antes de guardar.</p>
            )}
          <h3>Dataset</h3>
          <label>
            Dataset activo{' '}
            <select
              value={config.dataset_id ?? ''}
              onChange={(event) =>
                setConfig({
                  ...config,
                  dataset_id: event.target.value || null,
                  variables: config.variables.map((item) => ({
                    ...item,
                    columns: [],
                  })),
                })
              }
            >
              <option value="">Selecciona un dataset</option>
              {datasets
                .filter((item) => item.active)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} ·{' '}
                    {item.source_dataset_id ? 'preparado' : 'original'}
                  </option>
                ))}
            </select>
          </label>
          {selected && (
            <>
              <p>Columnas: {selected.columns.join(', ')}</p>
              <p>
                Filas: {selected.row_count} · Formato: {selected.format}
              </p>
              <label>
                Origen{' '}
                <select
                  value={
                    selected.synthetic == null ? '' : String(selected.synthetic)
                  }
                  disabled={!!selected.source_dataset_id || busy}
                  onChange={(event) =>
                    void work(async () => {
                      await datasetApi.setOrigin!(
                        projectId,
                        selected.id,
                        event.target.value === 'true',
                      );
                      const list = await datasetApi.list(projectId);
                      setDatasets(list);
                      setNotice(
                        'Procedencia guardada. Guarda de nuevo la configuración para confirmar la fuente.',
                      );
                    })
                  }
                >
                  <option value="">Sin declarar</option>
                  <option value="true">Sintético</option>
                  <option value="false">No sintético</option>
                </select>
              </label>
              {selected.source_dataset_id && (
                <p>
                  Procedencia heredada del dataset original{' '}
                  {selected.source_dataset_id}.
                </p>
              )}
            </>
          )}
          <div className="rp-actions">
            <label>
              Diseño{' '}
              <select
                value={config.design}
                onChange={(event) =>
                  setConfig({
                    ...config,
                    design: event.target
                      .value as PackageConfiguration['design'],
                  })
                }
              >
                {designs.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              Observaciones{' '}
              <select
                value={config.observations}
                onChange={(event) =>
                  setConfig({
                    ...config,
                    observations: event.target
                      .value as PackageConfiguration['observations'],
                  })
                }
              >
                {observations.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Notas de muestreo{' '}
            <textarea
              value={config.sampling_notes}
              onChange={(event) =>
                setConfig({ ...config, sampling_notes: event.target.value })
              }
            />
          </label>
          <h3>Variables y columnas</h3>
          {review?.content.variables.map((variable) => {
            const existing = config.variables.find(
              (item) => item.variable_id === variable.id,
            );
            const link = existing ?? {
              variable_id: variable.id,
              columns: [],
              role: 'unknown' as const,
              measurement_scale: 'unknown' as const,
            };
            const update = (next: typeof link) =>
              setConfig({
                ...config,
                variables: [
                  ...config.variables.filter(
                    (item) => item.variable_id !== variable.id,
                  ),
                  next,
                ],
              });
            return (
              <fieldset key={variable.id}>
                <legend>{variable.name.value ?? 'Variable sin nombre'}</legend>
                <p>
                  Rol revisado: {variable.role.value ?? 'desconocido'} · Escala
                  revisada: {variable.measurement_scale.value ?? 'desconocida'}
                </p>
                <label>
                  Rol confirmado{' '}
                  <select
                    value={link.role}
                    onChange={(event) =>
                      update({
                        ...link,
                        role: event.target.value as typeof link.role,
                      })
                    }
                  >
                    {roles.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Escala confirmada{' '}
                  <select
                    value={link.measurement_scale}
                    onChange={(event) =>
                      update({
                        ...link,
                        measurement_scale: event.target
                          .value as typeof link.measurement_scale,
                      })
                    }
                  >
                    {scales.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <p>Columnas asociadas:</p>
                {selected?.columns.map((column) => (
                  <label key={column}>
                    <input
                      type="checkbox"
                      checked={link.columns.includes(column)}
                      onChange={(event) =>
                        update({
                          ...link,
                          columns: event.target.checked
                            ? [...link.columns, column]
                            : link.columns.filter((item) => item !== column),
                        })
                      }
                    />
                    {column}
                  </label>
                ))}
              </fieldset>
            );
          })}
          <h3>Hipótesis y objetivos</h3>
          {sourceHypotheses.map(({ source, statement }) => {
            const existing = config.hypotheses.find(
              (item) => item.source === source,
            );
            const link = existing ?? {
              id: crypto.randomUUID(),
              source,
              objective: '',
              variable_ids: [],
              kind: 'unknown' as const,
              alternative: 'unspecified' as const,
              null_statement: null,
            };
            const update = (next: typeof link) =>
              setConfig({
                ...config,
                hypotheses: [
                  ...config.hypotheses.filter((item) => item.source !== source),
                  next,
                ],
              });
            return (
              <fieldset key={source}>
                <legend>
                  {source}: {statement}
                </legend>
                <label>
                  Objetivo correspondiente{' '}
                  <select
                    value={link.objective}
                    onChange={(event) =>
                      update({ ...link, objective: event.target.value })
                    }
                  >
                    <option value="">Selecciona un objetivo</option>
                    {objectives.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
                <p>Variables participantes:</p>
                {review?.content.variables.map((variable) => (
                  <label key={variable.id}>
                    <input
                      type="checkbox"
                      checked={link.variable_ids.includes(variable.id)}
                      onChange={(event) =>
                        update({
                          ...link,
                          variable_ids: event.target.checked
                            ? [...link.variable_ids, variable.id]
                            : link.variable_ids.filter(
                                (item) => item !== variable.id,
                              ),
                        })
                      }
                    />
                    {variable.name.value}
                  </label>
                ))}
                <label>
                  Tipo{' '}
                  <select
                    value={link.kind}
                    onChange={(event) =>
                      update({
                        ...link,
                        kind: event.target.value as typeof link.kind,
                      })
                    }
                  >
                    {kinds.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Dirección{' '}
                  <select
                    value={link.alternative}
                    onChange={(event) =>
                      update({
                        ...link,
                        alternative: event.target
                          .value as typeof link.alternative,
                      })
                    }
                  >
                    {directions.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Hipótesis nula, si está disponible{' '}
                  <input
                    value={link.null_statement ?? ''}
                    onChange={(event) =>
                      update({
                        ...link,
                        null_statement: event.target.value || null,
                      })
                    }
                  />
                </label>
              </fieldset>
            );
          })}
          <div className="rp-actions">
            <button
              disabled={busy}
              onClick={() =>
                void work(async () => {
                  const saved = await packageApi.save(projectId, config);
                  setConfig(saved);
                  const next = await packageApi.status(projectId);
                  setStatus(next);
                  if (next.state !== 'generated') setResult(null);
                  setNotice('Configuración guardada.');
                })
              }
            >
              Guardar vinculaciones
            </button>
            <button
              className="rp-secondary"
              disabled={busy}
              onClick={() =>
                void work(async () => {
                  const next = await packageApi.validate(projectId);
                  setStatus(next);
                  if (next.state !== 'generated') setResult(null);
                  setNotice('Validación completada.');
                })
              }
            >
              Validar investigación
            </button>
            <button
              disabled={busy || !!status?.errors.length}
              onClick={() =>
                void work(async () => {
                  const built = await packageApi.build(projectId);
                  setResult(built);
                  setStatus(await packageApi.status(projectId));
                  setNotice('Paquete generado y validado.');
                })
              }
            >
              Generar paquete de investigación
            </button>
          </div>
          {busy && <p role="status">Procesando…</p>}
          {status && (
            <div>
              <h3>Validación: {status.state}</h3>
              {status.state === 'incomplete' && (
                <p>
                  Completa las fuentes y vinculaciones antes de generar el
                  paquete.
                </p>
              )}
              {status.state === 'stale' && (
                <p>Revisa los cambios y vuelve a generar el paquete.</p>
              )}
              {status.errors.map((item) => (
                <p className="rp-error" key={item}>
                  {item}
                </p>
              ))}
              {status.warnings.map((item) => (
                <p key={item}>Advertencia: {item}</p>
              ))}
            </div>
          )}
          {status?.state === 'generated' && result && (
            <div aria-label="Preparación para Statistics">
              <p>
                Paquete vigente: {result.id} · versión del contrato: 1.0.0 ·{' '}
                {result.variables.length} variables · {result.hypotheses.length}{' '}
                hipótesis
              </p>
              <p>
                Dataset seleccionado: {selected?.name ?? result.dataset.id} ·{' '}
                {result.dataset.format} · {result.dataset.row_count} filas
              </p>
              <h3>Hipótesis disponibles</h3>
              <ul>
                {result.hypotheses.map((item) => (
                  <li key={item.id}>
                    {item.statement} (ID: {item.id})
                  </li>
                ))}
              </ul>
              {result.pending_questions.map((item) => (
                <p key={item}>Aclaración pendiente: {item}</p>
              ))}
              <p role="status">
                El paquete de investigación está preparado. La integración con
                Statistics está pendiente.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

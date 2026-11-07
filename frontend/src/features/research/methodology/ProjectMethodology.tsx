import { useCallback, useState } from 'react';
import { useReadResource } from '../projects/useReadResource';
import { createDocumentApi } from '../documents/api';
import { createMethodologyApi } from './api';
import { ReviewEditor } from './ReviewEditor';
import { DocumentMethodology } from './DocumentMethodology';
import { navigateWorkspace, navigateProject } from '../projects/navigation';
import {
  Guidance,
  SectionColumns,
  SupportPanel,
} from '../projects/SectionLayout';
import { EmptyState } from '../projects/ProjectShell';
const documentsApi = createDocumentApi();
const api = createMethodologyApi();
const findingLabels: Record<string, string> = {
  independent: 'Independiente',
  dependent: 'Dependiente',
  covariate: 'Covariable',
  descriptive: 'Descriptiva',
  unknown: 'Por confirmar',
  nominal: 'Nominal',
  ordinal: 'Ordinal',
  interval: 'De intervalo',
  ratio: 'De razón',
};
const findingLabel = (value: string | null) =>
  value ? (findingLabels[value] ?? value) : 'Por confirmar';
export function ProjectMethodology({
  projectId,
  view,
  item,
  active = true,
}: {
  projectId: string;
  view?: string | null;
  item?: string | null;
  active?: boolean;
}) {
  const tab = ['variables', 'hypotheses'].includes(view ?? '')
    ? view!
    : 'objectives';
  const [busy, setBusy] = useState(false);
  const [actionError, setError] = useState('');
  const loadDocuments = useCallback(
    () => documentsApi.list(projectId),
    [projectId],
  );
  const documentResource = useReadResource(loadDocuments, active);
  const documents = documentResource.data ?? [];
  const selected = documents.find((d) => d.id === item) ?? documents[0];
  const documentId = selected?.id;
  const loadReview = useCallback(
    () =>
      documentId
        ? api.reviewStatus!(projectId, documentId)
        : Promise.resolve(null),
    [projectId, documentId],
  );
  const reviewResource = useReadResource(
    loadReview,
    !!documentId && (active || view === 'edit'),
  );
  const loadText = useCallback(
    () =>
      documentId
        ? documentsApi.extraction(projectId, documentId)
        : Promise.resolve(null),
    [projectId, documentId],
  );
  const textResource = useReadResource(loadText, active && !!documentId);
  const review = reviewResource.data;
  const setReview = reviewResource.setData;
  const hasText =
    textResource.data?.status === 'completed' &&
    !!textResource.data.text.trim();
  const loading = documentResource.loading || reviewResource.loading;
  const error = actionError || documentResource.error || reviewResource.error;
  const extractionError = textResource.error
    ? 'No se pudo verificar el texto extraído. La revisión guardada sigue disponible.'
    : '';
  async function update(create: boolean) {
    if (!selected || busy) return;
    setBusy(true);
    setError('');
    try {
      const next = create
        ? await api.createReview!(projectId, selected.id)
        : await api.confirmReview!(projectId, selected.id, review!.version);
      setReview(next);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'No se pudo guardar la revisión.',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Metodología de investigación">
      <SectionColumns
        support={
          <SupportPanel
            title="Antes de confirmar"
            projectId={projectId}
            destination="assistant"
            action="Consultar al asistente"
          >
            <Guidance
              items={[
                'Verifica los objetivos con tu documento',
                'Comprueba variables, dimensiones y definiciones',
                'Revisa hipótesis y diseño de estudio',
              ]}
            />
          </SupportPanel>
        }
      >
        <div className="rp-surface rp-methodology-surface">
          <div className="rp-section-heading">
            <h2>Estructura metodológica</h2>
            {review && (
              <span className="rp-badge">
                {review.review_status === 'reviewed'
                  ? 'Confirmada'
                  : 'Pendiente de confirmación'}
              </span>
            )}
          </div>
          {error && (
            <p className="rp-error" role="alert">
              {error}
            </p>
          )}
          {extractionError && <p className="rp-warning">{extractionError}</p>}
          {loading && <p role="status">Cargando revisión metodológica…</p>}
          {error && (
            <button
              className="rp-secondary"
              onClick={() => {
                setError('');
                documentResource.reload();
                reviewResource.reload();
                textResource.reload();
              }}
            >
              Reintentar metodología
            </button>
          )}
          {!loading && !documents.length && !error && (
            <>
              <EmptyState title="Primero añade un documento">
                Carga tu proyecto de tesis en Documentos. Aquí podrás crear o
                revisar su metodología.
              </EmptyState>
              <button onClick={() => navigateProject(projectId, 'documents')}>
                Ir a Documentos
              </button>
            </>
          )}
          {selected && (
            <>
              {!loading && !review && !error && (
                <div className="rp-surface">
                  <h3>Revisión por completar</h3>
                  <p>
                    Puedes registrar la metodología manualmente y confirmar sus
                    campos antes de usarla.
                  </p>
                  <button disabled={busy} onClick={() => void update(true)}>
                    Crear revisión metodológica
                  </button>
                </div>
              )}
              {review &&
                (view === 'edit' ? (
                  <>
                    <button
                      className="rp-link"
                      onClick={() =>
                        navigateWorkspace(
                          projectId,
                          'methodology',
                          'summary',
                          selected.id,
                        )
                      }
                    >
                      ← Volver a la revisión
                    </button>
                    <ReviewEditor
                      key={selected.id}
                      initialEditing
                      review={review}
                      projectId={projectId}
                      documentId={selected.id}
                      api={api}
                      onChange={(next) => {
                        setReview(next);
                        navigateWorkspace(
                          projectId,
                          'methodology',
                          'summary',
                          selected.id,
                        );
                      }}
                    />
                  </>
                ) : (
                  <>
                    <nav
                      className="rp-segment"
                      aria-label="Elementos metodológicos"
                    >
                      {[
                        ['objectives', 'Objetivos'],
                        ['variables', 'Variables y dimensiones'],
                        ['hypotheses', 'Hipótesis'],
                      ].map(([id, label]) => (
                        <button
                          key={id}
                          aria-current={tab === id ? 'page' : undefined}
                          onClick={() =>
                            navigateWorkspace(
                              projectId,
                              'methodology',
                              id,
                              selected.id,
                            )
                          }
                        >
                          {label}
                        </button>
                      ))}
                    </nav>
                    <div className="rp-methodology-summary">
                      <article
                        hidden={tab !== 'objectives'}
                        className="rp-methodology-reading"
                      >
                        <div className="rp-academic-field">
                          <b>Objetivo general</b>
                          <p>
                            {review.content.general_objective.value ??
                              'Objetivo general pendiente'}
                          </p>
                        </div>
                        <h3>Objetivos específicos</h3>
                        <ol className="rp-academic-list">
                          {review.content.specific_objectives.map((f, i) => (
                            <li key={i}>{f.value ?? 'Pendiente'}</li>
                          ))}
                        </ol>
                      </article>
                      <article
                        hidden={tab !== 'hypotheses'}
                        className="rp-methodology-reading"
                      >
                        <h3>Hipótesis</h3>
                        <p>
                          {review.content.general_hypothesis.value ??
                            'Hipótesis general pendiente'}
                        </p>
                        <ul>
                          {review.content.specific_hypotheses.map((f, i) => (
                            <li key={i}>{f.value ?? 'Pendiente'}</li>
                          ))}
                        </ul>
                      </article>
                    </div>
                    <article
                      hidden={tab !== 'variables'}
                      className="rp-methodology-reading"
                    >
                      <h3>Variables y dimensiones</h3>
                      {review.content.variables.length ? (
                        review.content.variables.map((v) => (
                          <div className="rp-variable-summary" key={v.id}>
                            <strong>
                              {v.name.value ?? 'Variable pendiente'}
                            </strong>
                            <p>
                              {findingLabel(v.role.value)} ·{' '}
                              {findingLabel(v.measurement_scale.value)}
                            </p>
                            <ul>
                              {v.dimensions.map((f, i) => (
                                <li key={i}>
                                  {f.value ?? 'Dimensión pendiente'}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))
                      ) : (
                        <p>No se han registrado variables.</p>
                      )}
                    </article>
                    {!!review.pending_fields.length && (
                      <p className="rp-warning">
                        Hay {review.pending_fields.length} campos pendientes.
                        Revísalos en el editor antes de confirmar.
                      </p>
                    )}
                    <div className="rp-actions">
                      <button
                        className={
                          review.review_status === 'reviewed'
                            ? ''
                            : 'rp-secondary'
                        }
                        onClick={() =>
                          navigateWorkspace(
                            projectId,
                            'methodology',
                            'edit',
                            selected.id,
                          )
                        }
                      >
                        Editar metodología
                      </button>
                      {review.review_status !== 'reviewed' && (
                        <button
                          disabled={busy}
                          onClick={() => void update(false)}
                        >
                          Confirmar revisión
                        </button>
                      )}
                    </div>
                    <details className="rp-technical">
                      <summary>Diseño, procedencia y versión</summary>
                      <p>
                        Diseño:{' '}
                        {review.content.research_design.value ?? 'Pendiente'}
                      </p>
                      <p>
                        Observaciones:{' '}
                        {review.content.observation_design.value ?? 'Pendiente'}
                      </p>
                      <p>
                        Origen: {review.origin} · Versión {review.version}
                      </p>
                      <p>Documento: {selected.id}</p>
                      {review.content.clarifications.map((f, i) => (
                        <p key={i}>{f.value}</p>
                      ))}
                    </details>
                  </>
                ))}
              <details
                className="rp-technical"
                open={documents.length > 1 ? true : undefined}
              >
                <summary>Fuente metodológica: {selected.name}</summary>
                <label className="rp-field">
                  Fuente metodológica
                  <select
                    value={selected.id}
                    disabled={busy}
                    onChange={(e) =>
                      navigateWorkspace(
                        projectId,
                        'methodology',
                        'summary',
                        e.target.value,
                      )
                    }
                  >
                    {documents.map((d) => (
                      <option value={d.id} key={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
              </details>
              <details className="rp-technical">
                <summary>Extracción metodológica con IA</summary>
                <DocumentMethodology
                  key={selected.id}
                  projectId={projectId}
                  documentId={selected.id}
                  hasText={hasText}
                  reviewMode="external"
                />
              </details>
            </>
          )}
        </div>
      </SectionColumns>
    </section>
  );
}

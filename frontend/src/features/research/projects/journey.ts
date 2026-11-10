import { createDatasetApi, DatasetApiError } from '../datasets/api';
import { createAnalysisApi } from '../analysis/api';
import { createPackageApi } from '../packages/api';
import { recordIsCurrent } from '../analysis/analysisPresentation';
import type { Section } from './navigation';
import { createContextApi } from '../context/api';
import { facts } from '../context/draft';
import { createSourcesApi } from '../sources/api';
import { createDataApi } from '../data/api';

const datasets = createDatasetApi();
const analysis = createAnalysisApi();
const packages = createPackageApi();
const contexts = createContextApi();
const files = createSourcesApi();
const workspace = createDataApi();
type State = 'Pendiente' | 'En progreso' | 'Completado' | 'No verificable';
export interface JourneyStep {
  name: string;
  state: State;
  evidence: string;
  section: Section;
  view?: string;
}
export async function loadJourney(projectId: string): Promise<JourneyStep[]> {
  const [data, plans, sources, context, imported, summary] =
    await Promise.allSettled([
      datasets.list(projectId),
      analysis.plans(projectId),
      packages.status(projectId),
      contexts.get(projectId),
      files.files(projectId),
      workspace.summary(projectId),
    ]);
  const importedFiles = imported.status === 'fulfilled' ? imported.value : [];
  const importedTables = importedFiles.flatMap((file) =>
    file.sheets.filter((sheet) => sheet.state === 'ready'),
  );
  const pendingSheets = importedFiles.flatMap((file) =>
    file.sheets.filter(
      (sheet) => sheet.state === 'pending' || sheet.state === 'error',
    ),
  );
  const uploadFailed =
    data.status === 'rejected' || imported.status === 'rejected';
  const active =
    data.status === 'fulfilled' ? data.value.find((d) => d.active) : undefined;
  let profile: State =
    data.status === 'rejected'
      ? 'No verificable'
      : active
        ? 'En progreso'
        : 'Pendiente';
  if (active) {
    try {
      await datasets.getEda(projectId, active.id);
      profile = 'Completado';
    } catch (error) {
      profile =
        error instanceof DatasetApiError && error.status === 404
          ? 'Pendiente'
          : 'No verificable';
    }
  }
  if (imported.status === 'rejected') profile = 'No verificable';
  else if (importedFiles.length) profile = 'En progreso';
  const review = summary.status === 'fulfilled' ? summary.value : null;
  if (importedFiles.length && summary.status === 'rejected')
    profile = 'No verificable';
  const known = plans.status === 'fulfilled' && sources.status === 'fulfilled';
  const current = known
    ? plans.value.filter((r) => recordIsCurrent(r, sources.value))
    : [];
  const completed = current.some((r) => r.result?.status === 'completed');
  const proposed = current.some(
    (r) => r.plan.status === 'proposed' || r.plan.status === 'approved',
  );
  const approved = current.some((r) => r.approved_at);
  const contextFacts =
    context.status === 'fulfilled' ? facts(context.value) : [];
  const knownFacts = contextFacts.filter(
    ([path, f]) =>
      path !== '/observations' &&
      f.value != null &&
      f.value !== '' &&
      f.value !== 'unknown',
  );
  const confirmed = knownFacts.filter(([, f]) => f.confirmation).length;
  return [
    {
      name: 'Contexto necesario',
      state:
        context.status === 'rejected'
          ? 'No verificable'
          : knownFacts.length
            ? 'En progreso'
            : 'Pendiente',
      evidence:
        context.status === 'rejected'
          ? 'Error al consultar el contexto guardado. Reintenta para comprobar su estado.'
          : knownFacts.length
            ? `${knownFacts.length} campos con información guardada; ${confirmed} confirmados por ti. ${context.value.pending_questions.map((q) => q.question).join(' ')} La información necesaria depende del análisis; puedes continuar con Datos.`
            : 'Todavía no hay información de investigación guardada. Empieza con una pregunta u objetivo, o explora Datos.',
      section: 'context',
    },
    {
      name: 'Cargar datos',
      state: uploadFailed
        ? 'No verificable'
        : importedFiles.length
          ? importedTables.length && !pendingSheets.length
            ? 'Completado'
            : 'En progreso'
          : active
            ? 'Completado'
            : data.value.length
              ? 'En progreso'
              : 'Pendiente',
      evidence: uploadFailed
        ? 'Error al cargar los datos. Reintenta para comprobar su estado.'
        : importedFiles.length
          ? `${importedFiles.length} archivos originales guardados · ${importedTables.length} tablas listas · ${pendingSheets.length} hojas pendientes. La carga no acredita revisión de los datos.`
          : active
            ? `Archivo activo: ${active.name} · ${active.row_count} filas.`
            : data.value.length
              ? 'Hay archivos guardados; selecciona uno activo.'
              : 'Todavía no hay archivos guardados.',
      section: 'datasets',
    },
    {
      name: 'Revisar datos',
      state: profile,
      evidence:
        profile === 'No verificable'
          ? 'Error al consultar el perfil de datos.'
          : importedFiles.length
            ? review
              ? `${review.tables.length} tablas disponibles · ${review.tables.filter((t) => t.profile === 'current').length} perfiles vigentes · ${review.tables.filter((t) => t.profile === 'stale').length} perfiles desactualizados · ${review.tables.reduce((n, t) => n + t.confirmed_variables, 0)} variables confirmadas · ${review.derived} derivados · ${review.tables.filter((t) => !t.usable).length} fuentes desactualizadas. ${review.tables.filter((t) => t.profile === 'absent').length} perfiles pendientes; ${review.tables.reduce((n, t) => n + t.variables - t.confirmed_variables, 0)} variables por revisar. Preparar es opcional. La importación o el perfil no completan la revisión.`
              : 'No se pudo consultar la evidencia de revisión.'
            : profile === 'Completado'
              ? 'Existe un perfil exploratorio guardado del archivo activo. Revisa sus hallazgos.'
              : 'Consulta y genera el perfil del archivo activo para revisar calidad y columnas.',
      section: 'datasets',
      view: importedFiles.length ? 'review' : 'quality',
    },
    {
      name: 'Revisar propuesta',
      state: !known
        ? 'No verificable'
        : approved
          ? 'Completado'
          : proposed || current.length
            ? 'En progreso'
            : 'Pendiente',
      evidence: !known
        ? 'Error al comprobar propuestas o vigencia de fuentes.'
        : proposed
          ? 'Existe una propuesta vigente guardada; su existencia no acredita que la hayas revisado.'
          : 'En Análisis puedes guardar una pregunta, elegir una tabla y solicitar diagnósticos sin documento ni hipótesis. Las nuevas propuestas y ejecución corresponden a S04B.',
      section: 'analysis',
      view: 'plan',
    },
    {
      name: 'Aprobar y ejecutar',
      state: !known
        ? 'No verificable'
        : completed
          ? 'Completado'
          : approved
            ? 'En progreso'
            : 'Pendiente',
      evidence: !known
        ? 'No se pudo comprobar la ejecución.'
        : completed
          ? 'Existe un resultado completado y vigente.'
          : approved
            ? 'Existe aprobación guardada; aún falta un resultado completado vigente.'
            : 'Revisa y aprueba una propuesta del recorrido existente antes de ejecutar.',
      section: 'analysis',
      view: 'execution',
    },
    {
      name: 'Comprender resultados',
      state: !known
        ? 'No verificable'
        : completed
          ? 'En progreso'
          : 'Pendiente',
      evidence: !known
        ? 'No se pudo comprobar la disponibilidad de resultados vigentes.'
        : completed
          ? 'Hay resultados disponibles para consultar. La aplicación no verifica tu comprensión.'
          : 'Los resultados aparecerán después de una ejecución completada.',
      section: 'results',
    },
  ];
}

export function nextJourneyStep(steps: JourneyStep[]): JourneyStep | undefined {
  return (
    steps.find((s) => s.state === 'No verificable') ??
    (steps[0]?.state === 'Pendiente' ? steps[0] : undefined) ??
    steps.slice(1).find((s) => s.state !== 'Completado') ??
    steps[0]
  );
}

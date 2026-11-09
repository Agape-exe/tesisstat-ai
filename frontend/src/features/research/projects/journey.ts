import { createDatasetApi, DatasetApiError } from '../datasets/api';
import { createAnalysisApi } from '../analysis/api';
import { createPackageApi } from '../packages/api';
import { recordIsCurrent } from '../analysis/analysisPresentation';
import type { Section } from './navigation';

const datasets = createDatasetApi();
const analysis = createAnalysisApi();
const packages = createPackageApi();
type State = 'Pendiente' | 'En progreso' | 'Completado' | 'No verificable';
export interface JourneyStep {
  name: string;
  state: State;
  evidence: string;
  section: Section;
  view?: string;
}
export async function loadJourney(projectId: string): Promise<JourneyStep[]> {
  const [data, plans, sources] = await Promise.allSettled([
    datasets.list(projectId),
    analysis.plans(projectId),
    packages.status(projectId),
  ]);
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
  const known = plans.status === 'fulfilled' && sources.status === 'fulfilled';
  const current = known
    ? plans.value.filter((r) => recordIsCurrent(r, sources.value))
    : [];
  const completed = current.some((r) => r.result?.status === 'completed');
  const proposed = current.some(
    (r) => r.plan.status === 'proposed' || r.plan.status === 'approved',
  );
  const approved = current.some((r) => r.approved_at);
  return [
    {
      name: 'Contexto necesario',
      state: 'Pendiente',
      evidence:
        'La confirmación del nuevo contexto aún no está disponible. Puedes continuar con Datos.',
      section: 'context',
    },
    {
      name: 'Cargar datos',
      state:
        data.status === 'rejected'
          ? 'No verificable'
          : active
            ? 'Completado'
            : data.value.length
              ? 'En progreso'
              : 'Pendiente',
      evidence:
        data.status === 'rejected'
          ? 'Error al cargar los datos. Reintenta para comprobar su estado.'
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
          : profile === 'Completado'
            ? 'Existe un perfil exploratorio guardado del archivo activo. Revisa sus hallazgos.'
            : 'Consulta y genera el perfil del archivo activo para revisar calidad y columnas.',
      section: 'datasets',
      view: 'quality',
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
          : 'El análisis actual requiere la preparación documental y vinculaciones del recorrido existente.',
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

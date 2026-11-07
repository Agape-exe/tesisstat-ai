import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ProjectResults } from './ProjectResults';
import { ProjectReports } from './ProjectReports';
import { ProjectWorkspace } from '../projects/ProjectWorkspace';
import { useProjectRoute, navigateProject } from '../projects/navigation';
import { ProjectDatasets } from '../datasets/ProjectDatasets';
import { DatasetApiError, type DatasetApi } from '../datasets/api';
const finding = (value: string) => ({
  value,
  kind: 'manual' as const,
  evidence: [],
});
const dataset = {
  id: 'dataset',
  project_id: 'project',
  name: 'sintetico.csv',
  format: 'csv' as const,
  size: 50,
  row_count: 4,
  column_count: 2,
  columns: ['horas', 'rendimiento'],
  sheet: null,
  uploaded_at: '2026-11-06T12:00:00Z',
  active: true,
  warnings: [],
  synthetic: true,
};
const review = {
  project_id: 'project',
  document_id: 'doc',
  origin: 'manual' as const,
  review_status: 'reviewed' as const,
  version: 2,
  updated_at: '2026-11-06T12:00:00Z',
  reviewed_at: '2026-11-06T12:00:00Z',
  pending_fields: [],
  content: {
    title: finding('Tesis sintética'),
    general_problem: finding('Problema ficticio'),
    general_objective: finding('Relacionar horas y rendimiento'),
    specific_objectives: [],
    general_hypothesis: finding('Existe asociación'),
    specific_hypotheses: [],
    research_design: finding('observational'),
    observation_design: finding('independent'),
    additional_methodology: [],
    clarifications: [],
    variables: [
      {
        id: 'v',
        name: finding('Horas'),
        role: finding('independent'),
        measurement_scale: finding('ratio'),
        dimensions: [finding('Tiempo')],
        indicators: [],
        instrument_items: [],
      },
    ],
  },
};
const config = {
  version: 2,
  document_id: 'doc',
  review_version: 2,
  review_hash: 'r',
  dataset_id: 'dataset',
  dataset_hash: 'd',
  design: 'observational',
  observations: 'independent',
  sampling_notes: '',
  updated_at: null,
  variables: [
    {
      variable_id: 'v',
      columns: ['horas'],
      role: 'independent',
      measurement_scale: 'ratio',
    },
  ],
  hypotheses: [
    {
      id: 'h',
      source: 'general',
      objective: 'Relacionar horas y rendimiento',
      variable_ids: ['v'],
      kind: 'association',
      alternative: 'two-sided',
      null_statement: null,
    },
  ],
};
const status = {
  state: 'generated',
  errors: [],
  warnings: [],
  configuration: config,
  documents: [
    {
      id: 'doc',
      name: 'tesis.docx',
      review_status: 'reviewed',
      review_version: 2,
    },
  ],
  dataset,
  review,
  package_id: 'package',
};
const pack = {
  id: 'package',
  schema_version: '1.0.0',
  title: 'Tesis sintética',
  variables: [{ id: 'v', name: 'Horas', columns: ['horas'] }],
  hypotheses: [
    { id: 'h', statement: 'Existe asociación', variable_ids: ['v'] },
  ],
  dataset,
  pending_questions: [],
};
const record = {
  project_id: 'project',
  source_version: 'source',
  proposal_token: 'token',
  created_at: '2026-11-06T12:00:00Z',
  approved_at: '2026-11-06T12:01:00Z',
  invalidated_at: null,
  stale_reason: null,
  executable: true,
  limitation: null,
  plan: {
    schema_version: '1.0.0',
    id: 'plan',
    research_package_id: 'package',
    hypothesis_id: 'h',
    dataset_id: 'dataset',
    status: 'approved',
    technique: 'pearson',
    rationale: 'Asociación entre variables declaradas',
    assumptions_to_check: ['Linealidad'],
    pending_questions: [],
    alpha: 0.05,
  },
  result: {
    schema_version: '1.0.0',
    id: 'result',
    analysis_plan_id: 'plan',
    dataset_id: 'dataset',
    status: 'completed',
    engine_version: 'v1',
    metrics: [{ name: 'r', value: 0.8 }],
    warnings: ['Revisar supuestos'],
    assumptions: [],
    interpretation: 'Interpretación persistida del motor.',
  },
};
function mockApi(
  overrides: {
    sourceFailure?: boolean;
    denied?: boolean;
    stale?: boolean;
  } = {},
) {
  const calls: { url: string; options?: RequestInit }[] = [];
  let saved = structuredClone(review);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      calls.push({ url, options });
      let value: unknown = null;
      if (url.endsWith('/package/status')) {
        if (overrides.sourceFailure)
          return {
            ok: false,
            json: async () => ({ detail: 'Fuentes no disponibles' }),
          };
        value = { ...status, state: overrides.stale ? 'stale' : 'generated' };
      } else if (url.endsWith('/analysis/results')) value = [record];
      else if (url.endsWith('/analysis/plans')) value = [record];
      else if (url.endsWith('/package')) value = pack;
      else if (url.endsWith('/documents'))
        value = [
          {
            id: 'doc',
            project_id: 'project',
            name: 'tesis.docx',
            format: 'docx',
            size: 100,
            uploaded_at: '2026-11-06T12:00:00Z',
          },
        ];
      else if (url.includes('/methodology/review')) {
        if (options?.method === 'PUT') {
          const body = JSON.parse(options.body as string);
          saved = {
            ...saved,
            content: body.content,
            version: saved.version + 1,
          };
        }
        value = saved;
      } else if (url.endsWith('/methodology/status'))
        value = {
          status: 'not_started',
          provider_configured: false,
          draft: null,
          attempts: 0,
        };
      else if (url.includes('/extraction'))
        value = {
          status: 'completed',
          text: 'Documento ficticio',
          character_count: 18,
          warnings: [],
        };
      else if (url.endsWith('/report.pdf'))
        return {
          ok: false,
          json: async () => ({
            detail: overrides.denied
              ? 'La autorización local venció.'
              : 'No disponible',
          }),
        };
      else if (url.endsWith('/datasets')) value = [dataset];
      else if (url.endsWith('/preview'))
        value = { ...dataset, rows: [['1', '2']] };
      else if (url.endsWith('/eda'))
        return {
          ok: false,
          status: 404,
          json: async () => ({ detail: 'Sin EDA guardado' }),
        };
      else value = [];
      return { ok: true, json: async () => value };
    }),
  );
  return calls;
}
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});
function Host() {
  const route = useProjectRoute();
  return (
    <ProjectWorkspace
      projectId="project"
      section={route.section}
      view={route.view}
      item={route.item}
    />
  );
}

it('Results mounts only persisted results, with no preparation form or planning calls', async () => {
  const calls = mockApi();
  render(<ProjectResults projectId="project" />);
  expect(
    await screen.findByText('Interpretación persistida del motor.'),
  ).toBeInTheDocument();
  expect(
    screen.queryByLabelText('Documento metodológico'),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', {
      name: /Generar paquete|Proponer análisis|Ejecutar análisis/,
    }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Mostrar pares autorizados' }),
  ).toBeEnabled();
  expect(
    calls.every((c) => !c.options?.method || c.options.method === 'GET'),
  ).toBe(true);
  expect(calls.some((c) => c.url.endsWith('/analysis/results'))).toBe(true);
});

it('Reports mounts export controls only, without planning, execution or package generation', async () => {
  const calls = mockApi();
  render(<ProjectReports projectId="project" />);
  expect(
    await screen.findByRole('button', { name: 'Descargar informe' }),
  ).toBeEnabled();
  expect(
    screen.getByRole('combobox', { name: 'Formato de descarga' }),
  ).toHaveValue('pdf');
  expect(
    screen.queryByRole('button', {
      name: /Proponer análisis|Ejecutar análisis|Generar paquete/,
    }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByLabelText('Documento metodológico'),
  ).not.toBeInTheDocument();
  expect(
    calls.some(
      (c) =>
        c.url.endsWith('/analysis/plans') ||
        c.url.endsWith('/plan') ||
        c.url.endsWith('/execute'),
    ),
  ).toBe(false);
});

it('respects authorization denial at export without executing statistics', async () => {
  const calls = mockApi({ denied: true });
  render(<ProjectReports projectId="project" />);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Descargar informe' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'La autorización local venció.',
  );
  expect(calls.filter((c) => c.url.endsWith('/report.pdf'))).toHaveLength(1);
  expect(calls.some((c) => c.url.endsWith('/execute'))).toBe(false);
});

it.each(['stale', 'sourceFailure'] as const)(
  'keeps history readable for %s sources and blocks observations and exports',
  async (kind) => {
    mockApi({ [kind]: true });
    const view = render(<ProjectResults projectId="project" />);
    expect(
      await screen.findByText('Interpretación persistida del motor.'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('table')).getByText('0.8'),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Mostrar pares autorizados' }),
    ).not.toBeInTheDocument();
    view.rerender(<ProjectReports projectId="project" />);
    expect(
      await screen.findByRole('button', { name: 'Descargar informe' }),
    ).toBeDisabled();
  },
);

it('Analysis opens a preparation summary and only mounts the link editor when requested', async () => {
  mockApi();
  window.history.replaceState(null, '', '#project=project&section=analysis');
  render(<Host />);
  expect(
    await screen.findAllByText('1 vinculación', { exact: false }),
  ).toHaveLength(2);
  expect(
    screen.queryByLabelText('Documento metodológico'),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Proponer análisis' }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Editar vinculaciones' }));
  expect(
    await screen.findByLabelText('Documento metodológico'),
  ).toBeInTheDocument();
  expect(window.location.hash).toContain('view=links');
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
});

it('Methodology is a review of objectives and variables, with no upload or file list', async () => {
  mockApi();
  window.history.replaceState(null, '', '#project=project&section=methodology');
  render(<Host />);
  expect(
    await screen.findByText('Relacionar horas y rendimiento'),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('heading', { name: 'Variables y dimensiones' }),
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Variables y dimensiones' }),
  );
  expect(
    screen.getByRole('heading', { name: 'Variables y dimensiones' }),
  ).toBeInTheDocument();
  expect(screen.getByText('Tiempo')).toBeInTheDocument();
  expect(
    screen.queryByRole('region', { name: 'Documentos de investigación' }),
  ).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Archivo')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Adjuntar documento' }),
  ).not.toBeInTheDocument();
});

it('retains a saved methodological edit through navigation, Back and remount', async () => {
  mockApi();
  window.history.replaceState(null, '', '#project=project&section=methodology');
  const view = render(<Host />);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Editar metodología' }),
  );
  fireEvent.change(
    await screen.findByRole('textbox', { name: /^Objetivo general/ }),
    {
      target: { value: 'Objetivo actualizado y guardado' },
    },
  );
  fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
  await screen.findByText('Objetivo actualizado y guardado');
  act(() => navigateProject('project', 'results'));
  await screen.findByRole('region', { name: 'Resultados de investigación' });
  act(() => window.history.back());
  await waitFor(() =>
    expect(
      within(
        screen.getByRole('region', { name: 'Metodología de investigación' }),
      ).getByText('Objetivo actualizado y guardado'),
    ).toBeVisible(),
  );
  view.unmount();
  render(<Host />);
  expect(
    await screen.findByText('Objetivo actualizado y guardado'),
  ).toBeVisible();
});

it('separates preview, quality and preparation and retains a transformation draft between views', async () => {
  const api: DatasetApi = {
    list: vi.fn(async () => [dataset]),
    preview: vi.fn(async () => ({ ...dataset, rows: [['1', '2']] })),
    upload: vi.fn(async () => dataset),
    delete: vi.fn(async () => {}),
    activate: vi.fn(async () => dataset),
    getEda: vi.fn(async () => {
      throw new DatasetApiError('Sin EDA', 404);
    }),
    runEda: vi.fn(async () => {
      throw new Error('No solicitado');
    }),
  };
  render(<ProjectDatasets projectId="project" api={api} />);
  await screen.findByText('sintetico.csv');
  expect(
    screen.queryByRole('button', { name: 'Analizar calidad de datos' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Preparar datos' }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Calidad de datos' }));
  expect(
    await screen.findByRole('button', { name: 'Analizar calidad de datos' }),
  ).toBeVisible();
  expect(screen.getByLabelText('Archivo')).not.toBeVisible();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Preparación y transformaciones' }),
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Preparar datos' }),
  );
  expect(
    screen.getByRole('button', { name: 'Agregar operación' }),
  ).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Calidad de datos' }));
  expect(
    screen.queryByRole('button', { name: 'Agregar operación' }),
  ).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Preparación y transformaciones' }),
  );
  expect(
    screen.getByRole('button', { name: 'Agregar operación' }),
  ).toBeVisible();
  expect(api.runEda).not.toHaveBeenCalled();
});

it('restores the default dataset view with Back and the selected quality view with Forward', async () => {
  mockApi();
  window.history.replaceState(null, '', '#project=project&section=datasets');
  render(<Host />);
  await screen.findByText('sintetico.csv');
  fireEvent.click(screen.getByRole('button', { name: 'Calidad de datos' }));
  await screen.findByRole('button', { name: 'Analizar calidad de datos' });
  expect(window.location.hash).toContain('view=quality');
  act(() => window.history.back());
  await waitFor(() => expect(screen.getByRole('table')).toBeVisible());
  expect(
    screen.getByRole('button', { name: 'Archivo y vista previa' }),
  ).toHaveAttribute('aria-current', 'page');
  expect(window.location.hash).not.toContain('view=');
  act(() => window.history.forward());
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Analizar calidad de datos' }),
    ).toBeVisible(),
  );
  expect(window.location.hash).toContain('item=dataset');
});

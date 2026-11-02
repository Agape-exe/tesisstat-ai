import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ProjectPackage } from './ProjectPackage';

afterEach(() => vi.unstubAllGlobals());

it('shows reviewed links, validates and builds an explicitly configured package', async () => {
  const finding = (value: string) => ({ value, kind: 'manual', evidence: [] });
  const config = {
    version: 1,
    document_id: 'doc',
    review_version: 2,
    review_hash: 'a',
    dataset_id: 'data',
    dataset_hash: 'b',
    design: 'unknown',
    observations: 'unknown',
    sampling_notes: '',
    updated_at: null,
    variables: [
      {
        variable_id: 'variable',
        columns: ['score'],
        role: 'unknown',
        measurement_scale: 'unknown',
      },
    ],
    hypotheses: [
      {
        id: 'hypothesis',
        source: 'general',
        objective: 'Describir hábitos',
        variable_ids: ['variable'],
        kind: 'unknown',
        alternative: 'unspecified',
        null_statement: null,
      },
    ],
  };
  const dataset = {
    id: 'data',
    project_id: 'project',
    name: 'ficticio.csv',
    format: 'csv',
    size: 12,
    row_count: 1,
    column_count: 2,
    columns: ['score', 'other'],
    sheet: null,
    uploaded_at: '',
    active: true,
    warnings: [],
    synthetic: true,
    source_dataset_id: null,
  };
  const review = {
    review_status: 'reviewed',
    version: 2,
    content: {
      title: finding('Tesis ficticia'),
      general_objective: finding('Describir hábitos'),
      specific_objectives: [],
      general_hypothesis: finding('Existe relación'),
      specific_hypotheses: [],
      variables: [
        {
          id: 'variable',
          name: finding('Hábitos'),
          role: finding('unknown'),
          measurement_scale: finding('unknown'),
          dimensions: [],
          indicators: [],
          instrument_items: [],
        },
      ],
    },
  };
  const status = {
    state: 'warnings',
    errors: [],
    warnings: ['Confirmar diseño'],
    configuration: config,
    documents: [
      {
        id: 'doc',
        name: 'método.docx',
        review_status: 'reviewed',
        review_version: 2,
      },
    ],
    dataset,
    review,
    package_id: null,
  };
  const calls: string[] = [];
  const savedBodies: string[] = [];
  let built = false;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      calls.push(`${options?.method ?? 'GET'} ${url}`);
      if (url.endsWith('/analysis/plans'))
        return { ok: true, json: async () => [] };
      if (url.endsWith('/configuration') && options?.body)
        savedBodies.push(String(options.body));
      if (url.endsWith('/build')) built = true;
      const value = url.endsWith('/datasets')
        ? [dataset]
        : url.endsWith('/build')
          ? {
              id: 'package-1',
              schema_version: '1.0.0',
              title: 'Tesis ficticia',
              variables: config.variables,
              hypotheses: [
                { ...config.hypotheses[0], statement: 'Existe relación' },
              ],
              dataset,
              pending_questions: [],
            }
          : url.endsWith('/configuration')
            ? { ...config, version: 2 }
            : {
                ...status,
                state: built ? 'generated' : 'warnings',
                package_id: built ? 'package-1' : null,
              };
      return { ok: true, json: async () => value };
    }),
  );
  render(<ProjectPackage projectId="project" />);
  expect((await screen.findAllByText('Hábitos')).length).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole('checkbox', { name: 'other' }));
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar vinculaciones' }),
  );
  await waitFor(() =>
    expect(savedBodies.some((body) => body.includes('"other"'))).toBe(true),
  );
  expect(await screen.findByText('Configuración guardada.')).toBeTruthy();
  fireEvent.click(
    screen.getByRole('button', { name: 'Validar investigación' }),
  );
  await waitFor(() =>
    expect(
      calls.some((item) => item.includes('POST') && item.includes('/validate')),
    ).toBe(true),
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Generar paquete de investigación' }),
  );
  expect(await screen.findByText(/package-1/)).toBeTruthy();
  expect(
    screen.getByText(
      /El paquete de investigación está preparado para Statistics/,
    ),
  ).toBeTruthy();
  expect(
    screen.getByText(
      /Integración disponible: resumen descriptivo, Pearson y Spearman/,
    ),
  ).toBeTruthy();
  expect(
    screen.getAllByRole('region', { name: 'Análisis estadístico Research' }),
  ).toHaveLength(1);
  expect(
    screen.queryByRole('region', { name: 'Statistics sobre paquete Research' }),
  ).toBeNull();
  expect(
    screen.getAllByRole('button', { name: 'Proponer análisis' }),
  ).toHaveLength(1);
  expect(
    screen.queryByRole('button', { name: 'Ejecutar descriptivos' }),
  ).toBeNull();
  expect(calls.some((item) => item.includes('/statistics/'))).toBe(false);
  expect(screen.getByText(/Existe relación \(ID: hypothesis\)/)).toBeTruthy();
});

it('shows a stale package without claiming Statistics is ready', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith('/datasets')
          ? []
          : {
              state: 'stale',
              errors: ['El dataset cambió.'],
              warnings: [],
              configuration: {
                version: 0,
                document_id: null,
                dataset_id: null,
                design: 'unknown',
                observations: 'unknown',
                sampling_notes: '',
                variables: [],
                hypotheses: [],
              },
              documents: [],
              dataset: null,
              review: null,
              package_id: 'old-package',
            },
    })),
  );
  render(<ProjectPackage projectId="project" />);
  expect(await screen.findByText('Validación: stale')).toBeTruthy();
  expect(screen.getByText('El dataset cambió.')).toBeTruthy();
  expect(
    screen.queryByText(/La integración con Statistics está pendiente/),
  ).toBeNull();
  expect(
    screen.queryByText(
      /El paquete de investigación está preparado para Statistics/,
    ),
  ).toBeNull();
  expect(
    screen.queryByRole('region', { name: 'Análisis estadístico Research' }),
  ).toBeNull();
  expect(
    screen.queryByRole('region', { name: 'Statistics sobre paquete Research' }),
  ).toBeNull();
});

it('loads an existing current package when the project is reopened', async () => {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      calls.push(url);
      if (url.endsWith('/analysis/plans'))
        return { ok: true, json: async () => [] };
      return {
        ok: true,
        json: async () =>
          url.endsWith('/datasets')
            ? []
            : url.endsWith('/package')
              ? {
                  id: 'current-package',
                  variables: [
                    { id: 'v', name: 'Variable', columns: ['score'] },
                  ],
                  hypotheses: [{ id: 'h', statement: 'Hipótesis ficticia' }],
                  dataset: { id: 'd', format: 'csv', row_count: 1 },
                  pending_questions: ['Confirmar escala'],
                }
              : {
                  state: 'generated',
                  errors: [],
                  warnings: [],
                  configuration: {
                    version: 1,
                    document_id: null,
                    dataset_id: 'd',
                    design: 'unknown',
                    observations: 'unknown',
                    sampling_notes: '',
                    variables: [],
                    hypotheses: [],
                  },
                  documents: [],
                  dataset: null,
                  review: null,
                  package_id: 'current-package',
                },
      };
    }),
  );
  render(<ProjectPackage projectId="project" />);
  expect(
    await screen.findByText(/Paquete vigente: current-package/),
  ).toBeTruthy();
  expect(
    screen.getByText('Aclaración pendiente: Confirmar escala'),
  ).toBeTruthy();
  expect(calls.some((url) => url.endsWith('/package'))).toBe(true);
  expect(
    screen.getAllByRole('region', { name: 'Análisis estadístico Research' }),
  ).toHaveLength(1);
  expect(
    screen.queryByRole('region', { name: 'Statistics sobre paquete Research' }),
  ).toBeNull();
  expect(calls.some((url) => url.includes('/statistics/'))).toBe(false);
});

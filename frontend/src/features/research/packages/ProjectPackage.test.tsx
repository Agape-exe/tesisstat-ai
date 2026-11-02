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
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      calls.push(`${options?.method ?? 'GET'} ${url}`);
      if (url.endsWith('/configuration') && options?.body)
        savedBodies.push(String(options.body));
      const value = url.endsWith('/datasets')
        ? [dataset]
        : url.endsWith('/build')
          ? {
              id: 'package-1',
              schema_version: '1.0.0',
              title: 'Tesis ficticia',
              variables: config.variables,
              hypotheses: config.hypotheses,
              dataset,
              pending_questions: [],
            }
          : url.endsWith('/configuration')
            ? { ...config, version: 2 }
            : status;
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
});

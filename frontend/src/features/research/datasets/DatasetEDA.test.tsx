import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { DatasetEDA } from './DatasetEDA';
import { DatasetApiError } from './api';
import type { DatasetApi, EDAReport } from './api';

const report: EDAReport = {
  processed_at: '2026-11-02T00:00:00Z',
  rule_version: 'eda-1',
  summary: {
    rows: 25,
    columns: 1,
    missing: 1,
    missing_percentage: 4,
    duplicates: 0,
    problem_columns: 1,
  },
  columns: [
    {
      name: '<script>',
      suggested_type: 'categórico',
      present: 24,
      missing: 1,
      missing_percentage: 4,
      distinct: 2,
      uniqueness_percentage: 8.33,
      numeric_valid: 0,
      numeric_min: null,
      numeric_max: null,
      date_min: null,
      date_max: null,
      incompatible_examples: [],
      frequencies: [{ value: '<img>', count: 3, percentage: 12.5 }],
      warnings: [{ severity: 'quality', message: 'Revisar' }],
    },
  ],
  warnings: [{ severity: 'quality', message: 'Revisar' }],
};

function api(getEda: DatasetApi['getEda'], runEda: DatasetApi['runEda']) {
  return { getEda, runEda } as DatasetApi;
}

it('loads a persisted report and shows safe column details', async () => {
  render(
    <DatasetEDA
      projectId="p"
      datasetId="d"
      api={api(
        vi.fn(async () => report),
        vi.fn(async () => report),
      )}
    />,
  );
  expect(await screen.findByText(/25 filas/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ver detalle' }));
  expect(screen.getByText(/<img>/)).toBeInTheDocument();
  expect(screen.getByText('Revisar')).toBeInTheDocument();
});

it('handles missing reports and retries failed analysis', async () => {
  const runEda = vi
    .fn()
    .mockRejectedValueOnce(new Error('Error temporal'))
    .mockResolvedValue(report);
  render(
    <DatasetEDA
      projectId="p"
      datasetId="d"
      api={api(
        vi.fn(async () => {
          throw new DatasetApiError('No existe', 404);
        }),
        runEda,
      )}
    />,
  );
  expect(
    await screen.findByText('Aún no hay análisis guardado.'),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: 'Analizar calidad de datos' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Error temporal');
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
  await waitFor(() => expect(screen.getByText(/25 filas/)).toBeInTheDocument());
});

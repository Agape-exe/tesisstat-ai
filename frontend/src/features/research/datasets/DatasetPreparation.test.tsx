import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { DatasetPreparation } from './DatasetPreparation';
import type { DatasetApi, PreparationPreview, ResearchDataset } from './api';

const dataset: ResearchDataset = {
  id: 'dataset-1',
  project_id: 'project-1',
  name: 'source.csv',
  format: 'csv',
  size: 20,
  row_count: 2,
  column_count: 2,
  columns: ['id', 'value'],
  sheet: null,
  uploaded_at: '2026-11-02T00:00:00Z',
  active: false,
  warnings: [],
};
const preview: PreparationPreview = {
  preview_id: 'preview-1',
  plan_hash: 'hash',
  source_sha256: 'source',
  expires_at: '2026-11-02T01:00:00Z',
  original_rows: 2,
  result_rows: 1,
  original_columns: ['id', 'value'],
  result_columns: ['id', 'value'],
  rows_removed: 1,
  cells_changed: 0,
  warnings: [],
  rows: [['1', '<script>']],
  operations: [
    {
      type: 'drop_duplicates',
      rows_removed: 1,
      cells_changed: 0,
      columns_removed: [],
      rename: {},
    },
  ],
};

it('invalidates confirmation after changing the plan and applies only on confirmation', async () => {
  const previewPreparation = vi.fn(async () => preview);
  const applyPreparation = vi.fn(async () => ({
    ...preview,
    project_id: 'project-1',
    source_id: 'dataset-1',
    result_id: 'result-1',
    prepared_at: '2026-11-02T00:00:00Z',
    plan: { operations: [{ type: 'drop_duplicates' as const }] },
  }));
  const api = {
    previewPreparation,
    applyPreparation,
    listPreparations: vi.fn(async () => []),
  } as unknown as DatasetApi;
  render(
    <DatasetPreparation
      projectId="project-1"
      dataset={dataset}
      api={api}
      onCreated={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Preparar datos' }));
  fireEvent.click(screen.getByRole('button', { name: 'Agregar operación' }));
  fireEvent.click(
    screen.getByRole('button', { name: 'Previsualizar cambios' }),
  );
  expect(await screen.findByText('<script>')).toBeInTheDocument();
  expect(applyPreparation).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Agregar operación' }));
  expect(
    screen.queryByRole('button', {
      name: 'Confirmar y crear dataset preparado',
    }),
  ).toBeNull();
  fireEvent.click(screen.getAllByRole('button', { name: 'Quitar' })[1]);
  fireEvent.click(
    screen.getByRole('button', { name: 'Previsualizar cambios' }),
  );
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Confirmar y crear dataset preparado',
    }),
  );
  await waitFor(() => expect(applyPreparation).toHaveBeenCalledTimes(1));
});

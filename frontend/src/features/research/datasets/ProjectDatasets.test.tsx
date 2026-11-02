import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { ProjectDatasets } from './ProjectDatasets';
import { DatasetApiError } from './api';
import type { DatasetApi, ResearchDataset } from './api';

const dataset: ResearchDataset = {
  id: 'dataset-1',
  project_id: 'project-1',
  name: 'datos.csv',
  format: 'csv',
  size: 12,
  row_count: 1,
  column_count: 2,
  columns: ['A', 'B'],
  sheet: null,
  uploaded_at: '2026-11-02T00:00:00Z',
  active: false,
  warnings: [],
};
const api: DatasetApi = {
  list: vi.fn(async () => [dataset]),
  upload: vi.fn(async () => ({ ...dataset, id: 'dataset-2', name: 'new.csv' })),
  preview: vi.fn(async () => ({
    columns: ['A', 'B'],
    rows: [['1', '<script>']],
    row_count: 1,
    column_count: 2,
    format: 'csv' as const,
    sheet: null,
    warnings: [],
  })),
  activate: vi.fn(async () => ({ ...dataset, active: true })),
  delete: vi.fn(async () => undefined),
  getEda: vi.fn(async () => {
    throw new DatasetApiError('Sin reporte', 404);
  }),
  runEda: vi.fn(async () => {
    throw new Error('Sin reporte');
  }),
};

beforeEach(() => vi.clearAllMocks());

it('lists, previews and activates a dataset safely', async () => {
  render(<ProjectDatasets projectId="project-1" api={api} />);
  expect(await screen.findByText('datos.csv')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ver datos' }));
  const table = await screen.findByRole('table');
  expect(within(table).getByText('<script>')).toBeInTheDocument();
  expect(table.querySelector('script')).toBeNull();
  fireEvent.click(
    screen.getByRole('button', { name: 'Seleccionar como activo' }),
  );
  expect(await screen.findByText('Activo')).toBeInTheDocument();
  expect(api.activate).toHaveBeenCalledWith('project-1', 'dataset-1');
});

it('validates upload and requires confirmation to delete', async () => {
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
  render(<ProjectDatasets projectId="project-1" api={api} />);
  await screen.findByText('datos.csv');
  fireEvent.change(screen.getByLabelText('Archivo'), {
    target: { files: [new File(['x'], 'bad.txt')] },
  });
  expect(screen.getByRole('alert')).toHaveTextContent('CSV o XLSX');
  fireEvent.change(screen.getByLabelText('Archivo'), {
    target: { files: [new File(['A\n1'], 'new.csv')] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Subir dataset' }));
  await waitFor(() => expect(api.upload).toHaveBeenCalled());
  fireEvent.click(
    screen.getByRole('button', { name: 'Eliminar dataset datos.csv' }),
  );
  expect(api.delete).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  fireEvent.click(
    screen.getByRole('button', { name: 'Eliminar dataset datos.csv' }),
  );
  await waitFor(() =>
    expect(api.delete).toHaveBeenCalledWith('project-1', 'dataset-1'),
  );
  confirm.mockRestore();
});

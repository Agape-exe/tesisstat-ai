import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ProjectSources } from './ProjectSources';
import { context, source, table } from './testSources';
import type { SourcesApi, SourceFile } from './api';

function mockApi() {
  let files = [source()];
  const api: SourcesApi = {
    files: vi.fn(async () => files),
    contexts: vi.fn(async () => [context(1, 'Notas iniciales')]),
    upload: vi.fn(async (_, file) => {
      const next = { ...source(), id: file.name, name: file.name, sheets: [] };
      files = [...files, next];
      return next;
    }),
    sheet: vi.fn(async (_, __, id, patch) => {
      const changed: SourceFile = {
        ...files[0],
        revision: files[0].revision + 1,
        sheets: files[0].sheets.map((sheet) =>
          sheet.id === id
            ? {
                ...sheet,
                revision: sheet.revision + 1,
                state:
                  patch.action === 'exclude'
                    ? 'excluded'
                    : sheet.table_id
                      ? 'ready'
                      : 'pending',
              }
            : sheet,
        ),
      };
      files = [changed, ...files.slice(1)];
      return changed;
    }),
    originalUrl: vi.fn(() => '/original'),
    preview: vi.fn(async () => ({
      table,
      rows: [
        ['0001', '<script>alert(1)</script>'],
        ['0002', null],
      ],
    })),
    context: vi.fn(async () => context(1, 'Notas iniciales')),
    patchContext: vi.fn(async () => context(2, 'Notas iniciales')),
  };
  return api;
}

it('lists every sheet and opens a named table without activating a legacy dataset', async () => {
  const api = mockApi();
  render(<ProjectSources projectId="project" api={api} />);
  expect(await screen.findByText('Hoja: Antes')).toBeVisible();
  expect(screen.getByText('Hoja: Con título')).toBeVisible();
  expect(screen.getByText('Oculta')).toBeVisible();
  fireEvent.click(
    screen.getByRole('button', { name: 'Abrir Notas iniciales' }),
  );
  expect(await screen.findByRole('table')).toBeVisible();
  expect(screen.getByText('0001')).toBeVisible();
  expect(screen.getByText('<script>alert(1)</script>')).toBeVisible();
  expect(document.querySelector('script')).toBeNull();
  expect(screen.getByText(/123 procesadas completamente/)).toBeVisible();
  expect(api.preview).toHaveBeenCalledExactlyOnceWith('project', 'table');
  expect(screen.getByLabelText('Momento de medición')).toHaveValue('unknown');
  expect(
    screen.queryByRole('button', { name: /combinar/i }),
  ).not.toBeInTheDocument();
});

it('uploads multiple and successive files while retaining existing files', async () => {
  const api = mockApi();
  render(<ProjectSources projectId="project" api={api} />);
  await screen.findByText('Hoja: Antes');
  const input = screen.getByLabelText('Seleccionar archivos CSV o Excel');
  fireEvent.change(input, {
    target: {
      files: [
        new File(['id,x\n1,2'], 'segundo.csv'),
        new File(['id,x\n2,3'], 'tercero.csv'),
      ],
    },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Importar archivos' }));
  await screen.findByRole('article', { name: 'Archivo tercero.csv' });
  expect(
    screen.getByRole('article', { name: 'Archivo mediciones.xlsx' }),
  ).toBeVisible();
  expect(
    screen.getByRole('article', { name: 'Archivo segundo.csv' }),
  ).toBeVisible();
  expect(api.upload).toHaveBeenCalledTimes(2);
  fireEvent.change(input, {
    target: { files: [new File(['a,b\n3,4'], 'cuarto.csv')] },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Importar archivos' }));
  await screen.findByRole('article', { name: 'Archivo cuarto.csv' });
  expect(screen.getAllByRole('article')).toHaveLength(4);
});

it('filters pending sheets and excludes/reincludes without uploading again', async () => {
  const api = mockApi();
  render(<ProjectSources projectId="project" api={api} />);
  await screen.findByText('Hoja: Antes');
  fireEvent.click(screen.getByLabelText('Ver solo hojas pendientes'));
  expect(screen.queryByText('Hoja: Antes')).not.toBeInTheDocument();
  const pending = screen.getByText('Hoja: Con título').closest('li')!;
  fireEvent.click(
    within(pending).getByRole('button', { name: 'Excluir hoja' }),
  );
  await waitFor(() =>
    expect(screen.queryByText('Hoja: Con título')).not.toBeInTheDocument(),
  );
  fireEvent.click(screen.getByLabelText('Ver solo hojas pendientes'));
  fireEvent.click(screen.getByRole('button', { name: 'Volver a incluir' }));
  await screen.findByText('Pendiente');
  expect(api.upload).not.toHaveBeenCalled();
  expect(api.sheet).toHaveBeenLastCalledWith('project', 'file', 'pending', {
    expected_revision: 2,
    action: 'include',
  });
});

it('sends explicit header and range only for the pending sheet', async () => {
  const api = mockApi();
  render(<ProjectSources projectId="project" api={api} />);
  await screen.findByText('Hoja: Con título');
  fireEvent.click(screen.getByText('Confirmar encabezado y rango'));
  fireEvent.change(screen.getByLabelText('Fila de encabezados'), {
    target: { value: '3' },
  });
  fireEvent.change(screen.getByLabelText('Rango tabular'), {
    target: { value: 'a3:b40' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Confirmar e importar tabla' }),
  );
  await waitFor(() =>
    expect(api.sheet).toHaveBeenCalledWith('project', 'file', 'pending', {
      expected_revision: 1,
      action: 'extract',
      header_row: 3,
      range: 'A3:B40',
    }),
  );
});

it('distinguishes failed inventory from empty inventory and supports retry', async () => {
  const api = mockApi();
  vi.mocked(api.files).mockRejectedValueOnce(
    new Error('Almacenamiento no disponible'),
  );
  render(<ProjectSources projectId="project" api={api} />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Almacenamiento no disponible',
  );
  expect(screen.queryByText(/Aún no hay archivos/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar archivos' }));
  await screen.findByText('Hoja: Antes');
});

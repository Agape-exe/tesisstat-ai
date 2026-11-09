import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { TableContextEditor } from './TableContextEditor';
import { context, table } from './testSources';
import { createSourcesApi, SourcesError } from './api';

function setup() {
  const api = createSourcesApi();
  api.patchContext = vi.fn(async () => context(1, 'Notas'));
  api.context = vi.fn(async () => context(2, 'Nombre en servidor'));
  render(
    <TableContextEditor
      initial={context()}
      table={table}
      api={api}
      onSaved={vi.fn()}
    />,
  );
  return api;
}
it('sends only edited fields and explicitly selected confirmations', async () => {
  const api = setup();
  fireEvent.change(screen.getByLabelText('Nombre comprensible'), {
    target: { value: 'Notas' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar contexto de tabla' }),
  );
  await screen.findByText('Contexto guardado en el servidor.');
  expect(api.patchContext).toHaveBeenCalledWith('project', 'table', {
    expected_revision: 0,
    changes: { name: 'Notas' },
    confirm_fields: [],
  });
  fireEvent.click(screen.getByLabelText('Confirmar nombre comprensible'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar contexto de tabla' }),
  );
  await waitFor(() =>
    expect(api.patchContext).toHaveBeenLastCalledWith('project', 'table', {
      expected_revision: 1,
      changes: {},
      confirm_fields: ['/name'],
    }),
  );
});
it('retains and compares a 409 draft before rebasing only the changed field', async () => {
  const api = setup();
  vi.mocked(api.patchContext).mockRejectedValueOnce(
    new SourcesError('Otra revisión', 409, 2),
  );
  fireEvent.change(screen.getByLabelText('Para qué se utilizará'), {
    target: { value: 'Borrador de finalidad' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar contexto de tabla' }),
  );
  await screen.findByText('Otra edición guardó la revisión 2');
  expect(screen.getByLabelText('Para qué se utilizará')).toHaveValue(
    'Borrador de finalidad',
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Conservar borrador sobre revisión actual',
    }),
  );
  expect(screen.getByLabelText('Nombre comprensible')).toHaveValue(
    'Nombre en servidor',
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar contexto de tabla' }),
  );
  await waitFor(() =>
    expect(api.patchContext).toHaveBeenLastCalledWith('project', 'table', {
      expected_revision: 2,
      changes: { purpose: 'Borrador de finalidad' },
      confirm_fields: [],
    }),
  );
});
it('clearing a field also removes its pending confirmation', async () => {
  const api = setup();
  fireEvent.change(screen.getByLabelText('Nombre comprensible'), {
    target: { value: 'Notas' },
  });
  fireEvent.click(screen.getByLabelText('Confirmar nombre comprensible'));
  fireEvent.change(screen.getByLabelText('Nombre comprensible'), {
    target: { value: '' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar contexto de tabla' }),
  );
  await waitFor(() =>
    expect(api.patchContext).toHaveBeenCalledWith('project', 'table', {
      expected_revision: 0,
      changes: { name: null },
      confirm_fields: [],
    }),
  );
});

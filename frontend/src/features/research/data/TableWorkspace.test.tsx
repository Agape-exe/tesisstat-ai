import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { DictionaryEditor } from './DictionaryEditor';
import { PreparationEditor } from './PreparationEditor';
import { TableWorkspace } from './TableWorkspace';
import { SourcesError } from '../sources/api';
import {
  createDataApi,
  type DataApi,
  type Dataset,
  type Dictionary,
  type Preview,
  type Profile,
} from './api';

const dataset = {
  id: 'left',
  project_id: 'project',
  revision: 1,
  hash: 'a'.repeat(64),
  hash_algorithm: 'table-json-v1',
  format: 'table_json',
  kind: 'imported',
  name: 'Antes',
  row_count: 30,
  columns: [
    { id: 'id', name: 'estudiante', position: 0 },
    { id: 'nota', name: 'nota', position: 1 },
  ],
  source_refs: [],
  synthetic: null,
  preparation_ref: null,
  schema_version: '2.0.0',
} as Dataset;
function dictionary(): Dictionary {
  return {
    schema_version: '2.0.0',
    id: 'dictionary',
    project_id: 'project',
    revision: 0,
    hash: 'b'.repeat(64),
    dataset_ref: dataset,
    updated_at: null,
    pending_questions: [],
    variables: dataset.columns.map((c) => ({
      id: `v-${c.id}`,
      name: { value: c.name },
      description: { value: null },
      measurement_scale: { value: 'unknown' },
      identifier_confirmed: { value: null },
      column_ids: [c.id],
      category_order: [],
      missing_markers: ['', 'NA'],
      possible_identifier: c.id === 'id',
      storage_type: 'unknown',
      field_confirmations: {},
    })),
  } as Dictionary;
}
function api(): DataApi {
  return {
    ...createDataApi(),
    tables: vi.fn().mockResolvedValue([dataset]),
    summary: vi.fn().mockResolvedValue({ tables: [], derived: 0 }),
    preview: vi
      .fn()
      .mockResolvedValue({ dataset_ref: dataset, rows: [['E001', '10']] }),
    dictionary: vi.fn().mockResolvedValue(dictionary()),
    profile: vi.fn().mockResolvedValue(null),
    compute: vi.fn(),
    saveDictionary: vi.fn(),
    prepare: vi.fn(),
    apply: vi.fn(),
  };
}
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

it('saves a partial dictionary, explicitly confirms false and leaves unknown scales unconfirmed', async () => {
  const client = api();
  const initial = dictionary();
  vi.mocked(client.saveDictionary).mockResolvedValue({
    ...initial,
    revision: 1,
  });
  render(<DictionaryEditor initial={initial} api={client} onSaved={vi.fn()} />);
  const variable = within(
    screen.getByRole('article', { name: 'Variable nota' }),
  );
  fireEvent.change(variable.getByLabelText('¿Es identificador?'), {
    target: { value: 'no' },
  });
  fireEvent.click(
    variable.getByRole('button', {
      name: 'Seleccionar campos conocidos de esta variable',
    }),
  );
  expect(variable.getByLabelText('Confirmar escala')).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guardar diccionario y confirmaciones seleccionadas',
    }),
  );
  await waitFor(() => expect(client.saveDictionary).toHaveBeenCalled());
  const args = vi.mocked(client.saveDictionary).mock.calls[0];
  expect(args[2]).toEqual({ 'v-nota': { identifier_confirmed: false } });
  expect(args[3]).toEqual([
    '/variables/v-nota/name',
    '/variables/v-nota/column_ids',
    '/variables/v-nota/identifier_confirmed',
  ]);
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Diccionario guardado',
  );
});

it('preserves the draft on 409 and reapplies only edited fields against the new revision', async () => {
  const client = api();
  const initial = dictionary();
  const remote = {
    ...initial,
    revision: 2,
    variables: initial.variables.map((v) => ({
      ...v,
      description: { value: 'Otra persona guardó esto' },
    })),
  } as Dictionary;
  vi.mocked(client.dictionary).mockResolvedValue(remote);
  vi.mocked(client.saveDictionary)
    .mockRejectedValueOnce(new SourcesError('Otra edición', 409, 2))
    .mockResolvedValueOnce({ ...remote, revision: 3 });
  render(<DictionaryEditor initial={initial} api={client} onSaved={vi.fn()} />);
  const variable = within(
    screen.getByRole('article', { name: 'Variable nota' }),
  );
  fireEvent.change(variable.getByLabelText('Nombre de variable'), {
    target: { value: 'Nota antes' },
  });
  const save = screen.getByRole('button', {
    name: 'Guardar diccionario y confirmaciones seleccionadas',
  });
  fireEvent.click(save);
  await screen.findByText('Otra revisión fue guardada');
  expect(variable.getByLabelText('Nombre de variable')).toHaveValue(
    'Nota antes',
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Conservar mi borrador sobre la revisión actual',
    }),
  );
  fireEvent.click(save);
  await waitFor(() => expect(client.saveDictionary).toHaveBeenCalledTimes(2));
  expect(vi.mocked(client.saveDictionary).mock.calls[1][2]).toEqual({
    'v-nota': { name: 'Nota antes' },
  });
  expect(vi.mocked(client.saveDictionary).mock.calls[1][4]).toBe(2);
});

it('recovers the dictionary draft after remount without mixing another table', () => {
  const client = api();
  const initial = dictionary();
  const view = render(
    <DictionaryEditor initial={initial} api={client} onSaved={vi.fn()} />,
  );
  fireEvent.change(screen.getAllByLabelText('Nombre de variable')[1], {
    target: { value: 'Mi borrador' },
  });
  view.unmount();
  const again = render(
    <DictionaryEditor initial={initial} api={client} onSaved={vi.fn()} />,
  );
  expect(screen.getAllByLabelText('Nombre de variable')[1]).toHaveValue(
    'Mi borrador',
  );
  again.unmount();
  render(
    <DictionaryEditor
      initial={{ ...initial, dataset_ref: { ...dataset, id: 'otra' } }}
      api={client}
      onSaved={vi.fn()}
    />,
  );
  expect(screen.getAllByLabelText('Nombre de variable')[1]).toHaveValue('nota');
});

it('reads persisted evidence without computing and computes only on explicit action', async () => {
  const client = api();
  vi.mocked(client.compute).mockResolvedValue({
    id: 'profile',
    state: 'current',
    rows: 30,
    columns_count: 2,
    missing: 4,
    duplicates: 1,
    constant_columns: 0,
    empty_columns: 0,
    columns: [],
    warnings: [],
    source_refs: [],
    created_at: '2026-11-09T15:00:00Z',
  } as unknown as Profile);
  render(
    <TableWorkspace
      projectId="project"
      tableId="left"
      active
      onSelect={vi.fn()}
      onContext={vi.fn()}
      api={client}
    />,
  );
  await screen.findByText('No hay perfil guardado para esta tabla.');
  expect(client.compute).not.toHaveBeenCalled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Calcular perfil completo' }),
  );
  await screen.findByText('Perfil vigente');
  expect(client.compute).toHaveBeenCalledExactlyOnceWith('project', dataset);
  expect(
    screen.getByRole('region', { name: 'Perfil exploratorio completo' }),
  ).toHaveTextContent('30');
  expect(
    screen.getByText(/solicitar propuestas para estas tablas/),
  ).toBeInTheDocument();
});

it('invalidates a join preview after recipe changes and blocks duplicate-key confirmation', async () => {
  const client = api();
  const right = {
    ...dataset,
    id: 'right',
    name: 'Después',
    columns: [
      { id: 'rid', name: 'estudiante', position: 0 },
      { id: 'rnota', name: 'nota', position: 1 },
    ],
  } as Dataset;
  const result = {
    id: 'preview',
    counts: { left_rows: 3, right_rows: 3, matches: 2, result_rows: 4 },
    rows: [['E001', '10', 'E001', '13']],
    result_columns: ['id', 'antes', 'id2', 'despues'],
    unmatched_left: [2],
    unmatched_right: [3],
    warnings: [],
    blockers: ['Hay claves duplicadas'],
    recipe: {},
    source_refs: [],
  } as unknown as Preview;
  vi.mocked(client.prepare).mockResolvedValue(result);
  render(
    <PreparationEditor
      projectId="project"
      dataset={dataset}
      tables={[dataset, right]}
      api={client}
      onCreated={vi.fn()}
    />,
  );
  fireEvent.change(screen.getByLabelText('Nombre de la nueva tabla'), {
    target: { value: 'Emparejados' },
  });
  fireEvent.change(screen.getByLabelText('Tabla derecha'), {
    target: { value: 'right' },
  });
  fireEvent.change(screen.getByLabelText('Identificador izquierdo'), {
    target: { value: 'id' },
  });
  fireEvent.change(screen.getByLabelText('Identificador derecho'), {
    target: { value: 'rid' },
  });
  const button = screen.getByRole('button', {
    name: 'Ver vista previa y conteos',
  });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Casos sin correspondencia'), {
    target: { value: 'all_cases' },
  });
  fireEvent.click(button);
  expect(
    await screen.findByRole('button', {
      name: 'Confirmar y crear nueva tabla',
    }),
  ).toBeDisabled();
  expect(client.apply).not.toHaveBeenCalled();
  expect(vi.mocked(client.prepare).mock.calls[0][1]).toMatchObject({
    left_key: 'id',
    right_key: 'rid',
    unmatched_policy: 'all_cases',
  });
  fireEvent.change(
    screen.getByLabelText('Nombre de salida de nota (izquierda)'),
    { target: { value: 'nuevo_nombre' } },
  );
  expect(
    screen.queryByRole('region', { name: 'Resultado previsto' }),
  ).not.toBeInTheDocument();
});

it('distinguishes missing profile from storage failure and never POSTs while reading', async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(new Response('{}', { status: 404 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({ error: { message: 'Disco no disponible' } }),
        { status: 503 },
      ),
    );
  vi.stubGlobal('fetch', fetcher);
  const client = createDataApi('http://localhost:8014');
  expect(await client.profile('project', 'left')).toBeNull();
  await expect(client.profile('project', 'left')).rejects.toThrow(
    'Disco no disponible',
  );
  expect(fetcher.mock.calls.every(([, options]) => !options.method)).toBe(true);
});

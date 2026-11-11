import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { DiagnosticWorkspace } from './DiagnosticWorkspace';
import { SourcesError } from '../sources/api';

const mock = vi.hoisted(() => ({
  list: vi.fn(),
  save: vi.fn(),
  history: vi.fn(),
  compute: vi.fn(),
  tables: vi.fn(),
  dictionary: vi.fn(),
  profile: vi.fn(),
  tableCompute: vi.fn(),
}));
vi.mock('../analysis/v2api', () => ({
  createAnalysisV2Api: () => ({ plans: async () => [] }),
  techniqueLabels: {},
}));
vi.mock('../context/api', () => ({
  createContextApi: () => ({
    get: async () => ({ specific_objectives: [], hypotheses: [] }),
  }),
}));
vi.mock('./api', () => ({ createDiagnosticsApi: () => mock }));
vi.mock('../data/api', () => ({
  createDataApi: () => ({ ...mock, compute: mock.tableCompute }),
}));
const fact = (value: unknown) => ({
  value,
  provenance: { kind: 'manual', source_refs: [] },
  confirmation: null,
});
function intent(question = 'Mediciones de plantas', revision = 1) {
  return {
    id: 'i',
    project_id: 'p',
    revision,
    question: fact(question),
    dataset_id: 't',
    kind: 'comparison',
    estimand: 'mean_difference',
    variable_ids: ['v-a', 'v-b'],
    roles: [],
    observations: fact('paired'),
    observational_unit: fact('Una planta'),
    identification: fact('Código estable'),
    comparison_notes: fact('Dos momentos'),
    linkage: fact('same_row'),
    identifier_column_id: 'id',
    paired_columns: { before_column_id: 'a', after_column_id: 'b' },
    group_column_id: null,
    alternative: 'unspecified',
    alpha: 0.05,
    missing_policy: 'complete_cases',
  };
}
const table = {
  id: 't',
  revision: 1,
  name: 'Plantas sintéticas',
  row_count: 25,
  columns: [
    { id: 'id', name: 'Código' },
    { id: 'a', name: 'Altura inicial' },
    { id: 'b', name: 'Altura final' },
  ],
};
const dictionary = {
  revision: 1,
  variables: [
    {
      id: 'v-a',
      name: fact('Altura inicial'),
      column_ids: ['a'],
      measurement_scale: fact('ratio'),
    },
    {
      id: 'v-b',
      name: fact('Altura final'),
      column_ids: ['b'],
      measurement_scale: fact('ratio'),
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  mock.list.mockResolvedValue([intent()]);
  mock.tables.mockResolvedValue([table]);
  mock.dictionary.mockResolvedValue(dictionary);
  mock.profile.mockResolvedValue({ state: 'current' });
  mock.history.mockResolvedValue([]);
  mock.compute.mockResolvedValue({});
});
afterEach(cleanup);

it('allows an incomplete draft without a document or hypothesis', async () => {
  mock.save.mockResolvedValue({
    ...intent('Borrador ventas'),
    dataset_id: null,
    variable_ids: [],
    kind: 'descriptive',
    estimand: 'summary',
  });
  render(<DiagnosticWorkspace projectId="p" />);
  fireEvent.change(screen.getByLabelText('Nombre o pregunta del análisis'), {
    target: { value: 'Borrador ventas' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
  await waitFor(() => expect(mock.save).toHaveBeenCalled());
  const body = mock.save.mock.calls[0][2];
  expect(body).toMatchObject({
    expected_revision: 0,
    confirm: false,
    changes: { question: 'Borrador ventas', dataset_id: null },
  });
  expect(body.changes.hypothesis_id).toBeNull();
  expect(mock.compute).not.toHaveBeenCalled();
});

it('explains the scope and only computes on an explicit click', async () => {
  render(<DiagnosticWorkspace projectId="p" />);
  await screen.findByRole('option', { name: /Mediciones de plantas/ });
  fireEvent.change(screen.getByLabelText('Análisis guardado'), {
    target: { value: 'i' },
  });
  const button = screen.getByRole('button', {
    name: 'Calcular diagnósticos seleccionados',
  });
  await waitFor(() => expect(button).toBeEnabled());
  expect(screen.getByText(/No se ejecutará el contraste final/)).toBeVisible();
  expect(mock.compute).not.toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('Pares completos'));
  fireEvent.click(button);
  await waitFor(() =>
    expect(mock.compute).toHaveBeenCalledWith(
      'p',
      expect.objectContaining({
        intent_id: 'i',
        intent_revision: 1,
        confirm: true,
        checks: ['complete_cases', 'distribution', 'paired_cases'],
      }),
    ),
  );
  fireEvent.change(screen.getByLabelText('Nombre o pregunta del análisis'), {
    target: { value: 'Pregunta corregida' },
  });
  expect(button).toBeDisabled();
});

it('keeps edited fields after a conflict and preserves unrelated remote edits', async () => {
  render(<DiagnosticWorkspace projectId="p" />);
  await screen.findByRole('option', { name: /Mediciones de plantas/ });
  fireEvent.change(screen.getByLabelText('Análisis guardado'), {
    target: { value: 'i' },
  });
  await waitFor(() =>
    expect(screen.getByLabelText('Nombre o pregunta del análisis')).toHaveValue(
      'Mediciones de plantas',
    ),
  );
  fireEvent.change(screen.getByLabelText('Nombre o pregunta del análisis'), {
    target: { value: 'Mi pregunta' },
  });
  mock.list.mockResolvedValue([
    {
      ...intent('Mediciones de plantas', 2),
      identification: fact('Identificación corregida por otra edición'),
    },
  ]);
  mock.save.mockRejectedValueOnce(new SourcesError('Conflicto', 409, 2));
  fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
  await screen.findByText(/Tu borrador está conservado/);
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Recuperar revisión y conservar mis campos editados',
    }),
  );
  expect(screen.getByLabelText('Nombre o pregunta del análisis')).toHaveValue(
    'Mi pregunta',
  );
  expect(
    screen.getByLabelText('¿Cómo reconoces cada entidad y sus repeticiones?'),
  ).toHaveValue('Identificación corregida por otra edición');
  mock.save.mockResolvedValue(intent('Mi pregunta', 3));
  fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
  await waitFor(() =>
    expect(mock.save).toHaveBeenLastCalledWith('p', 'i', {
      expected_revision: 2,
      confirm: false,
      changes: { question: 'Mi pregunta' },
    }),
  );
});

it('refreshes evidence when returning from Datos without overwriting the draft', async () => {
  const view = render(<DiagnosticWorkspace projectId="p" />);
  await screen.findByRole('option', { name: /Mediciones de plantas/ });
  fireEvent.change(screen.getByLabelText('Análisis guardado'), {
    target: { value: 'i' },
  });
  await waitFor(() =>
    expect(
      screen.getByRole('button', {
        name: 'Calcular diagnósticos seleccionados',
      }),
    ).toBeEnabled(),
  );
  view.rerender(<DiagnosticWorkspace projectId="p" active={false} />);
  mock.profile.mockResolvedValue({ state: 'stale' });
  view.rerender(<DiagnosticWorkspace projectId="p" active />);
  await screen.findByText('Perfil de la tabla: desactualizado.');
  expect(
    screen.getByRole('button', { name: 'Calcular diagnósticos seleccionados' }),
  ).toBeDisabled();
  expect(screen.getByLabelText('Nombre o pregunta del análisis')).toHaveValue(
    'Mediciones de plantas',
  );
});

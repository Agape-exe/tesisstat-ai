import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ProjectInstrument } from './ProjectInstrument';
import { SourcesError } from '../sources/api';

const api = vi.hoisted(() => ({
  list: vi.fn(),
  save: vi.fn(),
  get: vi.fn(),
  confirm: vi.fn(),
  history: vi.fn(),
  mapping: vi.fn(),
  map: vi.fn(),
  preview: vi.fn(),
  scores: vi.fn(),
  score: vi.fn(),
}));
vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  createInstrumentApi: () => api,
}));
vi.mock('../data/api', () => ({
  createDataApi: () => ({
    tables: async () => [
      {
        id: 't',
        revision: 1,
        name: 'Respuestas',
        row_count: 2,
        columns: [{ id: 'c', name: 'respuesta' }],
      },
    ],
  }),
}));
const instrument = {
  instrument_id: 'i',
  project_id: 'p',
  revision: 1,
  status: 'draft',
  context_field: 'study_description',
  variables: [{ variable_id: 'v', name: 'Experiencia' }],
  dimensions: [{ dimension_id: 'd', variable_id: 'v', name: 'Conjunto' }],
  indicators: [{ indicator_id: 'ind', dimension_id: 'd', name: 'Respuesta' }],
  items: [
    {
      item_id: 'item',
      variable_id: 'v',
      dimension_id: 'd',
      indicator_id: 'ind',
      text: 'Ayuda recibida',
      response_type: 'numeric',
    },
  ],
  scoring_rules: [
    {
      scoring_rule_id: 'r',
      scope: 'dimension',
      dimension_id: 'd',
      item_ids: ['item'],
      aggregation: 'sum',
    },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  api.list.mockResolvedValue([instrument]);
  api.history.mockResolvedValue([]);
  api.scores.mockResolvedValue([]);
  api.mapping.mockRejectedValue(
    new SourcesError('Sin correspondencia', 404, null),
  );
});
afterEach(cleanup);

it('recovers a local draft after reload without overwriting it on mount', async () => {
  const { unmount } = render(<ProjectInstrument projectId="p" />);
  await screen.findByRole('option', { name: /Experiencia/ });
  fireEvent.change(screen.getByLabelText('Nombre del constructo 1'), {
    target: { value: 'Borrador propio' },
  });
  await waitFor(() =>
    expect(sessionStorage.getItem('s05:p:new')).toContain('Borrador propio'),
  );
  unmount();
  render(<ProjectInstrument projectId="p" />);
  fireEvent.click(
    screen.getByRole('button', { name: 'Recuperar borrador local' }),
  );
  expect(screen.getByLabelText('Nombre del constructo 1')).toHaveValue(
    'Borrador propio',
  );
  expect(api.save).not.toHaveBeenCalled();
  expect(api.confirm).not.toHaveBeenCalled();
});

it('preserves the edited structure on CAS conflict and requires an explicit revision confirmation', async () => {
  api.save.mockRejectedValue(new SourcesError('Otra revisión', 409, 2));
  api.get.mockResolvedValue({ ...instrument, revision: 2 });
  render(<ProjectInstrument projectId="p" />);
  await screen.findByRole('option', { name: /Experiencia/ });
  fireEvent.change(screen.getByLabelText('Instrumento guardado'), {
    target: { value: 'i' },
  });
  await waitFor(() =>
    expect(screen.getByLabelText('Nombre del constructo 1')).toHaveValue(
      'Experiencia',
    ),
  );
  fireEvent.change(screen.getByLabelText('Nombre del constructo 1'), {
    target: { value: 'Mi cambio' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar borrador del instrumento' }),
  );
  await screen.findByText(/Hay una revisión más reciente/);
  expect(screen.getByLabelText('Nombre del constructo 1')).toHaveValue(
    'Mi cambio',
  );
  expect(api.confirm).not.toHaveBeenCalled();
  expect(sessionStorage.getItem('s05:p:i')).toContain('Mi cambio');
});

it('separates mapping, preview and derived-data confirmation', async () => {
  const reviewed = { ...instrument, status: 'reviewed' };
  api.list.mockResolvedValue([reviewed]);
  api.mapping.mockResolvedValue({
    id: 'm',
    revision: 1,
    status: 'confirmed',
    dataset_ref: { id: 't' },
    item_columns: [{ item_id: 'item', column_id: 'c' }],
  });
  api.preview.mockResolvedValue({
    id: 'preview',
    expires_at: '2026-11-11T12:30:00Z',
    fingerprint: 'a'.repeat(64),
    counts: { total: 2, valid: 1, missing: 1 },
    bounded_preview: [4, null],
    warnings: ['Inversión explícita'],
    exclusions: [],
  });
  api.score.mockResolvedValue({});
  render(<ProjectInstrument projectId="p" />);
  await screen.findByRole('option', { name: /Experiencia/ });
  fireEvent.change(screen.getByLabelText('Instrumento guardado'), {
    target: { value: 'i' },
  });
  const previewButton = await screen.findByRole('button', {
    name: 'Solicitar vista previa de puntuación',
  });
  await waitFor(() => expect(previewButton).toBeEnabled());
  expect(api.preview).not.toHaveBeenCalled();
  expect(api.score).not.toHaveBeenCalled();
  fireEvent.click(previewButton);
  const confirm = await screen.findByRole('button', {
    name: 'Confirmar creación de datos derivados',
  });
  expect(api.score).not.toHaveBeenCalled();
  fireEvent.click(confirm);
  await waitFor(() => expect(api.score).toHaveBeenCalledTimes(1));
  expect(api.confirm).not.toHaveBeenCalled();
});

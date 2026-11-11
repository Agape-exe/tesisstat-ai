import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { ResultsV2 } from './ResultsV2';
const api = vi.hoisted(() => ({
  results: vi.fn(),
  presentation: vi.fn(),
  interpretations: vi.fn(),
  figures: vi.fn(),
  download: vi.fn(),
  review: vi.fn(),
}));
vi.mock('./v2api', () => ({
  createAnalysisV2Api: () => api,
  techniqueLabels: { descriptive_summary: 'Resumen descriptivo' },
}));
const result = {
  id: 'r',
  question: 'Ventas ficticias',
  technique: 'descriptive_summary',
  variable_names: ['Ventas'],
  dataset_id: 'tabla-a',
  case_counts: { total: 8, used: 7, excluded: 1, groups: [], pairs: null },
  validity: 'current',
  status: 'completed',
  stale_reasons: [],
  warnings: [],
  limitations: [],
  engine_version: 'motor-verificado',
  method_version: 'metodo-verificado',
  analysis_plan_id: 'p',
  created_at: '2026-11-11',
  assumptions: [],
  source_refs: [],
};
beforeEach(() => {
  vi.clearAllMocks();
  api.results.mockResolvedValue([result]);
  api.interpretations.mockResolvedValue([]);
  api.presentation.mockResolvedValue({
    status_label: 'Completado',
    metrics: [
      {
        key: 'p_value',
        label: 'p bilateral',
        formatted: '< límite de precisión numérica (no es probabilidad nula)',
      },
    ],
    tables: [],
    interpretation: 'Descripción con sus limitaciones.',
    interpretation_label: 'Plantilla básica',
  });
});
it('uses server formatting and explicit guarded downloads', async () => {
  render(<ResultsV2 projectId="proyecto" active selectedId="r" />);
  expect(
    await screen.findByText(
      '< límite de precisión numérica (no es probabilidad nula)',
    ),
  ).toBeInTheDocument();
  expect(api.download).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }));
  await waitFor(() =>
    expect(api.download).toHaveBeenCalledWith('proyecto', 'r', 'docx'),
  );
  expect(api.figures).not.toHaveBeenCalled();
});
it('marks not-calculable output separately and blocks historical exports', async () => {
  api.results.mockResolvedValue([
    {
      ...result,
      status: 'not_executed',
      validity: 'stale',
      stale_reasons: ['Cambió el instrumento.'],
    },
  ]);
  api.presentation.mockResolvedValue({
    status_label: 'No ejecutado: no calculable',
    metrics: [],
    tables: [],
    interpretation: null,
  });
  render(<ResultsV2 projectId="proyecto" active selectedId="r" />);
  await screen.findByText('No ejecutado: no calculable');
  expect(screen.getByRole('button', { name: 'Descargar PDF' })).toBeDisabled();
  expect(
    screen.getByRole('button', { name: 'Mostrar figuras autorizadas' }),
  ).toBeDisabled();
  expect(screen.getByText(/Cambió el instrumento/)).toBeInTheDocument();
  expect(screen.queryByText('Fallido')).not.toBeInTheDocument();
});
it('keeps a draft editable after a review conflict', async () => {
  api.interpretations.mockResolvedValue([
    {
      id: 'e',
      result_ref: { id: 'r' },
      metric_keys: ['p_value'],
      text: 'Borrador previo.',
      review_status: 'draft',
      revision: 1,
    },
  ]);
  api.review.mockRejectedValue(
    new Error('Conflicto de revisión; vuelve a consultar.'),
  );
  render(<ResultsV2 projectId="proyecto" active selectedId="r" />);
  await screen.findByText('Borrador IA pendiente de revisión');
  fireEvent.change(screen.getByLabelText('Explicación editable'), {
    target: { value: 'Mi revisión con límites.' },
  });
  fireEvent.click(
    screen.getByRole('button', { name: 'Guardar revisión de interpretación' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Conflicto de revisión',
  );
  expect(screen.getByLabelText('Explicación editable')).toHaveValue(
    'Mi revisión con límites.',
  );
});

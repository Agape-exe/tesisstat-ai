import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DocumentMethodology } from './DocumentMethodology';
import type {
  Finding,
  MethodologyApi,
  MethodologyContent,
  MethodologyState,
} from './api';

const unknown: Finding = { value: null, kind: 'unknown', evidence: [] };
const found = (value: string): Finding => ({
  value,
  kind: 'quotation',
  evidence: [value],
});
const content: MethodologyContent = {
  title: found('Título sintético'),
  general_problem: unknown,
  general_objective: found('Medir hábitos'),
  specific_objectives: [found('Describir hábitos')],
  general_hypothesis: unknown,
  specific_hypotheses: [],
  research_design: found('Diseño transversal'),
  observation_design: unknown,
  additional_methodology: [],
  variables: [
    {
      name: found('Hábitos'),
      role: unknown,
      measurement_scale: unknown,
      dimensions: [found('Frecuencia')],
      indicators: [found('Días')],
      instrument_items: [found('¿Cuántos días?')],
    },
  ],
  warnings: ['Evidencia parcial'],
  questions: ['¿Cuál es la hipótesis?'],
};
const initial: MethodologyState = {
  project_id: 'project',
  document_id: 'document',
  status: 'not_started',
  provider_configured: true,
  attempts: 0,
  message: null,
  error_code: null,
  retry_after: null,
  draft: null,
};
const completed: MethodologyState = {
  ...initial,
  status: 'completed',
  attempts: 1,
  draft: {
    project_id: 'project',
    document_id: 'document',
    review_status: 'unreviewed',
    content,
    pending_fields: ['general_hypothesis'],
    evidence: [
      {
        field: 'title',
        document_id: 'document',
        quote: 'Título sintético',
        start: 0,
        end: 16,
      },
    ],
    warnings: ['Texto omitido por límites'],
    model: 'synthetic-model',
    source_hash: 'synthetic-hash',
    schema_version: '1',
    created_at: '2026-11-01T12:00:00Z',
  },
};
const apiMock = (): MethodologyApi => ({
  status: vi.fn().mockResolvedValue(initial),
  analyze: vi.fn().mockResolvedValue(completed),
});

describe('DocumentMethodology', () => {
  it('requires explicit consent and never sends text on opening; shows the draft and references', async () => {
    const api = apiMock();
    let resolve: (result: MethodologyState) => void = () => {};
    vi.mocked(api.analyze).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    render(
      <DocumentMethodology
        projectId="project"
        documentId="document"
        hasText
        api={api}
      />,
    );
    const button = await screen.findByRole('button', {
      name: 'Analizar metodología con IA',
    });
    expect(api.analyze).not.toHaveBeenCalled();
    expect(button).toBeDisabled();
    expect(screen.getByText(/proveedor externo/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(button);
    expect(
      screen.getByRole('button', { name: 'Procesando metodología…' }),
    ).toBeDisabled();
    expect(api.analyze).toHaveBeenCalledTimes(1);
    resolve(completed);
    expect(await screen.findByText(/Borrador no revisado/)).toBeInTheDocument();
    expect(screen.getByText('¿Cuál es la hipótesis?')).toBeInTheDocument();
    expect(screen.getByText('Texto omitido por límites')).toBeInTheDocument();
    expect(screen.getAllByText('No identificado').length).toBeGreaterThan(0);
    expect(screen.getByText(/Caracteres 0–16/)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Variables' }),
    ).toBeInTheDocument();
  });

  it('disables an unconfigured provider and requires readable text', async () => {
    const api = apiMock();
    vi.mocked(api.status).mockResolvedValue({
      ...initial,
      provider_configured: false,
    });
    render(
      <DocumentMethodology
        projectId="project"
        documentId="document"
        hasText={false}
        api={api}
      />,
    );
    expect(await screen.findByText(/no está configurada/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(
      screen.getByRole('button', { name: 'Analizar metodología con IA' }),
    ).toBeDisabled();
    expect(
      screen.getByText('Primero extrae texto legible del documento.'),
    ).toBeInTheDocument();
  });

  it('shows a failed result and cooldown, and allows status recovery without another AI call', async () => {
    const api = apiMock();
    vi.mocked(api.analyze).mockResolvedValue({
      ...initial,
      status: 'failed',
      error_code: 'quota',
      message: 'Cuota agotada',
      retry_after: new Date(Date.now() + 60000).toISOString(),
    });
    render(
      <DocumentMethodology
        projectId="project"
        documentId="document"
        hasText
        api={api}
      />,
    );
    await screen.findByRole('checkbox');
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(
      screen.getByRole('button', { name: 'Analizar metodología con IA' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Cuota agotada');
    expect(
      screen.getByRole('button', { name: 'Reintentar análisis con IA' }),
    ).toBeDisabled();
    vi.mocked(api.status).mockResolvedValue(completed);
    fireEvent.click(
      screen.getByRole('button', { name: 'Consultar estado de IA' }),
    );
    expect(await screen.findByText(/Borrador no revisado/)).toBeInTheDocument();
    expect(api.analyze).toHaveBeenCalledTimes(1);
  });

  it('recovers a failed initial read and renders transport errors', async () => {
    const api = apiMock();
    vi.mocked(api.status).mockRejectedValueOnce(new Error('Lectura fallida'));
    render(
      <DocumentMethodology
        projectId="project"
        documentId="document"
        hasText
        api={api}
      />,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Lectura fallida',
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Consultar estado de IA' }),
    );
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole('checkbox'));
    vi.mocked(api.analyze).mockRejectedValueOnce(
      new Error('Tiempo de espera superado'),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Analizar metodología con IA' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Tiempo de espera superado',
    );
  });
});

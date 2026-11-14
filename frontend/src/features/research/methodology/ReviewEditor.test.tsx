import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReviewEditor } from './ReviewEditor';
import type {
  MethodologyApi,
  MethodologyReview,
  ReviewContent,
  ReviewFinding,
} from './api';

const unknown: ReviewFinding = { value: null, kind: 'unknown', evidence: [] };
const content: ReviewContent = {
  title: unknown,
  general_problem: unknown,
  general_objective: unknown,
  specific_objectives: [],
  general_hypothesis: unknown,
  specific_hypotheses: [],
  variables: [],
  research_design: unknown,
  observation_design: unknown,
  additional_methodology: [],
  clarifications: [],
};
const review: MethodologyReview = {
  project_id: 'project',
  document_id: 'document',
  origin: 'manual',
  content,
  pending_fields: ['title', 'general_objective'],
  review_status: 'unreviewed',
  version: 0,
  updated_at: '2026-11-02T00:00:00Z',
  reviewed_at: null,
};

describe('ReviewEditor', () => {
  it('edits, cancels and saves manual values with the expected version', async () => {
    const saveReview = vi.fn(
      async (
        _project: string,
        _document: string,
        _version: number,
        next: ReviewContent,
      ) => ({ ...review, content: next, version: 1 }),
    );
    const api = { saveReview } as unknown as MethodologyApi;
    const changed = vi.fn();
    render(
      <ReviewEditor
        review={review}
        api={api}
        projectId="project"
        documentId="document"
        onChange={changed}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Editar metodología' }));
    fireEvent.change(screen.getByRole('textbox', { name: /Título/ }), {
      target: { value: 'Estudio sintético' },
    });
    expect(screen.getByText('Hay cambios sin guardar.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
    await waitFor(() =>
      expect(saveReview).toHaveBeenCalledWith(
        'project',
        'document',
        0,
        expect.objectContaining({
          title: { value: 'Estudio sintético', kind: 'manual', evidence: [] },
        }),
      ),
    );
    expect(changed).toHaveBeenCalled();
  });

  it('adds a variable and shows confirmation errors', async () => {
    const api = {
      confirmReview: vi
        .fn()
        .mockRejectedValue(new Error('Faltan campos esenciales')),
    } as unknown as MethodologyApi;
    render(
      <ReviewEditor
        review={review}
        api={api}
        projectId="project"
        documentId="document"
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar revisión' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Faltan campos esenciales',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Editar metodología' }));
    fireEvent.click(screen.getByRole('button', { name: 'Agregar variable' }));
    expect(screen.getByText('Variable 1')).toBeInTheDocument();
  });
});

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectDocuments } from './ProjectDocuments';
import type { DocumentApi, ResearchDocument } from './api';

const document: ResearchDocument = {
  id: 'synthetic-document',
  project_id: 'synthetic-project',
  name: 'fixture.pdf',
  format: 'pdf',
  size: 20,
  uploaded_at: '2026-10-31T12:00:00Z',
};

function mockApi(): DocumentApi {
  return {
    list: vi.fn().mockResolvedValue([]),
    upload: vi.fn().mockResolvedValue(document),
    delete: vi.fn().mockResolvedValue(undefined),
    extraction: vi.fn().mockResolvedValue(null),
    extract: vi.fn().mockResolvedValue({
      document_id: document.id,
      project_id: document.project_id,
      status: 'completed',
      text: 'Texto sintético',
      character_count: 15,
      units_processed: 1,
      processed_at: '2026-10-31T12:00:00Z',
      warnings: [],
      truncated: false,
    }),
  };
}

describe('Research documents UI', () => {
  it('ignores an extraction response from a document that is no longer selected', async () => {
    const api = mockApi();
    vi.mocked(api.list).mockResolvedValue([
      document,
      {
        ...document,
        id: 'second-document',
        name: 'segundo.docx',
        format: 'docx',
      },
    ]);
    let finish!: (
      value: Awaited<ReturnType<DocumentApi['extraction']>>,
    ) => void;
    vi.mocked(api.extraction)
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      )
      .mockResolvedValueOnce({
        document_id: 'second-document',
        project_id: document.project_id,
        status: 'completed',
        text: 'Texto del segundo documento',
        character_count: 27,
        units_processed: 1,
        processed_at: document.uploaded_at,
        warnings: [],
        truncated: false,
      });
    render(<ProjectDocuments projectId="synthetic-project" api={api} />);
    await screen.findByText('segundo.docx');
    fireEvent.click(
      screen.getAllByRole('button', { name: 'Ver extracción' })[0],
    );
    fireEvent.click(screen.getByRole('button', { name: 'Ver extracción' }));
    await screen.findByText('Texto del segundo documento');
    await act(async () => finish(null));
    expect(screen.getByText('Texto del segundo documento')).toBeInTheDocument();
    expect(api.extract).not.toHaveBeenCalled();
  });

  it('shows cached text and warnings after selecting a document', async () => {
    const api = mockApi();
    vi.mocked(api.list).mockResolvedValue([document]);
    vi.mocked(api.extraction).mockResolvedValue({
      document_id: document.id,
      project_id: document.project_id,
      status: 'no_text',
      text: '',
      character_count: 0,
      units_processed: 1,
      processed_at: '2026-10-31T12:00:00Z',
      warnings: ['Requiere OCR'],
      truncated: false,
    });
    render(<ProjectDocuments projectId="synthetic-project" api={api} />);
    await screen.findByText('fixture.pdf');
    fireEvent.click(screen.getByRole('button', { name: 'Ver extracción' }));
    expect(
      await screen.findByText('Estado: Sin texto extraíble'),
    ).toBeInTheDocument();
    expect(screen.getByText('Requiere OCR')).toBeInTheDocument();
    expect(api.extract).not.toHaveBeenCalled();
  });

  it('extracts text and offers retry after a failed result', async () => {
    const api = mockApi();
    vi.mocked(api.list).mockResolvedValue([document]);
    vi.mocked(api.extract).mockResolvedValueOnce({
      document_id: document.id,
      project_id: document.project_id,
      status: 'failed',
      text: '',
      character_count: 0,
      units_processed: 0,
      processed_at: '2026-10-31T12:00:00Z',
      warnings: ['Archivo inválido'],
      truncated: false,
    });
    render(<ProjectDocuments projectId="synthetic-project" api={api} />);
    await screen.findByText('fixture.pdf');
    fireEvent.click(screen.getByRole('button', { name: 'Ver extracción' }));
    fireEvent.click(
      await screen.findByRole('button', { name: 'Extraer texto' }),
    );
    expect(await screen.findByText('Estado: Fallido')).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Reintentar extracción' }),
    );
    expect(await screen.findByText('Texto sintético')).toBeInTheDocument();
  });

  it('uploads, lists and confirms deletion', async () => {
    const api = mockApi();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<ProjectDocuments projectId="synthetic-project" api={api} />);
    expect(
      await screen.findByText('Aún no hay documentos en esta investigación.'),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Archivo'), {
      target: {
        files: [
          new File(['%PDF-1.4\n%%EOF'], 'fixture.pdf', {
            type: 'application/pdf',
          }),
        ],
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Adjuntar documento' }));
    expect(await screen.findByText('fixture.pdf')).toBeInTheDocument();
    expect(api.upload).toHaveBeenCalledTimes(1);
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar documento fixture.pdf' }),
    );
    expect(api.delete).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar documento fixture.pdf' }),
    );
    await waitFor(() =>
      expect(api.delete).toHaveBeenCalledWith(
        'synthetic-project',
        'synthetic-document',
      ),
    );
    expect(
      await screen.findByText('Aún no hay documentos en esta investigación.'),
    ).toBeInTheDocument();
    confirm.mockRestore();
  });

  it('rejects empty and oversized files before upload', async () => {
    const api = mockApi();
    render(<ProjectDocuments projectId="synthetic-project" api={api} />);
    await screen.findByText('Aún no hay documentos en esta investigación.');
    fireEvent.change(screen.getByLabelText('Archivo'), {
      target: { files: [new File([], 'empty.pdf')] },
    });
    expect(screen.getByRole('alert')).toHaveTextContent('vacío');
    expect(
      screen.getByRole('button', { name: 'Adjuntar documento' }),
    ).toBeDisabled();
    expect(api.upload).not.toHaveBeenCalled();
  });
});

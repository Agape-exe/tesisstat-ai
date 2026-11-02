import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
  };
}

describe('Research documents UI', () => {
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

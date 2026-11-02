import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { ProjectApiError } from './api';
import { ResearchProjects } from './ResearchProjects';
import type { Project, ProjectService } from './types';

const project: Project = {
  id: 'synthetic-project',
  title: 'Investigación ficticia de ejemplo',
  description: 'Descripción sintética.',
  university: 'Universidad ficticia',
  faculty: 'Facultad simulada',
  program: 'Programa ficticio',
  degree: 'bachelor',
  academic_year: 2026,
  status: 'draft',
  created_at: '2026-10-31T12:00:00Z',
  updated_at: '2026-10-31T12:00:00Z',
};

function mockService(): ProjectService {
  return {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn().mockResolvedValue(project),
    create: vi
      .fn()
      .mockImplementation(async (draft) => ({ ...project, ...draft })),
    update: vi
      .fn()
      .mockImplementation(async (id, draft) => ({ ...project, ...draft, id })),
    delete: vi.fn().mockResolvedValue(undefined),
  };
}

beforeAll(() => {
  // jsdom doesn't implement native modal dialogs; real browsers provide focus trapping.
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});

function fillForm() {
  fireEvent.change(screen.getByLabelText('Título de la investigación *'), {
    target: { value: project.title },
  });
  fireEvent.change(screen.getByLabelText('Universidad *'), {
    target: { value: project.university },
  });
  fireEvent.change(screen.getByLabelText('Carrera o programa *'), {
    target: { value: project.program },
  });
}

describe('Research projects UI', () => {
  it('shows loading and empty states', async () => {
    render(<ResearchProjects service={mockService()} />);
    expect(screen.getByText('Cargando investigaciones…')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Nueva investigación' }),
    ).toBeDisabled();
    expect(
      await screen.findByText('Tu próxima investigación empieza aquí'),
    ).toBeInTheDocument();
  });

  it('creates, reads, edits, cancels deletion, and deletes after confirmation', async () => {
    const service = mockService();
    render(<ResearchProjects service={service} />);
    await screen.findByText('Tu próxima investigación empieza aquí');
    fireEvent.click(
      screen.getByRole('button', { name: 'Nueva investigación' }),
    );
    fillForm();
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(
      await screen.findByText('Investigación creada.'),
    ).toBeInTheDocument();
    expect(service.create).toHaveBeenCalledWith(
      expect.objectContaining({ title: project.title, academic_year: null }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Editar investigación' }),
    );
    fireEvent.change(screen.getByLabelText('Título de la investigación *'), {
      target: { value: 'Investigación ficticia editada' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(
      await screen.findByText('Investigación actualizada.'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Investigación ficticia editada' }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar investigación' }),
    );
    const dialog = screen.getByRole('dialog');
    expect(
      within(dialog).getByRole('button', { name: 'Cancelar' }),
    ).toHaveFocus();
    expect(service.delete).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(service.delete).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: 'Eliminar investigación' }),
    ).toHaveFocus();
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar investigación' }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar definitivamente' }),
    );
    expect(
      await screen.findByText('Investigación eliminada.'),
    ).toBeInTheDocument();
    expect(service.delete).toHaveBeenCalledWith(project.id);
    expect(
      screen.getByText('Tu próxima investigación empieza aquí'),
    ).toBeInTheDocument();
  });

  it('loads detail from the API and lets the user cancel edits', async () => {
    const service = mockService();
    vi.mocked(service.list).mockResolvedValue([project]);
    render(<ResearchProjects service={service} />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    );
    expect(
      await screen.findByRole('region', {
        name: 'Información de la investigación',
      }),
    ).toBeInTheDocument();
    expect(service.get).toHaveBeenCalledWith(
      project.id,
      expect.any(AbortSignal),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Editar investigación' }),
    );
    expect(screen.getByLabelText('Título de la investigación *')).toHaveValue(
      project.title,
    );
    fireEvent.change(screen.getByLabelText('Título de la investigación *'), {
      target: { value: 'Cambio descartado' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(
      screen.getByRole('heading', { name: project.title }),
    ).toBeInTheDocument();
    expect(service.update).not.toHaveBeenCalled();
  });

  it('validates required fields and focuses the first error', async () => {
    const service = mockService();
    render(<ResearchProjects service={service} />);
    await screen.findByText('Tu próxima investigación empieza aquí');
    fireEvent.click(
      screen.getByRole('button', { name: 'Nueva investigación' }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(
      screen.getByLabelText('Título de la investigación *'),
    ).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Título de la investigación *')).toHaveFocus();
    expect(service.create).not.toHaveBeenCalled();
    fillForm();
    fireEvent.change(screen.getByLabelText('Año académico'), {
      target: { value: '2101' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(screen.getByText(/Ingresa un año entero/)).toBeInTheDocument();
    expect(service.create).not.toHaveBeenCalled();
  });

  it('preserves the form and displays API validation errors', async () => {
    const service = mockService();
    vi.mocked(service.create).mockRejectedValue(
      new ProjectApiError('Revisa los datos del proyecto.', 422, {
        title: 'Título rechazado por la API.',
      }),
    );
    render(<ResearchProjects service={service} />);
    await screen.findByText('Tu próxima investigación empieza aquí');
    fireEvent.click(
      screen.getByRole('button', { name: 'Nueva investigación' }),
    );
    fillForm();
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(
      await screen.findByText('Título rechazado por la API.'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('Título de la investigación *')).toHaveValue(
      project.title,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Revisa los datos');
  });

  it('disables the form while saving and prevents repeated submissions', async () => {
    const service = mockService();
    let finish!: (value: Project) => void;
    vi.mocked(service.create).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    render(<ResearchProjects service={service} />);
    await screen.findByText('Tu próxima investigación empieza aquí');
    fireEvent.click(
      screen.getByRole('button', { name: 'Nueva investigación' }),
    );
    fillForm();
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(screen.getByRole('button', { name: 'Guardando…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled();
    expect(
      screen.getByLabelText('Título de la investigación *'),
    ).toBeDisabled();
    fireEvent.submit(screen.getByRole('form', { name: 'Crear investigación' }));
    expect(service.create).toHaveBeenCalledTimes(1);
    finish(project);
    expect(
      await screen.findByText('Investigación creada.'),
    ).toBeInTheDocument();
  });

  it('shows list failures and supports retry', async () => {
    const service = mockService();
    vi.mocked(service.list)
      .mockRejectedValueOnce(
        new ProjectApiError('Almacenamiento no disponible.', 503),
      )
      .mockResolvedValueOnce([project]);
    render(<ResearchProjects service={service} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Almacenamiento no disponible.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    ).toBeInTheDocument();
  });

  it('shows a missing detail and supports retry', async () => {
    const service = mockService();
    vi.mocked(service.list).mockResolvedValue([project]);
    vi.mocked(service.get)
      .mockRejectedValueOnce(
        new ProjectApiError('No se encontró el proyecto.', 404),
      )
      .mockResolvedValueOnce(project);
    render(<ResearchProjects service={service} />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se encontró el proyecto.',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar detalle' }));
    expect(
      await screen.findByRole('button', { name: 'Editar investigación' }),
    ).toBeInTheDocument();
  });

  it('keeps the project when deletion fails and allows retry', async () => {
    const service = mockService();
    vi.mocked(service.list).mockResolvedValue([project]);
    vi.mocked(service.delete)
      .mockRejectedValueOnce(new ProjectApiError('No se pudo eliminar.', 503))
      .mockResolvedValueOnce(undefined);
    render(<ResearchProjects service={service} />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    );
    fireEvent.click(
      await screen.findByRole('button', { name: 'Eliminar investigación' }),
    );
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar definitivamente' }),
    );
    expect(
      await within(screen.getByRole('dialog')).findByRole('alert'),
    ).toHaveTextContent('No se pudo eliminar.');
    expect(
      screen.getByRole('heading', { name: project.title }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar definitivamente' }),
    );
    expect(
      await screen.findByText('Investigación eliminada.'),
    ).toBeInTheDocument();
  });

  it('ignores a late detail response after navigating back', async () => {
    const service = mockService();
    let finish!: (value: Project) => void;
    vi.mocked(service.list).mockResolvedValue([project]);
    vi.mocked(service.get).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    render(<ResearchProjects service={service} />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    );
    expect(screen.getByText('Cargando detalle…')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Volver al listado' }));
    finish(project);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: 'Mis investigaciones' }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole('button', { name: 'Editar investigación' }),
    ).not.toBeInTheDocument();
  });
});

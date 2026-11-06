import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
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

afterEach(() => {
  window.history.replaceState(null, '', '/');
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation(
        async (url: string) =>
          new Response(
            JSON.stringify(
              url.endsWith('/status')
                ? { provider_configured: false, max_message_characters: 2000 }
                : [],
            ),
          ),
      ),
  );
});

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

  it('creates, reads, and edits through the project service', async () => {
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
    expect(service.update).toHaveBeenCalledWith(
      project.id,
      expect.objectContaining({ title: 'Investigación ficticia editada' }),
    );
  });

  it('restores focus on cancellation and deletes only after confirmation', async () => {
    const service = mockService();
    vi.mocked(service.list).mockResolvedValue([project]);
    render(<ResearchProjects service={service} />);
    fireEvent.click(
      await screen.findByRole('button', {
        name: `Ver investigación: ${project.title}`,
      }),
    );
    await screen.findByRole('region', {
      name: 'Información de la investigación',
    });
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

it('navigates between document and dataset steps', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async () => new Response('[]')),
  );
  render(<ResearchProjects service={service} />);
  fireEvent.click(
    await screen.findByRole('button', {
      name: `Ver investigación: ${project.title}`,
    }),
  );
  await screen.findByRole('region', { name: 'Asistente IA' });
  fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
  expect(
    await screen.findByRole('region', { name: 'Documentos de investigación' }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Datos' }));
  expect(
    screen.queryByRole('region', { name: 'Documentos de investigación' }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Datos' })).toHaveAttribute(
    'aria-current',
    'page',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
  expect(
    screen.getByRole('region', { name: 'Documentos de investigación' }),
  ).toBeInTheDocument();
  vi.unstubAllGlobals();
});

it('opens Asistente IA, preserves document state and restores the project after refresh', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith('/conversations/status'))
        return new Response(
          JSON.stringify({
            provider_configured: false,
            max_message_characters: 2000,
          }),
        );
      return new Response('[]');
    }),
  );
  const first = render(<ResearchProjects service={service} integrated />);
  fireEvent.click(
    await screen.findByRole('button', {
      name: `Ver investigación: ${project.title}`,
    }),
  );
  await screen.findByRole('region', { name: 'Asistente IA' });
  fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
  const documents = await screen.findByRole('region', {
    name: 'Documentos de investigación',
  });
  fireEvent.click(screen.getByRole('button', { name: 'Asistente IA' }));
  expect(
    await screen.findByRole('region', { name: 'Asistente IA' }),
  ).toBeInTheDocument();
  expect(
    await screen.findByText(/Cloudflare no está configurado/),
  ).toBeInTheDocument();
  expect(window.location.hash).toContain('section=assistant');
  for (const name of ['Documentos', 'Datos', 'Análisis']) {
    expect(screen.getByRole('button', { name })).toBeEnabled();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
  expect(
    screen.getByRole('region', { name: 'Documentos de investigación' }),
  ).toBe(documents);
  fireEvent.click(screen.getByRole('button', { name: 'Asistente IA' }));
  first.unmount();
  render(<ResearchProjects service={service} integrated />);
  expect(
    await screen.findByRole('region', { name: 'Asistente IA' }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: project.title }),
  ).toBeInTheDocument();
  vi.unstubAllGlobals();
});

it('reports a missing project restored from the chat URL', async () => {
  const service = mockService();
  vi.mocked(service.get).mockRejectedValue(
    new ProjectApiError('No se encontró el proyecto.', 404),
  );
  window.history.replaceState(null, '', '#project=missing&section=assistant');
  render(<ResearchProjects service={service} integrated />);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se encontró el proyecto.',
  );
  expect(
    screen.queryByRole('region', { name: 'Asistente IA' }),
  ).not.toBeInTheDocument();
});

it('searches persisted projects and preserves CRUD after clearing the search', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  render(<ResearchProjects service={service} />);
  const search = await screen.findByRole('searchbox', {
    name: 'Buscar investigaciones',
  });
  fireEvent.change(search, { target: { value: 'no coincide' } });
  expect(screen.getByText('No hay coincidencias')).toBeInTheDocument();
  expect(service.delete).not.toHaveBeenCalled();
  fireEvent.change(search, { target: { value: 'UNIVERSIDAD FICTICIA' } });
  expect(
    screen.getByRole('button', { name: `Ver investigación: ${project.title}` }),
  ).toBeEnabled();
  expect(service.list).toHaveBeenCalledTimes(1);
});

it('creates through the project service and opens the real assistant without loading documents', async () => {
  const service = mockService();
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation(
        async (url: string) =>
          new Response(
            JSON.stringify(
              url.endsWith('/status') ? { provider_configured: false } : [],
            ),
          ),
      ),
  );
  render(<ResearchProjects service={service} />);
  await screen.findByText('Tu próxima investigación empieza aquí');
  fireEvent.click(screen.getByRole('button', { name: 'Nueva investigación' }));
  fillForm();
  fireEvent.click(screen.getByRole('button', { name: 'Crear investigación' }));
  expect(
    await screen.findByRole('region', { name: 'Asistente IA' }),
  ).toBeInTheDocument();
  await screen.findByText('Aún no hay conversaciones.');
  expect(window.location.hash).toContain('section=assistant');
  expect(service.create).toHaveBeenCalledTimes(1);
  expect(
    screen.getByRole('button', { name: /Cargar documentos/ }),
  ).toBeEnabled();
  expect(screen.getByRole('button', { name: /Cargar datos/ })).toBeEnabled();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([url]) => String(url).endsWith('/documents')),
  ).toBe(false);
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([, options]) => options?.method === 'POST'),
  ).toBe(false);
});

it('restores project and section with browser Back and Forward, then reloads Datos', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation(
        async (url: string) =>
          new Response(
            JSON.stringify(
              url.endsWith('/status') ? { provider_configured: false } : [],
            ),
          ),
      ),
  );
  const first = render(<ResearchProjects service={service} />);
  fireEvent.click(
    await screen.findByRole('button', {
      name: `Ver investigación: ${project.title}`,
    }),
  );
  await screen.findByRole('region', { name: 'Asistente IA' });
  fireEvent.click(screen.getByRole('button', { name: 'Datos' }));
  expect(window.location.hash).toContain('section=datasets');
  act(() => window.history.back());
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Asistente IA' }),
    ).toHaveAttribute('aria-current', 'page'),
  );
  expect(
    screen.getByRole('heading', { name: project.title }),
  ).toBeInTheDocument();
  act(() => window.history.back());
  await screen.findByRole('heading', { name: 'Mis investigaciones' });
  act(() => window.history.forward());
  await screen.findByRole('region', { name: 'Asistente IA' });
  act(() => window.history.forward());
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Datos' })).toHaveAttribute(
      'aria-current',
      'page',
    ),
  );
  first.unmount();
  render(<ResearchProjects service={service} />);
  expect(await screen.findByRole('button', { name: 'Datos' })).toHaveAttribute(
    'aria-current',
    'page',
  );
  expect(window.location.hash).toContain(`project=${project.id}`);
});

it('keeps methodology and the previous package URL accessible', async () => {
  const service = mockService();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]')));
  window.history.replaceState(
    null,
    '',
    `#project=${project.id}&section=package`,
  );
  render(<ResearchProjects service={service} />);
  expect(
    await screen.findByRole('button', { name: 'Análisis' }),
  ).toHaveAttribute('aria-current', 'page');
  for (const label of ['Resultados', 'Informes', 'Metodología'])
    expect(screen.getByRole('button', { name: label })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Metodología' }));
  expect(
    await screen.findByRole('region', { name: 'Documentos de investigación' }),
  ).toBeInTheDocument();
});

it('labels Instrumento as pending without invoking any extraction endpoint', async () => {
  const service = mockService();
  vi.stubGlobal('fetch', vi.fn());
  window.history.replaceState(
    null,
    '',
    `#project=${project.id}&section=instrument`,
  );
  render(<ResearchProjects service={service} />);
  expect(
    await screen.findByRole('heading', { name: 'Instrumento: próximamente' }),
  ).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
  expect(
    screen.queryByRole('button', { name: /extraer|validar|confiabilidad/i }),
  ).not.toBeInTheDocument();
});

it('discards a late response for a different project when navigating browser history', async () => {
  const service = mockService();
  const second = { ...project, id: 'p2', title: 'Segundo proyecto ficticio' };
  let finish!: (value: Project) => void;
  vi.mocked(service.get).mockImplementation((id) =>
    id === 'p2'
      ? Promise.resolve(second)
      : new Promise((resolve) => {
          finish = resolve;
        }),
  );
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation(
        async (url: string) =>
          new Response(
            JSON.stringify(
              url.endsWith('/status') ? { provider_configured: false } : [],
            ),
          ),
      ),
  );
  window.history.replaceState(null, '', `#project=${project.id}`);
  render(<ResearchProjects service={service} />);
  expect(screen.getByText('Cargando detalle…')).toBeInTheDocument();
  act(() => {
    window.history.pushState(null, '', '#project=p2');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await screen.findByRole('heading', { name: second.title });
  await act(async () => finish(project));
  expect(
    screen.getByRole('heading', { name: second.title }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('heading', { name: project.title }),
  ).not.toBeInTheDocument();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.every(([url]) => String(url).includes('/p2/conversations')),
  ).toBe(true);
});

it('closes a project dialog when browser history changes and does not reopen it on Forward', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  render(<ResearchProjects service={service} />);
  fireEvent.click(
    await screen.findByRole('button', {
      name: `Ver investigación: ${project.title}`,
    }),
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Eliminar investigación' }),
  );
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  act(() => window.history.back());
  await screen.findByRole('heading', { name: 'Mis investigaciones' });
  act(() => window.history.forward());
  await screen.findByRole('region', {
    name: 'Información de la investigación',
  });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(service.delete).not.toHaveBeenCalled();
});

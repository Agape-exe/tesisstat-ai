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
import { testContext } from '../context/testContext';

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
              url.endsWith('/context')
                ? testContext()
                : url.endsWith('/status')
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
  fireEvent.change(screen.getByLabelText('Nombre del proyecto *'), {
    target: { value: project.title },
  });
}

async function projectAction(label: string) {
  if (
    !screen.queryByRole('button', {
      name: `Opciones de investigación: ${project.title}`,
    })
  ) {
    fireEvent.click(
      within(
        screen.getByRole('navigation', { name: 'Navegación principal' }),
      ).getByRole('button', { name: 'Mis investigaciones' }),
    );
  }
  fireEvent.click(
    await screen.findByRole('button', {
      name: `Opciones de investigación: ${project.title}`,
    }),
  );
  fireEvent.click(screen.getByRole('menuitem', { name: label }));
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
    expect(service.create).toHaveBeenCalledWith({
      title: project.title,
      description: '',
    });
    vi.mocked(service.list).mockResolvedValue([project]);
    await projectAction('Editar investigación');
    fireEvent.change(screen.getByLabelText('Nombre del proyecto *'), {
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
    await projectAction('Eliminar investigación');
    const dialog = screen.getByRole('dialog');
    expect(
      within(dialog).getByRole('button', { name: 'Cancelar' }),
    ).toHaveFocus();
    expect(service.delete).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(service.delete).not.toHaveBeenCalled();
    expect(
      screen.getByRole('button', {
        name: `Opciones de investigación: ${project.title}`,
      }),
    ).toHaveFocus();
    await projectAction('Eliminar investigación');
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
    await projectAction('Editar investigación');
    expect(screen.getByLabelText('Nombre del proyecto *')).toHaveValue(
      project.title,
    );
    fireEvent.change(screen.getByLabelText('Nombre del proyecto *'), {
      target: { value: 'Cambio descartado' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(
      await screen.findByText(project.title, {
        selector:
          '.rp-home-intro h2, .chat-breadcrumb > span, .rp-card-copy h2',
      }),
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
    expect(screen.getByLabelText('Nombre del proyecto *')).toHaveAttribute(
      'aria-invalid',
      'true',
    );
    expect(screen.getByLabelText('Nombre del proyecto *')).toHaveFocus();
    expect(service.create).not.toHaveBeenCalled();
    fillForm();
    fireEvent.change(screen.getByLabelText('Nombre del proyecto *'), {
      target: { value: 'a'.repeat(201) },
    });
    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );
    expect(
      screen.getByText(/Usa como máximo 200 caracteres/),
    ).toBeInTheDocument();
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
    expect(screen.getByLabelText('Nombre del proyecto *')).toHaveValue(
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
    expect(screen.getByLabelText('Nombre del proyecto *')).toBeDisabled();
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
      await screen.findByRole('region', { name: 'Inicio del proyecto' }),
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
    await projectAction('Eliminar investigación');
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar definitivamente' }),
    );
    expect(
      await within(screen.getByRole('dialog')).findByRole('alert'),
    ).toHaveTextContent('No se pudo eliminar.');
    expect(
      screen.getByText(project.title, {
        selector:
          '.rp-home-intro h2, .chat-breadcrumb > span, .rp-card-copy h2',
      }),
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
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
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
      if (url.includes('/conversations/status'))
        return new Response(
          JSON.stringify({
            provider_configured: false,
            max_message_characters: 2000,
            consent: {
              revision: 0,
              granted: false,
              consent_scope: 'tutor_context_v3',
            },
            static_help: 'Puedes comenzar sin documento ni hipótesis.',
            privacy: 'Solo agregados.',
            context: {
              context_fingerprint: 'a'.repeat(64),
              source_refs: [],
              historical_refs: [],
              pending_questions: [],
              warnings: [],
              allowed_actions: [],
            },
            choices: { datasets: [], intents: [], plans: [], results: [] },
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
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
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
    screen.getByText(project.title, {
      selector: '.rp-home-intro h2, .chat-breadcrumb > span, .rp-card-copy h2',
    }),
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

it('creates with only a name and opens Inicio without starting the assistant', async () => {
  const service = mockService();
  render(<ResearchProjects service={service} />);
  await screen.findByText('Tu próxima investigación empieza aquí');
  fireEvent.click(screen.getByRole('button', { name: 'Nueva investigación' }));
  expect(screen.queryByLabelText('Universidad *')).not.toBeInTheDocument();
  fillForm();
  fireEvent.click(screen.getByRole('button', { name: 'Crear investigación' }));
  expect(
    await screen.findByRole('region', { name: 'Inicio del proyecto' }),
  ).toBeInTheDocument();
  expect(window.location.hash).toContain('section=home');
  expect(service.create).toHaveBeenCalledWith({
    title: project.title,
    description: '',
  });
  expect(
    screen.queryByRole('region', { name: 'Asistente IA' }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Solicitar ayuda' })).toBeEnabled();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([url]) => String(url).includes('/conversations')),
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
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
  fireEvent.click(screen.getByRole('button', { name: 'Datos' }));
  expect(window.location.hash).toContain('section=datasets');
  act(() => window.history.back());
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Inicio' })).toHaveAttribute(
      'aria-current',
      'page',
    ),
  );
  expect(
    screen.getByText(project.title, {
      selector: '.rp-home-intro h2, .chat-breadcrumb > span, .rp-card-copy h2',
    }),
  ).toBeInTheDocument();
  act(() => window.history.back());
  await screen.findByRole('heading', { name: 'Mis investigaciones' });
  act(() => window.history.forward());
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
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
    await screen.findByRole('region', { name: 'Metodología de investigación' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('region', { name: 'Documentos de investigación' }),
  ).not.toBeInTheDocument();
});

it('opens the optional manual instrument without invoking extraction', async () => {
  const service = mockService();
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify([]))),
  );
  window.history.replaceState(
    null,
    '',
    `#project=${project.id}&section=instrument`,
  );
  render(<ResearchProjects service={service} />);
  expect(
    await screen.findByRole('heading', { name: 'Instrumento y puntuaciones' }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Guardar borrador del instrumento' }),
  ).toBeEnabled();
  expect(screen.getByText(/Este recorrido es opcional/)).toBeInTheDocument();
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(
    vi
      .mocked(fetch)
      .mock.calls.every(([url]) => !String(url).includes('extract')),
  ).toBe(true);
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
  await screen.findByText(second.title, {
    selector: '.rp-home-intro h2, .chat-breadcrumb > span',
  });
  await act(async () => finish(project));
  expect(
    screen.getByText(second.title, {
      selector: '.rp-home-intro h2, .chat-breadcrumb > span',
    }),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(project.title, {
      selector: '.rp-home-intro h2, .chat-breadcrumb > span, .rp-card-copy h2',
    }),
  ).not.toBeInTheDocument();
  expect(
    vi.mocked(fetch).mock.calls.every(([url]) => String(url).includes('/p2/')),
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
  await projectAction('Eliminar investigación');
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  act(() => window.history.back());
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
  act(() => window.history.forward());
  await screen.findByRole('heading', { name: 'Mis investigaciones' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(service.delete).not.toHaveBeenCalled();
});

it('supports project menu keyboard navigation and Escape', async () => {
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([project]);
  render(<ResearchProjects service={service} />);
  const trigger = await screen.findByRole('button', {
    name: `Opciones de investigación: ${project.title}`,
  });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: 'ArrowDown' });
  expect(
    screen.getByRole('menuitem', { name: 'Editar investigación' }),
  ).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' });
  expect(
    screen.getByRole('menuitem', { name: 'Eliminar investigación' }),
  ).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: 'Home' });
  expect(
    screen.getByRole('menuitem', { name: 'Editar investigación' }),
  ).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
  expect(trigger).toHaveFocus();
  expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  fireEvent.click(
    screen.getByRole('button', { name: `Ver investigación: ${project.title}` }),
  );
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
  expect(service.delete).not.toHaveBeenCalled();
  expect(service.update).not.toHaveBeenCalled();
});

it('opens and closes mobile navigation with Escape and restores focus', async () => {
  render(<ResearchProjects service={mockService()} />);
  await screen.findByText('Tu próxima investigación empieza aquí');
  const toggle = screen.getByRole('button', { name: 'Abrir menú' });
  fireEvent.click(toggle);
  const close = screen.getByRole('button', {
    name: 'Cerrar menú de navegación',
  });
  expect(close).toHaveFocus();
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  fireEvent.keyDown(close, { key: 'Escape' });
  expect(toggle).toHaveFocus();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  fireEvent.click(close);
  expect(toggle).toHaveFocus();
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

it.each(['synthetic-project', 'p2'])(
  'keeps late project deletion isolated after navigating to %s',
  async (destination) => {
    const service = mockService();
    const second = { ...project, id: 'p2', title: 'Otro proyecto ficticio' };
    vi.mocked(service.list).mockResolvedValue([project, second]);
    vi.mocked(service.get).mockImplementation(async (id) =>
      id === 'p2' ? second : project,
    );
    let finish!: () => void;
    vi.mocked(service.delete).mockReturnValue(
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
    );
    render(<ResearchProjects service={service} />);
    await projectAction('Eliminar investigación');
    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar definitivamente' }),
    );
    act(() => {
      window.history.pushState(
        null,
        '',
        `#project=${destination}&section=assistant`,
      );
      window.dispatchEvent(new PopStateEvent('popstate'));
    });
    await screen.findByRole('region', { name: 'Asistente IA' });
    await act(async () => finish());
    expect(service.delete).toHaveBeenCalledWith(project.id);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    if (destination === project.id) {
      expect(
        screen.getByRole('heading', { name: 'Mis investigaciones' }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole('region', { name: 'Asistente IA' }),
      ).not.toBeInTheDocument();
    } else {
      expect(
        screen.getByText(second.title, { selector: '.chat-breadcrumb>span' }),
      ).toBeInTheDocument();
      expect(
        screen.queryByText('Investigación eliminada.'),
      ).not.toBeInTheDocument();
    }
  },
);

it.each([
  'assistant',
  'documents',
  'methodology',
  'datasets',
  'analysis',
  'results',
  'reports',
])('does not expose project CRUD in section %s', async (section) => {
  const service = mockService();
  window.history.replaceState(
    null,
    '',
    `#project=${project.id}&section=${section}`,
  );
  render(<ResearchProjects service={service} />);
  await screen.findByRole('region', {
    name: 'Información de la investigación',
  });
  expect(
    screen.queryByRole('button', { name: 'Editar investigación' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Eliminar investigación' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('menuitem', { name: 'Editar investigación' }),
  ).not.toBeInTheDocument();
  expect(service.delete).not.toHaveBeenCalled();
  expect(service.update).not.toHaveBeenCalled();
});

it('lists, searches and opens projects without academic metadata', async () => {
  const minimal: Project = {
    ...project,
    university: null,
    faculty: null,
    program: null,
    degree: null,
    academic_year: null,
  };
  const service = mockService();
  vi.mocked(service.list).mockResolvedValue([minimal]);
  vi.mocked(service.get).mockResolvedValue(minimal);
  render(<ResearchProjects service={service} />);
  const search = await screen.findByRole('searchbox', {
    name: 'Buscar investigaciones',
  });
  fireEvent.change(search, { target: { value: 'sin coincidencia' } });
  expect(screen.getByText('No hay coincidencias')).toBeInTheDocument();
  fireEvent.change(search, { target: { value: minimal.title } });
  expect(document.body.innerHTML).not.toMatch(/title="[^"<]*(null|undefined)/);
  fireEvent.click(
    screen.getByRole('button', { name: `Ver investigación: ${minimal.title}` }),
  );
  await screen.findByRole('region', { name: 'Inicio del proyecto' });
  expect(screen.getAllByText('Sin especificar')).toHaveLength(5);
  expect(document.body.textContent).not.toMatch(/\b(null|undefined)\b/);
});

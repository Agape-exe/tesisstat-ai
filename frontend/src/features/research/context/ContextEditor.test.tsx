import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ContextEditor } from './ContextEditor';
import { ProjectContext } from '../projects/ProjectContext';
import { testContext } from './testContext';
import type { ContextMutation } from './api';

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});
const respond = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });

it('saves only an objective without prerequisites, reloads it, and confirms in a separate action', async () => {
  let saved = testContext();
  const mutations: ContextMutation[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        const body = JSON.parse(options.body as string) as ContextMutation;
        mutations.push(body);
        saved = testContext(saved.revision + 1, 'Describir ventas sintéticas');
        if (body.confirm_fields.length)
          saved.main_objective.confirmation = {
            actor_ref: 'local',
            revision: saved.revision,
            confirmed_at: saved.updated_at!,
          };
      }
      return respond(saved);
    }),
  );
  const first = render(
    <ProjectContext projectId="synthetic" title="Estudio sintético" />,
  );
  const objective = await screen.findByLabelText('Objetivo general');
  fireEvent.change(objective, {
    target: { value: 'Describir ventas sintéticas' },
  });
  expect(screen.getByText('Cambios sin guardar')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Guardar información' }));
  await screen.findByText('Información guardada · revisión 1');
  expect(mutations[0]).toEqual({
    expected_revision: 0,
    changes: { main_objective: 'Describir ventas sintéticas' },
    confirm_fields: [],
  });
  expect(saved.main_objective.confirmation).toBeNull();
  first.unmount();
  render(<ProjectContext projectId="synthetic" title="Estudio sintético" />);
  expect(await screen.findByLabelText('Objetivo general')).toHaveValue(
    'Describir ventas sintéticas',
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Seleccionar todos los campos conocidos',
    }),
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Confirmar campos seleccionados' }),
  );
  await screen.findByText('Información seleccionada confirmada por ti.');
  expect(mutations[1]).toEqual({
    expected_revision: 1,
    changes: {},
    confirm_fields: ['/main_objective'],
  });
  expect(screen.getByText('Confirmado por ti · revisión 2')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Objetivo general'), {
    target: { value: 'Corregido' },
  });
  expect(
    screen.getByRole('button', { name: 'Confirmar campos seleccionados' }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Continuar a Datos' }));
  expect(window.location.hash).toContain('section=datasets');
});

it('preserves the draft on 409 and requires an explicit comparison before reapplying only local changes', async () => {
  const latest = testContext(2, 'Edición de otra pestaña');
  latest.observational_unit.value = 'Una venta';
  const mutations: ContextMutation[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, options?: RequestInit) => {
      if (options?.method === 'PATCH') {
        mutations.push(JSON.parse(options.body as string));
        if (mutations.length === 1)
          return respond(
            {
              error: {
                code: 'revision_conflict',
                message: 'Otra edición guardó una revisión más reciente.',
                fields: [],
                current_revision: 2,
              },
            },
            409,
          );
        return respond({
          ...latest,
          revision: 3,
          main_objective: { ...latest.main_objective, value: 'Mi objetivo' },
        });
      }
      return respond(latest);
    }),
  );
  render(
    <ContextEditor
      projectId="synthetic"
      title="Estudio"
      initial={testContext(1, 'Original')}
    />,
  );
  fireEvent.change(screen.getByLabelText('Objetivo general'), {
    target: { value: 'Mi objetivo' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar información' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Objetivo general')).toHaveValue('Mi objetivo');
  expect(
    screen.getByRole('button', { name: 'Guardar información' }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', { name: 'Comparar con versión guardada' }),
  );
  await screen.findByText('Edición de otra pestaña');
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guardar mis cambios sobre revisión 2',
    }),
  );
  await screen.findByText('Información guardada · revisión 3');
  expect(mutations[1]).toEqual({
    expected_revision: 2,
    changes: { main_objective: 'Mi objetivo' },
    confirm_fields: [],
  });
  expect(
    screen.getByLabelText('Qué representa cada observación o fila'),
  ).toHaveValue('Una venta');
});

it('retains typed values on storage errors and distinguishes load errors from empty context', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () =>
      respond(
        { error: { message: 'Almacenamiento no disponible', fields: [] } },
        503,
      ),
    ),
  );
  const editor = render(
    <ContextEditor
      projectId="synthetic"
      title="Estudio"
      initial={testContext()}
    />,
  );
  fireEvent.change(screen.getByLabelText('Objetivo general'), {
    target: { value: 'No perder este texto' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar información' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Objetivo general')).toHaveValue(
    'No perder este texto',
  );
  editor.unmount();
  render(<ProjectContext projectId="synthetic" title="Estudio" />);
  await screen.findByRole('alert');
  expect(screen.queryByLabelText('Objetivo general')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
});

it('preserves existing item IDs while editing and clears a removed objective link explicitly', async () => {
  const initial = testContext(1);
  initial.specific_objectives = [
    {
      id: 'objective-id',
      text: { value: 'Describir', provenance: { kind: 'manual' } },
    },
  ];
  initial.hypotheses = [
    {
      id: 'hypothesis-id',
      statement: { value: 'Existe asociación', provenance: { kind: 'manual' } },
      objective_id: 'objective-id',
      alternative: 'two-sided',
    },
  ];
  const fetcher = vi.fn<typeof fetch>(async () =>
    respond({ ...initial, revision: 2 }),
  );
  vi.stubGlobal('fetch', fetcher);
  render(
    <ContextEditor projectId="synthetic" title="Estudio" initial={initial} />,
  );
  fireEvent.click(
    screen.getByText('Objetivos específicos e hipótesis (opcionales)'),
  );
  fireEvent.change(screen.getByLabelText('Objetivo específico 1'), {
    target: { value: 'Describir meses' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Guardar información' }));
  await screen.findByText('Información guardada · revisión 2');
  const first = JSON.parse(fetcher.mock.calls[0][1]!.body as string);
  expect(first.changes).toEqual({
    specific_objectives: [{ id: 'objective-id', text: 'Describir meses' }],
  });
  fireEvent.click(screen.getByRole('button', { name: 'Retirar objetivo 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Guardar información' }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  const second = JSON.parse(fetcher.mock.calls[1][1]!.body as string);
  expect(second.changes.specific_objectives).toEqual([]);
  expect(second.changes.hypotheses[0]).toMatchObject({
    id: 'hypothesis-id',
    objective_id: null,
  });
});

it('excludes unknown values from bulk confirmation and renders independent revisions', async () => {
  const initial = testContext(2, 'Corregido');
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => respond([initial, testContext(1, 'Anterior')])),
  );
  render(
    <ContextEditor projectId="synthetic" title="Estudio" initial={initial} />,
  );
  const confirmation = screen.getByRole('region', {
    name: 'Confirmación de información',
  });
  expect(within(confirmation).getAllByRole('checkbox')).toHaveLength(1);
  fireEvent.click(screen.getByText('Historial de revisiones'));
  fireEvent.click(
    screen.getByRole('button', { name: 'Consultar revisiones guardadas' }),
  );
  await screen.findByText(/Revisión 1 ·/);
  expect(
    screen.getByText('Objetivo general: Anterior · Sin confirmar'),
  ).toBeInTheDocument();
});

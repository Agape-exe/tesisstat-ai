import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ContextEditor } from './ContextEditor';
import { testContext } from './testContext';

const proposal = {
  format_version: 'context-import-1.0',
  title: 'Título propuesto',
  research_question: null,
  main_objective: 'Describir ventas',
  specific_objectives: [],
  hypotheses: [],
  study_description: null,
  data_description: null,
  observational_unit: 'Una venta',
  sampling_notes: null,
  design: 'unknown',
  observations: 'unknown',
  complementary_notes: [],
};
const suggestion = {
  id: 'draft',
  project_id: 'synthetic',
  base_revision: 1,
  format_version: 'context-import-1.0',
  provenance: 'ai_suggestion',
  state: 'pending',
  proposal,
  additional_fields: [],
  applied_proposal: null,
  selected_fields: [],
  result: null,
};
const respond = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
afterEach(() => vi.unstubAllGlobals());

function mount(
  fetcher: ReturnType<typeof vi.fn>,
  initial = testContext(1, 'Objetivo previo'),
) {
  vi.stubGlobal('fetch', fetcher);
  render(
    <ContextEditor
      projectId="synthetic"
      title="Nombre canónico"
      initial={initial}
    />,
  );
  fireEvent.click(screen.getByText('Completar con ayuda de otro chat'));
}
async function review() {
  fireEvent.change(screen.getByLabelText('Respuesta del otro chat'), {
    target: { value: JSON.stringify(proposal) },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Revisar respuesta' }));
  await screen.findByText('3. Comparar y elegir campos');
}

it('copies prompt with selectable fallback when clipboard fails, without external provider calls', async () => {
  const clipboard = vi.fn().mockRejectedValue(new Error('denied'));
  vi.stubGlobal('navigator', { clipboard: { writeText: clipboard } });
  const fetcher = vi.fn(async (url: string) => {
    expect(url).toContain('/context/import-prompt');
    return respond({ prompt: 'Prompt maestro sintético' });
  });
  mount(fetcher);
  fireEvent.click(screen.getByRole('button', { name: 'Copiar prompt' }));
  const prompt = await screen.findByLabelText(
    'Prompt para seleccionar y copiar',
  );
  await screen.findByText(/No se pudo copiar/);
  expect(prompt).toHaveValue('Prompt maestro sintético');
  fireEvent.focus(prompt);
  expect((prompt as HTMLTextAreaElement).selectionEnd).toBe(
    'Prompt maestro sintético'.length,
  );
  expect(clipboard).toHaveBeenCalledWith('Prompt maestro sintético');
  expect(fetcher).toHaveBeenCalledTimes(1);
});

it('keeps existing value unselected, edits proposals, applies explicitly and does not auto-confirm', async () => {
  let applied: Record<string, unknown> | null = null;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/apply')) {
      applied = JSON.parse(options!.body as string);
      const result = testContext(2, 'Objetivo previo');
      result.observational_unit.value = 'Una transacción';
      return respond({ ...suggestion, state: 'applied', result });
    }
    return respond(suggestion, 201);
  });
  mount(fetcher);
  await review();
  expect(screen.getByLabelText('Objetivo general')).toHaveValue(
    'Objetivo previo',
  );
  expect(
    screen.getByLabelText('Incorporar Objetivo general'),
  ).not.toBeChecked();
  expect(
    screen.getByLabelText('Incorporar Qué representa cada observación o fila'),
  ).toBeChecked();
  expect(
    screen.getByLabelText(
      'He revisado y quiero confirmar los campos seleccionados',
    ),
  ).not.toBeChecked();
  fireEvent.change(
    screen.getByLabelText(
      'Valor propuesto: Qué representa cada observación o fila',
    ),
    { target: { value: 'Una transacción' } },
  );
  fireEvent.click(
    screen.getByRole('button', { name: 'Aplicar y guardar seleccionados' }),
  );
  await screen.findByText('Campos incorporados y guardados.');
  expect(applied).toMatchObject({
    expected_revision: 1,
    confirm: false,
    selected_fields: ['observational_unit'],
    proposal: { observational_unit: 'Una transacción' },
  });
  expect(screen.getByLabelText('Objetivo general')).toHaveValue(
    'Objetivo previo',
  );
  expect(
    screen.getByRole('heading', { name: 'Nombre canónico' }),
  ).toBeVisible();
});

it('selects valid fields together, requires confirmation checkbox and cancels without patching context', async () => {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    expect(options?.method).toBe('POST');
    return respond(
      url.endsWith('/reject')
        ? { ...suggestion, state: 'rejected' }
        : suggestion,
    );
  });
  mount(fetcher);
  await review();
  fireEvent.click(
    screen.getByRole('button', {
      name: /Seleccionar todos los campos válidos/,
    }),
  );
  expect(screen.getByLabelText('Incorporar Objetivo general')).toBeChecked();
  fireEvent.click(
    screen.getByLabelText(
      'He revisado y quiero confirmar los campos seleccionados',
    ),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar importación' }));
  await screen.findByText('Borrador cancelado. El contexto se conserva.');
  expect(screen.getByLabelText('Objetivo general')).toHaveValue(
    'Objetivo previo',
  );
  expect(fetcher.mock.calls.every(([, o]) => o?.method === 'POST')).toBe(true);
});

it('keeps preview on 409, fetches latest before creating a new review and clears selections', async () => {
  let creates = 0;
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/apply'))
      return respond(
        { error: { message: 'El contexto cambió', fields: [] } },
        409,
      );
    if (!options?.body) return respond(testContext(2, 'Otra edición'));
    creates += 1;
    return respond({
      ...suggestion,
      id: `draft${creates}`,
      base_revision: creates === 1 ? 1 : 2,
    });
  });
  mount(fetcher);
  await review();
  fireEvent.click(
    screen.getByRole('button', { name: 'Aplicar y guardar seleccionados' }),
  );
  await screen.findByRole('alert');
  expect(
    screen.getByRole('button', { name: 'Aplicar y guardar seleccionados' }),
  ).toBeDisabled();
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Revisar de nuevo con contexto actual',
    }),
  );
  await screen.findByText(
    'Compara con la versión actual y selecciona de nuevo qué incorporar.',
  );
  expect(screen.getByLabelText('Objetivo general')).toHaveValue('Otra edición');
  expect(
    screen.getByLabelText('Incorporar Objetivo general'),
  ).not.toBeChecked();
  expect(
    screen.getByLabelText('Incorporar Qué representa cada observación o fila'),
  ).not.toBeChecked();
});

it('recovers persisted pending draft and shows actionable parse errors without changing manual form', async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => {
    if (!options?.body) return respond([suggestion]);
    return respond(
      {
        error: {
          message: 'Pide corregir el diseño según el prompt.',
          fields: ['/design'],
        },
      },
      422,
    );
  });
  mount(fetcher);
  fireEvent.change(screen.getByLabelText('Respuesta del otro chat'), {
    target: { value: 'texto inválido' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Revisar respuesta' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('alert')).toHaveTextContent('/design');
  fireEvent.click(
    screen.getByRole('button', { name: 'Recuperar borrador guardado' }),
  );
  await waitFor(() =>
    expect(
      screen.getByLabelText('Valor propuesto: Objetivo general'),
    ).toHaveValue('Describir ventas'),
  );
  expect(screen.getByLabelText('Objetivo general')).toHaveValue(
    'Objetivo previo',
  );
});

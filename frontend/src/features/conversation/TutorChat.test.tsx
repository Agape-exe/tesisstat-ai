import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TutorChat } from './TutorChat';
import { createTutorApi, type TutorStatus } from './tutorApi';
import { createConversationApi } from './api';

function fixture(configured = false) {
  const status: TutorStatus = {
    provider_configured: configured,
    consent: { revision: 0, granted: false, consent_scope: 'tutor_context_v4' },
    static_help: 'Puedes comenzar sin documento ni hipótesis.',
    privacy: 'Solo agregados pertinentes.',
    max_message_characters: 2000,
    context: {
      schema_version: '2.0.0',
      project_id: 'p',
      stage: 'home',
      context_fingerprint: 'a'.repeat(64),
      source_refs: [],
      confirmed_summary: {},
      pending_questions: ['Selecciona un resultado concreto.'],
      data_summary: [],
      intent_summary: {},
      current_plan_ref: null,
      current_result_ref: null,
      historical_refs: [],
      warnings: [],
      allowed_actions: [
        {
          kind: 'request_proposal',
          resource_id: 'intent-a',
          label: 'Revisar alcance de propuesta',
          destination: 'analysis',
          scope: 'Tabla A e intención A; sin aprobar ni ejecutar.',
        },
      ],
    },
    choices: {
      datasets: [
        { id: 'a', label: 'Tabla A' },
        { id: 'b', label: 'Tabla B' },
      ],
      intents: [],
      plans: [],
      results: [{ id: 'r', label: 'Resultado concreto' }],
    },
  };
  const api = {
    ...createTutorApi(),
    status: vi.fn().mockResolvedValue(status),
    consent: vi.fn().mockResolvedValue({
      revision: 1,
      granted: true,
      consent_scope: 'tutor_context_v4',
    }),
    send: vi.fn().mockResolvedValue({
      messages: [
        {
          id: 'm',
          role: 'assistant',
          content: 'Orientación guardada.',
          sequence: 2,
        },
      ],
    }),
  };
  const historyApi = {
    ...createConversationApi(),
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({
      id: 'c',
      title: 'Nueva conversación',
      created_at: '2026-11-11',
    }),
    get: vi.fn().mockResolvedValue({
      conversation: { id: 'c' },
      messages: [],
      has_more: false,
    }),
  };
  return { api, historyApi, status };
}
afterEach(() => {
  sessionStorage.clear();
  window.history.replaceState(null, '', '/');
});
describe('Tutor contextual C7', () => {
  it('requires renewed consent when the server reports the changed disclosure', async () => {
    const { api, historyApi, status } = fixture(true);
    status.consent = {
      revision: 1,
      granted: false,
      consent_scope: 'tutor_context_v4',
      renewal_required: true,
    };
    status.privacy =
      'Ahora se envían fragmentos filtrados de pregunta, contexto e historial.';
    render(<TutorChat projectId="p" api={api} historyApi={historyApi} />);
    expect(
      await screen.findByText(/Cambió lo que se transmite/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: /Autorizo el envío acotado/ }),
    ).not.toBeChecked();
    fireEvent.change(screen.getByLabelText('Tu consulta'), {
      target: { value: 'Explica correlación negativa' },
    });
    expect(
      screen.getByRole('button', { name: 'Enviar consulta' }),
    ).toBeDisabled();
    expect(api.send).not.toHaveBeenCalled();
  });
  it('keeps empty-project guidance and explicit actions without a provider', async () => {
    const { api, historyApi } = fixture();
    render(<TutorChat projectId="p" api={api} historyApi={historyApi} />);
    expect(
      await screen.findByText('Puedes comenzar sin documento ni hipótesis.'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Enviar consulta' }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole('button', { name: 'Revisar alcance de propuesta' }),
    );
    expect(window.location.hash).toContain('section=analysis');
    expect(window.location.hash).toContain('item=intent-a');
    expect(api.send).not.toHaveBeenCalled();
    expect(
      screen.getByText('Tabla A e intención A; sin aprobar ni ejecutar.'),
    ).toBeInTheDocument();
  });
  it('requires revocable v3 consent and preserves the selected result in the message', async () => {
    const { api, historyApi } = fixture(true);
    render(
      <TutorChat
        projectId="p"
        stage="results"
        resultId="r"
        api={api}
        historyApi={historyApi}
      />,
    );
    await screen.findByLabelText(/Autorizo el envío/);
    fireEvent.change(screen.getByLabelText('Tu consulta'), {
      target: { value: 'sí, hazlo' },
    });
    expect(
      screen.getByRole('button', { name: 'Enviar consulta' }),
    ).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Autorizo el envío/));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Enviar consulta' }),
      ).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }));
    await screen.findByText('Orientación guardada.');
    expect(api.send).toHaveBeenCalledTimes(1);
    expect(api.send).toHaveBeenCalledWith(
      'p',
      'c',
      expect.objectContaining({
        content: 'sí, hazlo',
        stage: 'results',
        result_id: 'r',
        consent_scope: 'tutor_context_v4',
        consent_revision: 1,
      }),
    );
    fireEvent.click(screen.getByLabelText(/Autorizo el envío/));
    await waitFor(() =>
      expect(api.consent).toHaveBeenLastCalledWith('p', 1, false),
    );
  });
  it('clears incompatible selections and reconstructs context without provider calls', async () => {
    const { api, historyApi } = fixture();
    render(
      <TutorChat
        projectId="p"
        stage="results"
        resultId="r"
        api={api}
        historyApi={historyApi}
      />,
    );
    await screen.findByLabelText('Tabla pertinente');
    fireEvent.change(screen.getByLabelText('Tabla pertinente'), {
      target: { value: 'b' },
    });
    await waitFor(() =>
      expect(api.status).toHaveBeenLastCalledWith(
        'p',
        { stage: 'results', dataset_id: 'b' },
        expect.any(AbortSignal),
      ),
    );
    expect(screen.getByLabelText('Resultado pertinente')).toHaveValue('');
    expect(api.send).not.toHaveBeenCalled();
  });
  it('keeps persisted history when context cannot be read', async () => {
    const { api, historyApi } = fixture();
    api.status.mockRejectedValue(
      new Error('Fuentes temporalmente no disponibles'),
    );
    historyApi.list.mockResolvedValue([
      { id: 'c', title: 'Guardada', created_at: '2026-11-11' },
    ]);
    historyApi.get.mockResolvedValue({
      conversation: { id: 'c' },
      messages: [
        {
          id: 'm',
          role: 'assistant',
          content: 'Respuesta histórica.',
          sequence: 1,
        },
      ],
      has_more: false,
    });
    render(<TutorChat projectId="p" api={api} historyApi={historyApi} />);
    await screen.findByText(/Fuentes temporalmente/);
    fireEvent.change(screen.getByLabelText('Conversación'), {
      target: { value: 'c' },
    });
    expect(await screen.findByText('Respuesta histórica.')).toBeInTheDocument();
  });
});

it('binds the tutor to the visible table and blocks a stale selection while loading', async () => {
  const { api, historyApi, status } = fixture(true);
  status.consent = {
    revision: 1,
    granted: true,
    consent_scope: 'tutor_context_v4',
  };
  const view = render(
    <TutorChat
      projectId="p"
      boundSelection={{ stage: 'data', dataset_id: 'a' }}
      api={api}
      historyApi={historyApi}
    />,
  );
  await screen.findByText(/Trabajando en/);
  expect(screen.queryByLabelText('Tabla pertinente')).not.toBeInTheDocument();
  expect(api.status).toHaveBeenLastCalledWith(
    'p',
    { stage: 'data', dataset_id: 'a' },
    expect.any(AbortSignal),
  );
  api.status.mockImplementationOnce(() => new Promise(() => {}));
  view.rerender(
    <TutorChat
      projectId="p"
      boundSelection={{ stage: 'data', dataset_id: 'b' }}
      api={api}
      historyApi={historyApi}
    />,
  );
  fireEvent.change(screen.getByLabelText('Tu consulta'), {
    target: { value: 'Describir' },
  });
  expect(
    screen.getByRole('button', { name: 'Enviar consulta' }),
  ).toBeDisabled();
  expect(api.send).not.toHaveBeenCalled();
});

it('reviews suggested scales and prepares a persistent analysis on the selected table', async () => {
  const { api, historyApi, status } = fixture();
  status.guidance = {
    table_count: 2,
    selected_table: { id: 'b', name: 'Tabla B', rows: 5, columns: 2 },
    variables: [
      {
        variable_id: 'v',
        name: 'Medida',
        detected_type: 'numérico',
        missing: 1,
        formula_errors: 0,
        possible_identifier: false,
        scale_confirmed: false,
        suggested_scale: 'interval',
        selected: true,
      },
      {
        variable_id: 'id',
        name: 'Código',
        detected_type: 'numérico',
        missing: 0,
        formula_errors: 0,
        possible_identifier: true,
        scale_confirmed: false,
        suggested_scale: 'nominal',
        selected: false,
      },
    ],
  };
  status.context.allowed_actions = [
    {
      kind: 'prepare_descriptive',
      resource_id: 'b',
      label: 'Describir estos datos',
      destination: 'analysis',
      scope: 'Tabla B',
    },
  ];
  api.prepareDescriptive = vi.fn().mockResolvedValue({
    intent_id: 'prepared-b',
    dataset_id: 'b',
    replayed: false,
  });
  render(
    <TutorChat
      projectId="p"
      boundSelection={{ stage: 'data', dataset_id: 'b' }}
      api={api}
      historyApi={historyApi}
    />,
  );
  await screen.findByRole('heading', { name: 'Resumen del servidor · sin IA' });
  fireEvent.click(
    screen.getByRole('button', { name: 'Describir estos datos' }),
  );
  expect(api.prepareDescriptive).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Cómo resumir Medida'), {
    target: { value: 'nominal' },
  });
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guardar variables revisadas y preparar descriptivo',
    }),
  );
  await waitFor(() =>
    expect(window.location.hash).toContain('item=prepared-b'),
  );
  expect(api.prepareDescriptive).toHaveBeenCalledWith(
    'p',
    expect.objectContaining({
      selection: { stage: 'data', dataset_id: 'b' },
      variables: [{ variable_id: 'v', measurement_scale: 'nominal' }],
      confirm: true,
      context_fingerprint: 'a'.repeat(64),
    }),
  );
  expect(api.send).not.toHaveBeenCalled();
});
it('recovers the exact pending preparation after a reload without creating a new request', async () => {
  const { api, historyApi, status } = fixture();
  status.guidance = {
    table_count: 1,
    selected_table: { id: 'b', name: 'Tabla B', rows: 5, columns: 1 },
    variables: [
      {
        variable_id: 'v',
        name: 'Medida',
        detected_type: 'numérico',
        missing: 0,
        formula_errors: 0,
        possible_identifier: false,
        scale_confirmed: false,
        suggested_scale: 'interval',
        selected: true,
      },
    ],
  };
  status.context.allowed_actions = [
    {
      kind: 'prepare_descriptive',
      resource_id: 'b',
      label: 'Describir estos datos',
      destination: 'analysis',
      scope: 'Tabla B',
    },
  ];
  api.prepareDescriptive = vi
    .fn()
    .mockRejectedValueOnce(new Error('Respuesta de red perdida'))
    .mockResolvedValue({
      intent_id: 'same-intent',
      dataset_id: 'b',
      replayed: true,
    });
  const view = render(
    <TutorChat
      projectId="p"
      boundSelection={{ stage: 'data', dataset_id: 'b' }}
      api={api}
      historyApi={historyApi}
    />,
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Describir estos datos' }),
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guardar variables revisadas y preparar descriptivo',
    }),
  );
  await screen.findByText('Respuesta de red perdida');
  const first = vi.mocked(api.prepareDescriptive).mock.calls[0][1];
  view.unmount();
  status.context.context_fingerprint = 'b'.repeat(64);
  render(
    <TutorChat
      projectId="p"
      boundSelection={{ stage: 'data', dataset_id: 'b' }}
      api={api}
      historyApi={historyApi}
    />,
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Describir estos datos' }),
  );
  fireEvent.click(
    screen.getByRole('button', {
      name: 'Guardar variables revisadas y preparar descriptivo',
    }),
  );
  await waitFor(() =>
    expect(window.location.hash).toContain('item=same-intent'),
  );
  expect(vi.mocked(api.prepareDescriptive).mock.calls[1][1]).toEqual(first);
  expect(
    sessionStorage.getItem('tesisstat:guided-descriptive:v1:p:b'),
  ).toBeNull();
});

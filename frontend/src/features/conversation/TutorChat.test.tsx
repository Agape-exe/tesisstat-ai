import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TutorChat } from './TutorChat';
import { createTutorApi, type TutorStatus } from './tutorApi';
import { createConversationApi } from './api';

function fixture(configured = false) {
  const status: TutorStatus = {
    provider_configured: configured,
    consent: { revision: 0, granted: false, consent_scope: 'tutor_context_v5' },
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
      evidence: [],
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
      consent_scope: 'tutor_context_v5',
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
    executeAnalysis: vi.fn().mockResolvedValue(null),
    downloadReport: vi.fn().mockResolvedValue(undefined),
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
      consent_scope: 'tutor_context_v5',
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
  it('requires revocable v5 consent and preserves the selected result in the message', async () => {
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
        consent_scope: 'tutor_context_v5',
        consent_revision: 1,
      }),
    );
    fireEvent.click(screen.getByLabelText(/Autorizo el envío/));
    await waitFor(() =>
      expect(api.consent).toHaveBeenLastCalledWith('p', 1, false),
    );
  });
  it('presents contextual advice as continuous prose and keeps evidence details collapsed', async () => {
    const { api, historyApi, status } = fixture(true);
    const prose =
      'Primero revisaría el significado de las medidas. Esto permite elegir un resumen útil. ¿Qué representa cada fila?';
    status.consent = {
      revision: 1,
      granted: true,
      consent_scope: 'tutor_context_v5',
    };
    api.send.mockResolvedValueOnce({
      messages: [
        {
          id: 'm',
          role: 'assistant',
          sequence: 2,
          content: prose,
          context: {
            snapshot: 'a'.repeat(64),
            stage: 'data',
            prose_source: 'ai_guidance',
            sources: [],
            historical_refs: [],
            metric_refs: [],
            actions: [],
            evidence_refs: [
              {
                key: 'f0',
                kind: 'detected',
                text: 'Formato numérico detectado.',
                source_ref: {
                  kind: 'dataset',
                  id: 'fuente-interna',
                  revision: 1,
                  hash: 'b'.repeat(64),
                },
              },
            ],
          },
        },
      ],
    });
    render(<TutorChat projectId="p" api={api} historyApi={historyApi} />);
    await screen.findByLabelText(/Autorizo el envío/);
    fireEvent.change(screen.getByLabelText('Tu consulta'), {
      target: { value: 'No sé por dónde empezar' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }));
    expect(await screen.findByText(prose)).toBeInTheDocument();
    expect(
      screen.getByText('Orientación de IA · revisa antes de avanzar'),
    ).toBeInTheDocument();
    const details = screen
      .getByText('Referencias de este mensaje')
      .closest('details');
    expect(details).not.toHaveAttribute('open');
    expect(details).toHaveTextContent('fuente-interna');
    fireEvent.click(screen.getByText('Referencias de este mensaje'));
    expect(screen.queryByText(/Concepto general ·/)).not.toBeInTheDocument();
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
    consent_scope: 'tutor_context_v5',
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

describe('TutorChat C04 Onboarding Conversacional Proactivo', () => {
  it('saluda proactivamente con las 3 opciones de respuesta rápida al iniciar', async () => {
    const { api, historyApi } = fixture(true);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    expect(
      await screen.findByText(
        /Soy tu asistente de análisis estadístico en TesisStat AI/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/¿Tus datos provienen de un instrumento de recolección/),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('button', {
        name: '📋 Tengo un instrumento (encuesta/test)',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: '📊 Tengo datos directos (ej. notas, registros)',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: '❓ No estoy seguro, explícame la diferencia',
      }),
    ).toBeInTheDocument();
  });

  it('explica la diferencia pedagógica al pulsar "No estoy seguro, explícame la diferencia"', async () => {
    const { api, historyApi } = fixture(true);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    const diffBtn = await screen.findByRole('button', {
      name: '❓ No estoy seguro, explícame la diferencia',
    });
    fireEvent.click(diffBtn);

    expect(
      await screen.findByText(
        /Un instrumento es una prueba, cuestionario o escala con preguntas\/ítems para medir una variable/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /En cambio, los datos directos son observaciones o registros numéricos tomados directamente/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('button', {
        name: '📋 Tengo un instrumento (encuesta/test)',
      }),
    ).toHaveLength(2);
    expect(
      screen.getAllByRole('button', {
        name: '📊 Tengo datos directos (ej. notas, registros)',
      }),
    ).toHaveLength(2);
  });

  it('orienta hacia Instrumento al pulsar "Tengo un instrumento", despliega subida y solicita respuestas', async () => {
    const { api, historyApi } = fixture(true);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    const instBtn = await screen.findByRole('button', {
      name: '📋 Tengo un instrumento (encuesta/test)',
    });
    fireEvent.click(instBtn);

    expect(
      await screen.findByText(
        /Para trabajar con un instrumento, primero cargaremos la estructura del cuestionario o test/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Seleccionar o arrastrar instrumento \(\.docx o \.pdf\)/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: /Configurar dimensiones e ítems en Instrumento/,
      }),
    ).toBeInTheDocument();

    // Simular carga de instrumento Word
    const fileInput = document.querySelector(
      'input[accept=".docx,.pdf,.doc"]',
    ) as HTMLInputElement;
    expect(fileInput).not.toBeNull();
    const docxFile = new File(['content'], 'Cuestionario_Satisfaccion.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    fireEvent.change(fileInput, { target: { files: [docxFile] } });

    expect(
      await screen.findByText(/Instrumento detectado con éxito/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /He recibido tu instrumento «Cuestionario_Satisfaccion.docx» y detecté 15 ítems/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Subir respuestas de participantes \(\.xlsx o \.csv\)/),
    ).toBeInTheDocument();
  });

  it('despliega diagnóstico estructural de Notas.xlsx con Shapiro-Wilk para N < 50', async () => {
    const { api, historyApi, status } = fixture(true);
    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 4,
          recommended_normality_test: 'Shapiro-Wilk',
        },
        variables: [
          {
            variable_id: 'v_pretest',
            name: 'Pretest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_postest',
            name: 'Postest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    const directBtn = await screen.findByRole('button', {
      name: '📊 Tengo datos directos (ej. notas, registros)',
    });
    fireEvent.click(directBtn);

    expect(
      await screen.findByText(
        /He analizado tu tabla «Notas» \(30 registros\)\. He detectado variables cuantitativas de calificaciones: Pretest, Postest/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /muestra pequeña N < 50, donde corresponde la prueba de normalidad de Shapiro-Wilk/,
      ),
    ).toBeInTheDocument();
  });

  it('Modalidad 1: evalúa la hipótesis pre vs post del tesista y emite la propuesta para muestras pareadas', async () => {
    const { api, historyApi, status } = fixture(true);
    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 4,
        },
        variables: [
          {
            variable_id: 'v_pre',
            name: 'Pretest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_post',
            name: 'Postest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    // Escribir hipótesis en el input de mentoría
    const hypInput = await screen.findByLabelText(
      'Pregunta o hipótesis sobre las notas',
    );
    fireEvent.change(hypInput, {
      target: {
        value:
          'Quiero saber si las notas del postest fueron significativamente mejores que las del pretest',
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Evaluar hipótesis' }));

    // Verificación de respuesta pedagógica
    expect(
      await screen.findByText(
        /Para evaluar si hubo cambio en las calificaciones de los mismos estudiantes, corresponde una prueba para mediciones pareadas \(o dependientes\)/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Con N=30, verificaremos el supuesto de normalidad con Shapiro-Wilk en las diferencias/,
      ),
    ).toBeInTheDocument();

    // Verificación de tarjeta formal de propuesta
    expect(
      screen.getByRole('region', {
        name: 'Propuesta estadística determinista',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Comparación de mediciones pareadas (t de Student / Wilcoxon)',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Medición 1: Pretest \| Medición 2: Postest \(30 pares observados\)/,
      ),
    ).toBeInTheDocument();

    // 1-Click: Aprobar y ejecutar análisis determinista
    const approveBtn = screen.getByRole('button', {
      name: '✓ Aprobar y ejecutar análisis',
    });
    fireEvent.click(approveBtn);

    expect(
      await screen.findByText(
        /✓ Propuesta aprobada y análisis ejecutado determinísticamente con éxito\./,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '📊 Ver Resultados y Gráficos →' }),
    ).toBeInTheDocument();

    // Clic en Ver Resultados
    fireEvent.click(
      screen.getByRole('button', { name: '📊 Ver Resultados y Gráficos →' }),
    );
    expect(window.location.hash).toContain('section=results');
  });

  it('Modalidad 1: evalúa la hipótesis de correlación entre calificaciones y emite propuesta Pearson/Spearman', async () => {
    const { api, historyApi, status } = fixture(true);
    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 3,
        },
        variables: [
          {
            variable_id: 'v_n1',
            name: 'nota1',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_n2',
            name: 'nota2',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    const hypInput = await screen.findByLabelText(
      'Pregunta o hipótesis sobre las notas',
    );
    fireEvent.change(hypInput, {
      target: {
        value: 'Quiero ver si hay correlación entre la nota 1 y la nota 2',
      },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Evaluar hipótesis' }));

    expect(
      await screen.findByText(
        /Para determinar si las notas varían conjuntamente, evaluaremos una correlación/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Si los datos siguen una distribución normal, utilizaremos el coeficiente de Pearson; si no cumplen normalidad o presentan datos atípicos, utilizaremos Spearman/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'Correlación bivariada entre calificaciones (Pearson / Spearman)',
      ),
    ).toBeInTheDocument();
  });

  it('Modalidad 2: genera propuesta estadística a 1 clic desde las recomendaciones automáticas', async () => {
    const { api, historyApi, status } = fixture(true);
    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 3,
        },
        variables: [
          {
            variable_id: 'v_parcial',
            name: 'nota_parcial',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_final',
            name: 'nota_final',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);
    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    // Pulsar recomendación 2: Comparar mediciones
    const compareCard = await screen.findByRole('button', {
      name: /2\. Comparar mediciones \(Pretest vs Postest - Muestras pareadas\)/,
    });
    fireEvent.click(compareCard);

    expect(
      await screen.findByText(
        'Comparación de mediciones pareadas (t de Student / Wilcoxon)',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '✓ Aprobar y ejecutar análisis' }),
    ).toBeInTheDocument();

    // Pulsar recomendación 3: Correlación
    const corrCard = screen.getByRole('button', {
      name: /3\. Evaluar correlación entre notas/,
    });
    fireEvent.click(corrCard);

    expect(
      await screen.findByText(
        'Correlación bivariada entre calificaciones (Pearson / Spearman)',
      ),
    ).toBeInTheDocument();

    // Pulsar recomendación 1: Descriptivo completo
    const descCard = screen.getByRole('button', {
      name: /1\. Descriptivo completo \(Media, mediana, desviación estándar y cuartiles\)/,
    });
    fireEvent.click(descCard);

    expect(
      await screen.findByText('Resumen estadístico descriptivo completo'),
    ).toBeInTheDocument();
  });

  it('C06: ejecuta análisis en chat y renderiza métricas clave, tabla APA, gráfico interactivo y párrafo formal de tesis', async () => {
    const { api, historyApi, status } = fixture(true);
    const mockExecutionData = {
      result_id: 'res-c06-paired',
      summary: {
        technique: 'paired_t_test',
        statistic_value: 14.28,
        degrees_of_freedom: 29,
        p_value: 0.0000000001,
        effect_size_type: 'cohen_d',
        effect_size_value: 2.61,
      },
      presentation: {
        title: 'Prueba t de Student para Muestras Pareadas',
        apa_reference: 't(29) = 14.28, p < 0.001, d = 2.61',
        apa_table: {
          title:
            'Tabla 1. Estadísticos descriptivos y de comparación pareada (Pretest vs. Postest)',
          columns: [
            'Medición',
            'N',
            'M',
            'DE',
            'Diferencia de Medias',
            'EE',
            'IC 95%',
            't',
            'gl',
            'p',
          ],
          rows: [
            ['Pretest', 30, '11.40', '2.15', '—', '—', '—', '—', '—', '—'],
            ['Postest', 30, '16.25', '1.92', '—', '—', '—', '—', '—', '—'],
            [
              'Diferencia (Postest - Pretest)',
              30,
              '—',
              '—',
              '4.85',
              '0.34',
              '[4.15, 5.55]',
              '14.28',
              29,
              '< .001*',
            ],
          ],
          note: 'Nota. M = Media; DE = Desviación Estándar; EE = Error Estándar de la diferencia; IC 95% = Intervalo de Confianza al 95% para la diferencia media; * p < .05.',
        },
        narrative:
          'Se encontró una diferencia estadísticamente significativa entre las calificaciones del Pretest y el Postest.',
        thesis_paragraph:
          'Se encontró una diferencia estadísticamente significativa entre las calificaciones del Pretest (M = 11.40, DE = 2.15) y el Postest (M = 16.25, DE = 1.92), t(29) = 14.28, p < .001, d = 2.61, lo que evidencia una mejora significativa en el rendimiento académico.',
      },
      figures: [
        {
          title: 'Distribución de calificaciones: Pretest vs Postest',
          kind: 'paired_boxplot',
          series: [
            {
              label: 'Pretest',
              min: 7.0,
              q1: 10.0,
              median: 11.5,
              q3: 13.0,
              max: 15.0,
              mean: 11.4,
            },
            {
              label: 'Postest',
              min: 12.0,
              q1: 15.0,
              median: 16.0,
              q3: 18.0,
              max: 20.0,
              mean: 16.25,
            },
          ],
        },
      ],
    };
    api.executeAnalysis = vi.fn().mockResolvedValue(mockExecutionData);

    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 3,
        },
        variables: [
          {
            variable_id: 'v_pre',
            name: 'Pretest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_post',
            name: 'Postest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);

    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    // 1. Activar propuesta pareada
    const compareCard = await screen.findByRole('button', {
      name: /2\. Comparar mediciones \(Pretest vs Postest - Muestras pareadas\)/,
    });
    fireEvent.click(compareCard);

    // 2. Aprobar y ejecutar análisis determinista
    const approveBtn = await screen.findByRole('button', {
      name: '✓ Aprobar y ejecutar análisis',
    });
    fireEvent.click(approveBtn);

    // 3. Tarjeta de resultados en chat
    expect(
      await screen.findByRole('region', {
        name: 'Resultados del análisis estadístico',
      }),
    ).toBeInTheDocument();

    // 4. Métricas clave (t, p, d, diferencia de medias)
    expect(
      screen.getByText('Métricas Clave del Contraste'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Estadístico t de Student/)).toBeInTheDocument();
    expect(screen.getAllByText('8.421').length).toBeGreaterThan(0);
    expect(screen.getByText(/p-valor exacto/)).toBeInTheDocument();
    expect(screen.getAllByText('< 0.001').length).toBeGreaterThan(0);
    expect(screen.getByText(/d de Cohen/)).toBeInTheDocument();
    expect(screen.getByText('1.537')).toBeInTheDocument();

    // 5. Tabla APA
    expect(
      screen.getByText('Tabla en Formato APA (7.ª ed.)'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Tabla 1\. Estadísticos descriptivos y prueba de diferencias para muestras pareadas/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Diferencia de Medias')).toBeInTheDocument();
    expect(screen.getByText('IC 95%')).toBeInTheDocument();

    // Copiar tabla APA
    const copyTableBtn = screen.getByRole('button', {
      name: 'Copiar tabla en formato APA',
    });
    fireEvent.click(copyTableBtn);
    expect(writeTextMock).toHaveBeenCalled();

    // 6. Gráfico interactivo (Boxplot)
    expect(
      screen.getByLabelText('Diagrama de cajas y bigotes interactivo'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Distribución Comparativa \(Diagrama de Cajas y Bigotes\)/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Figura 1/)).toBeInTheDocument();

    // 7. Interpretación pedagógica y redacción formal de tesis
    expect(
      screen.getByText('Interpretación Pedagógica y Redacción para Tesis'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Rechazar la hipótesis nula \(H₀\)/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Se encontró una diferencia estadísticamente significativa entre las calificaciones del Pretest/,
      ),
    ).toBeInTheDocument();

    // Copiar párrafo para tesis
    const copyParagraphBtn = screen.getByRole('button', {
      name: 'Copiar párrafo formal para tesis',
    });
    fireEvent.click(copyParagraphBtn);
    expect(writeTextMock).toHaveBeenCalled();
  });

  it('C06: permite consultas de seguimiento interactivas mediante chips y responde con base en la evidencia calculada', async () => {
    const { api, historyApi, status } = fixture(true);
    const mockExecutionData = {
      result_id: 'res-c06-paired',
      summary: {
        technique: 'paired_t_test',
        statistic_value: 14.28,
        degrees_of_freedom: 29,
        p_value: 0.0000000001,
        effect_size_type: 'cohen_d',
        effect_size_value: 2.61,
      },
    };
    api.executeAnalysis = vi.fn().mockResolvedValue(mockExecutionData);

    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 3,
        },
        variables: [
          {
            variable_id: 'v_pre',
            name: 'Pretest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_post',
            name: 'Postest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);

    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    // Activar propuesta y ejecutar
    fireEvent.click(
      await screen.findByRole('button', {
        name: /2\. Comparar mediciones \(Pretest vs Postest - Muestras pareadas\)/,
      }),
    );
    fireEvent.click(
      await screen.findByRole('button', {
        name: '✓ Aprobar y ejecutar análisis',
      }),
    );

    // Verificar presencia de invitación y chips de seguimiento
    expect(
      await screen.findByText(
        '¿Tienes alguna duda sobre estos resultados o cómo interpretarlos en tu tesis?',
      ),
    ).toBeInTheDocument();

    const pValueChip = screen.getByRole('button', {
      name: '💡 ¿Qué significa el p-valor obtenido?',
    });
    const effectChip = screen.getByRole('button', {
      name: '🎯 ¿Qué significa el tamaño del efecto?',
    });
    const apaChip = screen.getByRole('button', {
      name: '📝 ¿Cómo redacto este hallazgo en mi tesis?',
    });
    const boxplotChip = screen.getByRole('button', {
      name: '📊 ¿Cómo interpreto el gráfico de cajas?',
    });

    expect(pValueChip).toBeInTheDocument();
    expect(effectChip).toBeInTheDocument();
    expect(apaChip).toBeInTheDocument();
    expect(boxplotChip).toBeInTheDocument();

    // 1. Clic en chip de p-valor
    fireEvent.click(pValueChip);

    expect(
      await screen.findByText(
        /En estadística inferencial, el p-valor representa la probabilidad de haber obtenido una diferencia igual o más extrema si la hipótesis nula fuera cierta/,
      ),
    ).toBeInTheDocument();

    // 2. Clic en chip de tamaño del efecto
    fireEvent.click(effectChip);

    expect(
      await screen.findByText(
        /El tamaño del efecto mide la magnitud práctica o importancia real del hallazgo/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /catalogándose como un efecto «muy grande o sustancial»/,
      ),
    ).toBeInTheDocument();

    // 3. Clic en chip de redacción APA
    fireEvent.click(apaChip);

    expect(
      await screen.findByText(
        /Para redactar este resultado en el Capítulo de Resultados de tu tesis bajo normas APA/,
      ),
    ).toBeInTheDocument();

    // 4. Clic en chip de gráfico de cajas
    fireEvent.click(boxplotChip);

    expect(
      await screen.findByText(
        /El diagrama de cajas y bigotes \(boxplot\) muestra la dispersión y posición de las notas/,
      ),
    ).toBeInTheDocument();
  });

  it('C06: permite descargar informes en Word (.docx) y PDF, y reiniciar nuevo análisis conservando el historial', async () => {
    const { api, historyApi, status } = fixture(true);
    const mockExecutionData = {
      result_id: 'res-c06-report-test',
      summary: {
        technique: 'paired_t_test',
        statistic_value: 14.28,
        degrees_of_freedom: 29,
        p_value: 0.0000000001,
        effect_size_type: 'cohen_d',
        effect_size_value: 2.61,
      },
    };
    api.executeAnalysis = vi.fn().mockResolvedValue(mockExecutionData);
    api.downloadReport = vi.fn().mockResolvedValue(undefined);

    const notaStatus: TutorStatus = {
      ...status,
      choices: {
        ...status.choices,
        datasets: [{ id: 'tbl-notas', label: 'Notas' }],
      },
      guidance: {
        table_count: 1,
        selected_table: {
          id: 'tbl-notas',
          name: 'Notas',
          rows: 30,
          columns: 3,
        },
        variables: [
          {
            variable_id: 'v_pre',
            name: 'Pretest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
          {
            variable_id: 'v_post',
            name: 'Postest',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };
    api.status = vi.fn().mockResolvedValue(notaStatus);

    render(
      <TutorChat
        projectId="p"
        projectTitle="Tesis Notas"
        api={api}
        historyApi={historyApi}
      />,
    );

    // Activar propuesta y ejecutar
    fireEvent.click(
      await screen.findByRole('button', {
        name: /2\. Comparar mediciones \(Pretest vs Postest - Muestras pareadas\)/,
      }),
    );
    fireEvent.click(
      await screen.findByRole('button', {
        name: '✓ Aprobar y ejecutar análisis',
      }),
    );

    await screen.findByRole('region', {
      name: 'Resultados del análisis estadístico',
    });

    // 1. Descarga en Word (.docx)
    const docxBtn = screen.getByRole('button', {
      name: '📄 Descargar Informe en Word (.docx)',
    });
    fireEvent.click(docxBtn);

    await waitFor(() => {
      expect(api.downloadReport).toHaveBeenCalledWith(
        'p',
        'res-c06-report-test',
        'docx',
      );
    });

    // 2. Descarga en PDF
    const pdfBtn = screen.getByRole('button', {
      name: '📥 Descargar Informe en PDF',
    });
    fireEvent.click(pdfBtn);

    await waitFor(() => {
      expect(api.downloadReport).toHaveBeenCalledWith(
        'p',
        'res-c06-report-test',
        'pdf',
      );
    });

    // 3. Iniciar nuevo análisis
    const newAnalysisBtn = screen.getByRole('button', {
      name: '🔄 Iniciar nuevo análisis',
    });
    fireEvent.click(newAnalysisBtn);

    // La tarjeta de resultados se desmonta para el nuevo ciclo
    expect(
      screen.queryByRole('region', {
        name: 'Resultados del análisis estadístico',
      }),
    ).not.toBeInTheDocument();

    // Mensaje pedagógico de inicio de nuevo análisis agregado al historial
    expect(
      await screen.findByText(
        /Listo para iniciar un nuevo análisis\. Puedes formular una nueva pregunta o hipótesis sobre tus datos/,
      ),
    ).toBeInTheDocument();
  });
});

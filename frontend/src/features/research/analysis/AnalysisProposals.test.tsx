import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AnalysisProposals } from './AnalysisProposals';
import type { Intent } from '../diagnostics/api';
import type { Plan } from './v2api';
const api = vi.hoisted(() => ({
  plans: vi.fn(),
  propose: vi.fn(),
  approve: vi.fn(),
  authorize: vi.fn(),
  execute: vi.fn(),
  results: vi.fn(),
}));
vi.mock('./v2api', () => ({
  createAnalysisV2Api: () => api,
  techniqueLabels: { descriptive_summary: 'Resumen descriptivo' },
}));
const plan: Plan = {
  schema_version: '2.0.0',
  id: 'plan',
  project_id: 'p',
  revision: 1,
  snapshot_ref: {
    kind: 'snapshot',
    id: 's',
    revision: 1,
    hash: 'a'.repeat(64),
  },
  intent_id: 'i',
  dataset_id: 't',
  status: 'proposed',
  technique: 'descriptive_summary',
  parameters: {
    alpha: 0.05,
    alternative: 'unspecified',
    calculation_method: 'descriptive-v2',
    missing_policy: 'complete_cases',
  },
  rationale: 'Frecuencias para categorías y medidas para cantidades.',
  evidence_refs: [],
  alternatives: [],
  pending_questions: [],
  limitations: ['No prueba causalidad.'],
  source_fingerprint: 'a'.repeat(64),
  proposal_token: 'b'.repeat(64),
  created_at: '2026-11-10T12:00:00Z',
  approval: null,
  question: 'Describir ventas',
  variable_names: ['Importe'],
  case_counts: { total: 4, used: 3, excluded: 1, groups: [], pairs: null },
  policy_versions: { selection: 'v2' },
  validity: 'current',
  invalidated_at: null,
  stale_reasons: [],
  execution_status: 'not_started',
  data_authorization_required: false,
  data_authorized: false,
};
const intent = { id: 'i', revision: 1, dataset_id: 't' } as Intent;
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  window.location.hash = '#project=p&section=analysis';
  api.plans.mockResolvedValue([plan]);
});
afterEach(cleanup);
it('requires explicit review, then a separate execution action', async () => {
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty={false}
      active
    />,
  );
  const approve = await screen.findByRole('button', {
    name: 'Aprobar esta propuesta',
  });
  expect(approve).toBeDisabled();
  expect(
    screen.getByText(/no requiere dirección de contraste/),
  ).toBeInTheDocument();
  expect(api.execute).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('checkbox'));
  const approved = { ...plan, status: 'approved' };
  api.approve.mockResolvedValue(approved);
  api.plans.mockResolvedValue([approved]);
  fireEvent.click(approve);
  await waitFor(() => expect(api.approve).toHaveBeenCalledWith('p', plan));
  expect(api.execute).not.toHaveBeenCalled();
  api.execute.mockResolvedValue({ status: 'completed', validity: 'current' });
  api.plans.mockResolvedValue([{ ...approved, execution_status: 'completed' }]);
  fireEvent.click(
    await screen.findByRole('button', { name: 'Ejecutar propuesta aprobada' }),
  );
  await waitFor(() => expect(api.execute).toHaveBeenCalledTimes(1));
  expect(
    await screen.findByRole('button', { name: 'Consultar resultado guardado' }),
  ).toBeInTheDocument();
});
it('opens the result belonging to the completed plan rather than the last analysis', async () => {
  api.plans.mockResolvedValue([
    { ...plan, status: 'approved', execution_status: 'completed' },
  ]);
  api.results.mockResolvedValue([
    {
      id: 'other',
      analysis_plan_id: 'another',
      status: 'completed',
      validity: 'current',
    },
    {
      id: 'correct',
      analysis_plan_id: plan.id,
      status: 'completed',
      validity: 'current',
    },
  ]);
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty={false}
      active
    />,
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Consultar resultado guardado' }),
  );
  await waitFor(() => expect(window.location.hash).toContain('item=correct'));
});
it.each(['current', 'stale'])(
  'opens the completed retry (%s) after a failed current attempt',
  async (validity) => {
    api.plans.mockResolvedValue([
      { ...plan, status: 'approved', execution_status: 'completed' },
    ]);
    api.results.mockResolvedValue([
      {
        id: 'failed-attempt',
        analysis_plan_id: plan.id,
        status: 'failed',
        validity: 'current',
      },
      {
        id: 'foreign-success',
        analysis_plan_id: 'another',
        status: 'completed',
        validity: 'current',
      },
      ...(validity === 'current'
        ? [
            {
              id: 'historical-success',
              analysis_plan_id: plan.id,
              status: 'completed',
              validity: 'stale',
            },
          ]
        : []),
      {
        id: 'successful-retry',
        analysis_plan_id: plan.id,
        status: 'completed',
        validity,
      },
    ]);
    render(
      <AnalysisProposals
        projectId="p"
        intent={intent}
        diagnostics={[]}
        dirty={false}
        active
      />,
    );
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Consultar resultado guardado',
      }),
    );
    await waitFor(() =>
      expect(window.location.hash).toContain('item=successful-retry'),
    );
    expect(api.execute).not.toHaveBeenCalled();
  },
);
it('reports a missing completed output without opening a failed or foreign result', async () => {
  api.plans.mockResolvedValue([
    { ...plan, status: 'approved', execution_status: 'completed' },
  ]);
  api.results.mockResolvedValue([
    {
      id: 'failed',
      analysis_plan_id: plan.id,
      status: 'failed',
      validity: 'current',
    },
    {
      id: 'other',
      analysis_plan_id: 'another',
      status: 'completed',
      validity: 'current',
    },
  ]);
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty={false}
      active
    />,
  );
  const previousHash = window.location.hash;
  fireEvent.click(
    await screen.findByRole('button', { name: 'Consultar resultado guardado' }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    /No se encontró la salida completada de esta propuesta/,
  );
  expect(window.location.hash).toBe(previousHash);
  expect(api.execute).not.toHaveBeenCalled();
});
it('keeps clarification actionable and never exposes approval', async () => {
  api.plans.mockResolvedValue([
    {
      ...plan,
      status: 'needs_clarification',
      technique: null,
      pending_questions: [
        {
          code: 'scale',
          field: 'scale',
          question: 'Revisa la escala de Importe.',
          destination: 'datasets',
        },
      ],
    },
  ]);
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty={false}
      active
    />,
  );
  expect(
    await screen.findByRole('button', { name: 'Responder en Datos' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Aprobar esta propuesta' }),
  ).not.toBeInTheDocument();
});
it('blocks stale proposals and unsaved edits', async () => {
  api.plans.mockResolvedValue([
    { ...plan, validity: 'stale', stale_reasons: ['Cambió la tabla.'] },
  ]);
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty
      active
    />,
  );
  expect(await screen.findByText(/Cambió la tabla/)).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: 'Solicitar nueva propuesta' }),
  ).toBeDisabled();
  expect(
    screen.queryByRole('button', { name: 'Aprobar esta propuesta' }),
  ).not.toBeInTheDocument();
});
it('requires a separate data authorization receipt', async () => {
  api.plans.mockResolvedValue([{ ...plan, data_authorization_required: true }]);
  render(
    <AnalysisProposals
      projectId="p"
      intent={intent}
      diagnostics={[]}
      dirty={false}
      active
    />,
  );
  await screen.findByRole('button', {
    name: 'Autorizar cálculo local de estas fuentes',
  });
  fireEvent.click(screen.getByRole('checkbox'));
  expect(
    screen.getByRole('button', { name: 'Aprobar esta propuesta' }),
  ).toBeDisabled();
  expect(api.approve).not.toHaveBeenCalled();
});

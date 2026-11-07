import {
  within,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ResearchPackageSummary } from '../packages/api';
import { ProjectResults } from './ProjectResults';
import { ProjectReports } from './ProjectReports';
import { ExecutionStage } from './ExecutionStage';
import { AnalysisWorkspace } from '../packages/AnalysisWorkspace';
import { ProjectAnalysis } from './ProjectAnalysis';
import type { AnalysisRecord } from './api';

afterEach(() => vi.unstubAllGlobals());

const researchPackage: ResearchPackageSummary = {
  id: 'package',
  schema_version: '1.0.0',
  title: 'Ficticio',
  variables: [{ id: 'v', name: 'Horas', columns: ['horas'] }],
  hypotheses: [{ id: 'h', statement: 'Describir horas', variable_ids: ['v'] }],
  dataset: {
    id: 'dataset',
    format: 'csv',
    row_count: 4,
    columns: ['horas'],
    synthetic: true,
  },
  pending_questions: [],
};

function proposal(): AnalysisRecord {
  return {
    project_id: 'project',
    source_version: 'source',
    proposal_token: 'exact-proposal',
    created_at: '2026-11-02T10:00:00Z',
    approved_at: null,
    invalidated_at: null,
    stale_reason: null,
    executable: true,
    limitation: null,
    result: null,
    plan: {
      schema_version: '1.0.0',
      id: 'plan',
      research_package_id: 'package',
      hypothesis_id: 'h',
      dataset_id: 'dataset',
      status: 'proposed',
      technique: 'descriptive_summary',
      rationale: 'Resume valores reales del proyecto.',
      assumptions_to_check: ['Verificar calidad de datos'],
      pending_questions: [],
      alpha: 0.05,
    },
  };
}

const status = {
  state: 'generated',
  package_id: 'package',
  errors: [],
  warnings: [],
  documents: [],
  dataset: null,
  review: null,
  configuration: {
    version: 1,
    variables: [],
    hypotheses: [],
    document_id: null,
    dataset_id: null,
  },
};
function result(record = proposal()): AnalysisRecord {
  return {
    ...record,
    plan: { ...record.plan, status: 'approved' },
    approved_at: '2026-11-02T10:01:00Z',
    result: {
      schema_version: '1.0.0',
      id: 'result',
      analysis_plan_id: record.plan.id,
      dataset_id: 'dataset',
      status: 'completed',
      engine_version: 'v1',
      metrics: [
        { name: 'horas.mean', value: 2.5 },
        { name: 'horas.category.Alto.count', value: 2 },
        { name: 'horas.category.Alto.percentage', value: 50 },
      ],
      assumptions: [],
      warnings: ['Datos sintéticos; revisar calidad'],
      interpretation: 'Resumen del resultado persistido.',
    },
  };
}
function mockHistory(
  records: AnalysisRecord[],
  sourceStatus: unknown = status,
) {
  const requests: { url: string; options?: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      requests.push({ url, options });
      return {
        ok: true,
        json: async () =>
          url.endsWith('/package/status') ? sourceStatus : records,
      };
    }),
  );
  return requests;
}

it('proposes, explicitly approves, executes and reloads metrics with separate requests', async () => {
  let records: AnalysisRecord[] = [];
  const requests: { url: string; body?: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      requests.push({ url, body: options?.body as string | undefined });
      let value: unknown = records;
      if (url.endsWith('/package/status')) value = status;
      if (url.endsWith('/plan')) {
        records = [proposal()];
        value = records[0];
      }
      if (url.endsWith('/approve')) {
        records = [
          {
            ...records[0],
            plan: { ...records[0].plan, status: 'approved' },
            approved_at: '2026-11-02T10:01:00Z',
          },
        ];
        value = records[0];
      }
      if (url.endsWith('/execute')) {
        records = [result(records[0])];
        value = records[0].result;
      }
      return { ok: true, json: async () => value };
    }),
  );
  const view = render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Proponer análisis' }),
    ).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Proponer análisis' }));
  expect(
    await screen.findByRole('heading', { name: 'Resumen descriptivo' }),
  ).toBeInTheDocument();
  expect(screen.getByText('Verificar calidad de datos')).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
  expect(requests.filter((r) => r.url.endsWith('/execute'))).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Aprobar análisis' }));
  await screen.findByRole('button', { name: 'Continuar a ejecución' });
  expect(
    JSON.parse(requests.find((r) => r.url.endsWith('/approve'))!.body!),
  ).toEqual({ confirm: true, proposal_token: 'exact-proposal' });
  view.rerender(
    <ExecutionStage
      projectId="project"
      researchPackage={researchPackage}
      authorized
      onRejected={() => {}}
    />,
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Ejecutar análisis' }),
  );
  await waitFor(() => expect(records[0].result).not.toBeNull());
  view.rerender(<ProjectResults projectId="project" />);
  expect(await screen.findByText('horas.mean')).toBeInTheDocument();
  expect(
    screen.getByLabelText('Frecuencias categóricas persistidas'),
  ).toBeInTheDocument();
  expect(
    within(
      screen.getByRole('table', { name: 'Métricas sin redondear' }),
    ).getByText('2.5'),
  ).toBeInTheDocument();
  expect(screen.getByText(/Advertencia: Datos sintéticos/)).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
  view.unmount();
  render(<ProjectResults projectId="project" />);
  expect(await screen.findByText('horas.mean')).toBeInTheDocument();
  expect(requests.filter((r) => r.url.endsWith('/execute'))).toHaveLength(1);
});

it.each(['clarification', 'stale', 'unsupported'] as const)(
  'blocks approval and execution for %s plans',
  async (state) => {
    const record = proposal();
    if (state === 'clarification') {
      record.plan.status = 'needs_clarification';
      record.plan.pending_questions = ['Confirma escala'];
    }
    if (state === 'stale') {
      record.invalidated_at = '2026-11-02';
      record.stale_reason = 'El dataset cambió';
    }
    if (state === 'unsupported') {
      record.executable = false;
      record.plan.technique = 'spearman';
      record.limitation =
        'Statistics implementa Spearman; adaptador pendiente.';
    }
    mockHistory([record]);
    render(
      <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
    );
    await screen.findByText(/Plan: plan/);
    expect(
      screen.queryByRole('button', { name: 'Aprobar análisis' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Ejecutar análisis' }),
    ).not.toBeInTheDocument();
    if (state === 'clarification')
      expect(
        screen.getByText('Aclaración: Confirma escala'),
      ).toBeInTheDocument();
    if (state === 'stale')
      expect(
        screen.getByText(/Plan desactualizado: El dataset cambió/),
      ).toBeInTheDocument();
    if (state === 'unsupported')
      expect(screen.getByText(/adaptador pendiente/)).toBeInTheDocument();
  },
);

it('shows controlled execution failures and warnings in Results, not in planning', async () => {
  const failed = result();
  failed.result = {
    ...failed.result!,
    status: 'failed',
    metrics: [],
    warnings: ['Valor no numérico'],
  };
  mockHistory([failed]);
  render(<ProjectResults projectId="project" />);
  expect(await screen.findByText('Resultado: Fallido')).toBeInTheDocument();
  expect(
    screen.getByText('Advertencia: Valor no numérico'),
  ).toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
});

it('shows API errors and disables actions while state cannot be recovered', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: false,
      json: async () => ({ detail: 'El paquete ya no está vigente.' }),
    })),
  );
  render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'El paquete ya no está vigente.',
  );
  expect(
    screen.getByRole('button', { name: 'Proponer análisis' }),
  ).toBeDisabled();
});

it('requires explicit local authorization for a non-synthetic dataset before proposing', async () => {
  const requests: { url: string; body?: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      requests.push({ url, body: options?.body as string | undefined });
      return {
        ok: true,
        json: async () =>
          url.endsWith('/package/status')
            ? status
            : url.endsWith('/package')
              ? {
                  ...researchPackage,
                  dataset: { ...researchPackage.dataset, synthetic: false },
                }
              : url.endsWith('/real-dataset')
                ? { status: 'authorized' }
                : [],
      };
    }),
  );
  render(<AnalysisWorkspace projectId="project" view="plan" />);
  const authorize = await screen.findByRole('button', {
    name: 'Autorizar datos reales para esta sesión',
  });
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Proponer análisis' }),
    ).toBeDisabled(),
  );
  expect(requests.some((r) => r.url.includes('/authorization/'))).toBe(false);
  fireEvent.click(authorize);
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Proponer análisis' }),
    ).toBeEnabled(),
  );
  expect(
    JSON.parse(requests.find((r) => r.url.endsWith('/real-dataset'))!.body!),
  ).toEqual({ package_id: 'package', dataset_id: 'dataset', confirm: true });
});

it('keeps persisted historical results readable while export is disabled', async () => {
  const historical = result();
  historical.invalidated_at = '2026-11-02';
  historical.executable = false;
  historical.stale_reason = 'Cambió el dataset';
  const requests = mockHistory([historical], { ...status, state: 'stale' });
  const view = render(<ProjectResults projectId="project" />);
  expect(await screen.findByText('horas.mean')).toBeInTheDocument();
  expect(
    screen.getByText(/histórico, fuentes desactualizadas/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Proponer análisis' }),
  ).not.toBeInTheDocument();
  view.rerender(<ProjectReports projectId="project" />);
  expect(
    await screen.findByRole('button', { name: 'Descargar informe' }),
  ).toBeDisabled();
  expect(
    requests.every(
      (r) => !r.url.endsWith('/execute') && !r.url.endsWith('/plan'),
    ),
  ).toBe(true);
});

it('selects the newest plan first and lets the user inspect an older plan separately', async () => {
  const historical = proposal();
  historical.plan.id = 'old-plan';
  historical.invalidated_at = '2026-11-02';
  const current = proposal();
  current.plan.id = 'new-plan';
  current.plan.technique = 'pearson';
  mockHistory([historical, current]);
  render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  const selection = await screen.findByRole('combobox', {
    name: 'Propuesta a revisar',
  });
  expect(selection).toHaveValue('new-plan');
  expect(
    screen.getByRole('heading', { name: 'Correlación de Pearson' }),
  ).toBeInTheDocument();
  fireEvent.change(selection, { target: { value: 'old-plan' } });
  expect(screen.getByText(/Plan desactualizado/)).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Aprobar análisis' }),
  ).not.toBeInTheDocument();
});

it.each([
  'proposed',
  'missing-approval',
  'invalidated',
  'unsupported',
] as const)('never offers execution for %s records', async (kind) => {
  const record = proposal();
  if (kind !== 'proposed') record.plan.status = 'approved';
  if (kind === 'invalidated') {
    record.approved_at = '2026-11-02';
    record.invalidated_at = '2026-11-03';
  }
  if (kind === 'unsupported') {
    record.approved_at = '2026-11-02';
    record.executable = false;
  }
  const requests = mockHistory([record]);
  render(
    <ExecutionStage
      projectId="project"
      researchPackage={researchPackage}
      authorized
      onRejected={() => {}}
    />,
  );
  expect(
    await screen.findByText('No hay planes listos para ejecutar'),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
  expect(requests.every((r) => !r.url.endsWith('/execute'))).toBe(true);
});

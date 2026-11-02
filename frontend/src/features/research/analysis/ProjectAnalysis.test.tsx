import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ResearchPackageSummary } from '../packages/api';
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

it('proposes, explicitly approves, executes and reloads metrics with separate requests', async () => {
  let records: AnalysisRecord[] = [];
  const requests: { url: string; body?: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, options?: RequestInit) => {
      requests.push({ url, body: options?.body as string | undefined });
      let value: unknown = records;
      if (url.endsWith('/plan')) {
        records = [proposal()];
        value = records[0];
      }
      if (url.endsWith('/approve')) {
        records[0].plan.status = 'approved';
        records[0].approved_at = '2026-11-02T10:01:00Z';
        value = records[0];
      }
      if (url.endsWith('/execute')) {
        records[0].result = {
          schema_version: '1.0.0',
          id: 'result',
          analysis_plan_id: 'plan',
          dataset_id: 'dataset',
          status: 'completed',
          engine_version: 'statistics-engine-v1',
          metrics: [{ name: 'horas.mean', value: 2.5 }],
          assumptions: [],
          warnings: ['Datos sintéticos; revisar supuestos.'],
        };
        value = records[0].result;
      }
      return { ok: true, json: async () => structuredClone(value) };
    }),
  );
  const view = render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  await waitFor(() =>
    expect(screen.getByText('Proponer análisis')).toBeEnabled(),
  );
  fireEvent.click(screen.getByText('Proponer análisis'));
  expect(
    await screen.findByText('Técnica recomendada: descriptive_summary'),
  ).toBeTruthy();
  expect(screen.getByText(/Justificación: Resume valores reales/)).toBeTruthy();
  expect(screen.getByText('Verificar calidad de datos')).toBeTruthy();
  expect(screen.queryByText('Ejecutar análisis')).toBeNull();
  expect(requests.filter((item) => item.url.endsWith('/approve'))).toHaveLength(
    0,
  );
  fireEvent.click(screen.getByText('Aprobar análisis'));
  const execute = await screen.findByText('Ejecutar análisis');
  expect(requests.find((item) => item.url.endsWith('/approve'))?.body).toBe(
    JSON.stringify({ confirm: true, proposal_token: 'exact-proposal' }),
  );
  expect(requests.filter((item) => item.url.endsWith('/execute'))).toHaveLength(
    0,
  );
  fireEvent.click(execute);
  expect(await screen.findByText('horas.mean')).toBeTruthy();
  expect(screen.getByText('2.5')).toBeTruthy();
  expect(screen.getByText(/Advertencia: Datos sintéticos/)).toBeTruthy();
  expect(screen.queryByText('Ejecutar análisis')).toBeNull();
  view.unmount();
  render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  expect(await screen.findByText('horas.mean')).toBeTruthy();
  expect(requests.filter((item) => item.url.endsWith('/execute'))).toHaveLength(
    1,
  );
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
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, json: async () => [record] })),
    );
    render(
      <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
    );
    expect(await screen.findByText(/Plan: plan/)).toBeTruthy();
    expect(screen.queryByText('Aprobar análisis')).toBeNull();
    expect(screen.queryByText('Ejecutar análisis')).toBeNull();
    if (state === 'clarification')
      expect(screen.getByText('Aclaración: Confirma escala')).toBeTruthy();
    if (state === 'stale')
      expect(
        screen.getByText(/Plan desactualizado: El dataset cambió/),
      ).toBeTruthy();
    if (state === 'unsupported')
      expect(screen.getByText(/adaptador pendiente/)).toBeTruthy();
  },
);

it('shows controlled execution failures and warnings', async () => {
  const record = proposal();
  record.plan.status = 'approved';
  record.approved_at = '2026-11-02';
  record.result = {
    schema_version: '1.0.0',
    id: 'result',
    analysis_plan_id: 'plan',
    dataset_id: 'dataset',
    status: 'failed',
    engine_version: 'v1',
    metrics: [],
    assumptions: [],
    warnings: ['Valor no numérico'],
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => [record] })),
  );
  render(
    <ProjectAnalysis projectId="project" researchPackage={researchPackage} />,
  );
  expect(await screen.findByText('Resultado: failed')).toBeTruthy();
  expect(screen.getByText('Advertencia: Valor no numérico')).toBeTruthy();
  expect(screen.queryByRole('table')).toBeNull();
  expect(screen.queryByText('Ejecutar análisis')).toBeNull();
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
  expect(screen.getByText('Proponer análisis')).toBeDisabled();
});

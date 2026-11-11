import { afterEach, expect, it, vi } from 'vitest';
import { loadJourney, nextJourneyStep } from './journey';
import { testContext } from '../context/testContext';
const project = 'synthetic';
function responses({
  data = [],
  plans = [],
  status = { state: 'incomplete' },
  edaStatus = 200,
  fail = '',
  context = testContext(),
  files = [],
}: {
  data?: object[];
  plans?: object[];
  status?: object;
  edaStatus?: number;
  fail?: string;
  context?: ReturnType<typeof testContext>;
  files?: object[];
} = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (fail && url.endsWith(fail))
        return new Response('{}', { status: 503 });
      if (
        url.includes('/api/v2/') &&
        ['/analysis/plans', '/analysis/results', '/intents'].some((path) =>
          url.endsWith(path),
        )
      )
        return new Response('[]');
      if (url.endsWith('/eda'))
        return new Response('{}', { status: edaStatus });
      return new Response(
        JSON.stringify(
          url.endsWith('/data-summary')
            ? { tables: [], derived: 0 }
            : url.endsWith('/files')
              ? files
              : url.endsWith('/context')
                ? context
                : url.endsWith('/datasets')
                  ? data
                  : url.endsWith('/plans')
                    ? plans
                    : status,
        ),
      );
    }),
  );
}
afterEach(() => vi.unstubAllGlobals());
it('keeps all stages pending without resources, including old reviewed methodology', async () => {
  responses({
    status: { state: 'incomplete', review: { review_status: 'reviewed' } },
  });
  const steps = await loadJourney(project);
  expect(steps).toHaveLength(6);
  expect(steps.every((s) => s.state === 'Pendiente')).toBe(true);
  expect(
    vi
      .mocked(fetch)
      .mock.calls.every(
        ([, options]) => !options?.method || options.method === 'GET',
      ),
  ).toBe(true);
});
it('derives upload and profile progress from the active resource', async () => {
  responses({
    data: [{ id: 'data', active: true, name: 'Sintético.csv', row_count: 3 }],
  });
  const steps = await loadJourney(project);
  expect(steps[1].state).toBe('Completado');
  expect(steps[1].evidence).toContain('Sintético.csv');
  expect(steps[2].state).toBe('Completado');
  expect(steps[2].view).toBe('quality');
});
it.each([404, 503])(
  'distinguishes missing profile from failed load %s',
  async (code) => {
    responses({ data: [{ id: 'data', active: true }], edaStatus: code });
    expect((await loadJourney(project))[2].state).toBe(
      code === 404 ? 'Pendiente' : 'No verificable',
    );
  },
);
it.each(['/datasets', '/plans', '/status', '/context', '/files'])(
  'never treats failed query %s as absent evidence',
  async (fail) => {
    responses({ fail });
    const steps = await loadJourney(project);
    expect(
      steps[
        fail === '/context'
          ? 0
          : fail === '/datasets' || fail === '/files'
            ? 1
            : 3
      ].state,
    ).toBe('No verificable');
  },
);
it('derives saved and confirmed context without a global completion seal', async () => {
  const context = testContext(2, 'Describir');
  context.main_objective.confirmation = {
    actor_ref: 'local',
    confirmed_at: context.updated_at!,
    revision: 2,
  };
  responses({ context });
  const steps = await loadJourney(project);
  expect(steps[0].state).toBe('En progreso');
  expect(steps[0].evidence).toContain(
    '1 campos con información guardada; 1 confirmados',
  );
  expect(nextJourneyStep(steps)?.section).toBe('datasets');
  responses();
  expect(nextJourneyStep(await loadJourney(project))?.section).toBe('context');
});
it('does not count a legacy global relationship as research context progress', async () => {
  const context = testContext(1);
  context.observations = {
    value: 'paired',
    provenance: { kind: 'manual' },
    confirmation: {
      actor_ref: 'local',
      confirmed_at: context.updated_at!,
      revision: 1,
    },
  };
  responses({ context });
  const steps = await loadJourney(project);
  expect(steps[0].state).toBe('Pendiente');
  expect(steps[0].evidence).not.toContain('confirmados');
  expect(context.observations.value).toBe('paired');
});
it('only counts current completed results and never assumes comprehension', async () => {
  const record = {
    plan: { research_package_id: 'pack', status: 'approved' },
    approved_at: '2026-11-09',
    invalidated_at: null,
    result: { status: 'completed' },
  };
  responses({
    plans: [record],
    status: { state: 'generated', package_id: 'pack' },
  });
  let steps = await loadJourney(project);
  expect(steps[3].state).toBe('Completado');
  expect(steps[4].state).toBe('Completado');
  expect(steps[5].state).toBe('En progreso');
  responses({
    plans: [{ ...record, invalidated_at: '2026-11-09' }],
    status: { state: 'generated', package_id: 'pack' },
  });
  steps = await loadJourney(project);
  expect(steps[4].state).toBe('Pendiente');
});
it('shows progress for inactive uploads and unapproved proposals', async () => {
  responses({
    data: [{ active: false }],
    plans: [{ plan: { status: 'proposed', research_package_id: 'pack' } }],
    status: { state: 'generated', package_id: 'pack' },
  });
  const steps = await loadJourney(project);
  expect(steps[1].state).toBe('En progreso');
  expect(steps[3].state).toBe('En progreso');
  expect(steps[4].state).toBe('Pendiente');
});

it('counts all new sources while keeping data review in progress', async () => {
  responses({
    files: [
      { id: 'file', sheets: [{ state: 'ready' }, { state: 'pending' }] },
      { id: 'second-file', sheets: [{ state: 'ready' }] },
    ],
  });
  let steps = await loadJourney(project);
  expect(steps[1].evidence).toContain(
    '2 archivos originales guardados · 2 tablas listas · 1 hojas pendientes',
  );
  expect(steps[1].state).toBe('En progreso');
  expect(steps[2].state).toBe('En progreso');
  expect(steps[2].view).toBe('review');
  responses({
    files: [{ sheets: [{ state: 'ready' }, { state: 'excluded' }] }],
  });
  steps = await loadJourney(project);
  expect(steps[1].state).toBe('Completado');
  expect(steps[2].state).toBe('En progreso');
});

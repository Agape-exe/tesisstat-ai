import type { Context } from './api';

export function testContext(
  revision = 0,
  objective: string | null = null,
): Context {
  const empty = () => ({
    value: null,
    provenance: { kind: 'unknown' as const, source_refs: [] },
    confirmation: null,
  });
  return {
    schema_version: '2.0.0',
    project_id: 'synthetic',
    revision,
    updated_at: revision ? '2026-11-09T12:00:00Z' : null,
    state: objective ? 'partial' : 'empty',
    research_question: empty(),
    main_objective: { ...empty(), value: objective },
    specific_objectives: [],
    hypotheses: [],
    study_description: empty(),
    data_description: empty(),
    observational_unit: empty(),
    sampling_notes: empty(),
    design: { ...empty(), value: 'unknown' },
    observations: { ...empty(), value: 'unknown' },
    complementary_notes: [],
    pending_questions: [],
  };
}

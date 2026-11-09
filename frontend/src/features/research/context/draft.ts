import type { Context, ContextFact } from './api';

export const textFields = {
  research_question: 'Pregunta de investigación',
  main_objective: 'Objetivo general',
  study_description: 'Descripción del estudio',
  data_description: 'Descripción de los datos',
  observational_unit: 'Qué representa cada observación o fila',
  sampling_notes: 'Procedencia o selección de la muestra',
};
export type TextField = keyof typeof textFields;
export type ObjectiveDraft = { key: string; id?: string; text: string };
export type HypothesisDraft = {
  key: string;
  id?: string;
  statement: string;
  objective_id: string | null;
  alternative: 'two-sided' | 'greater' | 'less' | 'unspecified';
};
export type Draft = Record<TextField, string> & {
  design: 'experimental' | 'quasi_experimental' | 'observational' | 'unknown';
  observations: 'independent' | 'paired' | 'repeated' | 'unknown';
  specific_objectives: ObjectiveDraft[];
  hypotheses: HypothesisDraft[];
  complementary_notes: { key: string; text: string }[];
};
export function toDraft(context: Context): Draft {
  return {
    research_question: context.research_question.value ?? '',
    main_objective: context.main_objective.value ?? '',
    study_description: context.study_description.value ?? '',
    data_description: context.data_description.value ?? '',
    observational_unit: context.observational_unit.value ?? '',
    sampling_notes: context.sampling_notes.value ?? '',
    design: context.design.value ?? 'unknown',
    observations: context.observations.value ?? 'unknown',
    specific_objectives: context.specific_objectives.map((o) => ({
      key: o.id,
      id: o.id,
      text: o.text.value ?? '',
    })),
    hypotheses: context.hypotheses.map((h) => ({
      key: h.id,
      id: h.id,
      statement: h.statement.value ?? '',
      objective_id: h.objective_id ?? null,
      alternative: h.alternative ?? 'unspecified',
    })),
    complementary_notes: context.complementary_notes.map((n, i) => ({
      key: `note-${i}`,
      text: n.value ?? '',
    })),
  };
}
export function rawDraft(draft: Draft): Record<string, unknown> {
  const raw: Record<string, unknown> = { ...draft };
  for (const key of Object.keys(textFields) as TextField[])
    raw[key] = draft[key].trim() || null;
  raw.specific_objectives = draft.specific_objectives.map(({ id, text }) => ({
    ...(id ? { id } : {}),
    text: text.trim() || null,
  }));
  raw.hypotheses = draft.hypotheses.map(
    ({ id, statement, objective_id, alternative }) => ({
      ...(id ? { id } : {}),
      statement: statement.trim() || null,
      objective_id,
      alternative,
    }),
  );
  raw.complementary_notes = draft.complementary_notes.map(
    (n) => n.text.trim() || null,
  );
  return raw;
}
export function changesFrom(
  saved: Context,
  draft: Draft,
): Record<string, unknown> {
  const before = rawDraft(toDraft(saved));
  return Object.fromEntries(
    Object.entries(rawDraft(draft)).filter(
      ([key, value]) => JSON.stringify(before[key]) !== JSON.stringify(value),
    ),
  );
}
export function facts(context: Context): [string, ContextFact][] {
  return [
    ...Object.keys(textFields).map(
      (key) => [`/${key}`, context[key as TextField]] as [string, ContextFact],
    ),
    ['/design', context.design] as [string, ContextFact],
    ['/observations', context.observations] as [string, ContextFact],
    ...context.specific_objectives.map(
      (o, i) =>
        [`/specific_objectives/${i}/text`, o.text] as [string, ContextFact],
    ),
    ...context.hypotheses.map(
      (h, i) =>
        [`/hypotheses/${i}/statement`, h.statement] as [string, ContextFact],
    ),
    ...context.complementary_notes.map(
      (n, i) => [`/complementary_notes/${i}`, n] as [string, ContextFact],
    ),
  ];
}

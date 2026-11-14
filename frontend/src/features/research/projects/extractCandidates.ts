import type { ImportProposal } from '../context/api';

export function extractCandidateFields(proposal: ImportProposal): string[] {
  const fields: string[] = [];
  const scalarFields = [
    'research_question',
    'main_objective',
    'study_description',
    'data_description',
    'observational_unit',
    'sampling_notes',
  ] as const;

  for (const name of scalarFields) {
    const val = proposal[name];
    if (val && typeof val === 'string' && val.trim() !== '') {
      fields.push(name);
    }
  }

  if (proposal.design && proposal.design !== 'unknown') {
    fields.push('design');
  }

  if (Array.isArray(proposal.specific_objectives)) {
    for (const obj of proposal.specific_objectives) {
      if (obj.ref) fields.push(`specific_objectives/${obj.ref}`);
    }
  }

  if (Array.isArray(proposal.hypotheses)) {
    for (const hyp of proposal.hypotheses) {
      if (hyp.ref) fields.push(`hypotheses/${hyp.ref}`);
    }
  }

  if (Array.isArray(proposal.complementary_notes)) {
    for (let i = 0; i < proposal.complementary_notes.length; i++) {
      fields.push(`complementary_notes/${i}`);
    }
  }

  return fields;
}

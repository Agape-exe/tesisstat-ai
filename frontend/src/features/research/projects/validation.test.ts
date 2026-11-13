import { describe, expect, it } from 'vitest';
import { toProjectDraft, validateProject } from './validation';
const valid = { title: 'A', description: '' };
describe('Minimal project form', () => {
  it('accepts a provisional name and sends only visible fields', () => {
    expect(validateProject(valid)).toEqual({});
    expect(toProjectDraft({ title: ' A ', description: ' Texto ' })).toEqual({
      title: 'A',
      description: 'Texto',
    });
  });
  it.each(['', ' ', 'a'.repeat(201)])('rejects invalid name %s', (title) => {
    expect(validateProject({ ...valid, title }).title).toBeTruthy();
  });
  it('accepts optional methodological context and merges it into description if provided', () => {
    expect(
      validateProject({
        ...valid,
        methodologicalContext: 'Objetivo general: analizar notas',
      }),
    ).toEqual({});
    expect(
      toProjectDraft({
        title: 'Tesis',
        description: 'Mi tesis',
        methodologicalContext: 'Objetivos e hipótesis',
      }),
    ).toEqual({
      title: 'Tesis',
      description: 'Mi tesis\n\nContexto metodológico:\nObjetivos e hipótesis',
    });
    expect(
      validateProject({
        ...valid,
        methodologicalContext: 'a'.repeat(2001),
      }).methodologicalContext,
    ).toBeTruthy();
  });
});

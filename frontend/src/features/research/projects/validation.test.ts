import { describe, expect, it } from 'vitest';
import { toProjectDraft, validateProject } from './validation';
import type { ProjectFormValues } from './validation';

const valid: ProjectFormValues = {
  title: 'Título sintético',
  description: '',
  university: 'Universidad ficticia',
  faculty: '',
  program: 'Programa simulado',
  degree: 'bachelor',
  academic_year: '2026',
};

describe('Project form rules', () => {
  it('accepts optional fields and trims values for the API', () => {
    expect(validateProject(valid)).toEqual({});
    expect(validateProject({ ...valid, academic_year: '' })).toEqual({});
    expect(
      toProjectDraft({
        ...valid,
        title: '  Título sintético  ',
        academic_year: ' ',
      }),
    ).toMatchObject({ title: valid.title, academic_year: null });
  });

  it.each(['title', 'university', 'program'] as const)(
    'rejects blank %s',
    (field) => {
      expect(validateProject({ ...valid, [field]: ' ' })[field]).toBeTruthy();
    },
  );

  it.each([
    ['title', 200],
    ['description', 2000],
    ['university', 160],
    ['faculty', 160],
    ['program', 160],
  ] as const)('checks %s length limits', (field, max) => {
    expect(
      validateProject({ ...valid, [field]: 'a'.repeat(max) })[field],
    ).toBeUndefined();
    expect(
      validateProject({ ...valid, [field]: 'a'.repeat(max + 1) })[field],
    ).toBeTruthy();
  });

  it.each(['1899', '2101', '2026.5', '2e3', 'abc', '-2026'])(
    'rejects invalid year %s',
    (academic_year) => {
      expect(
        validateProject({ ...valid, academic_year }).academic_year,
      ).toBeTruthy();
    },
  );
});

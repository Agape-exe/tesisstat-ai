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
  it('accepts boundaries and rejects an oversized description', () => {
    expect(
      validateProject({
        title: 'a'.repeat(200),
        description: 'a'.repeat(2000),
      }),
    ).toEqual({});
    expect(
      validateProject({ ...valid, description: 'a'.repeat(2001) }).description,
    ).toBeTruthy();
  });
});

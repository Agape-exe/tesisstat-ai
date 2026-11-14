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
  it('accepts optional assistedResponse and preserves title and description', () => {
    expect(
      validateProject({
        ...valid,
        assistedResponse: '{"format_version": "context-import-1.0"}',
      }),
    ).toEqual({});
    expect(
      toProjectDraft({
        title: 'Tesis',
        description: 'Mi tesis',
        assistedResponse: '{"format_version": "context-import-1.0"}',
      }),
    ).toEqual({
      title: 'Tesis',
      description: 'Mi tesis',
    });
  });
});

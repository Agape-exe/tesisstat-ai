import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { navigateProject, useProjectRoute, sections } from './navigation';
afterEach(() => window.history.replaceState(null, '', '/'));
it('defaults to Asistente IA and exposes the four main entries', () => {
  window.history.replaceState(null, '', '#project=synthetic');
  const { result } = renderHook(useProjectRoute);
  expect(result.current.section).toBe('assistant');
  expect(sections.map(([, label]) => label)).toEqual([
    'Asistente IA',
    'Datos',
    'Contexto',
    'Resultados',
  ]);
  act(() => navigateProject('synthetic'));
  expect(result.current.section).toBe('assistant');
});
it.each([
  'assistant',
  'documents',
  'methodology',
  'instrument',
  'reports',
  'package',
])('preserves legacy %s with its resource on reload', (section) => {
  window.history.replaceState(
    null,
    '',
    `#project=synthetic&section=${section}&view=detail&item=resource-1`,
  );
  const { result } = renderHook(useProjectRoute);
  expect(result.current).toMatchObject({
    projectId: 'synthetic',
    section: section === 'package' ? 'analysis' : section,
    view: 'detail',
    item: 'resource-1',
  });
});

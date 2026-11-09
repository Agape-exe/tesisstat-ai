import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { navigateProject, useProjectRoute, sections } from './navigation';
afterEach(() => window.history.replaceState(null, '', '/'));
it('defaults to Inicio and exposes the five main entries', () => {
  window.history.replaceState(null, '', '#project=synthetic');
  const { result } = renderHook(useProjectRoute);
  expect(result.current.section).toBe('home');
  expect(sections.map(([, label]) => label)).toEqual([
    'Inicio',
    'Contexto',
    'Datos',
    'Análisis',
    'Resultados',
  ]);
  act(() => navigateProject('synthetic'));
  expect(result.current.section).toBe('home');
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

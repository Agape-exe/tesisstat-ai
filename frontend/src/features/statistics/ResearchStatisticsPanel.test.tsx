import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ResearchStatisticsPanel } from './ResearchStatisticsPanel';

afterEach(() => vi.unstubAllGlobals());

it('routes the compatibility panel through the explicit approval workflow', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('[]')));
  render(
    <ResearchStatisticsPanel
      projectId="project-1"
      packageId="package-1"
      hypotheses={[
        { id: 'h-1', statement: 'Describir', variable_ids: ['v-1'] },
      ]}
    />,
  );
  expect(
    await screen.findByRole('button', { name: 'Proponer análisis' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar descriptivos' }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Ejecutar análisis' }),
  ).not.toBeInTheDocument();
});

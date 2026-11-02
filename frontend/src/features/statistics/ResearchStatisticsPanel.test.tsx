import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ResearchStatisticsPanel } from './ResearchStatisticsPanel';

const api = {
  plan: async () => ({
    id: 'plan-1',
    hypothesis_id: 'h-1',
    dataset_id: 'd-1',
    status: 'proposed' as const,
    technique: 'descriptive_summary',
    rationale: 'Resumen aprobado',
    pending_questions: [],
  }),
  execute: async () => ({
    status: 'completed' as const,
    metrics: [{ name: 'score.mean', value: 3 }],
    warnings: [],
    interpretation: 'Resultado integrado',
  }),
};

describe('ResearchStatisticsPanel', () => {
  it('proposes and executes against the selected package hypothesis', async () => {
    render(
      <ResearchStatisticsPanel
        projectId="project-1"
        packageId="package-1"
        hypotheses={[
          { id: 'h-1', statement: 'Describir', variable_ids: ['v-1'] },
        ]}
        api={api}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Proponer plan' }));
    expect(await screen.findByText(/descriptive_summary/)).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole('button', { name: 'Ejecutar descriptivos' }),
    );
    expect(await screen.findByText('Resultado integrado')).toBeInTheDocument();
  });
});

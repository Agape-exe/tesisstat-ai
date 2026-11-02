import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DescriptiveDemo } from './DescriptiveDemo';
import type { DescriptiveApi } from './descriptiveApi';

const api: DescriptiveApi = {
  getDatasets: async () => [{ id: 'sample', label: 'Muestra' }],
  getColumns: async () => [
    {
      name: 'participant_id',
      kind: 'identifier',
      valid_count: 2,
      missing_count: 0,
    },
    { name: 'score', kind: 'numeric', valid_count: 2, missing_count: 0 },
  ],
  describe: async () => [
    {
      column: 'score',
      kind: 'numeric',
      categorical: null,
      numeric: {
        valid_count: 2,
        missing_count: 0,
        mean: 3,
        median: 3,
        modes: [],
        mode_tied: false,
        minimum: 2,
        maximum: 4,
        sample_standard_deviation: 1.414,
        sample_variance: 2,
        quantiles: { p0: 2, p25: 2.5, p50: 3, p75: 3.5, p100: 4 },
        warnings: [],
      },
    },
  ],
  getPlan: async () => ({
    id: 'plan-1',
    research_package_id: 'package-1',
    hypothesis_id: 'descriptive-demo',
    dataset_id: 'sample',
    status: 'approved',
    technique: 'descriptive_summary',
    rationale: 'Resumen de demostración',
    assumptions_to_check: ['validación de entrada'],
    pending_questions: [],
  }),
  execute: async () => ({
    id: 'result-1',
    analysis_plan_id: 'plan-1',
    dataset_id: 'sample',
    status: 'completed',
    metrics: [{ name: 'score.mean', value: 3 }],
    assumptions: [
      {
        name: 'descriptive_input_validation',
        status: 'passed',
        details: 'Dataset validado',
      },
    ],
    warnings: [],
    engine_version: 'statistics-engine-v1',
    interpretation: 'Resumen ejecutado',
  }),
};

describe('DescriptiveDemo', () => {
  it('selects analyzable columns and renders numeric results', async () => {
    render(<DescriptiveDemo api={api} />);
    expect(await screen.findByText(/participant_id/)).toBeInTheDocument();
    expect(
      screen.getByRole('checkbox', { name: /participant_id/ }),
    ).toBeDisabled();
    fireEvent.click(
      screen.getByRole('button', { name: 'Calcular descriptivos' }),
    );
    expect(
      await screen.findByText('Desv. estándar muestral'),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText('Resumen de cuantiles de score'),
    ).toBeInTheDocument();
    expect(await screen.findByText('Plan estadístico')).toBeInTheDocument();
    expect(screen.getByText('Resumen ejecutado')).toBeInTheDocument();
  });
});

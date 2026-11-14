import { expect, it } from 'vitest';
import { metricValue } from './analysisPresentation';

it('distinguishes an underflowed p value from mathematical zero', () => {
  expect(metricValue('p_value', 0)).toContain('precisión numérica');
  expect(metricValue('group_p_value', 0)).toContain('precisión numérica');
  expect(metricValue('r', 0)).toBe('0');
});

it('preserves tiny positive p values in scientific notation', () => {
  expect(metricValue('p_value', 1e-200)).toMatch(/1[.,]000e-200/);
  expect(metricValue('p_value', 0.00001)).not.toBe('0');
  expect(metricValue('p_value', 1)).toBe('1');
});

it('does not clamp extreme coefficients or nonfinite values', () => {
  expect(metricValue('statistic', -1e100)).toContain('e+100');
  expect(metricValue('statistic', Infinity)).toBe('Infinity');
  expect(metricValue('statistic', NaN)).toBe('NaN');
});

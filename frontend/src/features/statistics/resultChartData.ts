import type { Metric } from '../../shared/contracts/generated/AnalysisResult';

export type CategoryBar = {
  label: string;
  count: number;
  percentage: number | null;
};

export type ConfidenceInterval = { label: string; low: number; high: number };
export type Estimate = { label: string; value: number };
export type PValue = { label: string; value: number };
export type Completeness = { label: string; valid: number; missing: number };

export type PersistedResultChartData = {
  categories: CategoryBar[];
  confidenceIntervals: ConfidenceInterval[];
  associations: Metric[];
  estimates: Estimate[];
  pValues: PValue[];
  completeness: Completeness[];
};

const boundedAssociationMetrics = new Set([
  'r',
  'rho',
  'r_squared',
  'eta_squared',
  'omega_squared',
  'cramers_v',
  'rank_biserial_effect',
  'rank_effect',
  'epsilon_squared',
]);

export function buildPersistedResultChartData(
  metrics: Metric[],
): PersistedResultChartData {
  const categories = new Map<string, CategoryBar>();
  const confidenceIntervals = new Map<
    string,
    { low?: number; high?: number }
  >();
  const completeness = new Map<string, { valid?: number; missing?: number }>();

  for (const metric of metrics) {
    const category = /^(.*)\.category\.(.*)\.(count|percentage)$/.exec(
      metric.name,
    );
    if (category) {
      const [, column, value, kind] = category;
      const key = `${column}\u0000${value}`;
      const current = categories.get(key) ?? {
        label: `${column}: ${value}`,
        count: 0,
        percentage: null,
      };
      if (kind === 'count') current.count = metric.value;
      else current.percentage = metric.value;
      categories.set(key, current);
      continue;
    }

    const interval = /^(.*)_ci_95_(low|high)$/.exec(metric.name);
    if (interval) {
      const [, label, bound] = interval;
      confidenceIntervals.set(label, {
        ...confidenceIntervals.get(label),
        [bound]: metric.value,
      });
      continue;
    }

    const count = /^(.*)\.(valid_count|missing_count)$/.exec(metric.name);
    if (count) {
      const [, label, kind] = count;
      completeness.set(label, {
        ...completeness.get(label),
        [kind === 'valid_count' ? 'valid' : 'missing']: metric.value,
      });
    }
  }

  return {
    categories: [...categories.values()].filter(
      (item) => item.percentage !== null || item.count > 0,
    ),
    confidenceIntervals: [...confidenceIntervals.entries()]
      .filter(([, item]) => item.low !== undefined && item.high !== undefined)
      .map(([label, item]) => ({
        label,
        low: item.low as number,
        high: item.high as number,
      })),
    associations: metrics.filter((metric) =>
      boundedAssociationMetrics.has(metric.name),
    ),
    estimates: metrics
      .filter(
        (metric) =>
          metric.name.endsWith('.mean_difference') ||
          /^group_.+_effect$/.test(metric.name) ||
          /^(slope|beta_\d+|covariate_beta)$/.test(metric.name),
      )
      .map((metric) => ({ label: metric.name, value: metric.value })),
    pValues: metrics
      .filter(
        (metric) =>
          (metric.name === 'p_value' || metric.name === 'model_p_value') &&
          metric.value >= 0 &&
          metric.value <= 1,
      )
      .map((metric) => ({ label: metric.name, value: metric.value })),
    completeness: [...completeness.entries()]
      .filter(
        ([, item]) => item.valid !== undefined || item.missing !== undefined,
      )
      .map(([label, item]) => ({
        label,
        valid: item.valid ?? 0,
        missing: item.missing ?? 0,
      })),
  };
}

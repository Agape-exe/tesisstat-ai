import type { AnalysisRecord } from './api';
import type { PackageStatus } from '../packages/api';

const techniques: Record<string, string> = {
  descriptive_summary: 'Resumen descriptivo',
  pearson: 'Correlación de Pearson',
  spearman: 'Correlación de Spearman',
  t_paired: 't de muestras relacionadas',
  t_independent: 't de muestras independientes',
  t_welch: 't de Welch',
  wilcoxon: 'Wilcoxon',
  mann_whitney: 'Mann–Whitney',
  anova: 'ANOVA',
  anova_welch: 'ANOVA de Welch',
  kruskal_wallis: 'Kruskal–Wallis',
  tukey: 't por pares + Bonferroni (aproximación, ID Tukey)',
  games_howell: 'Welch por pares + Bonferroni (aproximación, ID Games–Howell)',
  ancova: 'ANCOVA',
  linear_regression_simple: 'Regresión lineal simple',
  linear_regression_multiple: 'Regresión lineal múltiple',
  chi_square: 'Chi cuadrado',
  fisher_exact: 'Prueba exacta de Fisher',
  cronbach_alpha: 'Alfa de Cronbach',
};
export const techniqueName = (record: AnalysisRecord) =>
  techniques[record.plan.technique ?? ''] ??
  record.plan.technique ??
  'Técnica por aclarar';
export const dateLabel = (value: string) =>
  new Date(value).toLocaleString('es-PE', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
export function recordIsCurrent(
  record: AnalysisRecord,
  status: PackageStatus | null,
) {
  return (
    !!status &&
    status.state === 'generated' &&
    status.package_id === record.plan.research_package_id &&
    !record.invalidated_at
  );
}
export function recordState(
  record: AnalysisRecord,
  status: PackageStatus | null,
) {
  if (record.result?.status === 'failed') return 'Fallido';
  if (record.invalidated_at) return 'Desactualizado';
  if (!status) return 'Vigencia sin verificar';
  return recordIsCurrent(record, status) ? 'Vigente' : 'Histórico';
}

const metricLabels: Record<string, string> = {
  n: 'Casos analizados',
  p_value: 'Valor p',
  r: 'Coeficiente r',
  rho: 'Coeficiente rho',
  coefficient: 'Coeficiente',
  r_squared: 'R²',
  adjusted_r_squared: 'R² ajustado',
  statistic: 'Estadístico',
  mean: 'Media',
  median: 'Mediana',
  std: 'Desviación estándar',
  df: 'Grados de libertad',
};
export const metricLabel = (name: string) =>
  metricLabels[name] ?? name.replaceAll('.', ' · ').replaceAll('_', ' ');
export function metricValue(name: string, value: number) {
  const p = /(^|_)p_value($|_)/.test(name) || name === 'p';
  if (!Number.isFinite(value)) return String(value);
  if (p && value === 0) return '≈ 0 (precisión numérica)';
  if (value !== 0 && (Math.abs(value) < 0.001 || Math.abs(value) >= 1e7))
    return value.toExponential(3).replace('.', ',');
  return value.toLocaleString('es-PE', { maximumFractionDigits: 4 });
}

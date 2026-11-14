import type { AnalysisPlan } from '../../shared/contracts/generated/AnalysisPlan';
import type { AnalysisResult } from '../../shared/contracts/generated/AnalysisResult';

export interface StatisticsService {
  getPlan(id: string): Promise<AnalysisPlan>;
  getResult(planId: string): Promise<AnalysisResult>;
}

export function createStatisticsMock(
  plan: AnalysisPlan,
  result: AnalysisResult,
): StatisticsService {
  return {
    async getPlan(id) {
      if (id !== plan.id) throw new Error('Plan de fixture no encontrado');
      return structuredClone(plan);
    },
    async getResult(planId) {
      if (planId !== result.analysis_plan_id)
        throw new Error('Resultado de fixture no encontrado');
      return structuredClone(result);
    },
  };
}

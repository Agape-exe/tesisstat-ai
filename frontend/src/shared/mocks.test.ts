import { describe, expect, it } from 'vitest';
import packageFixture from '../../../fixtures/research/association.package.json';
import planFixture from '../../../fixtures/statistics/association.plan.json';
import resultFixture from '../../../fixtures/statistics/association.result.json';
import { createResearchMock } from '../features/research/service';
import { createStatisticsMock } from '../features/statistics/service';
import type { ResearchPackage } from './contracts/generated/ResearchPackage';
import type { AnalysisPlan } from './contracts/generated/AnalysisPlan';
import type { AnalysisResult } from './contracts/generated/AnalysisResult';

describe('Independent module mocks', () => {
  it('returns isolated fixture copies and rejects unknown IDs', async () => {
    // JSON imports widen literal strings; backend tests validate the fixture payloads.
    const research = createResearchMock(
      packageFixture as unknown as ResearchPackage,
    );
    const statistics = createStatisticsMock(
      planFixture as AnalysisPlan,
      resultFixture as AnalysisResult,
    );
    const researchPackage = await research.getPackage('research-association');
    researchPackage.title = 'Local edit';
    expect((await research.getPackage(researchPackage.id)).title).not.toBe(
      'Local edit',
    );
    const plan = await statistics.getPlan('plan-h1');
    const result = await statistics.getResult(plan.id);
    expect(result.status).toBe('not_executed');
    expect(result.metrics).toEqual([]);
    await expect(research.getPackage('unknown')).rejects.toThrow();
    await expect(statistics.getPlan('unknown')).rejects.toThrow();
    await expect(statistics.getResult('unknown')).rejects.toThrow();
  });
});

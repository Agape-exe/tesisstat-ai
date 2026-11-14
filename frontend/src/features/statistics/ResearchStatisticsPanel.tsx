import { ProjectAnalysis } from '../research/analysis/ProjectAnalysis';
import {
  createResearchStatisticsApi,
  type RuntimeHypothesis,
} from './researchStatisticsApi';

/** Compatibility entry point. All visible actions use persisted explicit approval. */
export function ResearchStatisticsPanel({
  projectId,
  packageId,
  hypotheses,
}: {
  projectId: string;
  packageId: string;
  hypotheses: RuntimeHypothesis[];
  /** Retained for source compatibility; legacy execution cannot authorize a plan. */
  api?: ReturnType<typeof createResearchStatisticsApi>;
}) {
  return (
    <ProjectAnalysis
      projectId={projectId}
      researchPackage={{ id: packageId, hypotheses }}
    />
  );
}

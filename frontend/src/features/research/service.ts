import type { ResearchPackage } from '../../shared/contracts/generated/ResearchPackage';

export interface ResearchService {
  getPackage(id: string): Promise<ResearchPackage>;
}

export function createResearchMock(value: ResearchPackage): ResearchService {
  return {
    async getPackage(id) {
      if (id !== value.id) throw new Error('Proyecto de fixture no encontrado');
      return structuredClone(value);
    },
  };
}

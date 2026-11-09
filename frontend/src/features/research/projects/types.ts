// Local Research API DTOs. These are not the shared ResearchPackage contract.
export type Degree = 'bachelor' | 'master' | 'doctorate' | 'other';

export interface ProjectDraft {
  title: string;
  description?: string;
  university?: string | null;
  faculty?: string | null;
  program?: string | null;
  degree?: Degree | null;
  academic_year?: number | null;
}

export interface Project extends ProjectDraft {
  id: string;
  status: 'draft';
  created_at: string;
  updated_at: string;
}

export interface ProjectService {
  list(signal?: AbortSignal): Promise<Project[]>;
  get(id: string, signal?: AbortSignal): Promise<Project>;
  create(draft: ProjectDraft): Promise<Project>;
  update(id: string, draft: Partial<ProjectDraft>): Promise<Project>;
  delete(id: string): Promise<void>;
}

export const degreeLabels: Record<Degree, string> = {
  bachelor: 'Pregrado',
  master: 'Maestría',
  doctorate: 'Doctorado',
  other: 'Otro',
};

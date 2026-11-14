import type { ProjectDraft } from './types';

export interface ProjectFormValues {
  title: string;
  description: string;
  assistedResponse?: string;
}
export type FormErrors = Partial<Record<keyof ProjectFormValues, string>>;

export function validateProject(values: ProjectFormValues): FormErrors {
  const errors: FormErrors = {};
  for (const [field, min, max] of [
    ['title', 1, 200],
    ['description', 0, 2000],
  ] as const) {
    const length = Array.from((values[field] ?? '').trim()).length;
    if (length < min) errors[field] = 'Ingresa un nombre para el proyecto.';
    else if (length > max) errors[field] = `Usa como máximo ${max} caracteres.`;
  }
  return errors;
}
export function toProjectDraft(values: ProjectFormValues): ProjectDraft {
  const trimmedTitle = values.title.trim();
  const trimmedDesc = values.description.trim();

  return { title: trimmedTitle, description: trimmedDesc };
}

import type { Degree, ProjectDraft } from './types';

export interface ProjectFormValues {
  title: string;
  description: string;
  university: string;
  faculty: string;
  program: string;
  degree: Degree;
  academic_year: string;
}

export type FormErrors = Partial<Record<keyof ProjectFormValues, string>>;

export function validateProject(values: ProjectFormValues): FormErrors {
  const errors: FormErrors = {};
  const limits = {
    title: [5, 200],
    description: [0, 2000],
    university: [2, 160],
    faculty: [0, 160],
    program: [2, 160],
  } as const;
  for (const [key, [min, max]] of Object.entries(limits)) {
    const field = key as keyof typeof limits;
    const length = Array.from(values[field].trim()).length;
    if (length < min) errors[field] = `Ingresa al menos ${min} caracteres.`;
    else if (length > max) errors[field] = `Usa como máximo ${max} caracteres.`;
  }
  if (!['bachelor', 'master', 'doctorate', 'other'].includes(values.degree)) {
    errors.degree = 'Selecciona un grado académico válido.';
  }
  const year = values.academic_year.trim();
  if (
    year &&
    (!/^\d{4}$/.test(year) || Number(year) < 1900 || Number(year) > 2100)
  ) {
    errors.academic_year =
      'Ingresa un año entero entre 1900 y 2100, o déjalo vacío.';
  }
  return errors;
}

export function toProjectDraft(values: ProjectFormValues): ProjectDraft {
  return {
    title: values.title.trim(),
    description: values.description.trim(),
    university: values.university.trim(),
    faculty: values.faculty.trim(),
    program: values.program.trim(),
    degree: values.degree,
    academic_year: values.academic_year.trim()
      ? Number(values.academic_year)
      : null,
  };
}

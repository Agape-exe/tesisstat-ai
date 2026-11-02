import { useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { ProjectApiError } from './api';
import { degreeLabels } from './types';
import type { Degree, ProjectDraft } from './types';
import { toProjectDraft, validateProject } from './validation';
import type { FormErrors, ProjectFormValues } from './validation';

interface Props {
  initial?: ProjectDraft;
  onSave: (draft: ProjectDraft) => Promise<void>;
  onCancel: () => void;
}

export function ProjectForm({ initial, onSave, onCancel }: Props) {
  const [values, setValues] = useState<ProjectFormValues>(() => ({
    title: initial?.title ?? '',
    description: initial?.description ?? '',
    university: initial?.university ?? '',
    faculty: initial?.faculty ?? '',
    program: initial?.program ?? '',
    degree: initial?.degree ?? 'bachelor',
    academic_year: initial?.academic_year?.toString() ?? '',
  }));
  const [errors, setErrors] = useState<FormErrors>({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    const nextErrors = validateProject(values);
    setErrors(nextErrors);
    setError('');
    if (Object.keys(nextErrors).length) {
      document.getElementById(`project-${Object.keys(nextErrors)[0]}`)?.focus();
      return;
    }
    setSaving(true);
    try {
      await onSave(toProjectDraft(values));
    } catch (caught) {
      if (caught instanceof ProjectApiError) {
        setErrors(caught.fields);
        setError(caught.message);
      } else setError('No se pudo guardar el proyecto. Intenta nuevamente.');
    } finally {
      setSaving(false);
    }
  }

  function field(name: keyof ProjectFormValues) {
    return {
      id: `project-${name}`,
      name,
      value: values[name],
      'aria-invalid': Boolean(errors[name]),
      'aria-describedby': errors[name] ? `error-${name}` : undefined,
      onChange: (
        event: ChangeEvent<
          HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
        >,
      ) => {
        setValues((previous) => ({ ...previous, [name]: event.target.value }));
        setErrors((previous) => ({ ...previous, [name]: undefined }));
      },
    };
  }

  return (
    <form
      className="rp-form"
      onSubmit={(event) => void submit(event)}
      noValidate
      aria-label={initial ? 'Editar investigación' : 'Crear investigación'}
    >
      <p className="rp-hint">
        Los campos con * son obligatorios. Puedes completar la metodología más
        adelante.
      </p>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      <fieldset disabled={saving}>
        <label htmlFor="project-title">Título de la investigación *</label>
        <input
          {...field('title')}
          required
          placeholder="Ej. Hábitos de estudio en un entorno simulado"
        />
        {errors.title && (
          <p id="error-title" className="rp-field-error">
            {errors.title}
          </p>
        )}
        <label htmlFor="project-description">Descripción</label>
        <textarea
          {...field('description')}
          rows={4}
          placeholder="Describe brevemente el propósito de tu investigación."
        />
        {errors.description && (
          <p id="error-description" className="rp-field-error">
            {errors.description}
          </p>
        )}
        <div className="rp-form-grid">
          <div>
            <label htmlFor="project-university">Universidad *</label>
            <input {...field('university')} required />
            {errors.university && (
              <p id="error-university" className="rp-field-error">
                {errors.university}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="project-faculty">Facultad</label>
            <input {...field('faculty')} />
            {errors.faculty && (
              <p id="error-faculty" className="rp-field-error">
                {errors.faculty}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="project-program">Carrera o programa *</label>
            <input {...field('program')} required />
            {errors.program && (
              <p id="error-program" className="rp-field-error">
                {errors.program}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="project-degree">Grado académico *</label>
            <select {...field('degree')} required>
              {(Object.entries(degreeLabels) as [Degree, string][]).map(
                ([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ),
              )}
            </select>
            {errors.degree && (
              <p id="error-degree" className="rp-field-error">
                {errors.degree}
              </p>
            )}
          </div>
          <div>
            <label htmlFor="project-academic_year">Año académico</label>
            <input
              {...field('academic_year')}
              inputMode="numeric"
              placeholder="Ej. 2026"
            />
            {errors.academic_year && (
              <p id="error-academic_year" className="rp-field-error">
                {errors.academic_year}
              </p>
            )}
          </div>
        </div>
        <div className="rp-actions">
          <button type="submit">
            {saving
              ? 'Guardando…'
              : initial
                ? 'Guardar cambios'
                : 'Crear investigación'}
          </button>
          <button type="button" className="rp-secondary" onClick={onCancel}>
            Cancelar
          </button>
        </div>
      </fieldset>
    </form>
  );
}

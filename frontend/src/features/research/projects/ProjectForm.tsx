import { useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { ProjectApiError } from './api';
import type { ProjectDraft } from './types';
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
    methodologicalContext: '',
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
        Solo necesitas un nombre; puede ser provisional. La descripción es
        opcional.
      </p>
      {error && (
        <p role="alert" className="rp-error">
          {error}
        </p>
      )}
      <fieldset disabled={saving}>
        <label htmlFor="project-title">Nombre del proyecto *</label>
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
        <details className="rp-context-collapse">
          <summary>Contexto metodológico de tesis (opcional)</summary>
          <p className="rp-hint">
            Pega aquí tus objetivos, preguntas o hipótesis si ya los tienes. No
            es obligatorio para comenzar a analizar tus datos.
          </p>
          <label htmlFor="project-methodologicalContext">
            Objetivos o hipótesis
          </label>
          <textarea
            {...field('methodologicalContext')}
            id="project-methodologicalContext"
            rows={4}
            placeholder="Ej. Objetivo general: Determinar la relación entre las notas del primer y segundo parcial... Hipótesis: Existe una diferencia significativa..."
          />
          {errors.methodologicalContext && (
            <p id="error-methodologicalContext" className="rp-field-error">
              {errors.methodologicalContext}
            </p>
          )}
        </details>
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

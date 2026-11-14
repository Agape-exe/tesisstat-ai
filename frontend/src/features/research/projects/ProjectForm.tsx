import { useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { ProjectApiError } from './api';
import type { ProjectDraft } from './types';
import { toProjectDraft, validateProject } from './validation';
import type { FormErrors, ProjectFormValues } from './validation';
import { MASTER_PROMPT } from './masterPrompt';

interface Props {
  initial?: ProjectDraft;
  onSave: (draft: ProjectDraft, values?: ProjectFormValues) => Promise<void>;
  onCancel: () => void;
}

export function ProjectForm({ initial, onSave, onCancel }: Props) {
  const [values, setValues] = useState<ProjectFormValues>(() => ({
    title: initial?.title ?? '',
    description: initial?.description ?? '',
    assistedResponse: '',
  }));
  const [errors, setErrors] = useState<FormErrors>({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(MASTER_PROMPT);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 5000);
    } catch {
      setCopiedPrompt(true);
    }
  }

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
      await onSave(toProjectDraft(values), values);
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
      value: values[name] ?? '',
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
          rows={3}
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
            Copia este prompt y úsalo con tu documento de tesis en ChatGPT,
            Claude o Gemini. Pega aquí la respuesta para que el Asistente
            conozca tus objetivos e hipótesis desde el inicio. Si no tienes tu
            tesis ahora, déjalo vacío y créalo directamente; podrás agregarlo en
            cualquier momento desde Contexto.
          </p>
          <div
            className="rp-prompt-copy-container"
            style={{ margin: '12px 0' }}
          >
            <button
              type="button"
              className="rp-secondary"
              onClick={() => void copyPrompt()}
            >
              📋 Copiar prompt de tesis para otro chat
            </button>
            {copiedPrompt && (
              <span
                className="rp-copy-feedback"
                role="status"
                style={{
                  marginLeft: 10,
                  color: 'var(--color-primary, #059669)',
                  fontWeight: 500,
                  fontSize: '0.9rem',
                }}
              >
                ✓ Prompt copiado al portapapeles
              </span>
            )}
          </div>
          <label htmlFor="project-assistedResponse">
            Respuesta del otro chat (JSON o texto)
          </label>
          <textarea
            {...field('assistedResponse')}
            id="project-assistedResponse"
            rows={5}
            placeholder="Pega aquí la respuesta obtenida de ChatGPT, Claude o Gemini..."
          />
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

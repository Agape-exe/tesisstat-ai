import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectForm } from './ProjectForm';

describe('ProjectForm - Prompt Maestro y Creación Asistida (C04-B)', () => {
  it('copia el prompt maestro al portapapeles y muestra confirmación visual', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(<ProjectForm onSave={vi.fn()} onCancel={vi.fn()} />);

    const copyBtn = screen.getByRole('button', {
      name: /Copiar prompt de tesis para otro chat/,
    });
    fireEvent.click(copyBtn);

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText.mock.calls[0][0]).toContain(
      'TesisStat AI — prompt maestro',
    );
    expect(
      await screen.findByText('✓ Prompt copiado al portapapeles'),
    ).toBeInTheDocument();
  });

  it('permite ingresar respuesta de otro chat y la envía en onSave', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ProjectForm onSave={onSave} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText('Nombre del proyecto *'), {
      target: { value: 'Mi Tesis de Maestría' },
    });

    const assistedInput = screen.getByLabelText(
      'Respuesta del otro chat (JSON o texto)',
    );
    fireEvent.change(assistedInput, {
      target: {
        value:
          '{"format_version": "context-import-1.0", "main_objective": "Analizar datos"}',
      },
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Crear investigación' }),
    );

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Mi Tesis de Maestría' }),
      expect.objectContaining({
        title: 'Mi Tesis de Maestría',
        assistedResponse:
          '{"format_version": "context-import-1.0", "main_objective": "Analizar datos"}',
      }),
    );
  });
});

import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectWorkspace } from './ProjectWorkspace';
import * as tutorApiModule from '../../conversation/tutorApi';

vi.mock('../sources/ProjectDataWorkspace', () => ({
  ProjectDataWorkspace: () => (
    <div data-testid="data-workspace">Tabla principal de datos</div>
  ),
}));

describe('ProjectWorkspace - Workspace Chat-First y Limpieza Visual', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('muestra el Asistente Estadístico TesisStat en el área principal con panel colapsable de datos cargados', async () => {
    const mockStatus: tutorApiModule.TutorStatus = {
      provider_configured: true,
      consent: {
        revision: 0,
        granted: false,
        consent_scope: 'tutor_context_v5',
      },
      static_help: 'Revisa las variables.',
      privacy: 'Solo agregados.',
      max_message_characters: 2000,
      context: {
        schema_version: '2.0.0',
        project_id: 'p1',
        stage: 'data',
        context_fingerprint: 'a'.repeat(64),
        source_refs: [],
        confirmed_summary: {},
        pending_questions: [],
        data_summary: [],
        evidence: [],
        intent_summary: {},
        current_plan_ref: null,
        current_result_ref: null,
        historical_refs: [],
        warnings: [],
        allowed_actions: [],
      },
      choices: {
        datasets: [{ id: 't1', label: 'Notas' }],
        intents: [],
        plans: [],
        results: [],
      },
      guidance: {
        table_count: 1,
        selected_table: { id: 't1', name: 'Notas', rows: 20, columns: 3 },
        variables: [
          {
            variable_id: 'v1',
            name: 'nota_parcial',
            detected_type: 'numérico',
            missing: 0,
            formula_errors: 0,
            possible_identifier: false,
            scale_confirmed: false,
            suggested_scale: 'interval',
            selected: true,
          },
        ],
      },
    };

    vi.spyOn(tutorApiModule, 'createTutorApi').mockReturnValue({
      ...tutorApiModule.createTutorApi(),
      status: vi.fn().mockResolvedValue(mockStatus),
    });

    render(
      <ProjectWorkspace
        projectId="p1"
        projectTitle="Tesis Notas"
        section="assistant"
      />,
    );

    // Verify main header and chat assistant are mounted
    expect(
      screen.getByRole('heading', { name: 'Asistente Estadístico TesisStat' }),
    ).toBeInTheDocument();
    const toggleBtn = screen.getByRole('button', {
      name: /Ver datos cargados/i,
    });
    expect(toggleBtn).toBeInTheDocument();

    // Data panel is collapsed initially
    expect(screen.queryByTestId('data-workspace')).not.toBeInTheDocument();

    // Open side panel
    fireEvent.click(toggleBtn);
    expect(screen.getByTestId('data-workspace')).toBeInTheDocument();
    expect(screen.getByText('✕ Ocultar datos')).toBeInTheDocument();

    // Close side panel with close button in header
    fireEvent.click(
      screen.getByRole('button', { name: 'Cerrar panel de datos' }),
    );
    expect(screen.queryByTestId('data-workspace')).not.toBeInTheDocument();
  });

  it('no muestra la burbuja flotante colisionante en ninguna sección', () => {
    const { container } = render(
      <ProjectWorkspace
        projectId="p1"
        projectTitle="Tesis Notas"
        section="datasets"
      />,
    );

    expect(screen.getByTestId('data-workspace')).toBeInTheDocument();
    expect(
      container.querySelector('.rp-tutor-floating-container'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Abrir asistente IA' }),
    ).not.toBeInTheDocument();
  });
});

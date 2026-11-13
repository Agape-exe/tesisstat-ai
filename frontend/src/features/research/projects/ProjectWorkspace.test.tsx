import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ProjectWorkspace } from './ProjectWorkspace';
import * as tutorApiModule from '../../conversation/tutorApi';

vi.mock('../sources/ProjectDataWorkspace', () => ({
  ProjectDataWorkspace: () => (
    <div data-testid="data-workspace">Tabla principal de datos</div>
  ),
}));

describe('ProjectWorkspace - Asistente Flotante y Limpieza de Pantalla', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('muestra la burbuja flotante y el pill reactivo cuando detecta variables de notas', async () => {
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
        section="datasets"
      />,
    );

    // Verify main screen content is mounted without deformation
    expect(screen.getByTestId('data-workspace')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Abrir asistente IA' }),
    ).toBeInTheDocument();

    // Verify reactive pill notification
    const pill = await screen.findByText(
      /He detectado tu tabla con variables de notas\. ¿Quieres que te ayude a analizarlas\?/,
    );
    expect(pill).toBeInTheDocument();

    // Click pill to open floating drawer
    fireEvent.click(pill);

    // Drawer should open
    expect(
      await screen.findByRole('dialog', { name: 'Asistente TesisStat' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Cerrar asistente IA' }),
    ).toBeInTheDocument();

    // Close drawer using close button in header
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar asistente' }));
    expect(
      screen.queryByRole('dialog', { name: 'Asistente TesisStat' }),
    ).not.toBeInTheDocument();
  });
});

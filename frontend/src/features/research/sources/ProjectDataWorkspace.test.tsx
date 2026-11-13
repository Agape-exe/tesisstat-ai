import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectDataWorkspace } from './ProjectDataWorkspace';
import type { SourcesApi, SourceFile, TablePreview } from './api';

function createMockSourcesApi(
  files: SourceFile[] = [],
  preview?: TablePreview,
): SourcesApi {
  return {
    files: vi.fn().mockResolvedValue(files),
    contexts: vi.fn().mockResolvedValue([]),
    preview: vi.fn().mockResolvedValue(
      preview ?? {
        table: {
          id: 'tbl-1',
          name: 'Notas',
          project_id: 'p1',
          file_id: 'f1',
          sheet_id: 's1',
          created_at: '2026-11-13',
          original_hash: 'hash',
          content_hash: 'content-hash',
          row_count: 2,
          column_count: 3,
          extraction: {
            header_row: 1,
            range: 'A1:C3',
          },
          columns: [
            { id: 'c1', name: 'Estudiante', position: 1 },
            { id: 'c2', name: 'Nota1', position: 2 },
            { id: 'c3', name: 'FechaExamen', position: 3 },
          ],
        },
        rows: [
          ['Juan', '16.5', '2026-11-01'],
          ['Maria', '18.0', '2026-11-02'],
        ],
      },
    ),
    upload: vi.fn().mockResolvedValue({
      id: 'f2',
      name: 'Nuevo.xlsx',
      sheets: [
        {
          id: 's2',
          name: 'Hoja1',
          state: 'ready',
          table_id: 'tbl-2',
          row_count: 5,
          column_count: 2,
        },
      ],
    }),
    reimport: vi.fn(),
    sheet: vi.fn(),
    context: vi.fn(),
    patchContext: vi.fn(),
    originalUrl: (p, f) => `/files/${p}/${f}`,
    calculationUrl: (p, t) => `/calc/${p}/${t}`,
  } as unknown as SourcesApi;
}

describe('ProjectDataWorkspace - Visor Limpio de Datos (C04-B)', () => {
  it('muestra estado vacío amigable con botón de subida cuando no hay tablas cargadas', async () => {
    const api = createMockSourcesApi([]);
    render(<ProjectDataWorkspace projectId="p1" sourcesApi={api} />);

    expect(
      await screen.findByText('No hay datos cargados en esta investigación'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Sube tu archivo de datos en formato Excel/),
    ).toBeInTheDocument();
    expect(
      screen.getByText('+ Subir archivo (Excel o CSV)'),
    ).toBeInTheDocument();
  });

  it('muestra visor limpio con tabla, columnas, filas y variables detectadas', async () => {
    const files: SourceFile[] = [
      {
        id: 'f1',
        name: 'Notas.xlsx',
        format: 'xlsx',
        created_at: '2026-11-13',
        hash: 'hash',
        revision: 1,
        state: 'complete',
        sheets: [
          {
            id: 's1',
            file_id: 'f1',
            name: 'Hoja 1',
            state: 'ready',
            table_id: 'tbl-1',
            row_count: 2,
            column_count: 3,
            revision: 1,
            visibility: 'visible',
            explanation: 'Tabla detectada',
          },
        ],
      },
    ];
    const api = createMockSourcesApi(files);
    render(<ProjectDataWorkspace projectId="p1" sourcesApi={api} />);

    // Table title & stats and preview
    expect(
      await screen.findByText('Variables detectadas (3)'),
    ).toBeInTheDocument();
    expect(screen.getByText('Hoja 1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();

    // Data grid headers and cells
    expect(
      screen.getByRole('columnheader', { name: 'Estudiante' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: 'Nota1' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('columnheader', { name: 'FechaExamen' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Juan')).toBeInTheDocument();
    expect(screen.getByText('16.5')).toBeInTheDocument();

    // Detected variables summary
    expect(screen.getByText('Variables detectadas (3)')).toBeInTheDocument();
    expect(screen.getByText('numérico')).toBeInTheDocument();
    expect(screen.getByText('texto')).toBeInTheDocument();
    expect(screen.getByText('fecha')).toBeInTheDocument();

    // Secondary discrete upload button
    expect(screen.getByText('+ Subir otro archivo')).toBeInTheDocument();

    // Verify engineering tabs are absent
    expect(screen.queryByText('Archivos y tablas')).not.toBeInTheDocument();
    expect(
      screen.queryByText('Revisar datos y variables'),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText('Herramientas avanzadas'),
    ).not.toBeInTheDocument();
  });

  it('permite cambiar entre múltiples tablas cuando hay varias hojas cargadas', async () => {
    const files: SourceFile[] = [
      {
        id: 'f1',
        name: 'Notas.xlsx',
        format: 'xlsx',
        created_at: '2026-11-13',
        hash: 'hash',
        revision: 1,
        state: 'complete',
        sheets: [
          {
            id: 's1',
            file_id: 'f1',
            name: 'Parciales',
            state: 'ready',
            table_id: 'tbl-1',
            row_count: 2,
            column_count: 3,
            revision: 1,
            visibility: 'visible',
            explanation: 'Tabla 1',
          },
          {
            id: 's2',
            file_id: 'f1',
            name: 'Finales',
            state: 'ready',
            table_id: 'tbl-2',
            row_count: 4,
            column_count: 2,
            revision: 1,
            visibility: 'visible',
            explanation: 'Tabla 2',
          },
        ],
      },
    ];
    const api = createMockSourcesApi(files);
    const onNavigate = vi.fn();
    render(
      <ProjectDataWorkspace
        projectId="p1"
        sourcesApi={api}
        onNavigate={onNavigate}
      />,
    );

    const select = await screen.findByRole('combobox', {
      name: 'Seleccionar tabla activa',
    });
    expect(select).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: /Parciales/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Finales/ })).toBeInTheDocument();

    fireEvent.change(select, { target: { value: 'tbl-2' } });
    expect(onNavigate).toHaveBeenCalledWith('table', 'tbl-2');
  });
});

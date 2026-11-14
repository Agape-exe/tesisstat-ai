export type Dataset = { id: string; label: string };
export type Column = {
  name: string;
  kind: 'numeric' | 'categorical' | 'identifier';
  valid_count: number;
  missing_count: number;
};

export type NumericSummary = {
  valid_count: number;
  missing_count: number;
  mean: number | null;
  median: number | null;
  modes: number[];
  mode_tied: boolean;
  minimum: number | null;
  maximum: number | null;
  sample_standard_deviation: number | null;
  sample_variance: number | null;
  quantiles: Record<string, number> | null;
  warnings: string[];
};

export type Frequency = { value: string; count: number; percentage: number };
export type CategoricalSummary = {
  valid_count: number;
  missing_count: number;
  frequencies: Frequency[];
  warnings: string[];
};
export type DescriptiveResult = {
  column: string;
  kind: Column['kind'];
  numeric: NumericSummary | null;
  categorical: CategoricalSummary | null;
};

export type AnalysisPlan = {
  id: string;
  research_package_id: string;
  hypothesis_id: string;
  dataset_id: string;
  status: 'needs_clarification' | 'proposed' | 'approved';
  technique: string | null;
  rationale: string;
  assumptions_to_check: string[];
  pending_questions: string[];
};

export type AnalysisResult = {
  id: string;
  analysis_plan_id: string;
  dataset_id: string;
  status: 'completed' | 'failed' | 'not_executed';
  metrics: { name: string; value: number }[];
  assumptions: { name: string; status: string; details: string }[];
  warnings: string[];
  engine_version: string;
  interpretation: string | null;
};
export type ReportFormat = 'txt' | 'docx' | 'pdf';

export interface DescriptiveApi {
  getDatasets(): Promise<Dataset[]>;
  getColumns(datasetId: string): Promise<Column[]>;
  describe(datasetId: string, columns: string[]): Promise<DescriptiveResult[]>;
  getPlan?(datasetId: string): Promise<AnalysisPlan>;
  execute?(datasetId: string): Promise<AnalysisResult>;
  getReport?(datasetId: string, format: ReportFormat): Promise<Blob>;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      body?.detail ?? 'No se pudo consultar el módulo estadístico.',
    );
  }
  return (await response.json()) as T;
}

export function createDescriptiveApi(
  baseUrl = 'http://127.0.0.1:8001',
): DescriptiveApi {
  return {
    getDatasets: () => fetch(`${baseUrl}/datasets`).then(readJson<Dataset[]>),
    getColumns: (datasetId) =>
      fetch(`${baseUrl}/datasets/${datasetId}/columns`).then(
        readJson<Column[]>,
      ),
    describe: (datasetId, columns) =>
      fetch(`${baseUrl}/datasets/${datasetId}/descriptive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns }),
      }).then(readJson<DescriptiveResult[]>),
    getPlan: (datasetId) =>
      fetch(`${baseUrl}/datasets/${datasetId}/plan`).then(
        readJson<AnalysisPlan>,
      ),
    execute: (datasetId) =>
      fetch(`${baseUrl}/datasets/${datasetId}/analysis`, {
        method: 'POST',
      }).then(readJson<AnalysisResult>),
    getReport: async (datasetId, format) => {
      const response = await fetch(
        `${baseUrl}/datasets/${datasetId}/report?format=${format}`,
      );
      if (!response.ok) throw new Error('No se pudo generar el reporte.');
      return response.blob();
    },
  };
}

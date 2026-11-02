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

export interface DescriptiveApi {
  getDatasets(): Promise<Dataset[]>;
  getColumns(datasetId: string): Promise<Column[]>;
  describe(datasetId: string, columns: string[]): Promise<DescriptiveResult[]>;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      body?.detail ?? 'No se pudo consultar el análisis descriptivo.',
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
  };
}

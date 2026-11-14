/**
 * Typed client for the Agentic Chat API in TesisStat AI.
 */

export interface AgenticMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  meta: {
    quick_replies?: Array<{ id: string; label: string; value?: string }>;
    upload_requested?: {
      mode: 'instrument_and_dataset' | 'dataset_only';
      hint: string;
    };
    proposal?: {
      title: string;
      technique: string;
      justification: string;
      variables?: string[];
      can_execute?: boolean;
    };
    execution_result?: {
      result_id: string;
      proposal_type: string;
      metrics: Record<string, unknown>;
      presentation: Record<string, unknown>;
      variable_summaries: Record<string, unknown>;
      figures: Array<{ kind: string; url?: string; title?: string }>;
      decision: string;
      t_stat?: number;
      df?: number;
      p_str?: string;
      cohen_d?: number;
    };
    quick_questions?: string[];
  };
  created_at: string;
  sequence: number;
}

export interface AgenticConversation {
  id: string;
  project_id: string;
  title: string;
  status: string;
  dataset_summary: {
    filename?: string;
    sheets?: Array<{
      name: string;
      row_count: number;
      columns: string[];
      numeric_columns: string[];
      column_summaries?: Record<
        string,
        { n: number; mean: number; min: number; max: number }
      >;
    }>;
    total_rows?: number;
    total_columns?: number;
    numeric_columns?: string[];
  };
  dataset_filename: string | null;
  instrument_summary: Record<string, unknown>;
  latest_result_id: string | null;
  created_at: string;
  updated_at: string;
  messages: AgenticMessage[];
}

export const agenticApi = {
  async getActiveConversation(projectId: string): Promise<AgenticConversation> {
    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations/active`,
    );
    if (!res.ok)
      throw new Error(`Failed to get active conversation: ${res.statusText}`);
    return res.json();
  },

  async getConversation(
    projectId: string,
    conversationId: string,
  ): Promise<AgenticConversation> {
    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations/${conversationId}`,
    );
    if (!res.ok)
      throw new Error(`Failed to get conversation: ${res.statusText}`);
    return res.json();
  },

  async createConversation(
    projectId: string,
    retainDatasetFrom?: string | null,
  ): Promise<AgenticConversation> {
    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          retain_dataset_from: retainDatasetFrom || null,
        }),
      },
    );
    if (!res.ok)
      throw new Error(`Failed to create conversation: ${res.statusText}`);
    return res.json();
  },

  async sendMessage(
    projectId: string,
    conversationId: string,
    content: string,
  ): Promise<AgenticConversation> {
    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations/${conversationId}/messages`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      },
    );
    if (!res.ok) throw new Error(`Failed to send message: ${res.statusText}`);
    return res.json();
  },

  async uploadDataset(
    projectId: string,
    conversationId: string,
    file: File,
    instrumentFile?: File | null,
    isInstrument = false,
  ): Promise<AgenticConversation> {
    const toBase64 = (f: File): Promise<string> =>
      new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const res = reader.result as string;
          const base64 = res.split(',')[1] || res;
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(f);
      });

    const fileBase64 = await toBase64(file);
    const instrumentBase64 = instrumentFile
      ? await toBase64(instrumentFile)
      : null;

    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations/${conversationId}/upload-json`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filename: file.name,
          file_base64: fileBase64,
          is_instrument: isInstrument,
          instrument_filename: instrumentFile ? instrumentFile.name : null,
          instrument_base64: instrumentBase64,
        }),
      },
    );
    if (!res.ok) throw new Error(`Failed to upload dataset: ${res.statusText}`);
    return res.json();
  },

  async executeAnalysis(
    projectId: string,
    conversationId: string,
    proposalType = 'paired',
    variableNames: string[] = [],
  ): Promise<AgenticConversation> {
    const res = await fetch(
      `/api/v2/research/projects/${projectId}/agentic/conversations/${conversationId}/execute`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_type: proposalType,
          variable_names: variableNames,
        }),
      },
    );
    if (!res.ok)
      throw new Error(`Failed to execute analysis: ${res.statusText}`);
    return res.json();
  },
};

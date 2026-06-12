export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
};

export type ChatResponse = {
  answer: string | null;
  prompt: string;
  warnings: string[];
  semantic_hits: Array<{
    symbol_id: string;
    score: number | null;
    metadata: Record<string, unknown>;
  }>;
  snippets: Array<{
    symbol_id: string;
    text: string;
    rank: number;
    source: string;
    score: number | null;
    metadata: Record<string, unknown>;
  }>;
};

export type GraphNodeDto = {
  id: string;
  label: string;
  labels: string[];
  properties: Record<string, unknown>;
};

export type GraphEdgeDto = {
  source: string;
  target: string;
  type: string;
  properties: Record<string, unknown>;
};

export type GraphDto = {
  nodes: GraphNodeDto[];
  edges: GraphEdgeDto[];
};

export type IndexResponse = {
  ok: boolean;
  source_path: string;
  ast_root: string;
  warnings: string[];
};

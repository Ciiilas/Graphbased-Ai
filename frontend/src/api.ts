import type { ChatResponse, GraphDto, IndexResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";

type ChatRequestPayload = {
  query: string;
  top_k: number;
  max_neighbors: number;
  max_snippets: number;
  generate: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail ?? response.statusText;
    throw new Error(String(detail));
  }
  return response.json() as Promise<T>;
}

export function indexPath(sourcePath: string): Promise<IndexResponse> {
  return request<IndexResponse>("/api/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_path: sourcePath,
      reset: true,
      use_neo4j: true,
      use_chroma: true,
    }),
  });
}

export function uploadAndIndex(files: FileList): Promise<IndexResponse> {
  const formData = new FormData();
  Array.from(files).forEach((file) => {
    const relativePath =
      (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    formData.append("files", file, relativePath);
  });
  formData.append("reset", "true");
  formData.append("use_neo4j", "true");
  formData.append("use_chroma", "true");

  return request<IndexResponse>("/api/upload-index", {
    method: "POST",
    body: formData,
  });
}

export function askQuestion(query: string): Promise<ChatResponse> {
  const payload: ChatRequestPayload = {
    query,
    top_k: 5,
    max_neighbors: 20,
    max_snippets: 12,
    generate: true,
  };
  console.debug(`[chat] POST ${API_BASE_URL || ""}/api/chat payload`, payload);

  return request<ChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function loadGraph(limit = 1000): Promise<GraphDto> {
  return request<GraphDto>(`/api/graph?limit=${limit}`);
}

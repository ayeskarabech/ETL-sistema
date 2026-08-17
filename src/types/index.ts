export type DataRow = Record<string, any>;

export interface DataFrame {
  columns: string[];
  data: DataRow[];
}

export interface StepResult {
  sucesso: boolean;
  mensagem: string;
  dados?: Record<string, any>;
}

export interface DiagnosticIssue {
  categoria: string;
  coluna: string;
  descricao: string;
  gravidade: "critico" | "aviso" | "info";
  detalhes?: Record<string, any>;
}

export interface SuggestedStep {
  operacao: string;
  params: Record<string, any>;
  descricao: string;
}

export interface PipelineStep {
  operacao: string;
  params: Record<string, any>;
}

export interface HistoryEntry {
  momento: string;
  operacao: string;
  linhas_antes: number;
  linhas_depois: number;
  colunas_antes: number;
  colunas_depois: number;
  colunas_antes_lista?: string[];
  colunas_depois_lista?: string[];
}

export interface SnapshotData {
  linhas: number;
  colunas: number;
  nomes_colunas: string[];
  tipos: Record<string, string>;
  nulos_por_coluna: Record<string, number>;
  total_nulos: number;
  duplicatas: number;
  memoria_mb: number;
}

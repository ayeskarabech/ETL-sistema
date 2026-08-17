import { DataFrame, HistoryEntry, SnapshotData } from "../types";
import { Logger } from "../utils/logger";

export class PipelineContext {
  public data: DataFrame = { columns: [], data: [] };
  public tabelas_referencia: Map<string, DataFrame> = new Map();
  public metadados: Record<string, any> = {};
  public historico: HistoryEntry[] = [];
  public log_buffer: string[] = [];
  public logger?: Logger;
  private _snapshot_inicial?: SnapshotData;

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string) {
    this.log_buffer.push(msg);
    if (this.logger) {
      this.logger.info(msg);
    }
  }

  public setData(df: DataFrame, descricao: string = "") {
    const linhasAntes = this.data.data.length;
    const colunasAntesCount = this.data.columns.length;
    const colunasAntesLista = [...this.data.columns];

    this.data = df;

    this.historico.push({
      momento: new Date().toISOString(),
      operacao: descricao,
      linhas_antes: linhasAntes,
      linhas_depois: df.data.length,
      colunas_antes: colunasAntesCount,
      colunas_depois: df.columns.length,
      colunas_antes_lista: colunasAntesLista,
      colunas_depois_lista: [...df.columns],
    });

    if (descricao) {
      this._log(`[CONTEXT] ${descricao} — ${df.data.length} linhas, ${df.columns.length} colunas.`);
    }
  }

  public getData(): DataFrame {
    return this.data;
  }

  public getSnapshotInicial(): SnapshotData | undefined {
    return this._snapshot_inicial;
  }

  public registrarSnapshotInicial() {
    if (this.data.data.length > 0) {
      const tipos: Record<string, string> = {};
      const nulosPorColuna: Record<string, number> = {};
      let totalNulos = 0;

      for (const col of this.data.columns) {
        let nulos = 0;
        let inferredType = "string";
        let isNum = true;
        for (const r of this.data.data) {
          const v = r[col];
          if (v === null || v === undefined || v === "") {
            nulos++;
          } else if (isNum && isNaN(Number(v))) {
            isNum = false;
          }
        }
        nulosPorColuna[col] = nulos;
        totalNulos += nulos;
        tipos[col] = isNum ? "number" : "string";
      }

      const seen = new Set<string>();
      let dups = 0;
      for (const r of this.data.data) {
        const k = this.data.columns.map((c) => String(r[c] ?? "")).join("|||");
        if (seen.has(k)) dups++;
        else seen.add(k);
      }

      // Memory estimate in MB
      const memoryMb = Number(((JSON.stringify(this.data.data).length * 2) / 1024 / 1024).toFixed(2));

      this._snapshot_inicial = {
        linhas: this.data.data.length,
        colunas: this.data.columns.length,
        nomes_colunas: [...this.data.columns],
        tipos,
        nulos_por_coluna: nulosPorColuna,
        total_nulos: totalNulos,
        duplicatas: dups,
        memoria_mb: memoryMb,
      };
    }
  }

  public registrarTabela(nome: string, df: DataFrame) {
    this.tabelas_referencia.set(nome, {
      columns: [...df.columns],
      data: df.data.map((r) => ({ ...r })),
    });
    this._log(`[CONTEXT] Tabela '${nome}' registrada (${df.data.length} linhas).`);
  }

  public getTabela(nome: string): DataFrame {
    if (!this.tabelas_referencia.has(nome)) {
      this._log(`[CONTEXT] AVISO: tabela '${nome}' nao encontrada.`);
      return { columns: [], data: [] };
    }
    return this.tabelas_referencia.get(nome)!;
  }

  public listTabelas(): string[] {
    return Array.from(this.tabelas_referencia.keys());
  }

  public relatorio(): string {
    const linhas: string[] = [];
    linhas.push("=".repeat(60));
    linhas.push("  HISTORICO DO PIPELINE");
    linhas.push("=".repeat(60));
    for (let i = 0; i < this.historico.length; i++) {
      const h = this.historico[i];
      linhas.push(`  ${i + 1}. ${h.operacao || "(sem descricao)"}`);
      linhas.push(`     ${h.linhas_antes ?? "?"} -> ${h.linhas_depois} linhas`);
    }
    linhas.push("=".repeat(60));
    return linhas.join("\n");
  }

  public relatorioFinal(): string {
    const s = this._snapshot_inicial;
    const atual = this.data;
    const hist = this.historico;

    const linhas: string[] = [];
    linhas.push("");
    linhas.push("#".repeat(70));
    linhas.push("  RELATORIO FINAL — ETL NGR-SEE");
    linhas.push("#".repeat(70));

    // ESTADO INICIAL
    linhas.push("");
    linhas.push("  ESTADO INICIAL DA BASE");
    linhas.push("  " + "-".repeat(50));
    if (s) {
      linhas.push(`  Linhas:           ${s.linhas}`);
      linhas.push(`  Colunas:          ${s.colunas}`);
      linhas.push(`  Colunas:          ${JSON.stringify(s.nomes_colunas)}`);
      linhas.push(`  Total nulos:      ${s.total_nulos}`);
      linhas.push(`  Duplicatas:       ${s.duplicatas}`);
      linhas.push(`  Memoria:          ${s.memoria_mb} MB`);
      linhas.push("");
      linhas.push("  Tipos por coluna:");
      for (const [col, tipo] of Object.entries(s.tipos)) {
        const nulos = s.nulos_por_coluna[col] || 0;
        linhas.push(`    ${col.padEnd(30, " ")} ${tipo.padEnd(20, " ")} (${nulos} nulos)`);
      }
    } else {
      linhas.push("  (snapshot nao registrado)");
    }

    // ETAPAS EXECUTADAS
    linhas.push("");
    linhas.push("  ETAPAS EXECUTADAS");
    linhas.push("  " + "-".repeat(50));
    for (let i = 0; i < hist.length; i++) {
      const h = hist[i];
      linhas.push(`  ${String(i + 1).padStart(3, " ")}. ${h.operacao}`);
      linhas.push(`       Linhas: ${h.linhas_antes} -> ${h.linhas_depois} | Colunas: ${h.colunas_antes} -> ${h.colunas_depois}`);
    }

    // ESTADO FINAL
    const seen = new Set<string>();
    let dupsFinal = 0;
    let totalNulosFinal = 0;
    for (const r of atual.data) {
      const k = atual.columns.map((c) => String(r[c] ?? "")).join("|||");
      if (seen.has(k)) dupsFinal++;
      else seen.add(k);

      for (const c of atual.columns) {
        if (r[c] === null || r[c] === undefined || r[c] === "") totalNulosFinal++;
      }
    }

    linhas.push("");
    linhas.push("  ESTADO FINAL DA BASE");
    linhas.push("  " + "-".repeat(50));
    linhas.push(`  Linhas:           ${atual.data.length}`);
    linhas.push(`  Colunas:          ${atual.columns.length}`);
    linhas.push(`  Colunas:          ${JSON.stringify(atual.columns)}`);
    linhas.push(`  Total nulos:      ${totalNulosFinal}`);
    linhas.push(`  Duplicatas:       ${dupsFinal}`);

    if (s) {
      linhas.push("");
      linhas.push("  VARIACOES");
      linhas.push("  " + "-".repeat(50));
      const linhasVar = atual.data.length - s.linhas;
      const linhasVarPct = s.linhas > 0 ? (linhasVar / s.linhas) * 100 : 0;
      const colunasVar = atual.columns.length - s.colunas;
      const nulosVar = totalNulosFinal - s.total_nulos;
      const duplicatasVar = dupsFinal - s.duplicatas;

      linhas.push(`  Linhas:     ${linhasVar >= 0 ? "+" : ""}${linhasVar} (${linhasVarPct >= 0 ? "+" : ""}${linhasVarPct.toFixed(1)}%)`);
      linhas.push(`  Colunas:    ${colunasVar >= 0 ? "+" : ""}${colunasVar}`);
      linhas.push(`  Nulos:      ${nulosVar >= 0 ? "+" : ""}${nulosVar}`);
      linhas.push(`  Duplicatas: ${duplicatasVar >= 0 ? "+" : ""}${duplicatasVar}`);

      const colsAntes = new Set(s.nomes_colunas);
      const colsDepois = new Set(atual.columns);
      const removidas = s.nomes_colunas.filter((c) => !colsDepois.has(c));
      const adicionadas = atual.columns.filter((c) => !colsAntes.has(c));

      if (removidas.length > 0) {
        linhas.push(`  Colunas removidas:    ${JSON.stringify(removidas)}`);
      }
      if (adicionadas.length > 0) {
        linhas.push(`  Colunas adicionadas:  ${JSON.stringify(adicionadas)}`);
      }
    }

    linhas.push("");
    linhas.push("#".repeat(70));
    return linhas.join("\n");
  }
}

import fs from "fs";
import path from "path";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class PowerBIExporter {
  private pastaSaida: string;
  private logger?: Logger;

  constructor(pastaSaida: string, logger?: Logger) {
    this.pastaSaida = pastaSaida;
    this.logger = logger;
    fs.mkdirSync(this.pastaSaida, { recursive: true });
  }

  private _log(msg: string) {
    if (this.logger) {
      this.logger.info(msg);
    } else {
      console.log(`[EXPORT] ${msg}`);
    }
  }

  public static snakeCase(nomeColuna: string): string {
    let nome = String(nomeColuna).trim();
    // Normalize accents to ASCII
    nome = nome.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
    // Remove non-word characters except spaces and underscores
    nome = nome.replace(/[^\w\s]/g, "");
    // Replace whitespace sequences with underscore
    nome = nome.replace(/\s+/g, "_");
    return nome.toLowerCase();
  }

  public padronizarNomesColuna(df: DataFrame): DataFrame {
    const colMap = new Map<string, string>();
    const newCols: string[] = [];

    for (const col of df.columns) {
      const cleanCol = PowerBIExporter.snakeCase(col);
      colMap.set(col, cleanCol);
      newCols.push(cleanCol);
    }

    const newData: DataRow[] = df.data.map((row) => {
      const newRow: DataRow = {};
      for (const col of df.columns) {
        newRow[colMap.get(col)!] = row[col];
      }
      return newRow;
    });

    this._log(`Nomes de coluna padronizados para snake_case: ${newCols.join(", ")}`);

    return {
      columns: newCols,
      data: newData,
    };
  }

  public exportar(df: DataFrame, nomeBase: string, formato: "powerbi" | "csv" | "excel" = "powerbi"): string {
    const dfExport = this.padronizarNomesColuna(df);

    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    const timestamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;

    if (formato === "excel") {
      const nomeArquivo = `${nomeBase}_${timestamp}.xlsx`;
      const caminhoCompleto = path.join(this.pastaSaida, nomeArquivo);

      const worksheet = XLSX.utils.json_to_sheet(dfExport.data, { header: dfExport.columns });
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "DadosTratados");
      XLSX.writeFile(workbook, caminhoCompleto);

      this._log(`Arquivo Excel exportado: ${caminhoCompleto} (${dfExport.data.length} linhas, ${dfExport.columns.length} colunas).`);
      return caminhoCompleto;
    }

    const isPowerBi = formato === "powerbi";
    const nomeArquivo = `${nomeBase}_${timestamp}.csv`;
    const caminhoCompleto = path.join(this.pastaSaida, nomeArquivo);

    const csvText = Papa.unparse(dfExport.data, {
      columns: dfExport.columns,
      header: true,
      delimiter: isPowerBi ? ";" : ",", // ; for Power BI / pt-BR, , for standard CSV
    });

    // UTF-8 BOM for Power BI compatibility with accented chars
    const content = isPowerBi ? "\uFEFF" + csvText : csvText;
    fs.writeFileSync(caminhoCompleto, content, { encoding: "utf8" });

    this._log(`Arquivo CSV (${formato}) exportado: ${caminhoCompleto} (${dfExport.data.length} linhas, ${dfExport.columns.length} colunas).`);
    return caminhoCompleto;
  }
}

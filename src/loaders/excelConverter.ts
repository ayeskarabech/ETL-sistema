import fs from "fs";
import path from "path";
import * as XLSX from "xlsx";
import Papa from "papaparse";
import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class ExcelConverter {
  private logger?: Logger;

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string) {
    if (this.logger) {
      this.logger.info(msg);
    } else {
      console.log(`[CONVERSOR] ${msg}`);
    }
  }

  public listarSheets(caminhoXlsx: string): string[] {
    try {
      const workbook = XLSX.readFile(caminhoXlsx);
      const sheets = workbook.SheetNames;
      this._log(`Sheets encontradas: ${sheets.join(", ")}`);
      return sheets;
    } catch (e: any) {
      this._log(`ERRO ao ler abas: ${e.message}`);
      return [];
    }
  }

  public lerSheet(caminhoXlsx: string, sheetNameOrIndex: string | number = 0): DataFrame {
    if (!fs.existsSync(caminhoXlsx)) {
      throw new Error(`Arquivo não encontrado: ${caminhoXlsx}`);
    }

    const workbook = XLSX.readFile(caminhoXlsx);
    let sheetName: string;

    if (typeof sheetNameOrIndex === "number") {
      sheetName = workbook.SheetNames[sheetNameOrIndex] || workbook.SheetNames[0];
    } else {
      sheetName = sheetNameOrIndex;
    }

    const worksheet = workbook.Sheets[sheetName];
    if (!worksheet) {
      throw new Error(`Aba '${sheetName}' não encontrada.`);
    }

    // Convert sheet to json rows
    const rows = XLSX.utils.sheet_to_json<Record<string, any>>(worksheet, { defval: null, raw: false });

    // Determine columns from rows or range
    const colSet = new Set<string>();
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        colSet.add(key.trim());
      }
    }
    const columns = Array.from(colSet);

    const data: DataRow[] = rows.map((row) => {
      const cleanRow: DataRow = {};
      for (const col of columns) {
        let val = row[col] !== undefined ? row[col] : null;
        if (val === "" || val === undefined) val = null;
        cleanRow[col] = val;
      }
      return cleanRow;
    });

    this._log(`Lida aba '${sheetName}': ${data.length} linhas, ${columns.length} colunas.`);
    return { columns, data };
  }

  public converter(
    caminhoXlsx: string,
    pastaSaida: string,
    sheet: string | number = 0,
    nomeSaida?: string,
    casasDecimais?: number
  ): string {
    const df = this.lerSheet(caminhoXlsx, sheet);

    if (casasDecimais !== undefined) {
      for (const row of df.data) {
        for (const col of df.columns) {
          if (typeof row[col] === "number") {
            row[col] = Number(row[col].toFixed(casasDecimais));
          }
        }
      }
    }

    if (!nomeSaida) {
      const base = path.basename(caminhoXlsx, path.extname(caminhoXlsx));
      nomeSaida = `${base}_convertido`;
    }

    fs.mkdirSync(pastaSaida, { recursive: true });
    const caminhoCsv = path.join(pastaSaida, `${nomeSaida}.csv`);

    const csvContent = Papa.unparse(df.data, {
      columns: df.columns,
      header: true,
    });

    // Write with UTF-8 BOM
    fs.writeFileSync(caminhoCsv, "\uFEFF" + csvContent, { encoding: "utf8" });
    this._log(`Convertido: ${df.data.length} linhas, ${df.columns.length} colunas -> ${caminhoCsv}`);
    return caminhoCsv;
  }

  public detectarProblemas(caminhoXlsx: string, sheet: string | number = 0): { tem_problemas: boolean; problemas: string[] } {
    try {
      const df = this.lerSheet(caminhoXlsx, sheet);
      const sample = df.data.slice(0, 100);
      const problemas: string[] = [];

      const colunasUnnamed = df.columns.filter((c) => c.startsWith("Unnamed") || c.startsWith("__EMPTY"));
      if (colunasUnnamed.length > 0) {
        problemas.push(`Colunas 'Unnamed' detectadas: ${colunasUnnamed.join(", ")}`);
      }

      for (const col of df.columns) {
        const nulos = sample.filter((r) => r[col] === null || r[col] === undefined || r[col] === "").length;
        if (nulos > sample.length * 0.5) {
          problemas.push(`Coluna '${col}' com muitos nulos (${Math.round((nulos / sample.length) * 100)}%)`);
        }
      }

      return {
        tem_problemas: problemas.length > 0,
        problemas,
      };
    } catch (e: any) {
      return {
        tem_problemas: true,
        problemas: [`Erro ao analisar: ${e.message}`],
      };
    }
  }
}

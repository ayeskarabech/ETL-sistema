import fs from "fs";
import path from "path";
import iconv from "iconv-lite";
import Papa from "papaparse";
import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class CSVLoader {
  private caminho: string;
  private logger?: Logger;

  constructor(caminho: string, logger?: Logger) {
    if (!fs.existsSync(caminho)) {
      throw new Error(`Arquivo não encontrado: ${caminho}`);
    }
    this.caminho = caminho;
    this.logger = logger;
  }

  private _log(msg: string, nivel: "info" | "warning" | "error" = "info") {
    if (this.logger) {
      this.logger[nivel](msg);
    } else {
      console.log(msg);
    }
  }

  public carregar(colunas?: string[], tipos?: Record<string, string>): DataFrame {
    const buffer = fs.readFileSync(this.caminho);
    const sizeMb = (buffer.length / (1024 * 1024)).toFixed(1);

    // Try decoding with utf-8 first, then latin1
    let text = "";
    let encodingUsed = "utf-8";

    try {
      // Check if valid utf-8
      text = buffer.toString("utf-8");
      // Check for replacement character indicating broken utf-8
      if (text.includes("\uFFFD")) {
        text = iconv.decode(buffer, "latin1");
        encodingUsed = "latin1";
      }
    } catch {
      text = iconv.decode(buffer, "latin1");
      encodingUsed = "latin1";
    }

    this._log(`Carregando '${path.basename(this.caminho)}' (${sizeMb}MB, ${encodingUsed})...`);

    // Detect delimiter using first 5 lines
    const parsed = Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: false, // Keep as strings initially for custom type casting
    });

    let rawData = parsed.data as DataRow[];
    let detectedCols = (parsed.meta.fields || []).map((c) => c.trim());

    // Normalize keys in rawData to trimmed column names
    let data: DataRow[] = rawData.map((row) => {
      const newRow: DataRow = {};
      for (const key of Object.keys(row)) {
        const cleanKey = key.trim();
        let val = row[key];
        if (val === "" || val === undefined || val === null) {
          val = null;
        }
        newRow[cleanKey] = val;
      }
      return newRow;
    });

    // If specific columns requested
    if (colunas && colunas.length > 0) {
      detectedCols = detectedCols.filter((c) => colunas.includes(c));
      data = data.map((row) => {
        const filteredRow: DataRow = {};
        for (const col of detectedCols) {
          filteredRow[col] = row[col] ?? null;
        }
        return filteredRow;
      });
    }

    // If types mapping specified
    if (tipos) {
      for (const [col, tipo] of Object.entries(tipos)) {
        if (!detectedCols.includes(col)) continue;
        if (tipo === "numero") {
          for (const row of data) {
            if (row[col] !== null && row[col] !== undefined) {
              const strVal = String(row[col]).trim().replace(/\./g, "").replace(",", ".");
              const num = parseFloat(strVal);
              row[col] = isNaN(num) ? null : num;
            }
          }
        } else if (tipo === "texto") {
          for (const row of data) {
            if (row[col] !== null && row[col] !== undefined) {
              row[col] = String(row[col]);
            }
          }
        }
      }
    }

    this._log(`Carregado: ${data.length} linhas, ${detectedCols.length} colunas.`);

    return {
      columns: detectedCols,
      data,
    };
  }

  public listarColunas(): string[] {
    const buffer = fs.readFileSync(this.caminho);
    const text = buffer.toString("utf-8");
    const parsed = Papa.parse(text, {
      header: true,
      preview: 1,
    });
    return (parsed.meta.fields || []).map((c) => c.trim());
  }
}

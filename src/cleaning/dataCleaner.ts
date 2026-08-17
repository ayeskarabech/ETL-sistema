import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class DataCleaner {
  private logger?: Logger;

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string) {
    if (this.logger) {
      this.logger.info(msg);
    }
  }

  private isNull(val: any): boolean {
    return val === null || val === undefined || val === "" || (typeof val === "number" && isNaN(val));
  }

  /**
   * Remove colunas onde proporção de nulos >= limiar (padrão 1.0 = 100% vazia).
   */
  public removerColunasVazias(df: DataFrame, limiar: number = 1.0): DataFrame {
    const totalLinhas = df.data.length;
    if (totalLinhas === 0) return df;

    const colunasManter: string[] = [];
    const colunasRemovidas: string[] = [];

    for (const col of df.columns) {
      let nulos = 0;
      for (const row of df.data) {
        if (this.isNull(row[col])) nulos++;
      }
      const propNulos = nulos / totalLinhas;
      if (propNulos >= limiar) {
        colunasRemovidas.push(col);
      } else {
        colunasManter.push(col);
      }
    }

    const newData = df.data.map((row) => {
      const newRow: DataRow = {};
      for (const col of colunasManter) {
        newRow[col] = row[col];
      }
      return newRow;
    });

    this._log(`[COLUNAS_VAZIAS] ${colunasRemovidas.length} colunas removidas: ${colunasRemovidas.join(", ")}`);

    return {
      columns: colunasManter,
      data: newData,
    };
  }

  /**
   * Remove linhas vazias (todas ou qualquer coluna nula).
   */
  public removerLinhasVazias(
    df: DataFrame,
    colunas?: string[],
    modo: "todas" | "qualquer" = "todas"
  ): DataFrame {
    const checkCols = colunas && colunas.length > 0 ? colunas.filter((c) => df.columns.includes(c)) : df.columns;
    if (checkCols.length === 0) return df;

    const filteredData = df.data.filter((row) => {
      if (modo === "todas") {
        return !checkCols.every((col) => this.isNull(row[col]));
      } else {
        return !checkCols.some((col) => this.isNull(row[col]));
      }
    });

    const removidas = df.data.length - filteredData.length;
    this._log(`[LINHAS_VAZIAS] ${removidas} linhas removidas (${df.data.length} -> ${filteredData.length}).`);

    return {
      columns: [...df.columns],
      data: filteredData,
    };
  }

  /**
   * Trata valores nulos com diferentes estratégias.
   */
  public tratarNulos(
    df: DataFrame,
    colunas: string[],
    estrategia: "mediana" | "media" | "moda" | "valor_fixo" | "remover_linha" | "ffill" | "bfill" = "valor_fixo",
    valorFixo: any = ""
  ): DataFrame {
    let currentData = df.data.map((r) => ({ ...r }));

    if (estrategia === "remover_linha") {
      const filtered = currentData.filter((row) => {
        return !colunas.some((col) => df.columns.includes(col) && this.isNull(row[col]));
      });
      this._log(`[NULOS] ${currentData.length - filtered.length} linhas com nulos removidas.`);
      return { columns: [...df.columns], data: filtered };
    }

    for (const col of colunas) {
      if (!df.columns.includes(col)) continue;

      if (estrategia === "valor_fixo") {
        for (const row of currentData) {
          if (this.isNull(row[col])) {
            row[col] = valorFixo;
          }
        }
      } else if (estrategia === "media" || estrategia === "mediana") {
        const nums: number[] = [];
        for (const row of currentData) {
          if (!this.isNull(row[col])) {
            const n = parseFloat(String(row[col]).replace(/\./g, "").replace(",", "."));
            if (!isNaN(n)) nums.push(n);
          }
        }

        if (nums.length > 0) {
          let repVal: number;
          if (estrategia === "media") {
            repVal = nums.reduce((a, b) => a + b, 0) / nums.length;
          } else {
            nums.sort((a, b) => a - b);
            const mid = Math.floor(nums.length / 2);
            repVal = nums.length % 2 !== 0 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
          }
          for (const row of currentData) {
            if (this.isNull(row[col])) {
              row[col] = Number(repVal.toFixed(2));
            }
          }
        }
      } else if (estrategia === "moda") {
        const counts = new Map<any, number>();
        for (const row of currentData) {
          if (!this.isNull(row[col])) {
            counts.set(row[col], (counts.get(row[col]) || 0) + 1);
          }
        }
        let topVal: any = null;
        let topCount = 0;
        for (const [val, c] of counts.entries()) {
          if (c > topCount) {
            topCount = c;
            topVal = val;
          }
        }
        if (topVal !== null) {
          for (const row of currentData) {
            if (this.isNull(row[col])) {
              row[col] = topVal;
            }
          }
        }
      } else if (estrategia === "ffill") {
        let lastVal: any = null;
        for (const row of currentData) {
          if (!this.isNull(row[col])) {
            lastVal = row[col];
          } else if (lastVal !== null) {
            row[col] = lastVal;
          }
        }
      } else if (estrategia === "bfill") {
        let nextVal: any = null;
        for (let i = currentData.length - 1; i >= 0; i--) {
          const row = currentData[i];
          if (!this.isNull(row[col])) {
            nextVal = row[col];
          } else if (nextVal !== null) {
            row[col] = nextVal;
          }
        }
      }
      this._log(`[NULOS] '${col}' tratado com estrategia '${estrategia}'.`);
    }

    return {
      columns: [...df.columns],
      data: currentData,
    };
  }

  /**
   * Padroniza texto: upper, lower, title, strip, remover_acentos.
   */
  public padronizarTexto(
    df: DataFrame,
    colunas: string[],
    modo: "upper" | "lower" | "title" | "strip" | "remover_acentos" = "upper",
    removerEspacosExtras: boolean = true
  ): DataFrame {
    const newData = df.data.map((r) => ({ ...r }));

    const removeAccents = (str: string) => {
      return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    };

    const toTitleCase = (str: string) => {
      return str.toLowerCase().replace(/(?:^|\s)\S/g, (a) => a.toUpperCase());
    };

    for (const col of colunas) {
      if (!df.columns.includes(col)) continue;
      for (const row of newData) {
        const val = row[col];
        if (val === null || val === undefined) continue;
        let s = String(val);

        if (removerEspacosExtras) {
          s = s.trim().replace(/\s+/g, " ");
        }

        if (modo === "upper") {
          s = s.toUpperCase();
        } else if (modo === "lower") {
          s = s.toLowerCase();
        } else if (modo === "title") {
          s = toTitleCase(s);
        } else if (modo === "remover_acentos") {
          s = removeAccents(s);
        } else if (modo === "strip") {
          s = s.trim();
        }

        row[col] = s;
      }
      this._log(`[TEXTO] '${col}' padronizado (${modo}).`);
    }

    return {
      columns: [...df.columns],
      data: newData,
    };
  }

  /**
   * Corrige tipos de dados das colunas.
   */
  public corrigirTipos(df: DataFrame, mapeamentoTipos: Record<string, string>): DataFrame {
    const newData = df.data.map((r) => ({ ...r }));

    for (const [col, tipo] of Object.entries(mapeamentoTipos)) {
      if (!df.columns.includes(col)) continue;

      for (const row of newData) {
        const val = row[col];
        if (this.isNull(val)) continue;

        if (tipo === "numero" || tipo === "float" || tipo === "int") {
          let s = String(val).trim().replace(/[R$€£%\s]/g, "");
          if (/^-?\d{1,3}(\.\d{3})*,\d+$/.test(s)) {
            s = s.replace(/\./g, "").replace(",", ".");
          } else if (/^-?\d+,\d+$/.test(s)) {
            s = s.replace(",", ".");
          }
          const num = tipo === "int" ? parseInt(s, 10) : parseFloat(s);
          row[col] = isNaN(num) ? null : num;
        } else if (tipo === "texto" || tipo === "string") {
          row[col] = String(val);
        } else if (tipo === "booleano") {
          const s = String(val).trim().toLowerCase();
          row[col] = s === "true" || s === "1" || s === "sim" || s === "s" || s === "verdadeiro";
        }
      }
      this._log(`[TIPO] '${col}' convertido para '${tipo}'.`);
    }

    return {
      columns: [...df.columns],
      data: newData,
    };
  }

  /**
   * Substituição por expressão regular.
   */
  public substituirPorRegex(
    df: DataFrame,
    colunas: string[],
    padrao: string,
    substituicao: string
  ): DataFrame {
    const newData = df.data.map((r) => ({ ...r }));
    const regex = new RegExp(padrao, "g");

    for (const col of colunas) {
      if (!df.columns.includes(col)) continue;
      for (const row of newData) {
        if (!this.isNull(row[col])) {
          row[col] = String(row[col]).replace(regex, substituicao);
        }
      }
      this._log(`[REGEX] '${col}': /${padrao}/ -> '${substituicao}'.`);
    }

    return {
      columns: [...df.columns],
      data: newData,
    };
  }

  /**
   * Tratamento de outliers com IQR.
   */
  public tratarOutliers(
    df: DataFrame,
    colunas: string[],
    fator: number = 1.5,
    acao: "clip" | "remover" | "null" = "clip"
  ): DataFrame {
    let currentData = df.data.map((r) => ({ ...r }));

    for (const col of colunas) {
      if (!df.columns.includes(col)) continue;
      const values: { index: number; num: number }[] = [];
      for (let i = 0; i < currentData.length; i++) {
        const val = currentData[i][col];
        if (!this.isNull(val)) {
          const num = typeof val === "number" ? val : parseFloat(String(val).replace(",", "."));
          if (!isNaN(num)) values.push({ index: i, num });
        }
      }

      if (values.length < 4) continue;
      const sortedNums = values.map((v) => v.num).sort((a, b) => a - b);
      const q1 = sortedNums[Math.floor(sortedNums.length * 0.25)];
      const q3 = sortedNums[Math.floor(sortedNums.length * 0.75)];
      const iqr = q3 - q1;
      const lowerBound = q1 - fator * iqr;
      const upperBound = q3 + fator * iqr;

      if (acao === "clip") {
        for (const v of values) {
          if (v.num < lowerBound) currentData[v.index][col] = lowerBound;
          else if (v.num > upperBound) currentData[v.index][col] = upperBound;
        }
      } else if (acao === "null") {
        for (const v of values) {
          if (v.num < lowerBound || v.num > upperBound) currentData[v.index][col] = null;
        }
      } else if (acao === "remover") {
        currentData = currentData.filter((row) => {
          const val = row[col];
          if (this.isNull(val)) return true;
          const num = typeof val === "number" ? val : parseFloat(String(val).replace(",", "."));
          if (isNaN(num)) return true;
          return num >= lowerBound && num <= upperBound;
        });
      }
      this._log(`[OUTLIERS] '${col}' tratados com IQR (bounds: [${lowerBound.toFixed(2)}, ${upperBound.toFixed(2)}]).`);
    }

    return {
      columns: [...df.columns],
      data: currentData,
    };
  }
}

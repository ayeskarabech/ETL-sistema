import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class CleaningRules {
  private logger?: Logger;

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string) {
    if (this.logger) {
      this.logger.info(msg);
    }
  }

  /**
   * Converte número em texto formatado no padrão brasileiro (1.234,56).
   */
  public formatarNumeroBR(
    df: DataFrame,
    colunas: string[],
    casas: number = 2,
    removerSimbolos: boolean = true,
    manterNegativos: boolean = true,
    novaColuna?: string
  ): DataFrame {
    const newDf: DataFrame = {
      columns: [...df.columns],
      data: df.data.map((r) => ({ ...r })),
    };

    for (const col of colunas) {
      if (!newDf.columns.includes(col)) continue;
      const targetCol = novaColuna || col;
      if (!newDf.columns.includes(targetCol)) {
        newDf.columns.push(targetCol);
      }

      for (const row of newDf.data) {
        let val = row[col];
        if (val === null || val === undefined || val === "") {
          row[targetCol] = null;
          continue;
        }

        let strVal = String(val).trim();
        if (removerSimbolos) {
          strVal = strVal.replace(/[R$€£%\s]/g, "");
        }

        // If already in brazilian format (e.g. 1.234,56)
        if (/^-?\d{1,3}(\.\d{3})*,\d+$/.test(strVal)) {
          strVal = strVal.replace(/\./g, "").replace(",", ".");
        } else if (/^-?\d+,\d+$/.test(strVal)) {
          strVal = strVal.replace(",", ".");
        }

        const num = parseFloat(strVal);
        if (isNaN(num)) {
          row[targetCol] = val;
          continue;
        }

        if (!manterNegativos && num < 0) {
          row[targetCol] = "0," + "0".repeat(casas);
          continue;
        }

        const isNeg = num < 0;
        const absVal = Math.abs(num);
        const fixed = absVal.toFixed(casas);
        const [intPart, decPart] = fixed.split(".");

        // Add dots as thousands separator
        const intWithDots = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        const formatted = (isNeg ? "-" : "") + intWithDots + (casas > 0 ? "," + decPart : "");
        row[targetCol] = formatted;
      }
      this._log(`[NUMERO_BR] '${col}' -> ${casas} casas decimais.`);
    }

    return newDf;
  }

  /**
   * Formata coluna numérica para texto padrão interno (1234.56).
   */
  public formatarNumeroInterno(
    df: DataFrame,
    colunas: string[],
    casas: number = 2,
    novaColuna?: string
  ): DataFrame {
    const newDf: DataFrame = {
      columns: [...df.columns],
      data: df.data.map((r) => ({ ...r })),
    };

    for (const col of colunas) {
      if (!newDf.columns.includes(col)) continue;
      const targetCol = novaColuna || col;
      if (!newDf.columns.includes(targetCol)) {
        newDf.columns.push(targetCol);
      }

      for (const row of newDf.data) {
        let val = row[col];
        if (val === null || val === undefined || val === "") {
          row[targetCol] = null;
          continue;
        }

        let strVal = String(val).trim().replace(/[R$€£%\s]/g, "");
        if (/^-?\d{1,3}(\.\d{3})*,\d+$/.test(strVal)) {
          strVal = strVal.replace(/\./g, "").replace(",", ".");
        } else if (/^-?\d+,\d+$/.test(strVal)) {
          strVal = strVal.replace(",", ".");
        }

        const num = parseFloat(strVal);
        if (isNaN(num)) {
          row[targetCol] = null;
        } else {
          row[targetCol] = Number(num.toFixed(casas));
        }
      }
      this._log(`[NUMERO_INTERNO] '${col}' -> ${casas} casas decimais.`);
    }

    return newDf;
  }

  /**
   * Formata coluna como moeda brasileira (R$ 1.234,56).
   */
  public formatarMoeda(
    df: DataFrame,
    colunas: string[],
    simbolo: string = "R$",
    casas: number = 2,
    novaColuna?: string
  ): DataFrame {
    const res = this.formatarNumeroBR(df, colunas, casas, true, true, novaColuna);
    for (const col of colunas) {
      const targetCol = novaColuna || col;
      for (const row of res.data) {
        if (row[targetCol] !== null && row[targetCol] !== undefined && row[targetCol] !== "") {
          row[targetCol] = `${simbolo} ${row[targetCol]}`;
        }
      }
    }
    return res;
  }

  /**
   * Formata como porcentagem (12,34%).
   */
  public formatarPorcentagem(
    df: DataFrame,
    colunas: string[],
    casas: number = 2,
    novaColuna?: string
  ): DataFrame {
    const res = this.formatarNumeroBR(df, colunas, casas, true, true, novaColuna);
    for (const col of colunas) {
      const targetCol = novaColuna || col;
      for (const row of res.data) {
        if (row[targetCol] !== null && row[targetCol] !== undefined && row[targetCol] !== "") {
          row[targetCol] = `${row[targetCol]}%`;
        }
      }
    }
    return res;
  }

  /**
   * Remove linhas duplicadas.
   */
  public removerDuplicatas(
    df: DataFrame,
    colunas?: string[],
    manter: "first" | "last" = "first",
    normalizarTexto: boolean = true
  ): DataFrame {
    const checkCols = colunas && colunas.length > 0 ? colunas.filter((c) => df.columns.includes(c)) : df.columns;
    const seen = new Set<string>();
    const keepIndices = new Set<number>();

    const rows = df.data;
    const loopOrder = manter === "last" ? Array.from({ length: rows.length }, (_, i) => rows.length - 1 - i) : Array.from({ length: rows.length }, (_, i) => i);

    for (const i of loopOrder) {
      const row = rows[i];
      const key = checkCols
        .map((col) => {
          let val = row[col];
          if (val === null || val === undefined) return "__NULL__";
          let s = String(val);
          if (normalizarTexto) {
            s = s.trim().toLowerCase();
          }
          return s;
        })
        .join("|||");

      if (!seen.has(key)) {
        seen.add(key);
        keepIndices.add(i);
      }
    }

    const filteredData = rows.filter((_, i) => keepIndices.has(i));
    const removidas = rows.length - filteredData.length;
    this._log(`[DUPLICATAS] ${removidas} linhas duplicadas removidas (${rows.length} -> ${filteredData.length}).`);

    return {
      columns: [...df.columns],
      data: filteredData,
    };
  }

  /**
   * Detecta duplicatas.
   */
  public detectarDuplicatas(df: DataFrame, colunas?: string[]): { quantidade: number; percentual: number } {
    const checkCols = colunas && colunas.length > 0 ? colunas.filter((c) => df.columns.includes(c)) : df.columns;
    const seen = new Set<string>();
    let dups = 0;

    for (const row of df.data) {
      const key = checkCols
        .map((col) => {
          const val = row[col];
          return val === null || val === undefined ? "__NULL__" : String(val).trim().toLowerCase();
        })
        .join("|||");
      if (seen.has(key)) {
        dups++;
      } else {
        seen.add(key);
      }
    }

    const pct = df.data.length > 0 ? (dups / df.data.length) * 100 : 0;
    return { quantidade: dups, percentual: Number(pct.toFixed(2)) };
  }

  /**
   * Bigram similarity entre duas strings.
   */
  public static bigramSimilarity(a: string, b: string): number {
    if (a === b) return 1.0;
    if (!a || !b) return 0.0;
    const getBigrams = (s: string) => {
      const bg: string[] = [];
      for (let i = 0; i < s.length - 1; i++) {
        bg.push(s.slice(i, i + 2));
      }
      return bg;
    };
    const bgA = getBigrams(a);
    const bgB = getBigrams(b);
    if (bgA.length === 0 || bgB.length === 0) {
      return a.includes(b) || b.includes(a) ? 1.0 : 0.0;
    }
    let inter = 0;
    const bgBSet = [...bgB];
    for (const item of bgA) {
      const idx = bgBSet.indexOf(item);
      if (idx !== -1) {
        inter++;
        bgBSet.splice(idx, 1);
      }
    }
    return (2.0 * inter) / (bgA.length + bgB.length);
  }

  /**
   * Distância Levenshtein normalizada.
   */
  public static editDistanceNormalized(a: string, b: string): number {
    if (a === b) return 1.0;
    const la = a.length;
    const lb = b.length;
    if (la === 0 || lb === 0) return 0.0;

    const matrix: number[][] = Array.from({ length: la + 1 }, () => Array(lb + 1).fill(0));
    for (let i = 0; i <= la; i++) matrix[i][0] = i;
    for (let j = 0; j <= lb; j++) matrix[0][j] = j;

    for (let i = 1; i <= la; i++) {
      for (let j = 1; j <= lb; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j - 1] + cost
        );
      }
    }

    const dist = matrix[la][lb];
    const maxLen = Math.max(la, lb);
    return 1.0 - dist / maxLen;
  }

  /**
   * Unifica valores similares em uma coluna (fuzzy match).
   */
  public unificarValoresSimilares(df: DataFrame, coluna: string, limiar: number = 0.82): DataFrame {
    if (!df.columns.includes(coluna)) return df;

    // Count frequency of each unique value
    const counts = new Map<string, number>();
    for (const row of df.data) {
      const val = row[coluna];
      if (val !== null && val !== undefined && val !== "") {
        const s = String(val).trim();
        counts.set(s, (counts.get(s) || 0) + 1);
      }
    }

    const uniqueVals = Array.from(counts.keys());
    if (uniqueVals.length <= 1) return df;

    // Disjoint set for clustering
    const parent = new Map<string, string>();
    for (const v of uniqueVals) parent.set(v, v);

    const find = (x: string): string => {
      let root = x;
      while (parent.get(root) !== root) {
        root = parent.get(root)!;
      }
      let curr = x;
      while (curr !== root) {
        const nxt = parent.get(curr)!;
        parent.set(curr, root);
        curr = nxt;
      }
      return root;
    };

    const union = (x: string, y: string) => {
      const rx = find(x);
      const ry = find(y);
      if (rx !== ry) {
        // Canonical is the one with higher frequency
        const countX = counts.get(rx) || 0;
        const countY = counts.get(ry) || 0;
        if (countX >= countY) {
          parent.set(ry, rx);
        } else {
          parent.set(rx, ry);
        }
      }
    };

    const limit = Math.min(uniqueVals.length, 300);
    for (let i = 0; i < limit; i++) {
      for (let j = i + 1; j < limit; j++) {
        const a = uniqueVals[i];
        const b = uniqueVals[j];
        const simBg = CleaningRules.bigramSimilarity(a.toUpperCase(), b.toUpperCase());
        const simEd = CleaningRules.editDistanceNormalized(a.toUpperCase(), b.toUpperCase());
        const score = Math.max(simBg, simEd);
        if (score >= limiar) {
          union(a, b);
        }
      }
    }

    const mapping = new Map<string, string>();
    let replacedCount = 0;
    for (const v of uniqueVals) {
      const canonical = find(v);
      if (canonical !== v) {
        mapping.set(v, canonical);
      }
    }

    const newDf: DataFrame = {
      columns: [...df.columns],
      data: df.data.map((r) => ({ ...r })),
    };

    for (const row of newDf.data) {
      const val = row[coluna];
      if (val !== null && val !== undefined && val !== "") {
        const s = String(val).trim();
        if (mapping.has(s)) {
          row[coluna] = mapping.get(s);
          replacedCount++;
        }
      }
    }

    this._log(`[UNIFICAR] '${coluna}': ${mapping.size} variantes unificadas (${replacedCount} celulas alteradas).`);
    return newDf;
  }

  /**
   * Aplica mapeamento direto chave-valor em uma ou mais colunas.
   */
  public aplicarDicionario(
    df: DataFrame,
    colunaOuColunas: string | string[],
    mapeamento: Record<string, string>,
    manterOriginalSeNaoEncontrado: boolean = true
  ): DataFrame {
    const cols = Array.isArray(colunaOuColunas) ? colunaOuColunas : [colunaOuColunas];
    const newDf: DataFrame = {
      columns: [...df.columns],
      data: df.data.map((r) => ({ ...r })),
    };

    for (const col of cols) {
      if (!newDf.columns.includes(col)) continue;
      for (const row of newDf.data) {
        const val = row[col];
        if (val !== null && val !== undefined) {
          const s = String(val).trim();
          if (s in mapeamento) {
            row[col] = mapeamento[s];
          } else if (!manterOriginalSeNaoEncontrado) {
            row[col] = null;
          }
        }
      }
      this._log(`[DICIONARIO] Mapeamento aplicado em '${col}'.`);
    }

    return newDf;
  }
}

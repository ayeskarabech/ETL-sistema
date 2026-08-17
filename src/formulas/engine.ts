import { DataFrame, DataRow } from "../types";
import { Logger } from "../utils/logger";

export class FormulaEngine {
  private logger?: Logger;
  private logBuffer: string[] = [];

  public static CATALOGO: Record<string, { descricao: string; params: string[] }> = {
    PROCV: {
      descricao: "Busca vertical (VLOOKUP): puxa valor de outra tabela",
      params: ["coluna_chave_tabela", "tabela_origem", "coluna_chave_origem", "coluna_valor_origem", "padrao_nao_encontrado"],
    },
    ESQUERDA: {
      descricao: "Extrai N caracteres da esquerda (LEFT)",
      params: ["coluna", "num_caracteres"],
    },
    DIREITA: {
      descricao: "Extrai N caracteres da direita (RIGHT)",
      params: ["coluna", "num_caracteres"],
    },
    MEIO: {
      descricao: "Extrai texto de posicao inicial com N caracteres (MID)",
      params: ["coluna", "posicao_inicial", "num_caracteres"],
    },
    TAMANHO: {
      descricao: "Retorna o tamanho do texto (LEN)",
      params: ["coluna"],
    },
    CORRESP: {
      descricao: "Posicao de um valor em intervalo (MATCH)",
      params: ["valor", "coluna_busca"],
    },
    INDICE: {
      descricao: "Valor na posicao N de uma coluna (INDEX)",
      params: ["coluna", "posicao"],
    },
    "CONT.SE": {
      descricao: "Conta celulas que atendem condicao (COUNTIF)",
      params: ["coluna", "condicao"],
    },
    SOMASE: {
      descricao: "Soma valores que atendem condicao (SUMIF)",
      params: ["coluna_valores", "coluna_criterios", "criterio"],
    },
    SE: {
      descricao: "Logica condicional (IF)",
      params: ["condicao_true", "valor_se_verdadeiro", "valor_se_falso"],
    },
    CONCATENAR: {
      descricao: "Junta textos (CONCATENATE / &)",
      params: ["colunas", "separador"],
    },
    SUBSTITUIR: {
      descricao: "Substitui texto por outro (SUBSTITUTE)",
      params: ["coluna", "antigo", "novo"],
    },
    VALOR: {
      descricao: "Converte texto para numero (VALUE)",
      params: ["coluna"],
    },
    TEXTO: {
      descricao: "Converte numero para texto formatado (TEXT)",
      params: ["coluna", "formato"],
    },
    ARRED: {
      descricao: "Arredonda numero (ROUND)",
      params: ["coluna", "casas"],
    },
    MAX: {
      descricao: "Maior valor de um grupo (MAX)",
      params: ["coluna"],
    },
    MIN: {
      descricao: "Menor valor de um grupo (MIN)",
      params: ["coluna"],
    },
    MEDIA: {
      descricao: "Media aritmetica (AVERAGE)",
      params: ["coluna"],
    },
    SOMA: {
      descricao: "Soma de valores (SUM)",
      params: ["coluna"],
    },
    HARMONICA: {
      descricao: "Media harmonica (HARMEAN) — util para taxas e precos medios",
      params: ["coluna"],
    },
    CORREL: {
      descricao: "Correlacao entre duas colunas (CORREL)",
      params: ["col_a", "col_b", "metodo(pearson/spearman)"],
    },
    PEARSON: {
      descricao: "Coeficiente de correlacao de Pearson (r)",
      params: ["col_a", "col_b"],
    },
    SPEARMAN: {
      descricao: "Correlacao de Spearman (rho) — baseada em postos",
      params: ["col_a", "col_b"],
    },
    PROCV_AGRUPADO: {
      descricao: "PROCV com retorno de multiplos valores agrupados",
      params: ["coluna_chave_tabela", "tabela_origem", "coluna_chave_origem", "coluna_valor_origem", "funcao_agregacao"],
    },
    INDICE_CORRESP: {
      descricao: "INDICE+CORRESP (INDEX-MATCH): busca avancada, mais flexivel que PROCV",
      params: ["coluna_retorno", "valor_procurado", "coluna_busca"],
    },
  };

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string) {
    this.logBuffer.push(msg);
    if (this.logger) {
      this.logger.info(msg);
    }
  }

  public flushLog(): string[] {
    const logs = [...this.logBuffer];
    this.logBuffer = [];
    return logs;
  }

  public listarFormulas(): Record<string, string> {
    const res: Record<string, string> = {};
    for (const [k, v] of Object.entries(FormulaEngine.CATALOGO)) {
      res[k] = v.descricao;
    }
    return res;
  }

  public procv(
    dfTabela: DataFrame,
    colunaChaveTabela: string,
    dfOrigem: DataFrame,
    colunaChaveOrigem: string,
    colunaValorOrigem: string,
    padraoNaoEncontrado: any = null
  ): DataFrame {
    const nomeCol = `${colunaValorOrigem}_procv`;
    const lookup = new Map<string, any>();

    for (const row of dfOrigem.data) {
      const k = row[colunaChaveOrigem];
      if (k !== null && k !== undefined) {
        lookup.set(String(k).trim(), row[colunaValorOrigem]);
      }
    }

    let encontrados = 0;
    const newData = dfTabela.data.map((r) => {
      const newRow = { ...r };
      const key = r[colunaChaveTabela];
      if (key !== null && key !== undefined && lookup.has(String(key).trim())) {
        newRow[nomeCol] = lookup.get(String(key).trim());
        encontrados++;
      } else {
        newRow[nomeCol] = padraoNaoEncontrado;
      }
      return newRow;
    });

    const newCols = dfTabela.columns.includes(nomeCol) ? dfTabela.columns : [...dfTabela.columns, nomeCol];
    this._log(`[PROCV] '${colunaChaveTabela}' -> '${colunaValorOrigem}': ${encontrados}/${dfTabela.data.length} registros encontrados.`);

    return { columns: newCols, data: newData };
  }

  public procvAgrupado(
    dfTabela: DataFrame,
    colunaChaveTabela: string,
    dfOrigem: DataFrame,
    colunaChaveOrigem: string,
    colunaValorOrigem: string,
    funcao: string = "soma"
  ): DataFrame {
    const nomeCol = `${colunaValorOrigem}_${funcao}`;
    const grouped = new Map<string, number[]>();

    for (const row of dfOrigem.data) {
      const k = row[colunaChaveOrigem];
      const v = row[colunaValorOrigem];
      if (k !== null && k !== undefined && v !== null && v !== undefined) {
        const strKey = String(k).trim();
        const num = parseFloat(String(v).replace(/\./g, "").replace(",", "."));
        if (!isNaN(num)) {
          if (!grouped.has(strKey)) grouped.set(strKey, []);
          grouped.get(strKey)!.push(num);
        }
      }
    }

    const aggLookup = new Map<string, number>();
    for (const [k, nums] of grouped.entries()) {
      let resVal = 0;
      if (funcao === "soma" || funcao === "sum") {
        resVal = nums.reduce((a, b) => a + b, 0);
      } else if (funcao === "media" || funcao === "mean") {
        resVal = nums.reduce((a, b) => a + b, 0) / nums.length;
      } else if (funcao === "contagem" || funcao === "count") {
        resVal = nums.length;
      } else if (funcao === "min") {
        resVal = Math.min(...nums);
      } else if (funcao === "max") {
        resVal = Math.max(...nums);
      } else if (funcao === "mediana" || funcao === "median") {
        nums.sort((a, b) => a - b);
        const mid = Math.floor(nums.length / 2);
        resVal = nums.length % 2 !== 0 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
      }
      aggLookup.set(k, Number(resVal.toFixed(2)));
    }

    const newData = dfTabela.data.map((r) => {
      const newRow = { ...r };
      const key = r[colunaChaveTabela];
      if (key !== null && key !== undefined && aggLookup.has(String(key).trim())) {
        newRow[nomeCol] = aggLookup.get(String(key).trim());
      } else {
        newRow[nomeCol] = null;
      }
      return newRow;
    });

    const newCols = dfTabela.columns.includes(nomeCol) ? dfTabela.columns : [...dfTabela.columns, nomeCol];
    this._log(`[PROCV_AGRUPADO] '${colunaChaveTabela}' -> '${colunaValorOrigem}' (${funcao}): ${dfTabela.data.length} linhas mapeadas.`);
    return { columns: newCols, data: newData };
  }

  public esquerda(df: DataFrame, coluna: string, numCaracteres: number, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_esquerda`;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      newRow[saida] = val !== null && val !== undefined ? String(val).slice(0, numCaracteres) : "";
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[ESQUERDA] '${coluna}' (${numCaracteres} chars) -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public direita(df: DataFrame, coluna: string, numCaracteres: number, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_direita`;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      newRow[saida] = val !== null && val !== undefined ? String(val).slice(-numCaracteres) : "";
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[DIREITA] '${coluna}' (${numCaracteres} chars) -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public meio(df: DataFrame, coluna: string, posicaoInicial: number, numCaracteres: number, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_meio`;
    const inicio = posicaoInicial - 1; // 1-based to 0-based
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      newRow[saida] = val !== null && val !== undefined ? String(val).substring(inicio, inicio + numCaracteres) : "";
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[MEIO] '${coluna}' (pos=${posicaoInicial}, ${numCaracteres} chars) -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public tamanho(df: DataFrame, coluna: string, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_tamanho`;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      newRow[saida] = val !== null && val !== undefined ? String(val).length : 0;
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[TAMANHO] '${coluna}' -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public substituirTexto(df: DataFrame, coluna: string, antigo: string, novo: string, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_substituido`;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      newRow[saida] = val !== null && val !== undefined ? String(val).split(antigo).join(novo) : "";
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[SUBSTITUIR] '${coluna}': '${antigo}' -> '${novo}' -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public concatenar(df: DataFrame, colunas: string[], separador: string = "", novaColuna: string = "concat"): DataFrame {
    const validCols = colunas.filter((c) => df.columns.includes(c));
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const parts = validCols.map((c) => (r[c] !== null && r[c] !== undefined ? String(r[c]) : ""));
      newRow[novaColuna] = parts.join(separador);
      return newRow;
    });
    const newCols = df.columns.includes(novaColuna) ? df.columns : [...df.columns, novaColuna];
    this._log(`[CONCATENAR] ${validCols.join(", ")} -> '${novaColuna}'.`);
    return { columns: newCols, data: newData };
  }

  public corresp(df: DataFrame, valor: any, colunaBusca: string): number[] {
    const positions: number[] = [];
    const strTarget = String(valor).trim().toUpperCase();
    for (let i = 0; i < df.data.length; i++) {
      const v = df.data[i][colunaBusca];
      if (v !== null && v !== undefined && String(v).trim().toUpperCase() === strTarget) {
        positions.push(i);
      }
    }
    this._log(`[CORRESP] Valor '${valor}' em '${colunaBusca}': ${positions.length} ocorrencia(s).`);
    return positions;
  }

  public indice(df: DataFrame, coluna: string, posicao: number): any {
    const idx = posicao - 1; // 1-based
    if (idx >= 0 && idx < df.data.length) {
      const val = df.data[idx][coluna];
      this._log(`[INDICE] '${coluna}' na posicao ${posicao}: '${val}'.`);
      return val;
    }
    this._log(`[INDICE] Posicao ${posicao} fora do intervalo (max=${df.data.length}).`);
    return null;
  }

  public se(df: DataFrame, condicao: string, valorVerdadeiro: any, valorFalso: any, novaColuna: string = "resultado_se"): DataFrame {
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      let res = false;
      try {
        // Safe evaluation of simple comparison conditions (e.g. col_a > 100, col_b == 'SIM')
        const keys = Object.keys(r);
        let evalExpr = condicao;
        for (const k of keys) {
          const val = r[k];
          const escapedVal = typeof val === "string" ? JSON.stringify(val) : val === null || val === undefined ? "null" : val;
          const reg = new RegExp(`\\b${k}\\b`, "g");
          evalExpr = evalExpr.replace(reg, String(escapedVal));
        }
        res = Boolean(Function(`"use strict"; return (${evalExpr})`)());
      } catch {
        res = false;
      }
      newRow[novaColuna] = res ? valorVerdadeiro : valorFalso;
      return newRow;
    });

    const newCols = df.columns.includes(novaColuna) ? df.columns : [...df.columns, novaColuna];
    this._log(`[SE] condicao='${condicao}' -> '${novaColuna}'.`);
    return { columns: newCols, data: newData };
  }

  public contSe(df: DataFrame, coluna: string, criterio: any): number {
    let count = 0;
    const strCrit = String(criterio).trim();

    if (/^[><!=]=?/.test(strCrit)) {
      const match = strCrit.match(/^([><!=]=?)\s*(.*)$/);
      if (match) {
        const op = match[1];
        const numVal = parseFloat(match[2].replace(",", "."));
        for (const r of df.data) {
          const val = r[coluna];
          if (val !== null && val !== undefined) {
            const rowNum = typeof val === "number" ? val : parseFloat(String(val).replace(",", "."));
            if (!isNaN(rowNum)) {
              if (op === ">" && rowNum > numVal) count++;
              else if (op === "<" && rowNum < numVal) count++;
              else if (op === ">=" && rowNum >= numVal) count++;
              else if (op === "<=" && rowNum <= numVal) count++;
              else if (op === "!=" && rowNum !== numVal) count++;
            }
          }
        }
      }
    } else {
      const critUpper = strCrit.toUpperCase();
      for (const r of df.data) {
        const val = r[coluna];
        if (val !== null && val !== undefined && String(val).trim().toUpperCase() === critUpper) {
          count++;
        }
      }
    }

    this._log(`[CONT.SE] '${coluna}' criterio='${criterio}': ${count}.`);
    return count;
  }

  public somase(df: DataFrame, colunaValores: string, colunaCriterios: string, criterio: any): number {
    let sum = 0;
    const strCrit = String(criterio).trim();

    if (/^[><!=]=?/.test(strCrit)) {
      const match = strCrit.match(/^([><!=]=?)\s*(.*)$/);
      if (match) {
        const op = match[1];
        const numVal = parseFloat(match[2].replace(",", "."));
        for (const r of df.data) {
          const critVal = r[colunaCriterios];
          if (critVal !== null && critVal !== undefined) {
            const rowCritNum = typeof critVal === "number" ? critVal : parseFloat(String(critVal).replace(",", "."));
            let matchCond = false;
            if (!isNaN(rowCritNum)) {
              if (op === ">" && rowCritNum > numVal) matchCond = true;
              else if (op === "<" && rowCritNum < numVal) matchCond = true;
              else if (op === ">=" && rowCritNum >= numVal) matchCond = true;
              else if (op === "<=" && rowCritNum <= numVal) matchCond = true;
              else if (op === "!=" && rowCritNum !== numVal) matchCond = true;
            }
            if (matchCond) {
              const val = r[colunaValores];
              const num = typeof val === "number" ? val : parseFloat(String(val).replace(/\./g, "").replace(",", "."));
              if (!isNaN(num)) sum += num;
            }
          }
        }
      }
    } else {
      const critUpper = strCrit.toUpperCase();
      for (const r of df.data) {
        const critVal = r[colunaCriterios];
        if (critVal !== null && critVal !== undefined && String(critVal).trim().toUpperCase() === critUpper) {
          const val = r[colunaValores];
          const num = typeof val === "number" ? val : parseFloat(String(val).replace(/\./g, "").replace(",", "."));
          if (!isNaN(num)) sum += num;
        }
      }
    }

    this._log(`[SOMASE] '${colunaValores}' onde '${colunaCriterios}'=${criterio}: ${sum.toFixed(2)}.`);
    return Number(sum.toFixed(2));
  }

  public valor(df: DataFrame, coluna: string, novaColuna?: string): DataFrame {
    const saida = novaColuna || coluna;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      if (val !== null && val !== undefined) {
        const strVal = String(val).trim().replace(/\./g, "").replace(",", ".");
        const num = parseFloat(strVal);
        newRow[saida] = isNaN(num) ? null : num;
      } else {
        newRow[saida] = null;
      }
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[VALOR] '${coluna}' -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public arred(df: DataFrame, coluna: string, casas: number = 0, novaColuna?: string): DataFrame {
    const saida = novaColuna || `${coluna}_arred`;
    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const val = r[coluna];
      if (val !== null && val !== undefined) {
        const num = typeof val === "number" ? val : parseFloat(String(val).replace(",", "."));
        newRow[saida] = isNaN(num) ? null : Number(num.toFixed(casas));
      } else {
        newRow[saida] = null;
      }
      return newRow;
    });
    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[ARRED] '${coluna}' (${casas} casas) -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }

  public maximo(df: DataFrame, coluna: string): number {
    let max = -Infinity;
    for (const r of df.data) {
      const v = r[coluna];
      if (v !== null && v !== undefined) {
        const num = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
        if (!isNaN(num) && num > max) max = num;
      }
    }
    return max === -Infinity ? 0 : max;
  }

  public minimo(df: DataFrame, coluna: string): number {
    let min = Infinity;
    for (const r of df.data) {
      const v = r[coluna];
      if (v !== null && v !== undefined) {
        const num = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
        if (!isNaN(num) && num < min) min = num;
      }
    }
    return min === Infinity ? 0 : min;
  }

  public media(df: DataFrame, coluna: string): number {
    let sum = 0;
    let count = 0;
    for (const r of df.data) {
      const v = r[coluna];
      if (v !== null && v !== undefined) {
        const num = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
        if (!isNaN(num)) {
          sum += num;
          count++;
        }
      }
    }
    return count > 0 ? Number((sum / count).toFixed(2)) : 0;
  }

  public soma(df: DataFrame, coluna: string): number {
    let sum = 0;
    for (const r of df.data) {
      const v = r[coluna];
      if (v !== null && v !== undefined) {
        const num = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
        if (!isNaN(num)) sum += num;
      }
    }
    return Number(sum.toFixed(2));
  }

  public harmonica(df: DataFrame, coluna: string): number {
    const valid: number[] = [];
    for (const r of df.data) {
      const v = r[coluna];
      if (v !== null && v !== undefined) {
        const num = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
        if (!isNaN(num) && num > 0) valid.push(num);
      }
    }
    if (valid.length === 0) return 0.0;
    const sumInv = valid.reduce((acc, x) => acc + 1.0 / x, 0);
    const res = valid.length / sumInv;
    this._log(`[HARMONICA] '${coluna}': ${res.toFixed(4)} (n=${valid.length}).`);
    return Number(res.toFixed(4));
  }

  public correl(df: DataFrame, colA: string, colB: string, metodo: "pearson" | "spearman" = "pearson"): number {
    const pairs: [number, number][] = [];
    for (const r of df.data) {
      const vA = r[colA];
      const vB = r[colB];
      if (vA !== null && vA !== undefined && vB !== null && vB !== undefined) {
        const nA = typeof vA === "number" ? vA : parseFloat(String(vA).replace(",", "."));
        const nB = typeof vB === "number" ? vB : parseFloat(String(vB).replace(",", "."));
        if (!isNaN(nA) && !isNaN(nB)) {
          pairs.push([nA, nB]);
        }
      }
    }

    if (pairs.length < 2) {
      this._log(`[CORREL] Dados insuficientes entre '${colA}' e '${colB}'.`);
      return 0.0;
    }

    if (metodo === "pearson") {
      const meanA = pairs.reduce((acc, p) => acc + p[0], 0) / pairs.length;
      const meanB = pairs.reduce((acc, p) => acc + p[1], 0) / pairs.length;
      let num = 0;
      let denA = 0;
      let denB = 0;
      for (const [a, b] of pairs) {
        const diffA = a - meanA;
        const diffB = b - meanB;
        num += diffA * diffB;
        denA += diffA * diffA;
        denB += diffB * diffB;
      }
      const den = Math.sqrt(denA * denB);
      const res = den === 0 ? 0 : num / den;
      this._log(`[CORREL] '${colA}' vs '${colB}' (pearson): ${res.toFixed(4)}.`);
      return Number(res.toFixed(4));
    } else {
      // Spearman
      const rankA = this.calculateRanks(pairs.map((p) => p[0]));
      const rankB = this.calculateRanks(pairs.map((p) => p[1]));
      let d2Sum = 0;
      const n = pairs.length;
      for (let i = 0; i < n; i++) {
        const d = rankA[i] - rankB[i];
        d2Sum += d * d;
      }
      const res = 1 - (6 * d2Sum) / (n * (n * n - 1));
      this._log(`[CORREL] '${colA}' vs '${colB}' (spearman): ${res.toFixed(4)}.`);
      return Number(res.toFixed(4));
    }
  }

  private calculateRanks(arr: number[]): number[] {
    const sorted = arr.map((val, idx) => ({ val, idx })).sort((a, b) => a.val - b.val);
    const ranks = new Array(arr.length);
    let i = 0;
    while (i < sorted.length) {
      let j = i;
      while (j < sorted.length && sorted[j].val === sorted[i].val) {
        j++;
      }
      const avgRank = (i + 1 + j) / 2;
      for (let k = i; k < j; k++) {
        ranks[sorted[k].idx] = avgRank;
      }
      i = j;
    }
    return ranks;
  }

  public indiceCorresp(df: DataFrame, colunaRetorno: string, valorProcurado: any, colunaBusca: string): DataFrame {
    const saida = `${colunaRetorno}_indice`;
    const lookup = new Map<string, any>();
    for (const r of df.data) {
      const k = r[colunaBusca];
      if (k !== null && k !== undefined) {
        const sk = String(k).trim();
        if (!lookup.has(sk)) lookup.set(sk, r[colunaRetorno]);
      }
    }

    const isCol = typeof valorProcurado === "string" && df.columns.includes(valorProcurado);
    const fixedTarget = !isCol ? String(valorProcurado).trim() : null;

    const newData = df.data.map((r) => {
      const newRow = { ...r };
      const targetVal = isCol ? r[valorProcurado] : fixedTarget;
      if (targetVal !== null && targetVal !== undefined) {
        newRow[saida] = lookup.get(String(targetVal).trim()) ?? null;
      } else {
        newRow[saida] = null;
      }
      return newRow;
    });

    const newCols = df.columns.includes(saida) ? df.columns : [...df.columns, saida];
    this._log(`[INDICE_CORRESP] '${colunaRetorno}' por '${colunaBusca}' -> '${saida}'.`);
    return { columns: newCols, data: newData };
  }
}

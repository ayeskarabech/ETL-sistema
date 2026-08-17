import { DataFrame, DiagnosticIssue } from "../types";
import { CleaningRules } from "../cleaning/rules";
import { Logger } from "../utils/logger";

export class DiagnosticScanner {
  private logger?: Logger;

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  public escanear(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    issues.push(...this.checarNulos(df));
    issues.push(...this.checarDuplicatas(df));
    issues.push(...this.checarColunasVazias(df));
    issues.push(...this.checarColunasUnnamed(df));
    issues.push(...this.checarFormatoDecimalPonto(df));
    issues.push(...this.checarFormatosNumericos(df));
    issues.push(...this.checarTipoColuna(df));
    issues.push(...this.checarValoresSuspeitos(df));
    issues.push(...this.checarTextoInconsistente(df));
    issues.push(...this.checarFuzzyMatch(df));

    const gravWeight: Record<string, number> = { critico: 3, aviso: 2, info: 1 };
    issues.sort((a, b) => (gravWeight[b.gravidade] || 0) - (gravWeight[a.gravidade] || 0));

    return issues;
  }

  private isNull(v: any): boolean {
    return v === null || v === undefined || v === "" || (typeof v === "number" && isNaN(v));
  }

  private checarNulos(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];
    const total = df.data.length;
    if (total === 0) return issues;

    for (const col of df.columns) {
      let nulos = 0;
      for (const r of df.data) {
        if (this.isNull(r[col])) nulos++;
      }
      if (nulos === 0) continue;

      const pct = (nulos / total) * 100;
      let gravidade: "critico" | "aviso" | "info" = "info";
      if (pct === 100 || pct > 30) gravidade = "critico";
      else if (pct > 10) gravidade = "aviso";

      issues.push({
        categoria: "NULOS",
        coluna: col,
        descricao: `${nulos} valores nulos (${pct.toFixed(1)}% da base)`,
        gravidade,
        detalhes: { quantidade: nulos, percentual: Number(pct.toFixed(2)) },
      });
    }
    return issues;
  }

  private checarDuplicatas(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];
    const total = df.data.length;
    if (total === 0) return issues;

    const seen = new Set<string>();
    let dups = 0;
    for (const r of df.data) {
      const k = df.columns.map((c) => String(r[c] ?? "")).join("|||");
      if (seen.has(k)) dups++;
      else seen.add(k);
    }

    if (dups > 0) {
      const pct = (dups / total) * 100;
      const gravidade: "critico" | "aviso" | "info" = pct > 20 ? "critico" : pct > 5 ? "aviso" : "info";
      issues.push({
        categoria: "DUPLICATAS",
        coluna: "(todas as colunas)",
        descricao: `${dups} linhas totalmente duplicadas (${pct.toFixed(1)}%)`,
        gravidade,
        detalhes: { quantidade: dups, percentual: Number(pct.toFixed(2)) },
      });
    }

    for (const col of df.columns) {
      const colSeen = new Set<string>();
      let colDups = 0;
      for (const r of df.data) {
        const v = r[col];
        if (this.isNull(v)) continue;
        const s = String(v);
        if (colSeen.has(s)) colDups++;
        else colSeen.add(s);
      }
      const unicos = colSeen.size;
      if (colDups > 0 && unicos < total * 0.5 && unicos > 1) {
        issues.push({
          categoria: "DUPLICATA_COLUNA",
          coluna: col,
          descricao: `Coluna tem apenas ${unicos} valores unicos (${colDups} repetidos)`,
          gravidade: "info",
          detalhes: { unicos, repetidos: colDups },
        });
      }
    }

    return issues;
  }

  private checarColunasVazias(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];
    const total = df.data.length;
    if (total === 0) return issues;

    for (const col of df.columns) {
      let nulos = 0;
      for (const r of df.data) {
        if (this.isNull(r[col])) nulos++;
      }
      if (nulos === total) {
        issues.push({
          categoria: "COLUNA_VAZIA",
          coluna: col,
          descricao: "Coluna 100% vazia — provavelmente erro de mapeamento",
          gravidade: "critico",
        });
      } else if (nulos > total * 0.9) {
        issues.push({
          categoria: "COLUNA_VAZIA",
          coluna: col,
          descricao: `Coluna com ${Math.round((nulos / total) * 100)}% de valores nulos`,
          gravidade: "aviso",
        });
      }
    }
    return issues;
  }

  private checarColunasUnnamed(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];
    for (const col of df.columns) {
      if (col.startsWith("Unnamed") || col.startsWith("__EMPTY")) {
        issues.push({
          categoria: "COLUNA_UNNAMED",
          coluna: col,
          descricao: "Coluna 'Unnamed' — provavel linha de titulo incorreta no CSV original",
          gravidade: "aviso",
        });
      }
    }
    return issues;
  }

  private checarFormatoDecimalPonto(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    for (const col of df.columns) {
      const amostra = df.data
        .map((r) => r[col])
        .filter((v) => !this.isNull(v))
        .map((v) => String(v).trim())
        .slice(0, 500);

      if (amostra.length < 5) continue;

      const padraoPontoDecimal = /^-?\d+\.\d{1,6}$/;
      const padraoVirgulaDecimal = /^-?\d+,\d{1,6}$/;
      const padraoInteiro = /^-?\d+$/;

      let nPonto = 0;
      let nVirgula = 0;
      let nInteiro = 0;
      const exemplosPonto: string[] = [];

      for (const s of amostra) {
        if (padraoPontoDecimal.test(s)) {
          nPonto++;
          if (exemplosPonto.length < 5) exemplosPonto.push(s);
        } else if (padraoVirgulaDecimal.test(s)) {
          nVirgula++;
        } else if (padraoInteiro.test(s)) {
          nInteiro++;
        }
      }

      const totalNumericos = nPonto + nVirgula + nInteiro;
      if (totalNumericos < 3) continue;

      if (nPonto > nVirgula && nPonto >= 3) {
        const pctPonto = (nPonto / amostra.length) * 100;
        issues.push({
          categoria: "NUMERO_PONTO_DECIMAL",
          coluna: col,
          descricao:
            `Coluna contem ${nPonto} numeros com PONTO decimal (${pctPonto.toFixed(0)}% da amostra). ` +
            `No formato brasileiro, deveria ser VIRGULA (ex: 1234,56 em vez de 1234.56).`,
          gravidade: "aviso",
          detalhes: {
            qtd_ponto_decimal: nPonto,
            qtd_virgula_decimal: nVirgula,
            qtd_inteiros: nInteiro,
            sugestao: "Usar opcao 'Converter texto para numero interno' ou 'Formato brasileiro' para corrigir",
            exemplos_ponto: exemplosPonto,
          },
        });
      } else if (nPonto > 0 && nVirgula > 0) {
        issues.push({
          categoria: "NUMERO_PONTO_DECIMAL",
          coluna: col,
          descricao: `Formato numerico INCONSISTENTE: ${nPonto} valores com ponto decimal e ${nVirgula} com virgula decimal na mesma coluna`,
          gravidade: "critico",
          detalhes: {
            qtd_ponto_decimal: nPonto,
            qtd_virgula_decimal: nVirgula,
            sugestao: "Unificar formato antes de manipular",
          },
        });
      }
    }

    return issues;
  }

  private checarFormatosNumericos(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    for (const col of df.columns) {
      const amostra = df.data
        .map((r) => r[col])
        .filter((v) => !this.isNull(v))
        .map((v) => String(v))
        .slice(0, 500);

      if (amostra.length === 0) continue;

      const temMoeda = amostra.some((s) => s.includes("R$"));
      const temPorcentagem = amostra.some((s) => s.includes("%"));
      const temMilharBr = amostra.some((s) => /^\d{1,3}(\.\d{3})+,\d+$/.test(s.trim()));

      const formatos: string[] = [];
      if (temMoeda) formatos.push("moeda (R$)");
      if (temPorcentagem) formatos.push("porcentagem (%)");
      if (temMilharBr) formatos.push("milhar brasileiro (1.234,56)");

      if (formatos.length > 0) {
        issues.push({
          categoria: "FORMATO_ESPECIAL",
          coluna: col,
          descricao: `Formato especial detectado: ${formatos.join(", ")}`,
          gravidade: "info",
          detalhes: { formatos },
        });
      }
    }

    return issues;
  }

  private checarTipoColuna(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    for (const col of df.columns) {
      const amostra = df.data
        .map((r) => r[col])
        .filter((v) => !this.isNull(v))
        .slice(0, 500);

      if (amostra.length < 10) continue;

      const padraoNum = /^-?\d+([.,]\d+)?$/;
      let nNum = 0;
      const naoNumericos: string[] = [];
      const numExemplos: string[] = [];

      for (const val of amostra) {
        const s = String(val).trim();
        if (padraoNum.test(s)) {
          nNum++;
          if (numExemplos.length < 5) numExemplos.push(s);
        } else {
          if (naoNumericos.length < 5) naoNumericos.push(s);
        }
      }

      const pctNum = (nNum / amostra.length) * 100;
      if (pctNum >= 80 && nNum >= 10) {
        issues.push({
          categoria: "TIPO_TEXTO_NUMERO",
          coluna: col,
          descricao: `Coluna e TEXTO mas ${pctNum.toFixed(0)}% dos valores sao numericamente validos (${nNum}/${amostra.length}). Sugestao: converter para numero.`,
          gravidade: "aviso",
          detalhes: {
            formato_atual: "texto",
            sugestao: "numero/float",
            exemplos: numExemplos,
          },
        });
      } else if (pctNum >= 50 && pctNum < 80) {
        issues.push({
          categoria: "TIPO_TEXTO_NUMERO",
          coluna: col,
          descricao: `Coluna e TEXTO com ${pctNum.toFixed(0)}% numericos, mas com ${naoNumericos.length} valores nao numericos (${naoNumericos.join(", ")}).`,
          gravidade: "aviso",
          detalhes: {
            formato_atual: "texto",
            sugestao: "verificar valores nao numericos antes de converter",
            valores_nao_numericos: naoNumericos,
          },
        });
      } else if (pctNum >= 10 && pctNum < 50) {
        issues.push({
          categoria: "TIPO_TEXTO_NUMERO",
          coluna: col,
          descricao: `Coluna e TEXTO com apenas ${pctNum.toFixed(0)}% numericos (${nNum}/${amostra.length}). Valores mistos.`,
          gravidade: "info",
          detalhes: {
            formato_atual: "texto",
            exemplos_numericos: numExemplos,
          },
        });
      }
    }

    return issues;
  }

  private checarValoresSuspeitos(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];
    const suspeitos = new Set([
      "", "-", "--", "---", ".", "..", "...", "N/A", "NA", "n/a",
      "NULL", "null", "None", "none", "SEM DADO", "SEM VALOR",
      "NAO INFORMADO", "NAO DISPONIVEL", "0000-00-00", "00/00/0000",
      "S/N", "SN", "NI", "NR", "N/D", "N/R",
    ]);

    for (const col of df.columns) {
      const encontrados: Record<string, number> = {};
      let totalSuspeitos = 0;

      for (const r of df.data) {
        const val = r[col];
        if (val !== null && val !== undefined) {
          const s = String(val).trim().toUpperCase();
          if (suspeitos.has(s)) {
            encontrados[s] = (encontrados[s] || 0) + 1;
            totalSuspeitos++;
          }
        }
      }

      if (totalSuspeitos > 0) {
        issues.push({
          categoria: "VALOR_SUSPEITO",
          coluna: col,
          descricao: `${totalSuspeitos} valores suspeitos encontrados: ${JSON.stringify(encontrados)}`,
          gravidade: totalSuspeitos > 10 ? "aviso" : "info",
          detalhes: { valores: encontrados },
        });
      }
    }

    return issues;
  }

  private checarTextoInconsistente(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    for (const col of df.columns) {
      const amostra = df.data
        .map((r) => r[col])
        .filter((v) => !this.isNull(v))
        .map((v) => String(v))
        .slice(0, 500);

      if (amostra.length === 0) continue;

      let temEspacoInicio = false;
      let temEspacoFim = false;
      let temEspacoMeio = false;
      let nUpper = 0;
      let nLower = 0;

      for (const s of amostra) {
        if (/^\s+/.test(s)) temEspacoInicio = true;
        if (/\s+$/.test(s)) temEspacoFim = true;
        if (/\s{2,}/.test(s)) temEspacoMeio = true;

        if (s.length > 2) {
          if (s === s.toUpperCase() && /[A-Z]/.test(s)) nUpper++;
          if (s === s.toLowerCase() && /[a-z]/.test(s)) nLower++;
        }
      }

      const problemasEspaco: string[] = [];
      if (temEspacoInicio) problemasEspaco.push("espacos no inicio");
      if (temEspacoFim) problemasEspaco.push("espacos no fim");
      if (temEspacoMeio) problemasEspaco.push("espacos extras no meio");

      if (problemasEspaco.length > 0) {
        issues.push({
          categoria: "TEXTO_ESPACO",
          coluna: col,
          descricao: `Espacos incorretos: ${problemasEspaco.join(", ")}`,
          gravidade: "info",
        });
      }

      const total = amostra.length;
      if (nUpper > total * 0.3 && nLower > total * 0.3) {
        issues.push({
          categoria: "TEXTO_CASO",
          coluna: col,
          descricao: `Caixa INCONSISTENTE: ${nUpper} maiusculas e ${nLower} minusculas. Padronizar para formato unico.`,
          gravidade: "aviso",
        });
      }
    }

    return issues;
  }

  private checarFuzzyMatch(df: DataFrame): DiagnosticIssue[] {
    const issues: DiagnosticIssue[] = [];

    for (const col of df.columns) {
      const counts = new Map<string, number>();
      for (const r of df.data) {
        const v = r[col];
        if (!this.isNull(v)) {
          const s = String(v).trim().toUpperCase();
          if (s.length > 2 && !/^\d+$/.test(s)) {
            counts.set(s, (counts.get(s) || 0) + 1);
          }
        }
      }

      const uniqueVals = Array.from(counts.keys());
      if (uniqueVals.length < 2 || uniqueVals.length > 300) continue;

      const grupos: Record<string, string[]> = {};
      const parent = new Map<string, string>();
      for (const v of uniqueVals) parent.set(v, v);

      const find = (x: string): string => {
        let root = x;
        while (parent.get(root) !== root) root = parent.get(root)!;
        return root;
      };

      const union = (x: string, y: string) => {
        const rx = find(x);
        const ry = find(y);
        if (rx !== ry) parent.set(ry, rx);
      };

      for (let i = 0; i < uniqueVals.length; i++) {
        for (let j = i + 1; j < uniqueVals.length; j++) {
          const a = uniqueVals[i];
          const b = uniqueVals[j];
          const simBg = CleaningRules.bigramSimilarity(a, b);
          const simEd = CleaningRules.editDistanceNormalized(a, b);
          if (Math.max(simBg, simEd) >= 0.75) {
            union(a, b);
          }
        }
      }

      for (const v of uniqueVals) {
        const root = find(v);
        if (!grupos[root]) grupos[root] = [];
        grupos[root].push(v);
      }

      const filteredGrupos = Object.entries(grupos).filter(([_, list]) => list.length > 1);
      if (filteredGrupos.length > 0) {
        const totalPares = filteredGrupos.reduce((acc, [_, list]) => acc + list.length - 1, 0);
        const gruposSample: Record<string, string[]> = {};
        for (const [k, list] of filteredGrupos.slice(0, 10)) {
          gruposSample[k] = list.slice(0, 6);
        }

        issues.push({
          categoria: "FUZZY_MATCH",
          coluna: col,
          descricao: `${filteredGrupos.length} grupo(s) com valores similares (${totalPares} variantes possiveis)`,
          gravidade: "aviso",
          detalhes: {
            grupos: gruposSample,
            sugestao: "Usar opcao 'Unificar valores similares' para corrigir",
          },
        });
      }
    }

    return issues;
  }
}

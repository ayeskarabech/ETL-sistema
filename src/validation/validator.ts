import { DataFrame } from "../types";
import { Logger } from "../utils/logger";

export class DataValidator {
  private logger?: Logger;
  public alertas: string[] = [];

  constructor(logger?: Logger) {
    this.logger = logger;
  }

  private _log(msg: string, nivel: "info" | "warning" | "error" = "info") {
    if (this.logger) {
      this.logger[nivel](msg);
    } else {
      console.log(`[VALIDAÇÃO] ${msg}`);
    }
  }

  public validar(
    df: DataFrame,
    colunasObrigatorias?: string[],
    linhasMinimasEsperadas?: number
  ): { aprovado: boolean; alertas: string[] } {
    this.alertas = [];
    const resultado = { aprovado: true, alertas: [] as string[] };

    // 1. Colunas obrigatórias
    if (colunasObrigatorias && colunasObrigatorias.length > 0) {
      const faltantes = colunasObrigatorias.filter((c) => !df.columns.includes(c));
      if (faltantes.length > 0) {
        this._registrarAlerta(`Colunas obrigatórias ausentes: ${faltantes.join(", ")}`, resultado);
      }
    }

    // 2. Volume mínimo de linhas
    if (linhasMinimasEsperadas && df.data.length < linhasMinimasEsperadas) {
      this._registrarAlerta(
        `Volume de linhas abaixo do esperado: ${df.data.length} (esperado no mínimo ${linhasMinimasEsperadas}).`,
        resultado
      );
    }

    // 3. Colunas totalmente vazias
    const total = df.data.length;
    if (total > 0) {
      const colunasVazias = df.columns.filter((col) => {
        return df.data.every((r) => r[col] === null || r[col] === undefined || r[col] === "");
      });
      if (colunasVazias.length > 0) {
        this._registrarAlerta(`Colunas totalmente vazias (revisar mapeamento): ${colunasVazias.join(", ")}`, resultado);
      }
    }

    // 4. Colunas "Unnamed"
    const colunasUnnamed = df.columns.filter((c) => c.startsWith("Unnamed") || c.startsWith("__EMPTY"));
    if (colunasUnnamed.length > 0) {
      this._registrarAlerta(
        `Colunas 'Unnamed' detectadas (provável linha de título incorreta no arquivo original): ${colunasUnnamed.join(", ")}`,
        resultado
      );
    }

    // 5. Linhas totalmente duplicadas
    if (df.data.length > 0) {
      const seen = new Set<string>();
      let dups = 0;
      for (const r of df.data) {
        const k = df.columns.map((c) => String(r[c] ?? "")).join("|||");
        if (seen.has(k)) dups++;
        else seen.add(k);
      }
      if (dups > 0) {
        this._registrarAlerta(`${dups} linhas totalmente duplicadas ainda presentes na base.`, resultado);
      }
    }

    if (resultado.aprovado) {
      this._log("Validação concluída: nenhum problema encontrado.");
    } else {
      this._log(`Validação concluída com ${resultado.alertas.length} alerta(s). Revisar antes de publicar.`, "warning");
    }

    return resultado;
  }

  private _registrarAlerta(mensagem: string, resultado: { aprovado: boolean; alertas: string[] }) {
    resultado.aprovado = false;
    resultado.alertas.push(mensagem);
    this.alertas.push(mensagem);
    this._log(`⚠ ${mensagem}`, "warning");
  }
}

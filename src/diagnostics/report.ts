import { DiagnosticIssue, SuggestedStep } from "../types";

export class DiagnosticReport {
  private issues: DiagnosticIssue[];

  constructor(issues: DiagnosticIssue[]) {
    this.issues = issues;
  }

  public resumo(): string {
    if (!this.issues || this.issues.length === 0) {
      return "  Nenhum problema encontrado. Base parece saudavel.";
    }

    const criticos = this.issues.filter((i) => i.gravidade === "critico");
    const avisos = this.issues.filter((i) => i.gravidade === "aviso");
    const infos = this.issues.filter((i) => i.gravidade === "info");

    const linhas: string[] = [];
    linhas.push(`  Total de problemas: ${this.issues.length}`);
    linhas.push(`    Criticos: ${criticos.length}`);
    linhas.push(`    Avisos:   ${avisos.length}`);
    linhas.push(`    Info:     ${infos.length}`);

    const categorias: Record<string, number> = {};
    for (const i of this.issues) {
      categorias[i.categoria] = (categorias[i.categoria] || 0) + 1;
    }
    linhas.push("");
    linhas.push("  Por categoria:");
    for (const [cat, count] of Object.entries(categorias).sort((a, b) => b[1] - a[1])) {
      linhas.push(`    ${cat}: ${count}`);
    }

    return linhas.join("\n");
  }

  public detalhado(): string {
    if (!this.issues || this.issues.length === 0) {
      return "  Nenhum problema encontrado.";
    }

    const linhas: string[] = [];
    for (let i = 0; i < this.issues.length; i++) {
      const issue = this.issues[i];
      const icone = issue.gravidade === "critico" ? "[!!!]" : issue.gravidade === "aviso" ? "[ ! ]" : "[ i ]";
      linhas.push(`  ${String(i + 1).padStart(3, " ")}. ${icone} ${issue.categoria}`);
      linhas.push(`       Coluna: ${issue.coluna}`);
      linhas.push(`       ${issue.descricao}`);

      if (issue.detalhes) {
        for (const [chave, valor] of Object.entries(issue.detalhes)) {
          if (Array.isArray(valor) && valor.length > 3) {
            linhas.push(`       ${chave}: ${JSON.stringify(valor.slice(0, 5))}... (mais ${valor.length - 5})`);
          } else {
            linhas.push(`       ${chave}: ${typeof valor === "object" ? JSON.stringify(valor) : valor}`);
          }
        }
      }
      linhas.push("");
    }

    return linhas.join("\n");
  }

  public sugerirTratamentos(): SuggestedStep[] {
    const etapasSugeridas: SuggestedStep[] = [];
    const categorias = new Set(this.issues.map((i) => i.categoria));

    if (categorias.has("COLUNA_VAZIA") || categorias.has("NULOS")) {
      etapasSugeridas.push({
        operacao: "remover_colunas_vazias",
        params: { limiar: 1.0 },
        descricao: "Remover colunas 100% vazias",
      });
    }

    if (categorias.has("DUPLICATAS")) {
      etapasSugeridas.push({
        operacao: "remover_duplicatas",
        params: { normalizar: true },
        descricao: "Remover linhas duplicadas",
      });
    }

    if (categorias.has("NUMERO_PONTO_DECIMAL") || categorias.has("TIPO_TEXTO_NUMERO")) {
      const colsPonto = this.issues
        .filter((i) => i.categoria === "NUMERO_PONTO_DECIMAL" || i.categoria === "TIPO_TEXTO_NUMERO")
        .map((i) => i.coluna);
      if (colsPonto.length > 0) {
        const uniqueCols = Array.from(new Set(colsPonto));
        etapasSugeridas.push({
          operacao: "numero_interno",
          params: { colunas: uniqueCols, casas: 2 },
          descricao: `Converter textos numéricos para numero: ${uniqueCols.join(", ")}`,
        });
      }
    }

    if (categorias.has("TEXTO_ESPACO") || categorias.has("TEXTO_CASO")) {
      const colsEspaco = this.issues
        .filter((i) => i.categoria === "TEXTO_ESPACO" || i.categoria === "TEXTO_CASO")
        .map((i) => i.coluna);
      if (colsEspaco.length > 0) {
        const uniqueCols = Array.from(new Set(colsEspaco));
        etapasSugeridas.push({
          operacao: "normalizar_texto",
          params: { colunas: uniqueCols, modo: "upper" },
          descricao: `Normalizar espacos e caixa alta em: ${uniqueCols.join(", ")}`,
        });
      }
    }

    if (categorias.has("FUZZY_MATCH")) {
      for (const issue of this.issues) {
        if (issue.categoria === "FUZZY_MATCH") {
          etapasSugeridas.push({
            operacao: "unificar_valores",
            params: { coluna: issue.coluna, limiar: 0.82 },
            descricao: `Unificar valores similares em '${issue.coluna}'`,
          });
        }
      }
    }

    return etapasSugeridas;
  }

  public paraArquivo(): string {
    const linhas: string[] = [];
    linhas.push("=".repeat(70));
    linhas.push("  RELATORIO DE DIAGNOSTICO — ETL NGR-SEE");
    linhas.push("=".repeat(70));
    linhas.push("");
    linhas.push(this.resumo());
    linhas.push("");
    linhas.push("-".repeat(70));
    linhas.push("  DETALHAMENTO");
    linhas.push("-".repeat(70));
    linhas.push(this.detalhado());
    linhas.push("-".repeat(70));
    linhas.push("  SUGESTOES DE TRATAMENTO");
    linhas.push("-".repeat(70));
    const etapas = this.sugerirTratamentos();
    if (etapas.length > 0) {
      for (let i = 0; i < etapas.length; i++) {
        linhas.push(`  ${i + 1}. ${etapas[i].descricao}`);
      }
    } else {
      linhas.push("  Nenhuma acao sugerida.");
    }
    linhas.push("=".repeat(70));
    return linhas.join("\n");
  }
}

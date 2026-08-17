import { DataFrame, PipelineStep, StepResult } from "../types";
import { PipelineContext } from "./context";
import { DataCleaner } from "../cleaning/dataCleaner";
import { CleaningRules } from "../cleaning/rules";
import { FormulaEngine } from "../formulas/engine";
import { DataValidator } from "../validation/validator";
import { PowerBIExporter } from "../export/csvExporter";
import { DiagnosticScanner } from "../diagnostics/scanner";
import { Logger } from "../utils/logger";

export class Pipeline {
  public context: PipelineContext;
  public cleaner: DataCleaner;
  public rules: CleaningRules;
  public formulas: FormulaEngine;
  public validator: DataValidator;
  public scanner: DiagnosticScanner;
  public logger?: Logger;
  private filaEtapas: PipelineStep[] = [];

  constructor(context?: PipelineContext, logger?: Logger) {
    this.logger = logger;
    this.context = context || new PipelineContext(logger);
    this.cleaner = new DataCleaner(logger);
    this.rules = new CleaningRules(logger);
    this.formulas = new FormulaEngine(logger);
    this.validator = new DataValidator(logger);
    this.scanner = new DiagnosticScanner(logger);
  }

  public adicionarEtapa(operacao: string, params: Record<string, any> = {}): this {
    this.filaEtapas.push({ operacao, params });
    return this;
  }

  public limparFila() {
    this.filaEtapas = [];
  }

  public preview(linhas: number = 50): { colunas: string[]; dados: Record<string, any>[]; total_linhas: number; total_colunas: number } {
    const df = this.context.getData();
    return {
      colunas: df.columns,
      dados: df.data.slice(0, linhas),
      total_linhas: df.data.length,
      total_colunas: df.columns.length,
    };
  }

  public executarUmaEtapa(operacao: string, params: Record<string, any> = {}): StepResult {
    let df = this.context.getData();
    let novaDescricao = operacao;

    try {
      switch (operacao) {
        case "remover_colunas_vazias": {
          const limiar = params.limiar ?? 1.0;
          df = this.cleaner.removerColunasVazias(df, limiar);
          novaDescricao = `Remover colunas vazias (limiar=${limiar})`;
          break;
        }
        case "remover_linhas_vazias": {
          const colunas = params.colunas;
          const modo = params.modo ?? "todas";
          df = this.cleaner.removerLinhasVazias(df, colunas, modo);
          novaDescricao = `Remover linhas vazias (${modo})`;
          break;
        }
        case "remover_duplicatas": {
          const colunas = params.colunas;
          const normalizar = params.normalizar ?? true;
          df = this.rules.removerDuplicatas(df, colunas, "first", normalizar);
          novaDescricao = `Remover duplicatas ${colunas ? `em ${colunas.join(", ")}` : "(todas as colunas)"}`;
          break;
        }
        case "numero_br": {
          const colunas = params.colunas || [params.coluna];
          const casas = params.casas ?? 2;
          df = this.rules.formatarNumeroBR(df, colunas, casas, true, true, params.nova_coluna);
          novaDescricao = `Formatar numero BR (${colunas.join(", ")}, ${casas} casas)`;
          break;
        }
        case "numero_interno": {
          const colunas = params.colunas || [params.coluna];
          const casas = params.casas ?? 2;
          df = this.rules.formatarNumeroInterno(df, colunas, casas, params.nova_coluna);
          novaDescricao = `Converter para numero interno (${colunas.join(", ")}, ${casas} casas)`;
          break;
        }
        case "moeda": {
          const colunas = params.colunas || [params.coluna];
          const simbolo = params.simbolo ?? "R$";
          const casas = params.casas ?? 2;
          df = this.rules.formatarMoeda(df, colunas, simbolo, casas, params.nova_coluna);
          novaDescricao = `Formatar moeda ${simbolo} (${colunas.join(", ")})`;
          break;
        }
        case "porcentagem": {
          const colunas = params.colunas || [params.coluna];
          const casas = params.casas ?? 2;
          df = this.rules.formatarPorcentagem(df, colunas, casas, params.nova_coluna);
          novaDescricao = `Formatar porcentagem (${colunas.join(", ")})`;
          break;
        }
        case "normalizar_texto": {
          const colunas = params.colunas || [params.coluna];
          const modo = params.modo ?? "upper";
          df = this.cleaner.padronizarTexto(df, colunas, modo);
          novaDescricao = `Padronizar texto (${modo}) em ${colunas.join(", ")}`;
          break;
        }
        case "substituir_valores": {
          const colunas = params.colunas || [params.coluna];
          const mapeamento = params.mapeamento || {};
          df = this.rules.aplicarDicionario(df, colunas, mapeamento);
          novaDescricao = `Substituir valores em ${colunas.join(", ")}`;
          break;
        }
        case "unificar_valores": {
          const coluna = params.coluna;
          const limiar = params.limiar ?? 0.82;
          df = this.rules.unificarValoresSimilares(df, coluna, limiar);
          novaDescricao = `Unificar valores similares em '${coluna}'`;
          break;
        }
        case "corrigir_tipos": {
          const tipos = params.tipos || {};
          df = this.cleaner.corrigirTipos(df, tipos);
          novaDescricao = `Corrigir tipos: ${JSON.stringify(tipos)}`;
          break;
        }
        case "tratar_nulos": {
          const colunas = params.colunas || [params.coluna];
          const estrategia = params.estrategia ?? "valor_fixo";
          const valorFixo = params.valor_fixo ?? "";
          df = this.cleaner.tratarNulos(df, colunas, estrategia, valorFixo);
          novaDescricao = `Tratar nulos (${estrategia}) em ${colunas.join(", ")}`;
          break;
        }
        case "procv": {
          const colunaChaveTabela = params.coluna_chave_tabela;
          const tabelaOrigemNome = params.tabela_origem;
          const colunaChaveOrigem = params.coluna_chave_origem;
          const colunaValorOrigem = params.coluna_valor_origem;
          const padraoNaoEncontrado = params.padrao_nao_encontrado ?? null;

          const dfOrigem = this.context.getTabela(tabelaOrigemNome);
          if (dfOrigem.data.length === 0) {
            throw new Error(`Tabela de origem '${tabelaOrigemNome}' nao encontrada no contexto.`);
          }
          df = this.formulas.procv(df, colunaChaveTabela, dfOrigem, colunaChaveOrigem, colunaValorOrigem, padraoNaoEncontrado);
          novaDescricao = `PROCV: '${colunaChaveTabela}' -> '${tabelaOrigemNome}'.'${colunaValorOrigem}'`;
          break;
        }
        case "procv_agrupado": {
          const colunaChaveTabela = params.coluna_chave_tabela;
          const tabelaOrigemNome = params.tabela_origem;
          const colunaChaveOrigem = params.coluna_chave_origem;
          const colunaValorOrigem = params.coluna_valor_origem;
          const funcao = params.funcao_agregacao || params.funcao || "soma";

          const dfOrigem = this.context.getTabela(tabelaOrigemNome);
          if (dfOrigem.data.length === 0) {
            throw new Error(`Tabela de origem '${tabelaOrigemNome}' nao encontrada no contexto.`);
          }
          df = this.formulas.procvAgrupado(df, colunaChaveTabela, dfOrigem, colunaChaveOrigem, colunaValorOrigem, funcao);
          novaDescricao = `PROCV Agrupado (${funcao}): '${colunaChaveTabela}' -> '${tabelaOrigemNome}'.'${colunaValorOrigem}'`;
          break;
        }
        case "esquerda": {
          const coluna = params.coluna;
          const n = parseInt(params.num_caracteres || params.n, 10);
          df = this.formulas.esquerda(df, coluna, n, params.nova_coluna);
          novaDescricao = `ESQUERDA('${coluna}', ${n})`;
          break;
        }
        case "direita": {
          const coluna = params.coluna;
          const n = parseInt(params.num_caracteres || params.n, 10);
          df = this.formulas.direita(df, coluna, n, params.nova_coluna);
          novaDescricao = `DIREITA('${coluna}', ${n})`;
          break;
        }
        case "meio": {
          const coluna = params.coluna;
          const inicio = parseInt(params.posicao_inicial || params.posicao || params.inicio, 10);
          const n = parseInt(params.num_caracteres || params.n, 10);
          df = this.formulas.meio(df, coluna, inicio, n, params.nova_coluna);
          novaDescricao = `MEIO('${coluna}', ${inicio}, ${n})`;
          break;
        }
        case "tamanho": {
          const coluna = params.coluna;
          df = this.formulas.tamanho(df, coluna, params.nova_coluna);
          novaDescricao = `TAMANHO('${coluna}')`;
          break;
        }
        case "concatenar": {
          const colunas = params.colunas || [];
          const sep = params.separador ?? "";
          const novaCol = params.nova_coluna || "concat";
          df = this.formulas.concatenar(df, colunas, sep, novaCol);
          novaDescricao = `CONCATENAR(${colunas.join(", ")})`;
          break;
        }
        case "substituir_texto": {
          const coluna = params.coluna;
          const antigo = params.antigo;
          const novo = params.novo;
          df = this.formulas.substituirTexto(df, coluna, antigo, novo, params.nova_coluna);
          novaDescricao = `SUBSTITUIR('${coluna}': '${antigo}' -> '${novo}')`;
          break;
        }
        case "se": {
          const condicao = params.condicao_true || params.condicao;
          const vTrue = params.valor_se_verdadeiro;
          const vFalse = params.valor_se_falso;
          const novaCol = params.nova_coluna || "resultado_se";
          df = this.formulas.se(df, condicao, vTrue, vFalse, novaCol);
          novaDescricao = `SE(${condicao})`;
          break;
        }
        case "arred": {
          const coluna = params.coluna;
          const casas = parseInt(params.casas || 0, 10);
          df = this.formulas.arred(df, coluna, casas, params.nova_coluna);
          novaDescricao = `ARRED('${coluna}', ${casas})`;
          break;
        }
        case "valor": {
          const coluna = params.coluna;
          df = this.formulas.valor(df, coluna, params.nova_coluna);
          novaDescricao = `VALOR('${coluna}')`;
          break;
        }
        case "indice_corresp": {
          const colRetorno = params.coluna_retorno;
          const valProcurado = params.valor_procurado;
          const colBusca = params.coluna_busca;
          df = this.formulas.indiceCorresp(df, colRetorno, valProcurado, colBusca);
          novaDescricao = `INDICE_CORRESP: '${colRetorno}' por '${colBusca}'`;
          break;
        }
        case "filtrar_linhas": {
          const coluna = params.coluna;
          const condicao = params.condicao; // "igual", "contem", "maior", "menor"
          const valor = params.valor;
          df = {
            columns: [...df.columns],
            data: df.data.filter((r) => {
              const v = r[coluna];
              if (v === null || v === undefined) return false;
              const sv = String(v).toUpperCase();
              const st = String(valor).toUpperCase();
              if (condicao === "igual") return sv === st;
              if (condicao === "contem") return sv.includes(st);
              if (condicao === "diferente") return sv !== st;
              const nv = typeof v === "number" ? v : parseFloat(String(v).replace(",", "."));
              const nt = parseFloat(String(valor).replace(",", "."));
              if (condicao === "maior") return nv > nt;
              if (condicao === "menor") return nv < nt;
              if (condicao === "maior_igual") return nv >= nt;
              if (condicao === "menor_igual") return nv <= nt;
              return true;
            }),
          };
          novaDescricao = `Filtrar '${coluna}' ${condicao} '${valor}'`;
          break;
        }
        case "renomear_coluna": {
          const de = params.de;
          const para = params.para;
          if (df.columns.includes(de)) {
            const newCols = df.columns.map((c) => (c === de ? para : c));
            const newData = df.data.map((r) => {
              const nr = { ...r };
              nr[para] = nr[de];
              delete nr[de];
              return nr;
            });
            df = { columns: newCols, data: newData };
            novaDescricao = `Renomear coluna '${de}' -> '${para}'`;
          }
          break;
        }
        case "remover_coluna": {
          const coluna = params.coluna;
          if (df.columns.includes(coluna)) {
            const newCols = df.columns.filter((c) => c !== coluna);
            const newData = df.data.map((r) => {
              const nr = { ...r };
              delete nr[coluna];
              return nr;
            });
            df = { columns: newCols, data: newData };
            novaDescricao = `Remover coluna '${coluna}'`;
          }
          break;
        }
        default:
          throw new Error(`Operação '${operacao}' não reconhecida.`);
      }

      this.context.setData(df, novaDescricao);
      return { sucesso: true, mensagem: `Etapa '${novaDescricao}' executada com sucesso.` };
    } catch (e: any) {
      return { sucesso: false, mensagem: `Erro na etapa '${operacao}': ${e.message}` };
    }
  }

  public executar(limparFila: boolean = true): StepResult[] {
    const resultados: StepResult[] = [];
    for (const etapa of this.filaEtapas) {
      const res = this.executarUmaEtapa(etapa.operacao, etapa.params);
      resultados.push(res);
      if (!res.sucesso) break;
    }
    if (limparFila) {
      this.limparFila();
    }
    return resultados;
  }

  public validar(colunasObrigatorias?: string[], linhasMinimas?: number) {
    return this.validator.validar(this.context.getData(), colunasObrigatorias, linhasMinimas);
  }

  public exportar(pastaSaida: string, nomeBase: string): string {
    const exporter = new PowerBIExporter(pastaSaida, this.logger);
    return exporter.exportar(this.context.getData(), nomeBase);
  }
}

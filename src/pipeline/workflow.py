"""
Workflow baseado em etapas: cada etapa e um dict {tipo, operacao, params}.
O executor roda as etapas em sequencia, registra resultado, e permite
desfazer/reescrever o historico — pronto para interface grafica.
"""

import numpy as np
import pandas as pd

from .context import PipelineContext
from src.cleaning.data_cleaner import DataCleaner
from src.cleaning.rules import CleaningRules
from src.formulas.engine import FormulaEngine


class StepResult:
    """Resultado da execucao de uma etapa."""

    def __init__(self, sucesso: bool, mensagem: str, dados: dict = None):
        self.sucesso = sucesso
        self.mensagem = mensagem
        self.dados = dados or {}

    def __repr__(self):
        status = "OK" if self.sucesso else "ERRO"
        return f"[{status}] {self.mensagem}"


class Pipeline:
    """
    Executa uma sequencia de etapas sobre um PipelineContext.
    Cada etapa e um dict com:
      - operacao: nome da operacao a executar
      - params: dict de parametros para a operacao
    """

    OPERACOES = {}

    def __init__(self, context: PipelineContext, logger=None):
        self.context = context
        self.logger = logger
        self.log_buffer = []
        self._cleaner = DataCleaner(logger)
        self._regras = CleaningRules(logger)
        self._engine = FormulaEngine(logger)
        self._registrar_operacoes()

    def _log(self, msg: str):
        self.log_buffer.append(msg)
        if self.logger:
            self.logger.info(msg)

    def flush_log(self) -> list:
        logs = list(self.log_buffer)
        self.log_buffer.clear()
        return logs

    def _registrar_operacoes(self):
        self.OPERACOES = {
            # ── Limpeza ──
            "formatar_brasileiro": self._op_formatar_brasileiro,
            "numero_interno": self._op_numero_interno,
            "detectar_duplicatas": self._op_detectar_duplicatas,
            "remover_duplicatas": self._op_remover_duplicatas,
            "valores_similares": self._op_valores_similares,
            "unificar_valores": self._op_unificar_valores,
            "remover_colunas_vazias": self._op_remover_colunas_vazias,
            "preencher_nulos": self._op_preencher_nulos,
            "remover_nulos": self._op_remover_nulos,
            "substituir_valores": self._op_substituir_valores,
            "substituir_regex": self._op_substituir_regex,
            "normalizar_texto": self._op_normalizar_texto,
            "corrigir_tipo": self._op_corrigir_tipo,
            # ── Transformacao ──
            "adicionar_coluna": self._op_adicionar_coluna,
            "renomear_coluna": self._op_renomear_coluna,
            "remover_coluna": self._op_remover_coluna,
            "filtrar_linhas": self._op_filtrar_linhas,
            "ordenar_por": self._op_ordenar_por,
            "reordenar_colunas": self._op_reordenar_colunas,
            "manter_n_primeiras": self._op_manter_n_primeiras,
            "manter_n_ultimas": self._op_manter_n_ultimas,
            # ── Formulas ──
            "procv": self._op_procv,
            "procv_agrupado": self._op_procv_agrupado,
            "esquerda": self._op_esquerda,
            "direita": self._op_direita,
            "meio": self._op_meio,
            "tamanho": self._op_tamanho,
            "concatenar": self._op_concatenar,
            "substituir_texto": self._op_substituir_texto,
            "corresp": self._op_corresp,
            "se": self._op_se,
            "cont_se": self._op_cont_se,
            "somase": self._op_somase,
            "arred": self._op_arred,
            "coluna_calculada": self._op_coluna_calculada,
            "indice": self._op_indice,
            "valor": self._op_valor,
            "maximo": self._op_maximo,
            "minimo": self._op_minimo,
            "media": self._op_media,
            "soma": self._op_soma,
            "harmonica": self._op_harmonica,
            "correl": self._op_correl,
            "pearson": self._op_pearson,
            "spearman": self._op_spearman,
            "indice_corresp": self._op_indice_corresp,
            # ── Join ──
            "juntar": self._op_juntar,
            # ── Agregacao ──
            "agregar": self._op_agregar,
        }

    def executar_etapas(self, etapas: list) -> list:
        resultados = []
        for i, etapa in enumerate(etapas, 1):
            operacao = etapa.get("operacao", "")
            params = etapa.get("params", {})

            if operacao not in self.OPERACOES:
                resultado = StepResult(False, f"Operacao '{operacao}' nao encontrada.")
                resultados.append(resultado)
                self._log(f"Etapa {i}: {resultado}")
                continue

            try:
                resultado = self.OPERACOES[operacao](params)
                resultados.append(resultado)
                self._log(f"Etapa {i}: {resultado}")
            except Exception as e:
                resultado = StepResult(False, f"ERRO na etapa '{operacao}': {e}")
                resultados.append(resultado)
                self._log(f"Etapa {i}: {resultado}")

        return resultados

    # ── LIMPEZA ────────────────────────────────────────────────────────────

    def _op_formatar_brasileiro(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._regras.formatar_brasileiro(df, p["colunas"], p.get("casas", 2))
        self.context.set_data(df, f"Formatar brasileiro: {p['colunas']}")
        return StepResult(True, f"Formato brasileiro aplicado em {p['colunas']}.")

    def _op_numero_interno(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._regras.formatar_numero_interno(df, p["colunas"], p.get("casas", 2))
        self.context.set_data(df, f"Numero interno: {p['colunas']}")
        return StepResult(True, f"Numeros convertidos: {p['colunas']}.")

    def _op_detectar_duplicatas(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._regras.detectar_duplicatas(df, p.get("colunas"), p.get("normalizar", True))
        self.context.set_data(df, "Duplicatas detectadas")
        dup = df["_duplicata"].sum() if "_duplicata" in df.columns else 0
        return StepResult(True, f"{dup} duplicatas encontradas.")

    def _op_remover_duplicatas(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._regras.remover_duplicatas(df, p.get("colunas"), p.get("normalizar", True))
        self.context.set_data(df, "Duplicatas removidas")
        return StepResult(True, "Duplicatas removidas.")

    def _op_valores_similares(self, p: dict) -> StepResult:
        df = self.context.get_data()
        pares = self._regras.encontrar_valores_similares(df, p["coluna"], p.get("limiar", 0.85))
        self.context.metadados["valores_similares"] = pares
        return StepResult(True, f"{len(pares)} pares similares encontrados.", {"pares": pares})

    def _op_unificar_valores(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._regras.unificar_valores(df, p["coluna"], p["mapeamento"])
        self.context.set_data(df, f"Unificado: '{p['coluna']}'")
        return StepResult(True, f"Valores unificados em '{p['coluna']}'.")

    def _op_remover_colunas_vazias(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._cleaner.remover_colunas_vazias(df, p.get("limiar", 1.0))
        self.context.set_data(df, "Colunas vazias removidas")
        return StepResult(True, "Colunas vazias removidas.")

    def _op_preencher_nulos(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._cleaner.tratar_nulos(df, p["estrategias"])
        self.context.set_data(df, f"Nulos preenchidos: {list(p['estrategias'].keys())}")
        return StepResult(True, f"Nulos tratados.")

    def _op_remover_nulos(self, p: dict) -> StepResult:
        df = self.context.get_data()
        estrategias = {col: "remover_linha" for col in p["colunas"]}
        df = self._cleaner.tratar_nulos(df, estrategias)
        self.context.set_data(df, f"Nulos removidos: {p['colunas']}")
        return StepResult(True, f"Linhas com nulos removidas.")

    def _op_substituir_valores(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._cleaner.substituir_valores(df, p["colunas"], p["mapeamento"])
        self.context.set_data(df, f"Substituicao: {p['mapeamento']}")
        return StepResult(True, "Substituicoes aplicadas.")

    def _op_substituir_regex(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._cleaner.substituir_regex(df, p["colunas"], p["padrao"], p["novo"])
        self.context.set_data(df, f"Regex: {p['padrao']}")
        return StepResult(True, f"Regex '{p['padrao']}' aplicada.")

    def _op_normalizar_texto(self, p: dict) -> StepResult:
        df = self.context.get_data()
        colunas = p["colunas"]
        modo = p.get("modo", "upper")
        if modo == "upper":
            df = self._cleaner.padronizar_texto(df, colunas)
        elif modo == "lower":
            df = self._cleaner.padronizar_texto_minusculas(df, colunas)
        self.context.set_data(df, f"Texto ({modo}): {colunas}")
        return StepResult(True, f"Texto normalizado em {colunas}.")

    def _op_corrigir_tipo(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._cleaner.corrigir_tipos(df, p["tipos"])
        self.context.set_data(df, f"Tipos: {p['tipos']}")
        return StepResult(True, "Tipos corrigidos.")

    # ── TRANSFORMACAO ──────────────────────────────────────────────────────

    def _op_adicionar_coluna(self, p: dict) -> StepResult:
        df = self.context.get_data()
        if "expressao" in p:
            escopo = {col: df[col] for col in df.columns}
            escopo["np"] = np
            escopo["pd"] = pd
            df[p["nome"]] = eval(p["expressao"], {"__builtins__": {}}, escopo)
        else:
            df[p["nome"]] = p.get("valor", "")
        self.context.set_data(df, f"Coluna '{p['nome']}' adicionada")
        return StepResult(True, f"Coluna '{p['nome']}' criada.")

    def _op_renomear_coluna(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = df.rename(columns=p["mapeamento"])
        self.context.set_data(df, f"Renomeado: {p['mapeamento']}")
        return StepResult(True, f"Renomeado: {p['mapeamento']}.")

    def _op_remover_coluna(self, p: dict) -> StepResult:
        df = self.context.get_data()
        colunas = [c for c in p["colunas"] if c in df.columns]
        df = df.drop(columns=colunas)
        self.context.set_data(df, f"Removidas: {colunas}")
        return StepResult(True, f"Colunas removidas: {colunas}.")

    def _op_filtrar_linhas(self, p: dict) -> StepResult:
        df = self.context.get_data()
        total_antes = len(df)
        try:
            escopo = {col: df[col] for col in df.columns}
            escopo["np"] = np
            escopo["pd"] = pd
            mascara = eval(p["condicao"], {"__builtins__": {}}, escopo)
            df = df[mascara].reset_index(drop=True)
            self.context.set_data(df, f"Filtro: {p['condicao']}")
            return StepResult(True, f"Filtro: {total_antes} -> {len(df)} linhas.")
        except Exception as e:
            return StepResult(False, f"Erro no filtro: {e}")

    def _op_ordenar_por(self, p: dict) -> StepResult:
        df = self.context.get_data()
        colunas = [c for c in p["colunas"] if c in df.columns]
        df = df.sort_values(by=colunas, ascending=p.get("ascendente", True)).reset_index(drop=True)
        self.context.set_data(df, f"Ordenado: {colunas}")
        return StepResult(True, f"Ordenado por {colunas}.")

    def _op_reordenar_colunas(self, p: dict) -> StepResult:
        df = self.context.get_data()
        existentes = [c for c in p["ordem"] if c in df.columns]
        restantes = [c for c in df.columns if c not in existentes]
        df = df[existentes + restantes]
        self.context.set_data(df, "Colunas reordenadas")
        return StepResult(True, "Colunas reordenadas.")

    def _op_manter_n_primeiras(self, p: dict) -> StepResult:
        df = self.context.get_data()
        total = len(df)
        df = df.head(p["n"]).reset_index(drop=True)
        self.context.set_data(df, f"Primeiras {p['n']}")
        return StepResult(True, f"Mantidas {len(df)}/{total} linhas.")

    def _op_manter_n_ultimas(self, p: dict) -> StepResult:
        df = self.context.get_data()
        total = len(df)
        df = df.tail(p["n"]).reset_index(drop=True)
        self.context.set_data(df, f"Ultimas {p['n']}")
        return StepResult(True, f"Mantidas {len(df)}/{total} linhas.")

    # ── FORMULAS ───────────────────────────────────────────────────────────

    def _op_procv(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df_ref = self.context.get_tabela(p["tabela_origem"])
        if df_ref.empty:
            return StepResult(False, f"Tabela '{p['tabela_origem']}' nao encontrada.")
        df = self._engine.procv(
            df, p["coluna_chave"], df_ref,
            p["coluna_chave_origem"], p["coluna_valor_origem"],
            p.get("padrao", "")
        )
        self.context.set_data(df, f"PROCV: {p['tabela_origem']}")
        return StepResult(True, "PROCV executado.")

    def _op_procv_agrupado(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df_ref = self.context.get_tabela(p["tabela_origem"])
        if df_ref.empty:
            return StepResult(False, f"Tabela '{p['tabela_origem']}' nao encontrada.")
        df = self._engine.procv_agrupado(
            df, p["coluna_chave"], df_ref,
            p["coluna_chave_origem"], p["coluna_valor_origem"],
            p.get("funcao", "soma")
        )
        self.context.set_data(df, f"PROCV agrupado: {p['tabela_origem']}")
        return StepResult(True, "PROCV agrupado executado.")

    def _op_esquerda(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.esquerda(df, p["coluna"], p["n"], p.get("nova_coluna"))
        self.context.set_data(df, f"ESQUERDA: {p['coluna']}")
        return StepResult(True, f"ESQUERDA em '{p['coluna']}'.")

    def _op_direita(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.direita(df, p["coluna"], p["n"], p.get("nova_coluna"))
        self.context.set_data(df, f"DIREITA: {p['coluna']}")
        return StepResult(True, f"DIREITA em '{p['coluna']}'.")

    def _op_meio(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.meio(df, p["coluna"], p["inicio"], p["n"], p.get("nova_coluna"))
        self.context.set_data(df, f"MEIO: {p['coluna']}")
        return StepResult(True, f"MEIO em '{p['coluna']}'.")

    def _op_tamanho(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.tamanho(df, p["coluna"], p.get("nova_coluna"))
        self.context.set_data(df, f"TAMANHO: {p['coluna']}")
        return StepResult(True, f"TAMANHO de '{p['coluna']}'.")

    def _op_concatenar(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.concatenar(df, p["colunas"], p.get("separador", ""), p.get("nova_coluna", "concat"))
        self.context.set_data(df, f"CONCATENAR: {p['colunas']}")
        return StepResult(True, "Colunas concatenadas.")

    def _op_substituir_texto(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.substituir_texto(df, p["coluna"], p["antigo"], p["novo"], p.get("nova_coluna"))
        self.context.set_data(df, f"SUBST: {p['coluna']}")
        return StepResult(True, f"Texto substituido em '{p['coluna']}'.")

    def _op_corresp(self, p: dict) -> StepResult:
        df = self.context.get_data()
        pos = self._engine.corresp(df, p["valor"], p["coluna_busca"])
        return StepResult(True, f"CORRESP: {len(pos)} ocorrencia(s).", {"posicoes": pos.tolist()})

    def _op_se(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.se(df, p["condicao"], p["valor_verdadeiro"], p["valor_falso"], p.get("nova_coluna", "resultado_se"))
        self.context.set_data(df, f"SE: {p['condicao']}")
        return StepResult(True, "SE aplicado.")

    def _op_cont_se(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.cont_se(df, p["coluna"], p["criterio"])
        return StepResult(True, f"CONT.SE = {r}", {"resultado": r})

    def _op_somase(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.somase(df, p["coluna_valores"], p["coluna_criterios"], p["criterio"])
        return StepResult(True, f"SOMASE = {r:.2f}", {"resultado": r})

    def _op_arred(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.arred(df, p["coluna"], p.get("casas", 0), p.get("nova_coluna"))
        self.context.set_data(df, f"ARRED: {p['coluna']}")
        return StepResult(True, f"ARRED em '{p['coluna']}'.")

    def _op_coluna_calculada(self, p: dict) -> StepResult:
        df = self.context.get_data()
        try:
            escopo = {col: df[col] for col in df.columns}
            escopo["np"] = np
            escopo["pd"] = pd
            resultado = eval(p["expressao"], {"__builtins__": {}}, escopo)
            df[p["nome"]] = resultado
            self.context.set_data(df, f"Calculada: '{p['nome']}'")
            return StepResult(True, f"Coluna '{p['nome']}' criada.")
        except Exception as e:
            return StepResult(False, f"Erro na expressao: {e}")

    def _op_indice(self, p: dict) -> StepResult:
        df = self.context.get_data()
        valor = self._engine.indice(df, p["coluna"], p["posicao"])
        return StepResult(True, f"INDICE = {valor}", {"resultado": valor})

    def _op_valor(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.valor(df, p["coluna"], p.get("nova_coluna"))
        self.context.set_data(df, f"VALOR: {p['coluna']}")
        return StepResult(True, f"VALOR em '{p['coluna']}'.")

    def _op_maximo(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.maximo(df, p["coluna"])
        return StepResult(True, f"MAX = {r}", {"resultado": r})

    def _op_minimo(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.minimo(df, p["coluna"])
        return StepResult(True, f"MIN = {r}", {"resultado": r})

    def _op_media(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.media(df, p["coluna"])
        return StepResult(True, f"MEDIA = {r:.2f}", {"resultado": r})

    def _op_soma(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.soma(df, p["coluna"])
        return StepResult(True, f"SOMA = {r:.2f}", {"resultado": r})

    def _op_harmonica(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.harmonica(df, p["coluna"])
        return StepResult(True, f"MEDIA HARMONICA = {r:.4f}", {"resultado": r})

    def _op_correl(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.correl(df, p["col_a"], p["col_b"], p.get("metodo", "pearson"))
        return StepResult(True, f"CORREL({p.get('metodo','pearson')}) = {r:.4f}", {"resultado": r})

    def _op_pearson(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.pearson(df, p["col_a"], p["col_b"])
        return StepResult(True, f"PEARSON = {r:.4f}", {"resultado": r})

    def _op_spearman(self, p: dict) -> StepResult:
        df = self.context.get_data()
        r = self._engine.spearman(df, p["col_a"], p["col_b"])
        return StepResult(True, f"SPERMAN = {r:.4f}", {"resultado": r})

    def _op_indice_corresp(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df = self._engine.indice_corresp(
            df, p["coluna_retorno"], p["valor_procurado"], p["coluna_busca"]
        )
        self.context.set_data(df, f"INDICE+CORRESP: {p['coluna_retorno']}")
        return StepResult(True, f"INDICE+CORRESP em '{p['coluna_retorno']}'.")

    # ── JOIN / AGREGACAO ───────────────────────────────────────────────────

    def _op_juntar(self, p: dict) -> StepResult:
        df = self.context.get_data()
        df_ref = self.context.get_tabela(p["tabela"])
        if df_ref.empty:
            return StepResult(False, f"Tabela '{p['tabela']}' nao encontrada.")

        # Usa DuckDB para bases grandes se disponivel
        duckdb = self.context.duckdb_engine
        if duckdb and duckdb.disponivel and len(df) >= 50_000:
            df = duckdb.juntar(df, df_ref, on=p["coluna_chave"], tipo=p.get("tipo", "left"))
        else:
            df = pd.merge(df, df_ref, on=p["coluna_chave"], how=p.get("tipo", "left"))

        self.context.set_data(df, f"JOIN: {p['tabela']}")
        return StepResult(True, f"JOIN com '{p['tabela']}'.")

    def _op_agregar(self, p: dict) -> StepResult:
        df = self.context.get_data()

        # Usa DuckDB para bases grandes se disponivel
        duckdb = self.context.duckdb_engine
        if duckdb and duckdb.disponivel and len(df) >= 100_000:
            df = duckdb.agregar(df, p["colunas_grupo"], p["coluna_alvo"], p.get("funcao", "sum"))
        else:
            df = df.groupby(p["colunas_grupo"], as_index=False).agg({p["coluna_alvo"]: p.get("funcao", "sum")})

        self.context.set_data(df, f"Agregacao: {p['colunas_grupo']}")
        return StepResult(True, f"Agregacao: {len(df)} grupos.")

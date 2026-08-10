"""
Regras de limpeza baseadas em regras: formato de numeros, deteccao de
duplicatas inteligente, e fuzzy matching para valores similares.

Design: cada regra e uma funcao pura (recebe DataFrame, retorna DataFrame + metadata).
Nenhuma regra depende de estado externo — facilita testes e composicao.
"""

import re
import pandas as pd
import numpy as np


class CleaningRules:
    """Motor de regras de limpeza. Operacoes puras, sem estado."""

    def __init__(self, logger=None):
        self.logger = logger
        self.log_buffer = []

    def _log(self, msg: str):
        self.log_buffer.append(msg)
        if self.logger:
            self.logger.info(msg)

    def flush_log(self) -> list:
        logs = list(self.log_buffer)
        self.log_buffer.clear()
        return logs

    # ── NUMEROS ────────────────────────────────────────────────────────────

    def formatar_brasileiro(self, df: pd.DataFrame, colunas: list,
                           casas: int = 2) -> pd.DataFrame:
        """
        Converte colunas numericas para formato brasileiro: virgula como
        separador decimal, ponto como separador de milhar.
        Exemplos: 1234567.89 -> 1.234.567,89 | "1.234,56" -> 1234.56 (interno)
        """
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"[FORMATO] Coluna '{col}' nao encontrada.")
                continue

            serie = df[col]

            if serie.dtype == object:
                serie = self._parse_brasileiro_para_float(serie)

            serie = pd.to_numeric(serie, errors="coerce")
            serie = serie.round(casas)

            df[col] = serie.apply(
                lambda x: self._float_para_brasileiro(x, casas) if pd.notna(x) else x
            )
            self._log(f"[FORMATO] '{col}': formato brasileiro, {casas} casas decimais.")
        return df

    def formatar_numero_interno(self, df: pd.DataFrame, colunas: list,
                                casas: int = 2) -> pd.DataFrame:
        """
        Converte para float interno (pandas) — util quando a coluna veio
        como texto brasileiro ("1.234,56") e precisa virar numero de verdade.
        """
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"[NUMERO] Coluna '{col}' nao encontrada.")
                continue
            serie = df[col]
            if serie.dtype == object:
                serie = self._parse_brasileiro_para_float(serie)
            df[col] = pd.to_numeric(serie, errors="coerce").round(casas)
            self._log(f"[NUMERO] '{col}': convertido para numero (float, {casas} casas).")
        return df

    @staticmethod
    def _parse_brasileiro_para_float(serie: pd.Series) -> pd.Series:
        """
        Converte strings brasileiras para float.
        "1.234,56" -> 1234.56 | "1234,56" -> 1234.56 | "1234.56" -> 1234.56
        """
        def _converter(valor):
            if pd.isna(valor) or valor == "":
                return np.nan
            s = str(valor).strip()
            if not s:
                return np.nan
            s = s.replace(" ", "")
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return np.nan
        return serie.apply(_converter)

    @staticmethod
    def _float_para_brasileiro(valor: float, casas: int) -> str:
        """1234.56 -> '1.234,56'"""
        if pd.isna(valor):
            return ""
        texto = f"{valor:,.{casas}f}"
        texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
        return texto

    # ── DUPLICATAS ─────────────────────────────────────────────────────────

    def detectar_duplicatas(self, df: pd.DataFrame, colunas: list = None,
                            normalizar: bool = True) -> pd.DataFrame:
        """
        Detecta linhas duplicadas (ou quasi-duplicatas por colunas especificas).
        Retorna DataFrame com coluna auxiliar '_duplicata' (True/False).
        Se normalizar=True, compara versoes normalizadas (lower, strip).
        """
        df = df.copy()
        colunas_comp = colunas or list(df.columns)

        if normalizar:
            comparacao = df[colunas_comp].apply(
                lambda c: c.astype(str).str.strip().str.lower() if c.dtype == object else c
            )
        else:
            comparacao = df[colunas_comp]

        df["_duplicata"] = comparacao.duplicated(keep="first")
        dup_count = df["_duplicata"].sum()
        self._log(f"[DUPLICATAS] {dup_count} linhas marcadas como duplicatas (de {len(df)}).")
        return df

    def remover_duplicatas(self, df: pd.DataFrame, colunas: list = None,
                           normalizar: bool = True) -> pd.DataFrame:
        """Remove duplicatas diretamente (sem coluna auxiliar)."""
        df = df.copy()
        colunas_comp = colunas or list(df.columns)

        total_antes = len(df)
        if normalizar:
            comparacao = df[colunas_comp].apply(
                lambda c: c.astype(str).str.strip().str.lower() if c.dtype == object else c
            )
            df = df[~comparacao.duplicated(keep="first")].reset_index(drop=True)
        else:
            df = df.drop_duplicates(subset=colunas_comp, keep="first").reset_index(drop=True)

        removidas = total_antes - len(df)
        self._log(f"[DUPLICATAS] {removidas} duplicatas removidas (de {total_antes}).")
        return df

    # ── FUZZY MATCHING ─────────────────────────────────────────────────────

    def encontrar_valores_similares(self, df: pd.DataFrame, coluna: str,
                                    limiar: float = 0.85) -> list:
        """
        Encontra pares de valores na coluna que sao parecidos mas nao iguais
        (erros de digitacao, acentos, abreviacoes).
        Retorna lista de dicts: [{"valor_a": ..., "valor_b": ..., "similaridade": ...}]
        """
        if coluna not in df.columns:
            self._log(f"[FUZZY] Coluna '{coluna}' nao encontrada.")
            return []

        valores = df[coluna].dropna().astype(str).str.strip().str.upper().unique()
        if len(valores) < 2:
            return []

        pares = []
        for i in range(len(valores)):
            for j in range(i + 1, len(valores)):
                a, b = valores[i], valores[j]
                sim = self._calcular_similaridade(a, b)
                if sim >= limiar and sim < 1.0:
                    pares.append({"valor_a": a, "valor_b": b, "similaridade": round(sim, 3)})

        pares.sort(key=lambda x: x["similaridade"], reverse=True)
        self._log(
            f"[FUZZY] Coluna '{coluna}': {len(pares)} pares similares encontrados "
            f"(limiar={limiar})."
        )
        return pares

    def sugerir_unificacao(self, df: pd.DataFrame, coluna: str,
                           limiar: float = 0.85) -> dict:
        """
        Detecta grupos de valores similares e sugere unificacao.
        Retorna: {"valor_principal": ["variante1", "variante2", ...], ...}
        """
        if coluna not in df.columns:
            return {}

        valores = df[coluna].dropna().astype(str).str.strip().str.upper().unique()
        if len(valores) < 2:
            return {}

        # Union-Find simples para agrupar valores similares
        pai = {v: v for v in valores}

        def encontrar(x):
            while pai[x] != x:
                pai[x] = pai[pai[x]]
                x = pai[x]
            return x

        def unir(x, y):
            rx, ry = encontrar(x), encontrar(y)
            if rx != ry:
                pai[rx] = ry

        for i in range(len(valores)):
            for j in range(i + 1, len(valores)):
                a, b = valores[i], valores[j]
                sim = self._calcular_similaridade(a, b)
                if sim >= limiar:
                    unir(a, b)

        # Agrupar por raiz
        grupos = {}
        for v in valores:
            raiz = encontrar(v)
            if raiz not in grupos:
                grupos[raiz] = []
            grupos[raiz].append(v)

        # Filtrar: so grupos com mais de 1 variante
        sugestoes = {k: sorted(v) for k, v in grupos.items() if len(v) > 1}

        if sugestoes:
            self._log(
                f"[FUZZY] Coluna '{coluna}': {len(sugestoes)} grupo(s) de valores "
                f"similares para unificar."
            )
        return sugestoes

    def unificar_valores(self, df: pd.DataFrame, coluna: str,
                         mapeamento: dict) -> pd.DataFrame:
        """
        Aplica unificacao: mapeamento = {"CORRETO": ["ERRADO1", "ERRADO2"]}
        """
        df = df.copy()
        if coluna not in df.columns:
            self._log(f"[FUZZY] Coluna '{coluna}' nao encontrada.")
            return df

        total_trocas = 0
        for correto, variantes in mapeamento.items():
            for variante in variantes:
                mask = df[coluna].astype(str).str.strip().str.upper() == variante.strip().upper()
                count = mask.sum()
                df.loc[mask, coluna] = correto
                total_trocas += count

        self._log(f"[FUZZY] '{coluna}': {total_trocas} valores unificados.")
        return df

    @staticmethod
    def _calcular_similaridade(a: str, b: str) -> float:
        """
        Similaridade baseada em bigramas (Levenshtein simplificado).
        Rapido o suficiente para milhares de valores unicos.
        """
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        def bigramas(s):
            return [s[i:i+2] for i in range(len(s) - 1)]

        bg_a = bigramas(a)
        bg_b = bigramas(b)

        if not bg_a or not bg_b:
            return 1.0 if a in b or b in a else 0.0

        intersecao = sum(1 for bg in bg_a if bg in bg_b)
        total = len(bg_a) + len(bg_b)
        return (2.0 * intersecao) / total if total > 0 else 0.0

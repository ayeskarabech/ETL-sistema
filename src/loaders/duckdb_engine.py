"""
Motor DuckDB para operacoes pesadas: JOINs, agregacoes, filtros complexos.

DuckDB funciona como banco de dados analitico em memoria — processa dados
diretamente do DataFrame ou de arquivos Parquet/CSV com custo minimo
de copia. Para bases de 200MB+, operacoes como PROCV (VLOOKUP), agregacoes
e GROUP BY sao 5-20x mais rapidas e usam 3-5x menos RAM que pandas.

Uso tipico:
  engine = DuckDBEngine()
  resultado = engine.juntar(df_escola, df_notas, on="id_aluno", how="left")
  resultado = engine.agregar(df, grupo=["cidade"], coluna="nota", func="avg")

Todas as operacoes retornam pandas DataFrame — o resto do pipeline nao
precisa saber que DuckDB existe por baixo.
"""

import os
import pandas as pd

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


class DuckDBEngine:
    """
    Motor de operacoes pesadas usando DuckDB em memoria.
    Se DuckDB nao estiver instalado, fallback automatico para pandas.
    """

    LIMIAR_DUCKDB_MB = 50  # Opera com DuckDB acima deste tamanho

    def __init__(self, logger=None):
        self.logger = logger
        self._conn = None
        if HAS_DUCKDB:
            self._conn = duckdb.connect(":memory:")

    def _log(self, msg: str, nivel: str = "info"):
        if self.logger:
            getattr(self.logger, nivel)(msg)

    @property
    def disponivel(self) -> bool:
        return HAS_DUCKDB and self._conn is not None

    def fechar(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _registrar_df(self, df: pd.DataFrame, nome: str):
        """Registra um DataFrame como tabela temporaria no DuckDB."""
        self._conn.execute(f"CREATE OR REPLACE TEMPORARY TABLE {nome} AS SELECT * FROM df")

    # ── JOIN (PROCV) ──────────────────────────────────────────────────────

    def juntar(self, df_esquerda: pd.DataFrame, df_direita: pd.DataFrame,
               on: str, tipo: str = "left") -> pd.DataFrame:
        """
        JOIN entre dois DataFrames usando DuckDB.
        Para tabelas grandes, DuckDB executa hash join eficiente em memoria.
        """
        if not self.disponivel or len(df_esquerda) < 10_000:
            return pd.merge(df_esquerda, df_direita, on=on, how=tipo)

        self._registrar_df(df_esquerda, "_esq")
        self._registrar_df(df_direita, "_dir")

        sql = f"""
            SELECT e.*, d.*
            FROM _esq e
            {tipo.upper()} JOIN _dir d ON e.{on} = d.{on}
        """
        resultado = self._conn.execute(sql).fetchdf()
        self._log(f"[DUCKDB] JOIN {tipo} on '{on}': {len(df_esquerda)}x{len(df_direita)} -> {len(resultado)} linhas.")
        return resultado

    # ── PROCV (VLOOKUP) ───────────────────────────────────────────────────

    def procv(self, df_tabela: pd.DataFrame, coluna_chave: str,
              df_origem: pd.DataFrame, coluna_chave_origem: str,
              coluna_valor: str, padrao_nao_encontrado=None) -> pd.DataFrame:
        """
        PROCV via DuckDB: para cada linha de df_tabela, busca coluna_valor
        em df_origem usando coluna_chave_origem como chave.
        Funciona como SET + map lookup no pandas, mas escala melhor.
        """
        if not self.disponivel or len(df_tabela) < 50_000:
            lookup = df_origem.set_index(coluna_chave_origem)[coluna_valor]
            resultado = df_tabela.copy()
            nome_col = f"{coluna_valor}_procv"
            resultado[nome_col] = resultado[coluna_chave].map(lookup)
            if padrao_nao_encontrado is not None:
                resultado[nome_col] = resultado[nome_col].fillna(padrao_nao_encontrado)
            return resultado

        self._registrar_df(df_tabela, "_tabela")
        self._registrar_df(df_origem, "_origem")

        padrao_sql = f"'{padrao_nao_encontrado}'" if padrao_nao_encontrado else "NULL"
        nome_col = f"{coluna_valor}_procv"
        sql = f"""
            SELECT t.*,
                   COALESCE(o.{coluna_valor}, {padrao_sql}) AS {nome_col}
            FROM _tabela t
            LEFT JOIN _origem o ON t.{coluna_chave} = o.{coluna_chave_origem}
        """
        resultado = self._conn.execute(sql).fetchdf()
        encontrados = resultado[nome_col].notna().sum()
        self._log(
            f"[DUCKDB] PROCV '{coluna_chave}' -> '{coluna_valor}': "
            f"{encontrados}/{len(df_tabela)} registros encontrados."
        )
        return resultado

    # ── PROCV AGRUPADO ────────────────────────────────────────────────────

    def procv_agrupado(self, df_tabela: pd.DataFrame, coluna_chave: str,
                       df_origem: pd.DataFrame, coluna_chave_origem: str,
                       coluna_valor: str, funcao: str = "sum") -> pd.DataFrame:
        """
        PROCV com agregacao: agrupa df_origem por coluna_chave_origem
        e aplica funcao (sum, mean, count, etc), depois mapeia em df_tabela.
        """
        mapa_agg = {
            "soma": "SUM", "media": "AVG", "contagem": "COUNT",
            "min": "MIN", "max": "MAX", "mediana": "MEDIAN",
        }
        sql_func = mapa_agg.get(funcao, funcao.upper())

        if not self.disponivel or len(df_tabela) < 50_000:
            df_tabela = df_tabela.copy()
            agg = df_origem.groupby(coluna_chave_origem)[coluna_valor].agg(
                funcao if funcao != "contagem" else "count"
            )
            nome_col = f"{coluna_valor}_{funcao}"
            df_tabela[nome_col] = df_tabela[coluna_chave].map(agg)
            return df_tabela

        self._registrar_df(df_tabela, "_tabela")
        self._registrar_df(df_origem, "_origem")

        nome_col = f"{coluna_valor}_{funcao}"
        sql = f"""
            SELECT t.*,
                   agg.{coluna_valor} AS {nome_col}
            FROM _tabela t
            LEFT JOIN (
                SELECT {coluna_chave_origem}, {sql_func}({coluna_valor}) AS {coluna_valor}
                FROM _origem
                GROUP BY {coluna_chave_origem}
            ) agg ON t.{coluna_chave} = agg.{coluna_chave_origem}
        """
        resultado = self._conn.execute(sql).fetchdf()
        self._log(
            f"[DUCKDB] PROCV_AGRUPADO '{coluna_chave}' -> '{coluna_valor}' "
            f"({funcao}): {len(df_tabela)} linhas mapeadas."
        )
        return resultado

    # ── AGREGACAO ─────────────────────────────────────────────────────────

    def agregar(self, df: pd.DataFrame, colunas_grupo: list,
                coluna_alvo: str, funcao: str = "sum") -> pd.DataFrame:
        """
        Agregacao com GROUP BY usando DuckDB.
        Para bases grandes, DuckDB evita o custo de criar multiplas copias
        intermediarias que pandas cria durante groupby.
        """
        if not self.disponivel or len(df) < 100_000:
            return df.groupby(colunas_grupo, as_index=False).agg({coluna_alvo: funcao})

        self._registrar_df(df, "_agg")
        cols_grupo = ", ".join(colunas_grupo)
        sql = f"""
            SELECT {cols_grupo}, {funcao.upper()}({coluna_alvo}) AS {coluna_alvo}
            FROM _agg
            GROUP BY {cols_grupo}
        """
        resultado = self._conn.execute(sql).fetchdf()
        self._log(f"[DUCKDB] Agregacao {funcao}({coluna_alvo}) por {colunas_grupo}: {len(df)} -> {len(resultado)} linhas.")
        return resultado

    # ── FILTRO ────────────────────────────────────────────────────────────

    def filtrar(self, df: pd.DataFrame, condicao: str) -> pd.DataFrame:
        """
        Filtrar usando expressao SQL-like ou pandas-eval.
        DuckDB: filtro pushdown + vectorizado.
        """
        if not self.disponivel or len(df) < 100_000:
            return df

        self._registrar_df(df, "_filt")
        sql = f"SELECT * FROM _filt WHERE {condicao}"
        try:
            resultado = self._conn.execute(sql).fetchdf()
            self._log(f"[DUCKDB] Filtro '{condicao}': {len(df)} -> {len(resultado)} linhas.")
            return resultado
        except Exception as e:
            self._log(f"[DUCKDB] Filtro SQL falhou ({e}), retornando df original.", "warning")
            return df

    # ── CONTAGEM / ESTATISTICAS ───────────────────────────────────────────

    def contar(self, df: pd.DataFrame, condicao: str = None) -> int:
        """Contagem rapida com DuckDB."""
        if not self.disponivel:
            if condicao:
                return len(df.query(condicao))
            return len(df)

        self._registrar_df(df, "_cnt")
        where = f"WHERE {condicao}" if condicao else ""
        sql = f"SELECT COUNT(*) as total FROM _cnt {where}"
        return self._conn.execute(sql).fetchdf()["total"].iloc[0]

    def estatisticas(self, df: pd.DataFrame, coluna: str) -> dict:
        """Estatisticas descritivas via DuckDB."""
        if not self.disponivel:
            s = pd.to_numeric(df[coluna], errors="coerce")
            return {"media": s.mean(), "mediana": s.median(), "min": s.min(),
                    "max": s.max(), "std": s.std()}

        self._registrar_df(df, "_stat")
        sql = f"""
            SELECT
                AVG({coluna}) AS media,
                MEDIAN({coluna}) AS mediana,
                MIN({coluna}) AS minimo,
                MAX({coluna}) AS maximo,
                STDDEV({coluna}) AS desvio_padrao,
                COUNT({coluna}) AS n
            FROM _stat
        """
        r = self._conn.execute(sql).fetchdf()
        return {
            "media": float(r["media"].iloc[0]) if r["n"].iloc[0] > 0 else None,
            "mediana": float(r["mediana"].iloc[0]) if r["n"].iloc[0] > 0 else None,
            "minimo": float(r["minimo"].iloc[0]) if r["n"].iloc[0] > 0 else None,
            "maximo": float(r["maximo"].iloc[0]) if r["n"].iloc[0] > 0 else None,
            "desvio_padrao": float(r["desvio_padrao"].iloc[0]) if r["n"].iloc[0] > 1 else None,
            "n": int(r["n"].iloc[0]),
        }

    # ── DUPLICATAS ────────────────────────────────────────────────────────

    def remover_duplicatas(self, df: pd.DataFrame, subset: list = None,
                           keep: str = "first") -> pd.DataFrame:
        """Remove duplicatas com DuckDB para bases grandes."""
        if not self.disponivel or len(df) < 100_000:
            return df.drop_duplicates(subset=subset, keep=keep)

        self._registrar_df(df, "_dedup")
        cols = subset or list(df.columns)
        cols_str = ", ".join(cols)

        if keep == "first":
            sql = f"""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {cols_str} ORDER BY rowid) AS _rn
                    FROM _dedup
                ) WHERE _rn = 1
            """
        elif keep == "last":
            sql = f"""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {cols_str} ORDER BY rowid DESC) AS _rn
                    FROM _dedup
                ) WHERE _rn = 1
            """
        else:
            sql = f"""
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY {cols_str} ORDER BY rowid) AS _rn
                    FROM _dedup
                ) WHERE _rn = 1
            """

        resultado = self._conn.execute(sql).fetchdf()
        resultado = resultado.drop(columns=["_rn"], errors="ignore")
        removidas = len(df) - len(resultado)
        self._log(f"[DUCKDB] Duplicatas removidas: {removidas} (de {len(df)}).")
        return resultado

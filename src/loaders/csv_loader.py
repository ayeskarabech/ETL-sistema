"""
Carregamento de arquivos CSV.

Regras de negócio:
  - Bases governamentais brasileiras costumam vir em encoding Latin-1/CP1252
    (não UTF-8) e usar ';' como separador — detecta automaticamente.
  - Usa polars para leitura eficiente em memória (5-10x menos RAM que pandas),
    depois converte para pandas pois o resto do pipeline depende dele.
  - Nunca altera o arquivo original — toda transformação acontece em memória.
"""

import os
import pandas as pd
import polars as pl

COMBINACOES_TESTADAS = [
    {"encoding": "utf-8", "separator": ";"},
    {"encoding": "utf-8", "separator": ","},
    {"encoding": "latin-1", "separator": ";"},
    {"encoding": "cp1252", "separator": ";"},
    {"encoding": "latin-1", "separator": ","},
]

COMBINACOES_PANDAS = [
    {"encoding": "utf-8", "sep": ";"},
    {"encoding": "utf-8", "sep": ","},
    {"encoding": "latin-1", "sep": ";"},
    {"encoding": "cp1252", "sep": ";"},
    {"encoding": "latin-1", "sep": ","},
]


class CSVLoader:

    def __init__(self, caminho_arquivo: str, logger=None):
        if not os.path.exists(caminho_arquivo):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho_arquivo}")
        self.caminho_arquivo = caminho_arquivo
        self.logger = logger
        self.combo_detectado = None

    def _log(self, mensagem: str, nivel: str = "info"):
        if self.logger:
            getattr(self.logger, nivel)(mensagem)
        else:
            print(mensagem)

    def detectar_formato(self) -> dict:
        """Testa combinações de encoding/separador nas primeiras linhas."""
        for combo in COMBINACOES_PANDAS:
            try:
                pd.read_csv(self.caminho_arquivo, nrows=5, **combo)
                self.combo_detectado = combo
                self._log(f"Formato detectado para '{os.path.basename(self.caminho_arquivo)}': {combo}")
                return combo
            except Exception:
                continue
        raise ValueError(
            f"Nao foi possivel detectar encoding/separador de '{os.path.basename(self.caminho_arquivo)}'. "
            "Verifique o arquivo manualmente."
        )

    def carregar(self, colunas: list = None, tipos: dict = None) -> pd.DataFrame:
        """
        Carrega CSV usando polars (eficiente em memoria) e converte para pandas.
        Para 250MB de CSV, polars usa ~80MB RAM vs pandas que usa ~800MB+.
        """
        if self.combo_detectado is None:
            self.detectar_formato()

        tamanho_mb = os.path.getsize(self.caminho_arquivo) / (1024 * 1024)
        encoding = self.combo_detectado["encoding"]
        separator = self.combo_detectado["sep"]

        self._log(f"Carregando '{os.path.basename(self.caminho_arquivo)}' ({tamanho_mb:.1f}MB) com polars...")

        try:
            df = self._carregar_polars(encoding, separator, colunas, tipos)
        except Exception as e_polars:
            self._log(f"Polars falhou ({e_polars}), tentando com pandas...", "warning")
            df = self._carregar_pandas(colunas, tipos)

        colunas_com_espaco = [c for c in df.columns if c != c.strip()]
        if colunas_com_espaco:
            self._log(f"Colunas com espaco extra corrigidas: {colunas_com_espaco}")
        df.columns = [c.strip() for c in df.columns]

        self._log(f"Carregado: {len(df)} linhas, {len(df.columns)} colunas.")
        return df

    def _carregar_polars(self, encoding: str, separator: str, colunas: list, tipos: dict) -> pd.DataFrame:
        """Le CSV com polars (muito mais eficiente em memoria) e converte para pandas."""
        kwargs = {"encoding": encoding, "separator": separator, "truncate_ragged_lines": True}

        if colunas:
            df_pl = pl.read_csv(self.caminho_arquivo, **kwargs, columns=colunas)
        else:
            df_pl = pl.read_csv(self.caminho_arquivo, **kwargs)

        if tipos:
            casting = {}
            for col, tipo in tipos.items():
                if col in df_pl.columns:
                    if tipo == "numero":
                        casting[col] = pl.Float64
                    elif tipo == "texto":
                        casting[col] = pl.Utf8
                    elif tipo == "data":
                        casting[col] = pl.Utf8
            if casting:
                df_pl = df_pl.cast(casting)

        df_pd = df_pl.to_pandas()
        return df_pd

    def _carregar_pandas(self, colunas: list, tipos: dict) -> pd.DataFrame:
        """Fallback: leitura direta com pandas."""
        kwargs = dict(self.combo_detectado)
        if colunas:
            kwargs["usecols"] = colunas
        if tipos:
            kwargs["dtype"] = tipos

        tamanho_mb = os.path.getsize(self.caminho_arquivo) / (1024 * 1024)

        if tamanho_mb < 50:
            return pd.read_csv(self.caminho_arquivo, **kwargs)
        else:
            pedacos = []
            for pedaco in pd.read_csv(self.caminho_arquivo, chunksize=100_000, **kwargs):
                pedacos.append(pedaco)
            df = pd.concat(pedacos, ignore_index=True)
            del pedacos
            return df

    def listar_colunas(self) -> list:
        """Le so o cabecalho, sem carregar o arquivo inteiro."""
        if self.combo_detectado is None:
            self.detectar_formato()
        df_cabecalho = pd.read_csv(self.caminho_arquivo, nrows=0, **self.combo_detectado)
        return [c.strip() for c in df_cabecalho.columns]

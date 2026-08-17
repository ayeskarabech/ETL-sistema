"""
Carregamento de arquivos CSV.

Regras de negocio:
  - Bases governamentais brasileiras costumam vir em encoding Latin-1/CP1252
    (nao UTF-8) e usar ';' como separador -- detecta automaticamente.
  - Usa polars para leitura eficiente em memoria (5-10x menos RAM que pandas),
    depois converte para pandas pois o resto do pipeline depende dele.
  - Para arquivos >100MB, usa leitura em chunks e salva como Parquet
    intermediario para re-leituras subsequentes serem instantaneas.
  - Nunca altera o arquivo original -- toda transformacao acontece em memoria.
"""

import os
import pandas as pd
import polars as pl

try:
    from .parquet_handler import ParquetHandler
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False

COMBINACOES_PANDAS = [
    {"encoding": "utf-8", "sep": ";"},
    {"encoding": "utf-8", "sep": ","},
    {"encoding": "latin-1", "sep": ";"},
    {"encoding": "cp1252", "sep": ";"},
    {"encoding": "latin-1", "sep": ","},
]


class CSVLoader:

    TAMANHO_PARQUET_MB = 100  # Acima deste tamanho, salva como Parquet intermediario
    CHUNKSIZE_POLARS = 500_000  # Linhas por chunk na leitura polars

    def __init__(self, caminho_arquivo: str, logger=None):
        if not os.path.exists(caminho_arquivo):
            raise FileNotFoundError(f"Arquivo nao encontrado: {caminho_arquivo}")
        self.caminho_arquivo = caminho_arquivo
        self.logger = logger
        self.combo_detectado = None
        self._parquet_handler = ParquetHandler(logger) if HAS_PARQUET else None

    def _log(self, mensagem: str, nivel: str = "info"):
        if self.logger:
            getattr(self.logger, nivel)(mensagem)
        else:
            print(mensagem)

    def detectar_formato(self) -> dict:
        """Testa combinacoes de encoding/separador nas primeiras linhas."""
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
        Carrega CSV com otimizacao de memoria:
        - Arquivos <50MB: leitura direta com polars
        - Arquivos 50-100MB: leitura polars direta (ja eficiente)
        - Arquivos >100MB: salva como Parquet intermediario, depois re-le
          (reduz RAM em 3-5x em re-leituras e acelera carregamentos futuros)
        """
        if self.combo_detectado is None:
            self.detectar_formato()

        tamanho_mb = os.path.getsize(self.caminho_arquivo) / (1024 * 1024)
        encoding = self.combo_detectado["encoding"]
        separator = self.combo_detectado["sep"]

        # Verifica se existe Parquet intermediario mais recente
        caminho_parquet = self._caminho_parquet_cache()
        if self._parquet_handler and os.path.exists(caminho_parquet):
            if os.path.getmtime(caminho_parquet) >= os.path.getmtime(self.caminho_arquivo):
                self._log(f"Carregando de cache Parquet: {os.path.basename(caminho_parquet)}")
                df = self._parquet_handler.carregar(caminho_parquet, colunas=colunas)
                df = self._aplicar_tipos(df, tipos)
                df.columns = [c.strip() for c in df.columns]
                self._log(f"Carregado do cache: {len(df)} linhas, {len(df.columns)} colunas.")
                return df

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

        # Salva Parquet intermediario para re-leituras rapidas
        if self._parquet_handler and tamanho_mb >= self.TAMANHO_PARQUET_MB:
            self._log(f"Salvando cache Parquet para re-leituras futuras...")
            self._parquet_handler.salvar(df, caminho_parquet)

        self._log(f"Carregado: {len(df)} linhas, {len(df.columns)} colunas.")
        return df

    def carregar_pedacos(self, chunksize: int = 100_000):
        """
        Generator que retorna chunks do CSV um por vez.
        Para bases de 200-300MB, processa ~100k linhas por vez.
        Ideal para operacoes que nao precisam de todo o dado na RAM.
        """
        if self.combo_detectado is None:
            self.detectar_formato()

        encoding = self.combo_detectado["encoding"]
        separator = self.combo_detectado["sep"]

        for pedaco in pd.read_csv(
            self.caminho_arquivo,
            chunksize=chunksize,
            encoding=encoding,
            sep=separator,
        ):
            pedaco.columns = [c.strip() for c in pedaco.columns]
            yield pedaco

    def _carregar_polars(self, encoding: str, separator: str, colunas: list, tipos: dict) -> pd.DataFrame:
        """Le CSV com polars (muito mais eficiente em memoria) e converte para pandas."""
        kwargs = {"encoding": encoding, "separator": separator, "truncate_ragged_lines": True}

        tamanho_mb = os.path.getsize(self.caminho_arquivo) / (1024 * 1024)

        if tamanho_mb < 100 or not HAS_PARQUET:
            # Leitura direta (ja eficiente com polars)
            if colunas:
                df_pl = pl.read_csv(self.caminho_arquivo, **kwargs, columns=colunas)
            else:
                df_pl = pl.read_csv(self.caminho_arquivo, **kwargs)
        else:
            # Leitura em chunks para arquivos grandes (polars streaming)
            chunks = []
            for i, chunk in enumerate(pl.read_csv_batched(
                self.caminho_arquivo,
                **kwargs,
                batch_size=self.CHUNKSIZE_POLARS,
            )):
                if colunas:
                    chunk = chunk.select(colunas)
                chunks.append(chunk)
                if (i + 1) % 10 == 0:
                    self._log(f"  ...processados {(i + 1) * self.CHUNKSIZE_POLARS:,} registros")
            df_pl = pl.concat(chunks)

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
        del df_pl
        return df_pd

    def _carregar_pandas(self, colunas: list, tipos: dict) -> pd.DataFrame:
        """Fallback: leitura direta com pandas otimizada."""
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

    def _aplicar_tipos(self, df: pd.DataFrame, tipos: dict) -> pd.DataFrame:
        """Aplica tipos de coluna apos leitura do Parquet."""
        if not tipos:
            return df
        for col, tipo in tipos.items():
            if col not in df.columns:
                continue
            if tipo == "numero":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif tipo == "texto":
                df[col] = df[col].astype(str)
            elif tipo == "data":
                df[col] = df[col].astype(str)
        return df

    def _caminho_parquet_cache(self) -> str:
        """Gera caminho para o arquivo Parquet de cache."""
        base = os.path.splitext(self.caminho_arquivo)[0]
        return f"{base}_cache.parquet"

    def limpar_cache(self):
        """Remove o arquivo Parquet intermediario."""
        caminho = self._caminho_parquet_cache()
        if os.path.exists(caminho):
            os.remove(caminho)
            self._log(f"Cache Parquet removido: {caminho}")

    def listar_colunas(self) -> list:
        """Le so o cabecalho, sem carregar o arquivo inteiro."""
        if self.combo_detectado is None:
            self.detectar_formato()
        df_cabecalho = pd.read_csv(self.caminho_arquivo, nrows=0, **self.combo_detectado)
        return [c.strip() for c in df_cabecalho.columns]

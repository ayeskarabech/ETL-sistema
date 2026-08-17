"""
Exportacao do resultado final, pronto para importar no Power BI.

Regras de negocio:
  - UTF-8 com BOM: garante que acentuacao abra corretamente no Power BI/Excel
    (sem o BOM, "Educacao" pode virar "EducaÃ§ao" ao importar).
  - Nomes de coluna em snake_case, sem espaco/acento: evita erro de referencia
    dentro do Power Query/DAX.
  - Nome do arquivo de saida inclui timestamp: nunca sobrescreve silenciosamente
    uma exportacao anterior sem querer.
  - Suporta exportacao em Parquet: compressao colunar 3-5x menor que CSV,
    tipos preservados, leitura seletiva possivel.
"""

import os
import re
import unicodedata
from datetime import datetime
import pandas as pd

try:
    from ..loaders.parquet_handler import ParquetHandler
    HAS_PARQUET = True
except ImportError:
    HAS_PARQUET = False


class PowerBIExporter:

    def __init__(self, pasta_saida: str, logger=None):
        self.pasta_saida = pasta_saida
        self.logger = logger
        os.makedirs(self.pasta_saida, exist_ok=True)
        self._parquet_handler = ParquetHandler(logger) if HAS_PARQUET else None

    def _log(self, mensagem: str):
        if self.logger:
            self.logger.info(mensagem)
        else:
            print(f"[EXPORT] {mensagem}")

    @staticmethod
    def _snake_case(nome_coluna: str) -> str:
        nome = str(nome_coluna).strip()
        nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("utf-8")
        nome = re.sub(r"[^\w\s]", "", nome)
        nome = re.sub(r"\s+", "_", nome)
        return nome.lower()

    def padronizar_nomes_coluna(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        mapeamento = {col: self._snake_case(col) for col in df.columns}
        df = df.rename(columns=mapeamento)
        self._log(f"Nomes de coluna padronizados para snake_case: {list(mapeamento.values())}")
        return df

    def exportar(self, df: pd.DataFrame, nome_base: str,
                 formato: str = "csv") -> str:
        """
        Exporta DataFrame no formato especificado.
        - formato: "csv" (default), "xlsx", "parquet"
        Retorna o caminho completo do arquivo gerado.
        """
        df_export = self.padronizar_nomes_coluna(df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        if formato == "parquet":
            return self._exportar_parquet(df_export, nome_base, timestamp)
        elif formato == "xlsx":
            return self._exportar_xlsx(df_export, nome_base, timestamp)
        else:
            return self._exportar_csv(df_export, nome_base, timestamp)

    def _exportar_csv(self, df: pd.DataFrame, nome_base: str, timestamp: str) -> str:
        """Exporta como CSV UTF-8 com BOM."""
        nome_arquivo = f"{nome_base}_{timestamp}.csv"
        caminho_completo = os.path.join(self.pasta_saida, nome_arquivo)
        df.to_csv(caminho_completo, index=False, encoding="utf-8-sig")
        self._log(f"Arquivo exportado: {caminho_completo} ({len(df)} linhas, {len(df.columns)} colunas).")
        return caminho_completo

    def _exportar_xlsx(self, df: pd.DataFrame, nome_base: str, timestamp: str) -> str:
        """Exporta como XLSX (Excel)."""
        nome_arquivo = f"{nome_base}_{timestamp}.xlsx"
        caminho_completo = os.path.join(self.pasta_saida, nome_arquivo)
        df.to_excel(caminho_completo, index=False, engine="openpyxl")
        self._log(f"Arquivo exportado: {caminho_completo} ({len(df)} linhas, {len(df.columns)} colunas).")
        return caminho_completo

    def _exportar_parquet(self, df: pd.DataFrame, nome_base: str, timestamp: str) -> str:
        """Exporta como Parquet (compressao colunar, 3-5x menor que CSV)."""
        if not self._parquet_handler:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        nome_arquivo = f"{nome_base}_{timestamp}.parquet"
        caminho_completo = os.path.join(self.pasta_saida, nome_arquivo)
        self._parquet_handler.salvar(df, caminho_completo)
        self._log(f"Arquivo exportado: {caminho_completo} ({len(df)} linhas, {len(df.columns)} colunas).")
        return caminho_completo

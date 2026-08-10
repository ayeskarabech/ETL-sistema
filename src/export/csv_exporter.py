"""
Exportação do resultado final, pronto para importar no Power BI.

Regras de negócio:
  - UTF-8 com BOM: garante que acentuação abra corretamente no Power BI/Excel
    (sem o BOM, "Educação" pode virar "EducaÃ§Ã£o" ao importar).
  - Nomes de coluna em snake_case, sem espaço/acento: evita erro de referência
    dentro do Power Query/DAX.
  - Nome do arquivo de saída inclui timestamp: nunca sobrescreve silenciosamente
    uma exportação anterior sem querer.
"""

import os
import re
import unicodedata
from datetime import datetime
import pandas as pd


class PowerBIExporter:

    def __init__(self, pasta_saida: str, logger=None):
        self.pasta_saida = pasta_saida
        self.logger = logger
        os.makedirs(self.pasta_saida, exist_ok=True)

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

    def exportar(self, df: pd.DataFrame, nome_base: str) -> str:
        """
        nome_base: nome descritivo do arquivo, sem extensão (ex: 'aprovacao_PE_2024').
        Retorna o caminho completo do arquivo gerado.
        """
        df_export = self.padronizar_nomes_coluna(df)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        nome_arquivo = f"{nome_base}_{timestamp}.csv"
        caminho_completo = os.path.join(self.pasta_saida, nome_arquivo)

        df_export.to_csv(caminho_completo, index=False, encoding="utf-8-sig")

        self._log(f"Arquivo exportado: {caminho_completo} ({len(df_export)} linhas, {len(df_export.columns)} colunas).")
        return caminho_completo

"""
Conversor de XLSX para CSV.
Suporta multiplos sheets, detecta automaticamente o melhor encoding,
e gera CSV pronto para o pipeline ETL.
"""

import os
import pandas as pd


class ExcelConverter:
    """Converte arquivos Excel (.xlsx) para CSV."""

    def __init__(self, logger=None):
        self.logger = logger

    def _log(self, msg: str):
        if self.logger:
            self.logger.info(msg)
        else:
            print(f"[CONVERSOR] {msg}")

    def listar_sheets(self, caminho_xlsx: str) -> list:
        """Lista todas as abas (sheets) do arquivo Excel."""
        try:
            xl = pd.ExcelFile(caminho_xlsx)
            sheets = xl.sheet_names
            self._log(f"Sheets encontradas: {sheets}")
            return sheets
        except Exception as e:
            self._log(f"ERRO ao ler abas: {e}")
            return []

    def converter(self, caminho_xlsx: str, pasta_saida: str,
                  sheet: str = 0, nome_saida: str = None,
                  casas_decimais: int = None) -> str:
        """
        Converte uma aba do Excel para CSV.
        Retorna o caminho do CSV gerado.
        """
        if not os.path.exists(caminho_xlsx):
            raise FileNotFoundError(f"Arquivo nao encontrado: {caminho_xlsx}")

        os.makedirs(pasta_saida, exist_ok=True)

        self._log(f"Lendo aba '{sheet}' de '{os.path.basename(caminho_xlsx)}'...")
        df = pd.read_excel(caminho_xlsx, sheet_name=sheet, engine="openpyxl")

        if casas_decimais is not None:
            for col in df.select_dtypes(include=["float"]).columns:
                df[col] = df[col].round(casas_decimais)

        if nome_saida is None:
            base = os.path.splitext(os.path.basename(caminho_xlsx))[0]
            nome_saida = f"{base}_convertido"

        caminho_csv = os.path.join(pasta_saida, f"{nome_saida}.csv")
        df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

        self._log(
            f"Convertido: {len(df)} linhas, {len(df.columns)} colunas -> {caminho_csv}"
        )
        return caminho_csv

    def converter_todas_sheets(self, caminho_xlsx: str, pasta_saida: str) -> list:
        """Converte todas as abas do Excel para CSVs separados."""
        sheets = self.listar_sheets(caminho_xlsx)
        caminhos = []
        for sheet in sheets:
            try:
                caminho = self.converter(caminho_xlsx, pasta_saida, sheet=sheet)
                caminhos.append(caminho)
            except Exception as e:
                self._log(f"ERRO ao converter aba '{sheet}': {e}")
        return caminhos

    def detectar_problemas(self, caminho_xlsx: str, sheet: str = 0) -> dict:
        """Detecta problemas comuns antes da conversao."""
        try:
            df = pd.read_excel(caminho_xlsx, sheet_name=sheet, nrows=100, engine="openpyxl")
            problemas = []

            colunas_unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
            if colunas_unnamed:
                problemas.append(f"Colunas 'Unnamed' detectadas: {colunas_unnamed}")

            nulos_por_col = df.isna().sum()
            colinas_muito_nulas = nulos_por_col[nulos_por_col > len(df) * 0.5].index.tolist()
            if colinas_muito_nulas:
                problemas.append(f"Colunas com muitos nulos: {colinas_muito_nulas}")

            duplicatas = df.duplicated().sum()
            if duplicatas > 0:
                problemas.append(f"{duplicatas} linhas duplicadas (na amostra)")

            return {"tem_problemas": len(problemas) > 0, "problemas": problemas}
        except Exception as e:
            return {"tem_problemas": True, "problemas": [f"Erro ao analisar: {e}"]}

"""
Carregamento de arquivos CSV.

Regras de negócio:
  - Bases governamentais brasileiras costumam vir em encoding Latin-1/CP1252
    (não UTF-8) e usar ';' como separador — detecta automaticamente em vez
    de assumir um padrão fixo.
  - Arquivos grandes (>50MB) são lidos em pedaços (chunks) para não
    sobrecarregar máquinas com pouca memória RAM.
  - Nunca lê e sobrescreve o arquivo original — toda transformação acontece
    em memória/cópia, o arquivo em data/raw/ nunca é alterado.
"""

import os
import pandas as pd

COMBINACOES_TESTADAS = [
    {"encoding": "utf-8", "sep": ";"},
    {"encoding": "utf-8", "sep": ","},
    {"encoding": "latin-1", "sep": ";"},
    {"encoding": "cp1252", "sep": ";"},
    {"encoding": "latin-1", "sep": ","},
]

LIMITE_MB_PARA_CHUNK = 50
TAMANHO_CHUNK_PADRAO = 100_000


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
        """Testa combinações de encoding/separador nas primeiras linhas até uma funcionar."""
        for combo in COMBINACOES_TESTADAS:
            try:
                pd.read_csv(self.caminho_arquivo, nrows=5, **combo)
                self.combo_detectado = combo
                self._log(f"Formato detectado para '{os.path.basename(self.caminho_arquivo)}': {combo}")
                return combo
            except Exception:
                continue
        raise ValueError(
            f"Não foi possível detectar encoding/separador de '{self.caminho_arquivo}'. "
            "Verifique o arquivo manualmente (pode ter linhas de título antes do cabeçalho real)."
        )

    def carregar(self, colunas: list = None, tipos: dict = None) -> pd.DataFrame:
        """
        colunas: lista de nomes de coluna a carregar (usecols do pandas) — opcional,
                 mas recomendado para arquivos grandes, evita carregar coluna à toa.
        tipos: dict {"coluna": tipo} — opcional, evita o pandas "adivinhar" tipo errado.
        """
        if self.combo_detectado is None:
            self.detectar_formato()

        tamanho_mb = os.path.getsize(self.caminho_arquivo) / (1024 * 1024)
        kwargs = dict(self.combo_detectado)
        if colunas:
            kwargs["usecols"] = colunas
        if tipos:
            kwargs["dtype"] = tipos

        if tamanho_mb < LIMITE_MB_PARA_CHUNK:
            self._log(f"Arquivo pequeno ({tamanho_mb:.1f}MB) — leitura direta.")
            df = pd.read_csv(self.caminho_arquivo, **kwargs)
        else:
            self._log(f"Arquivo grande ({tamanho_mb:.1f}MB) — leitura em chunks de {TAMANHO_CHUNK_PADRAO}.")
            pedacos = []
            for pedaco in pd.read_csv(self.caminho_arquivo, chunksize=TAMANHO_CHUNK_PADRAO, **kwargs):
                pedacos.append(pedaco)
            df = pd.concat(pedacos, ignore_index=True)

        colunas_com_espaco = [c for c in df.columns if c != c.strip()]
        if colunas_com_espaco:
            self._log(f"Nomes de coluna com espaço extra detectados e corrigidos: {colunas_com_espaco}")
        df.columns = [c.strip() for c in df.columns]

        self._log(f"Carregado: {len(df)} linhas, {len(df.columns)} colunas.")
        return df

    def listar_colunas(self) -> list:
        """Lê só o cabeçalho, sem carregar o arquivo inteiro — útil para o menu interativo."""
        if self.combo_detectado is None:
            self.detectar_formato()
        df_cabecalho = pd.read_csv(self.caminho_arquivo, nrows=0, **self.combo_detectado)
        return [c.strip() for c in df_cabecalho.columns]

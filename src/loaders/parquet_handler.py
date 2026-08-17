"""
Handler de leitura/escrita de arquivos Parquet.

Parquet e o formato ideal para intermediarios ETL em memoria:
  - Compressao colunar: 3-5x menor que CSV para o mesmo dado
  - Leitura seletiva: carrega so as colunas que precisa (projection pushdown)
  - Tipos preservados: nao precisa re-inferir como no CSV
  - Escrita incremental: pode escrever por chunks sem carregar tudo na RAM

Uso tipico:
  handler = ParquetHandler()
  handler.salvar(df, "base_etapa1.parquet")
  df = handler.carregar("base_etapa1.parquet", colunas=["col_a", "col_b"])
  handler.converter_csv_para_parquet("base.csv", "base.parquet")
"""

import os
import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


class ParquetHandler:
    """Leitura e escrita de arquivos Parquet com pyarrow."""

    def __init__(self, logger=None):
        self.logger = logger

    def _log(self, msg: str, nivel: str = "info"):
        if self.logger:
            getattr(self.logger, nivel)(msg)

    @property
    def disponivel(self) -> bool:
        return HAS_PYARROW

    def salvar(self, df: pd.DataFrame, caminho: str,
               compressao: str = "snappy", chunksize: int = None) -> str:
        """
        Salva DataFrame como Parquet.
        - compressao: snappy (rapido), gzip (melhor ratio), zstd (balanceado)
        - chunksize: se especificado, escreve em blocos para economizar RAM
        Retorna caminho do arquivo salvo.
        """
        if not self.disponivel:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)

        if chunksize and chunksize > 0 and len(df) > chunksize:
            tabelas = []
            for i in range(0, len(df), chunksize):
                pedaco = df.iloc[i:i + chunksize]
                tabelas.append(pa.Table.from_pandas(pedaco))
            pa.parquet.write_tables(caminho, tabelas, compression=compressao)
        else:
            tabela = pa.Table.from_pandas(df)
            pq.write_table(tabela, caminho, compression=compressao)

        tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
        self._log(f"[PARQUET] Salvo: {caminho} ({tamanho_mb:.2f}MB, {len(df)} linhas).")
        return caminho

    def carregar(self, caminho: str, colunas: list = None,
                 filtros: list = None) -> pd.DataFrame:
        """
        Carrega Parquet com leitura seletiva:
        - colunas: so carrega estas colunas (projection pushdown)
        - filtros:expressoes pyarrow para filtrar durante leitura (predicate pushdown)
          Ex: [("col_a", ">", 100)]
        """
        if not self.disponivel:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        kwargs = {}
        if colunas:
            kwargs["columns"] = colunas
        if filtros:
            kwargs["filters"] = filtros

        tabela = pq.read_table(caminho, **kwargs)
        df = tabela.to_pandas()

        self._log(
            f"[PARQUET] Carregado: {os.path.basename(caminho)} "
            f"({len(df)} linhas, {len(df.columns)} colunas)."
        )
        return df

    def carregar_pedacos(self, caminho: str, colunas: list = None,
                         chunksize: int = 100_000):
        """
        Gera pedacos do Parquet um por vez (generator).
        Ideal para processar arquivos muito grandes sem estourar RAM.
        """
        if not self.disponivel:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        kwargs = {}
        if colunas:
            kwargs["columns"] = colunas

        parquet_file = pq.ParquetFile(caminho)
        for batch in parquet_file.iter_batches(batch_size=chunksize, **kwargs):
            yield batch.to_pandas()

    def converter_csv_para_parquet(self, caminho_csv: str, caminho_parquet: str,
                                   encoding: str = "latin-1", separator: str = ";",
                                   compressao: str = "snappy") -> str:
        """
        Converte CSV direto para Parquet sem passar inteiro pela RAM.
        Usa pyarrow.csv para leitura eficiente.
        """
        if not self.disponivel:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        try:
            import pyarrow.csv as pcsv
            read_opts = pcsv.ReadOptions(encoding=encoding)
            parse_opts = pcsv.ParseOptions(delimiter=separator)
            tabela = pcsv.read_csv(caminho_csv, read_options=read_opts, parse_options=parse_opts)
        except Exception:
            df = pd.read_csv(caminho_csv, encoding=encoding, sep=separator)
            tabela = pa.Table.from_pandas(df)

        pq.write_table(tabela, caminho_parquet, compression=compressao)
        tamanho_mb = os.path.getsize(caminho_parquet) / (1024 * 1024)
        self._log(f"[PARQUET] CSV -> Parquet: {tamanho_mb:.2f}MB ({tabela.num_rows} linhas).")
        return caminho_parquet

    def informacoes(self, caminho: str) -> dict:
        """Retorna metadados do arquivo Parquet sem carregar os dados."""
        if not self.disponivel:
            raise RuntimeError("pyarrow nao instalado. pip install pyarrow")

        metadata = pq.read_metadata(caminho)
        schema = pq.read_schema(caminho)
        tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)

        return {
            "linhas": metadata.num_rows,
            "colunas": len(schema),
            "tamanho_mb": round(tamanho_mb, 2),
            "colunas_nomes": [field.name for field in schema],
            "colunas_tipos": {field.name: str(field.type) for field in schema},
            "colunas_por_grupo": metadata.num_row_groups,
        }

"""
Contexto do pipeline: armazena o estado atual do processamento
(DataFrame, metadados, historico de etapas, tabelas de referencia).

Otimizacao: get_data() retorna view quando possivel, so copia quando necessario.
set_data() armazena direto, sem copia extra — quem chama decide se copia.
"""

import pandas as pd
from datetime import datetime


class PipelineContext:
    """
    Estado compartilhado entre todas as etapas de um pipeline.
    Cada etapa le de context.data e escreve de volta em context.data.
    """

    def __init__(self, logger=None):
        self.data: pd.DataFrame = pd.DataFrame()
        self.tabelas_referencia: dict[str, pd.DataFrame] = {}
        self.metadados: dict = {}
        self.historico: list[dict] = []
        self.log_buffer: list[str] = []
        self.logger = logger
        self._timestamp_inicio = datetime.now()

        # Snapshot inicial para o relatorio final
        self._snapshot_inicial: dict = {}

    def _log(self, msg: str):
        self.log_buffer.append(msg)
        if self.logger:
            self.logger.info(msg)

    def set_data(self, df: pd.DataFrame, descricao: str = ""):
        """Armazena o DataFrame e registra no historico."""
        linhas_antes = len(self.data) if not self.data.empty else 0
        colunas_antes_count = self.data.shape[1] if not self.data.empty else 0
        colunas_antes_lista = list(self.data.columns) if not self.data.empty else []
        self.data = df
        self.historico.append({
            "momento": datetime.now().isoformat(),
            "operacao": descricao,
            "linhas_antes": linhas_antes,
            "linhas_depois": len(df),
            "colunas_antes": colunas_antes_count,
            "colunas_depois": len(df.columns),
            "colunas_antes_lista": colunas_antes_lista,
            "colunas_depois_lista": list(df.columns),
        })
        if descricao:
            self._log(f"[CONTEXT] {descricao} — {len(df)} linhas, {len(df.columns)} colunas.")

    def get_data(self) -> pd.DataFrame:
        """Retorna o DataFrame atual. Operacoes devem copiar internamente se precisar modificar."""
        return self.data

    def registrar_snapshot_inicial(self):
        """Registra o estado inicial da base para o relatorio final."""
        if not self.data.empty:
            self._snapshot_inicial = {
                "linhas": len(self.data),
                "colunas": len(self.data.columns),
                "nomes_colunas": list(self.data.columns),
                "tipos": {col: str(dtype) for col, dtype in self.data.dtypes.items()},
                "nulos_por_coluna": {col: int(self.data[col].isna().sum()) for col in self.data.columns},
                "total_nulos": int(self.data.isna().sum().sum()),
                "duplicatas": int(self.data.duplicated().sum()),
                "memoria_mb": round(self.data.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            }

    def registrar_tabela(self, nome: str, df: pd.DataFrame):
        self.tabelas_referencia[nome] = df.copy()
        self._log(f"[CONTEXT] Tabela '{nome}' registrada ({len(df)} linhas).")

    def get_tabela(self, nome: str) -> pd.DataFrame:
        if nome not in self.tabelas_referencia:
            self._log(f"[CONTEXT] AVISO: tabela '{nome}' nao encontrada.")
            return pd.DataFrame()
        return self.tabelas_referencia[nome]

    def list_tabelas(self) -> list:
        return list(self.tabelas_referencia.keys())

    def relatorio(self) -> str:
        """Relatorio textual do historico de processamento."""
        linhas = []
        linhas.append("=" * 60)
        linhas.append("  HISTORICO DO PIPELINE")
        linhas.append("=" * 60)
        for i, h in enumerate(self.historico, 1):
            linhas.append(f"  {i}. {h['operacao'] or '(sem descricao)'}")
            linhas.append(f"     {h.get('linhas_antes', '?')} -> {h['linhas_depois']} linhas")
        linhas.append("=" * 60)
        return "\n".join(linhas)

    def relatorio_final(self) -> str:
        """
        Relatorio completo antes/depois da operacao ETL.
        Mostra estado inicial, cada etapa executada, e estado final.
        """
        s = self._snapshot_inicial
        atual = self.data
        hist = self.historico

        linhas = []
        linhas.append("")
        linhas.append("#" * 70)
        linhas.append("  RELATORIO FINAL — ETL NGR-SEE")
        linhas.append("#" * 70)

        # ── ESTADO INICIAL ──
        linhas.append("")
        linhas.append("  ESTADO INICIAL DA BASE")
        linhas.append("  " + "-" * 50)
        if s:
            linhas.append(f"  Linhas:           {s['linhas']}")
            linhas.append(f"  Colunas:          {s['colunas']}")
            linhas.append(f"  Colunas:          {s['nomes_colunas']}")
            linhas.append(f"  Total nulos:      {s['total_nulos']}")
            linhas.append(f"  Duplicatas:       {s['duplicatas']}")
            linhas.append(f"  Memoria:          {s['memoria_mb']} MB")
            linhas.append("")
            linhas.append("  Tipos por coluna:")
            for col, tipo in s["tipos"].items():
                nulos = s["nulos_por_coluna"].get(col, 0)
                linhas.append(f"    {col:<30} {tipo:<20} ({nulos} nulos)")
        else:
            linhas.append("  (snapshot nao registrado)")

        # ── ETAPAS EXECUTADAS ──
        linhas.append("")
        linhas.append("  ETAPAS EXECUTADAS")
        linhas.append("  " + "-" * 50)
        for i, h in enumerate(hist, 1):
            desc = h.get("operacao", "?")
            la = h.get("linhas_antes", "?")
            ld = h.get("linhas_depois", "?")
            ca = h.get("colunas_antes", "?")
            cd = h.get("colunas_depois", "?")
            linhas.append(f"  {i:>3}. {desc}")
            linhas.append(f"       Linhas: {la} -> {ld} | Colunas: {ca} -> {cd}")

        # ── ESTADO FINAL ──
        linhas.append("")
        linhas.append("  ESTADO FINAL DA BASE")
        linhas.append("  " + "-" * 50)
        linhas.append(f"  Linhas:           {len(atual)}")
        linhas.append(f"  Colunas:          {len(atual.columns)}")
        linhas.append(f"  Colunas:          {list(atual.columns)}")
        linhas.append(f"  Total nulos:      {int(atual.isna().sum().sum())}")
        linhas.append(f"  Duplicatas:       {int(atual.duplicated().sum())}")

        if s:
            linhas.append("")
            linhas.append("  VARIACOES")
            linhas.append("  " + "-" * 50)
            linhas_var = len(atual) - s["linhas"]
            linhas_var_pct = (linhas_var / s["linhas"] * 100) if s["linhas"] > 0 else 0
            colunas_var = len(atual.columns) - s["colunas"]
            nulos_var = int(atual.isna().sum().sum()) - s["total_nulos"]
            duplicatas_var = int(atual.duplicated().sum()) - s["duplicatas"]
            linhas.append(f"  Linhas:     {linhas_var:+d} ({linhas_var_pct:+.1f}%)")
            linhas.append(f"  Colunas:    {colunas_var:+d}")
            linhas.append(f"  Nulos:      {nulos_var:+d}")
            linhas.append(f"  Duplicatas: {duplicatas_var:+d}")

            # Colunas removidas / adicionadas
            cols_antes = set(s["nomes_colunas"])
            cols_depois = set(atual.columns)
            removidas = cols_antes - cols_depois
            adicionadas = cols_depois - cols_antes
            if removidas:
                linhas.append(f"  Colunas removidas:    {list(removidas)}")
            if adicionadas:
                linhas.append(f"  Colunas adicionadas:  {list(adicionadas)}")

        linhas.append("")
        linhas.append("#" * 70)
        return "\n".join(linhas)

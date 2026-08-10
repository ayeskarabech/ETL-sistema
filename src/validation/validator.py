"""
Validação de qualidade após a limpeza.

Regra de negócio: antes de considerar um CSV "pronto para o Power BI",
o sistema roda checagens automáticas e reporta claramente se algo está
fora do esperado — em vez de simplesmente exportar e deixar o problema
ser descoberto só quando o painel já estiver publicado.
"""

import pandas as pd


class DataValidator:

    def __init__(self, logger=None):
        self.logger = logger
        self.alertas = []

    def _log(self, mensagem: str, nivel: str = "info"):
        if self.logger:
            getattr(self.logger, nivel)(mensagem)
        else:
            print(f"[VALIDAÇÃO] {mensagem}")

    def validar(self, df: pd.DataFrame, colunas_obrigatorias: list = None,
                linhas_minimas_esperadas: int = None) -> dict:
        """
        Roda o conjunto de checagens e devolve um dicionário com o resultado.
        Não interrompe a execução — reporta os problemas para decisão humana.
        """
        self.alertas = []
        resultado = {"aprovado": True, "alertas": []}

        # 1. Colunas obrigatórias presentes
        if colunas_obrigatorias:
            faltantes = [c for c in colunas_obrigatorias if c not in df.columns]
            if faltantes:
                self._registrar_alerta(f"Colunas obrigatórias ausentes: {faltantes}", resultado)

        # 2. Volume mínimo de linhas
        if linhas_minimas_esperadas and len(df) < linhas_minimas_esperadas:
            self._registrar_alerta(
                f"Volume de linhas abaixo do esperado: {len(df)} (esperado no mínimo {linhas_minimas_esperadas}).",
                resultado,
            )

        # 3. Colunas totalmente vazias (sinal de erro de leitura/mapeamento)
        colunas_vazias = [c for c in df.columns if df[c].isna().all()]
        if colunas_vazias:
            self._registrar_alerta(f"Colunas totalmente vazias (revisar mapeamento): {colunas_vazias}", resultado)

        # 4. Colunas "Unnamed" (sinal clássico de cabeçalho mal lido)
        colunas_unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
        if colunas_unnamed:
            self._registrar_alerta(
                f"Colunas 'Unnamed' detectadas (provável linha de título incorreta no arquivo original): {colunas_unnamed}",
                resultado,
            )

        # 5. Linhas totalmente duplicadas remanescentes
        duplicatas = df.duplicated().sum()
        if duplicatas > 0:
            self._registrar_alerta(f"{duplicatas} linhas totalmente duplicadas ainda presentes na base.", resultado)

        if resultado["aprovado"]:
            self._log("Validação concluída: nenhum problema encontrado.")
        else:
            self._log(f"Validação concluída com {len(resultado['alertas'])} alerta(s). Revisar antes de publicar.", nivel="warning")

        return resultado

    def _registrar_alerta(self, mensagem: str, resultado: dict):
        resultado["aprovado"] = False
        resultado["alertas"].append(mensagem)
        self._log(f"⚠ {mensagem}", nivel="warning")

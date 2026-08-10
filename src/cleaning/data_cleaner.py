"""
Limpeza e padronização de dados.

Regras de negócio (não negociáveis, aprendidas de erros anteriores do projeto):
  - Nunca aplicar a mesma estratégia de nulo para todas as colunas de uma vez.
  - Sempre medir e logar quantas linhas/valores foram afetados por cada etapa —
    isso é o que permite auditar e defender o resultado depois.
  - Nunca sobrescrever o DataFrame original sem gerar um retorno novo — quem
    chama decide se quer substituir ou manter os dois para comparar.
"""

import pandas as pd


class DataCleaner:

    def __init__(self, logger=None):
        self.logger = logger
        self.resumo_execucao = []

    def _log(self, mensagem: str):
        self.resumo_execucao.append(mensagem)
        if self.logger:
            self.logger.info(mensagem)
        else:
            print(f"[LIMPEZA] {mensagem}")

    def padronizar_texto(self, df: pd.DataFrame, colunas: list) -> pd.DataFrame:
        """Remove espaços extras e padroniza caixa em colunas categóricas de texto."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' não encontrada — pulando padronização de texto.")
                continue
            antes = df[col].nunique(dropna=True)
            df[col] = df[col].astype(str).str.strip().str.upper()
            depois = df[col].nunique(dropna=True)
            self._log(
                f"Coluna '{col}': padronizada (strip + upper). "
                f"Categorias distintas antes={antes}, depois={depois}."
            )
        return df

    def tratar_nulos(self, df: pd.DataFrame, estrategia_por_coluna: dict) -> pd.DataFrame:
        """
        estrategia_por_coluna: {"coluna": "mediana" | "moda" | "remover_linha" | valor_fixo}
        """
        df = df.copy()
        for col, estrategia in estrategia_por_coluna.items():
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' não encontrada — pulando tratamento de nulo.")
                continue

            nulos_antes = df[col].isna().sum()
            if nulos_antes == 0:
                continue

            if estrategia == "mediana":
                df[col] = df[col].fillna(df[col].median())
            elif estrategia == "moda":
                moda = df[col].mode()
                if len(moda) > 0:
                    df[col] = df[col].fillna(moda[0])
            elif estrategia == "remover_linha":
                total_antes = len(df)
                df = df.dropna(subset=[col])
                removidas = total_antes - len(df)
                self._log(
                    f"Coluna '{col}': removidas {removidas} linhas com valor nulo "
                    f"({removidas / total_antes * 100:.1f}% da base)."
                )
                continue
            else:
                df[col] = df[col].fillna(estrategia)

            self._log(f"Coluna '{col}': {nulos_antes} valores nulos tratados (estratégia: '{estrategia}').")
        return df

    def remover_duplicatas(self, df: pd.DataFrame, subset: list = None) -> pd.DataFrame:
        total_antes = len(df)
        df = df.drop_duplicates(subset=subset)
        removidas = total_antes - len(df)
        pct = (removidas / total_antes * 100) if total_antes > 0 else 0
        self._log(f"Duplicatas removidas: {removidas} ({pct:.2f}% da base).")
        return df

    def corrigir_tipos(self, df: pd.DataFrame, tipos_esperados: dict) -> pd.DataFrame:
        """
        tipos_esperados: {"coluna": "numero" | "texto" | "data"}
        Valores que não conseguem ser convertidos viram NaN (não travam a execução).
        """
        df = df.copy()
        for col, tipo in tipos_esperados.items():
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' não encontrada — pulando conversão de tipo.")
                continue

            if tipo == "numero":
                antes_invalidos = pd.to_numeric(df[col], errors="coerce").isna().sum()
                df[col] = pd.to_numeric(df[col], errors="coerce")
                self._log(f"Coluna '{col}': convertida para número. {antes_invalidos} valores não numéricos viraram nulo.")
            elif tipo == "data":
                df[col] = pd.to_datetime(df[col], errors="coerce")
                self._log(f"Coluna '{col}': convertida para data.")
            elif tipo == "texto":
                df[col] = df[col].astype(str)
                self._log(f"Coluna '{col}': convertida para texto.")
        return df

    def detectar_outliers_iqr(self, df: pd.DataFrame, coluna: str) -> pd.DataFrame:
        """
        Retorna apenas as linhas identificadas como outlier (método IQR),
        para inspeção manual — não remove nada automaticamente, porque
        outlier pode ser dado real e essa decisão exige julgamento humano.
        """
        if coluna not in df.columns:
            self._log(f"Aviso: coluna '{coluna}' não encontrada — não é possível checar outliers.")
            return pd.DataFrame()

        q1 = df[coluna].quantile(0.25)
        q3 = df[coluna].quantile(0.75)
        iqr = q3 - q1
        limite_inferior = q1 - 1.5 * iqr
        limite_superior = q3 + 1.5 * iqr

        outliers = df[(df[coluna] < limite_inferior) | (df[coluna] > limite_superior)]
        self._log(
            f"Coluna '{coluna}': {len(outliers)} possíveis outliers encontrados "
            f"(fora do intervalo [{limite_inferior:.2f}, {limite_superior:.2f}]). "
            "Revisar manualmente antes de decidir remover."
        )
        return outliers

    def substituir_valores(self, df: pd.DataFrame, colunas: list,
                           mapeamento: dict) -> pd.DataFrame:
        """Substitui valores exatos conforme mapeamento {antigo: novo} em colunas selecionadas."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada — pulando substituicao.")
                continue
            antes_valores = df[col].value_counts().to_dict()
            df[col] = df[col].replace(mapeamento)
            depois_valores = df[col].value_counts().to_dict()
            total_trocas = sum(antes_valores.get(k, 0) for k in mapeamento if k in antes_valores)
            self._log(
                f"Coluna '{col}': {total_trocas} valores substituidos. "
                f"Mapeamento: {mapeamento}"
            )
        return df

    def padronizar_texto_minusculas(self, df: pd.DataFrame, colunas: list) -> pd.DataFrame:
        """Converte texto para minusculo (diferente de padronizar_texto que usa UPPER)."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada.")
                continue
            df[col] = df[col].astype(str).str.strip().str.lower()
            self._log(f"Coluna '{col}': convertida para minusculo.")
        return df

    def extrair_texto_regex(self, df: pd.DataFrame, colunas: list,
                            padrao: str, nome_nova_coluna: str = None) -> pd.DataFrame:
        """Extrai partes de texto de uma coluna usando regex e cria nova coluna."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada.")
                continue
            saida = nome_nova_coluna or f"{col}_extraido"
            df[saida] = df[col].astype(str).str.extract(padrao, expand=False)
            self._log(f"Regex '{padrao}' aplicada na coluna '{col}' -> '{saida}'.")
        return df

    def tratar_nulos_por_colunas(self, df: pd.DataFrame, colunas: list,
                                 valor_padrao) -> pd.DataFrame:
        """Preenche nulos com um valor fixo especifico (string, numero, etc)."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada.")
                continue
            nulos = df[col].isna().sum()
            if nulos > 0:
                df[col] = df[col].fillna(valor_padrao)
                self._log(f"Coluna '{col}': {nulos} nulos preenchidos com '{valor_padrao}'.")
        return df

    def padronizar_datas(self, df: pd.DataFrame, colunas: list,
                         formato_saida: str = "%d/%m/%Y") -> pd.DataFrame:
        """Converte colunas de texto/data para formato padronizado."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada.")
                continue
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                formato_br = df[col].dt.strftime(formato_saida)
                df[col] = formato_br
                self._log(f"Coluna '{col}': datas padronizadas no formato {formato_saida}.")
            except Exception as e:
                self._log(f"ERRO ao padronizar datas na coluna '{col}': {e}")
        return df

    def normalizar_numeros(self, df: pd.DataFrame, colunas: list,
                           casas_decimais: int = 2) -> pd.DataFrame:
        """Arredonda valores numericos para o numero especificado de casas decimais."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada.")
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].round(casas_decimais)
            self._log(f"Coluna '{col}': numeros arredondados para {casas_decimais} casas.")
        return df

    def substituir_regex(self, df: pd.DataFrame, colunas: list,
                         padrao: str, novo: str) -> pd.DataFrame:
        """Substitui texto em colunas usando expressao regular."""
        df = df.copy()
        for col in colunas:
            if col not in df.columns:
                self._log(f"Aviso: coluna '{col}' nao encontrada — pulando substituicao regex.")
                continue
            antes = df[col].nunique(dropna=True)
            df[col] = df[col].astype(str).str.replace(padrao, novo, regex=True)
            depois = df[col].nunique(dropna=True)
            self._log(
                f"Regex '{padrao}' -> '{novo}' aplicada em '{col}'. "
                f"Categorias antes={antes}, depois={depois}."
            )
        return df

    def remover_colunas_vazias(self, df: pd.DataFrame, limiar: float = 1.0) -> pd.DataFrame:
        """Remove colunas onde todos (ou quase todos) os valores sao nulos."""
        df = df.copy()
        limiar_nulos = int(len(df) * limiar)
        colunas_vazias = [c for c in df.columns if df[c].isna().sum() >= limiar_nulos]
        if colunas_vazias:
            df = df.drop(columns=colunas_vazias)
            self._log(f"Colunas vazias removidas ({limiar*100:.0f}% nulos): {colunas_vazias}")
        else:
            self._log("Nenhuma coluna totalmente vazia encontrada.")
        return df

    def relatorio_resumo(self, df_antes: pd.DataFrame, df_depois: pd.DataFrame) -> str:
        linhas_removidas = len(df_antes) - len(df_depois)
        pct = (linhas_removidas / len(df_antes) * 100) if len(df_antes) > 0 else 0
        resumo = (
            f"Linhas: {len(df_antes)} -> {len(df_depois)} ({linhas_removidas} removidas, {pct:.1f}%) | "
            f"Colunas: {df_antes.shape[1]} -> {df_depois.shape[1]}"
        )
        self._log(f"RESUMO FINAL: {resumo}")
        return resumo

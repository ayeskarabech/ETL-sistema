"""
Motor de formulas estilo Excel: PROCV, ESQUERDA, DIREITA, CORRESP, CONT.SE,
SOMASE, CONCATENAR, SE, etc.

Cada formula e uma funcao que recebe DataFrame(s) + parametros e retorna Series/DataFrame.
Todas as formulas sao puras — nao modificam o DataFrame original.
"""

import pandas as pd
import numpy as np


class FormulaEngine:
    """Motor de formulas com interface similar ao Excel."""

    # Catalogo de formulas disponiveis (nome -> descricao + parametros)
    CATALOGO = {
        "PROCV": {
            "descricao": "Busca vertical (VLOOKUP): puxa valor de outra tabela",
            "params": ["coluna_chave_tabela", "tabela_origem", "coluna_chave_origem",
                        "coluna_valor_origem", "padrao_nao_encontrado"],
        },
        "ESQUERDA": {
            "descricao": "Extrai N caracteres da esquerda (LEFT)",
            "params": ["coluna", "num_caracteres"],
        },
        "DIREITA": {
            "descricao": "Extrai N caracteres da direita (RIGHT)",
            "params": ["coluna", "num_caracteres"],
        },
        "MEIO": {
            "descricao": "Extrai texto de posicao inicial com N caracteres (MID)",
            "params": ["coluna", "posicao_inicial", "num_caracteres"],
        },
        "TAMANHO": {
            "descricao": " Retorna o tamanho do texto (LEN)",
            "params": ["coluna"],
        },
        "CORRESP": {
            "descricao": "Posicao de um valor em intervalo (MATCH)",
            "params": ["valor", "coluna_busca"],
        },
        "INDICE": {
            "descricao": "Valor na posicao N de uma coluna (INDEX)",
            "params": ["coluna", "posicao"],
        },
        "CONT.SE": {
            "descricao": "Conta celulas que atendem condicao (COUNTIF)",
            "params": ["coluna", "condicao"],
        },
        "SOMASE": {
            "descricao": "Soma valores que atendem condicao (SUMIF)",
            "params": ["coluna_valores", "coluna_criterios", "criterio"],
        },
        "SE": {
            "descricao": "Logica condicional (IF)",
            "params": ["condicao_true", "valor_se_verdadeiro", "valor_se_falso"],
        },
        "CONCATENAR": {
            "descricao": "Junta textos (CONCATENATE / &)",
            "params": ["colunas", "separador"],
        },
        "SUBSTITUIR": {
            "descricao": "Substitui texto por outro (SUBSTITUTE)",
            "params": ["coluna", "antigo", "novo"],
        },
        "VALOR": {
            "descricao": "Converte texto para numero (VALUE)",
            "params": ["coluna"],
        },
        "TEXTO": {
            "descricao": "Converte numero para texto formatado (TEXT)",
            "params": ["coluna", "formato"],
        },
        "ARRED": {
            "descricao": "Arredonda numero (ROUND)",
            "params": ["coluna", "casas"],
        },
        "MAX": {
            "descricao": "Maior valor de um grupo (MAX)",
            "params": ["coluna"],
        },
        "MIN": {
            "descricao": "Menor valor de um grupo (MIN)",
            "params": ["coluna"],
        },
        "MEDIA": {
            "descricao": "Media aritmetica (AVERAGE)",
            "params": ["coluna"],
        },
        "SOMA": {
            "descricao": "Soma de valores (SUM)",
            "params": ["coluna"],
        },
        "HARMONICA": {
            "descricao": "Media harmonica (HARMEAN) — util para taxas e precos medios",
            "params": ["coluna"],
        },
        "CORREL": {
            "descricao": "Correlacao entre duas colunas (CORREL)",
            "params": ["col_a", "col_b", "metodo(pearson/spearman/kendall)"],
        },
        "PEARSON": {
            "descricao": "Coeficiente de correlacao de Pearson (r)",
            "params": ["col_a", "col_b"],
        },
        "SPEARMAN": {
            "descricao": "Correlacao de Spearman (rho) — baseada em postos",
            "params": ["col_a", "col_b"],
        },
        "PROCV_AGRUPADO": {
            "descricao": "PROCV com retorno de multiplos valores agrupados",
            "params": ["coluna_chave_tabela", "tabela_origem", "coluna_chave_origem",
                        "coluna_valor_origem", "funcao_agregacao"],
        },
        "INDICE_CORRESP": {
            "descricao": "INDICE+CORRESP (INDEX-MATCH): busca avancada, mais flexivel que PROCV",
            "params": ["coluna_retorno", "valor_procurado", "coluna_busca"],
        },
    }

    def __init__(self, logger=None):
        self.logger = logger
        self.log_buffer = []

    def _log(self, msg: str):
        self.log_buffer.append(msg)
        if self.logger:
            self.logger.info(msg)

    def flush_log(self) -> list:
        logs = list(self.log_buffer)
        self.log_buffer.clear()
        return logs

    def listar_formulas(self) -> dict:
        """Retorna o catalogo de formulas disponiveis."""
        return {k: v["descricao"] for k, v in self.CATALOGO.items()}

    # ── PROCV (VLOOKUP) ────────────────────────────────────────────────────

    def procv(self, df_tabela: pd.DataFrame, coluna_chave_tabela: str,
              df_origem: pd.DataFrame, coluna_chave_origem: str,
              coluna_valor_origem: str, padrao_nao_encontrado=np.nan) -> pd.DataFrame:
        """
        Busca vertical: para cada valor de coluna_chave_tabela, encontra
        o correspondente em coluna_chave_origem e retorna coluna_valor_origem.
        Equivalente ao PROCV/VLOOKUP do Excel.
        """
        df_tabela = df_tabela.copy()
        nome_col = f"{coluna_valor_origem}_procv"

        lookup = df_origem.set_index(coluna_chave_origem)[coluna_valor_origem]

        df_tabela[nome_col] = df_tabela[coluna_chave_tabela].map(lookup)
        df_tabela[nome_col] = df_tabela[nome_col].fillna(padrao_nao_encontrado)

        encontrados = df_tabela[nome_col].notna().sum()
        total = len(df_tabela)
        self._log(
            f"[PROCV] '{coluna_chave_tabela}' -> '{coluna_valor_origem}': "
            f"{encontrados}/{total} registros encontrados."
        )
        return df_tabela

    def procv_agrupado(self, df_tabela: pd.DataFrame, coluna_chave_tabela: str,
                       df_origem: pd.DataFrame, coluna_chave_origem: str,
                       coluna_valor_origem: str,
                       funcao: str = "soma") -> pd.DataFrame:
        """
        PROCV que retorna valor agregado (soma, media, contagem, etc.)
        para cada chave da tabela.
        """
        df_tabela = df_tabela.copy()
        nome_col = f"{coluna_valor_origem}_{funcao}"

        mapa_agg = {
            "soma": "sum", "media": "mean", "contagem": "count",
            "min": "min", "max": "max", "mediana": "median",
        }
        agg_func = mapa_agg.get(funcao, funcao)

        agg = df_origem.groupby(coluna_chave_origem)[coluna_valor_origem].agg(agg_func)
        df_tabela[nome_col] = df_tabela[coluna_chave_tabela].map(agg)

        self._log(
            f"[PROCV_AGRUPADO] '{coluna_chave_tabela}' -> '{coluna_valor_origem}' "
            f"({funcao}): {len(df_tabela)} linhas mapeadas."
        )
        return df_tabela

    # ── TEXTO ──────────────────────────────────────────────────────────────

    def esquerda(self, df: pd.DataFrame, coluna: str,
                 num_caracteres: int, nova_coluna: str = None) -> pd.DataFrame:
        """ESQUERDA (LEFT): extrai N caracteres do inicio."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_esquerda"
        df[saida] = df[coluna].astype(str).str[:num_caracteres]
        self._log(f"[ESQUERDA] '{coluna}' ({num_caracteres} chars) -> '{saida}'.")
        return df

    def direita(self, df: pd.DataFrame, coluna: str,
                num_caracteres: int, nova_coluna: str = None) -> pd.DataFrame:
        """DIREITA (RIGHT): extrai N caracteres do final."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_direita"
        df[saida] = df[coluna].astype(str).str[-num_caracteres:]
        self._log(f"[DIREITA] '{coluna}' ({num_caracteres} chars) -> '{saida}'.")
        return df

    def meio(self, df: pd.DataFrame, coluna: str,
             posicao_inicial: int, num_caracteres: int,
             nova_coluna: str = None) -> pd.DataFrame:
        """MEIO (MID): extrai N caracteres a partir da posicao inicial."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_meio"
        inicio = posicao_inicial - 1  # Excel e 1-based, Python e 0-based
        df[saida] = df[coluna].astype(str).str[inicio:inicio + num_caracteres]
        self._log(f"[MEIO] '{coluna}' (pos={posicao_inicial}, {num_caracteres} chars) -> '{saida}'.")
        return df

    def tamanho(self, df: pd.DataFrame, coluna: str,
                nova_coluna: str = None) -> pd.DataFrame:
        """TAMANHO (LEN): numero de caracteres."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_tamanho"
        df[saida] = df[coluna].astype(str).str.len()
        self._log(f"[TAMANHO] '{coluna}' -> '{saida}'.")
        return df

    def substituir_texto(self, df: pd.DataFrame, coluna: str,
                         antigo: str, novo: str,
                         nova_coluna: str = None) -> pd.DataFrame:
        """SUBSTITUIR (SUBSTITUTE): troca texto dentro da celula."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_substituido"
        df[saida] = df[coluna].astype(str).str.replace(antigo, novo, regex=False)
        self._log(f"[SUBSTITUIR] '{coluna}': '{antigo}' -> '{novo}' -> '{saida}'.")
        return df

    def concatenar(self, df: pd.DataFrame, colunas: list,
                   separador: str = "", nova_coluna: str = "concat") -> pd.DataFrame:
        """CONCATENAR: junta texto de multiplas colunas."""
        df = df.copy()
        colunas_validas = [c for c in colunas if c in df.columns]
        df[nova_coluna] = df[colunas_validas].astype(str).agg(separador.join, axis=1)
        self._log(f"[CONCATENAR] {colunas_validas} -> '{nova_coluna}'.")
        return df

    # ── BUSCA E INDICE ─────────────────────────────────────────────────────

    def corresp(self, df: pd.DataFrame, valor, coluna_busca: str) -> pd.Series:
        """
        CORRESP (MATCH): retorna a posicao (0-based) onde valor occur na coluna.
        Se encontrar multiplos, retorna a primeira ocorrencia.
        """
        serie = df[coluna_busca]
        mascara = serie == valor
        posicoes = np.where(mascara)[0]
        self._log(f"[CORRESP] Valor '{valor}' em '{coluna_busca}': {len(posicoes)} ocorrencia(s).")
        return posicoes

    def indice(self, df: pd.DataFrame, coluna: str, posicao: int):
        """
        INDICE (INDEX): retorna o valor na posicao especificada.
        posicao e 1-based (como no Excel).
        """
        idx = posicao - 1
        if 0 <= idx < len(df):
            valor = df[coluna].iloc[idx]
            self._log(f"[INDICE] '{coluna}' na posicao {posicao}: '{valor}'.")
            return valor
        self._log(f"[INDICE] Posicao {posicao} fora do intervalo (max={len(df)}).")
        return np.nan

    # ── CONDICIONAL ────────────────────────────────────────────────────────

    def se(self, df: pd.DataFrame, condicao: str,
           valor_verdadeiro, valor_falso,
           nova_coluna: str = "resultado_se") -> pd.DataFrame:
        """
        SE (IF): avalia condicao e retorna valor_verdadeiro ou valor_falso.
        condicao: expressao pandas-safe (ex: "col_a > 100", "col_b == 'SIM'")
        """
        df = df.copy()
        try:
            escopo = {col: df[col] for col in df.columns}
            escopo["np"] = np
            escopo["pd"] = pd
            mascara = eval(condicao, {"__builtins__": {}}, escopo)
            df[nova_coluna] = np.where(mascara, valor_verdadeiro, valor_falso)
            self._log(f"[SE] condicao='{condicao}' -> '{nova_coluna}'.")
        except Exception as e:
            df[nova_coluna] = np.nan
            self._log(f"[SE] ERRO ao avaliar condicao '{condicao}': {e}")
        return df

    # ── AGREGACAO CONDICIONAL ──────────────────────────────────────────────

    def cont_se(self, df: pd.DataFrame, coluna: str, criterio) -> int:
        """CONT.SE (COUNTIF): conta celulas que atendem o criterio."""
        serie = df[coluna]
        if isinstance(criterio, str) and criterio.startswith((">", "<", "!=", ">=", "<=")):
            operador = ""
            for prefixo in [">=", "<=", "!=", ">", "<"]:
                if criterio.startswith(prefixo):
                    operador = prefixo
                    break
            valor = criterio[len(operador):].strip()
            valor = pd.to_numeric(valor, errors="coerce") if valor.replace(".", "", 1).isdigit() else valor
            comparacoes = {
                ">": lambda s, v: s > v,
                "<": lambda s, v: s < v,
                ">=": lambda s, v: s >= v,
                "<=": lambda s, v: s <= v,
                "!=": lambda s, v: s != v,
            }
            if operador in comparacoes:
                resultado = comparacoes[operador](serie, valor).sum()
            else:
                resultado = (serie == criterio).sum()
        elif isinstance(criterio, (int, float)):
            resultado = (serie == criterio).sum()
        else:
            resultado = (serie.astype(str).str.strip().str.upper() == str(criterio).strip().upper()).sum()

        self._log(f"[CONT.SE] '{coluna}' criterio='{criterio}': {resultado}.")
        return resultado

    def somase(self, df: pd.DataFrame, coluna_valores: str,
               coluna_criterios: str, criterio) -> float:
        """SOMASE (SUMIF): soma valores onde a coluna criterio atende a condicao."""
        df_filtrado = df.copy()
        serie_crit = df_filtrado[coluna_criterios]

        if isinstance(criterio, str) and criterio.startswith((">", "<", "!=", ">=", "<=")):
            operador = ""
            for prefixo in [">=", "<=", "!=", ">", "<"]:
                if criterio.startswith(prefixo):
                    operador = prefixo
                    break
            valor = criterio[len(operador):].strip()
            valor = pd.to_numeric(valor, errors="coerce") if valor.replace(".", "", 1).isdigit() else valor
            comparacoes = {
                ">": lambda s, v: s > v,
                "<": lambda s, v: s < v,
                ">=": lambda s, v: s >= v,
                "<=": lambda s, v: s <= v,
                "!=": lambda s, v: s != v,
            }
            if operador in comparacoes:
                mascara = comparacoes[operador](serie_crit, valor)
            else:
                mascara = serie_crit.astype(str).str.upper() == str(criterio).upper()
        else:
            mascara = serie_crit.astype(str).str.upper() == str(criterio).upper()

        resultado = pd.to_numeric(df_filtrado.loc[mascara, coluna_valores], errors="coerce").sum()
        self._log(f"[SOMASE] '{coluna_valores}' onde '{coluna_criterios}'={criterio}: {resultado:.2f}.")
        return resultado

    # ── NUMEROS ────────────────────────────────────────────────────────────

    def valor(self, df: pd.DataFrame, coluna: str,
              nova_coluna: str = None) -> pd.DataFrame:
        """VALOR (VALUE): converte texto para numero."""
        df = df.copy()
        saida = nova_coluna or coluna
        serie = df[coluna].astype(str).str.strip()
        serie = serie.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        df[saida] = pd.to_numeric(serie, errors="coerce")
        self._log(f"[VALOR] '{coluna}' -> '{saida}'.")
        return df

    def texto(self, df: pd.DataFrame, coluna: str,
              formato: str, nova_coluna: str = None) -> pd.DataFrame:
        """TEXTO (TEXT): formata numero como texto com mascara."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_formatado"
        serie = pd.to_numeric(df[coluna], errors="coerce")
        df[saida] = serie.apply(lambda x: formato.format(x) if pd.notna(x) else "")
        self._log(f"[TEXTO] '{coluna}' formato='{formato}' -> '{saida}'.")
        return df

    def arred(self, df: pd.DataFrame, coluna: str,
              casas: int = 0, nova_coluna: str = None) -> pd.DataFrame:
        """ARRED (ROUND): arredonda numero."""
        df = df.copy()
        saida = nova_coluna or f"{coluna}_arred"
        df[saida] = pd.to_numeric(df[coluna], errors="coerce").round(casas)
        self._log(f"[ARRED] '{coluna}' ({casas} casas) -> '{saida}'.")
        return df

    def maximo(self, df: pd.DataFrame, coluna: str) -> float:
        return pd.to_numeric(df[coluna], errors="coerce").max()

    def minimo(self, df: pd.DataFrame, coluna: str) -> float:
        return pd.to_numeric(df[coluna], errors="coerce").min()

    def media(self, df: pd.DataFrame, coluna: str) -> float:
        return pd.to_numeric(df[coluna], errors="coerce").mean()

    def soma(self, df: pd.DataFrame, coluna: str) -> float:
        return pd.to_numeric(df[coluna], errors="coerce").sum()

    def harmonica(self, df: pd.DataFrame, coluna: str) -> float:
        """MEDIA HARMONICA: N / soma(1/x) — util para taxas, precos, razoes."""
        serie = pd.to_numeric(df[coluna], errors="coerce").dropna()
        serie = serie[serie > 0]
        if serie.empty:
            return 0.0
        resultado = len(serie) / (1.0 / serie).sum()
        self._log(f"[HARMONICA] '{coluna}': {resultado:.4f} (n={len(serie)}).")
        return resultado

    def correl(self, df: pd.DataFrame, col_a: str, col_b: str, metodo: str = "pearson") -> float:
        """
        CORREL: correlacao entre duas colunas.
        metodo: 'pearson', 'spearman', ou 'kendall'.
        """
        serie_a = pd.to_numeric(df[col_a], errors="coerce")
        serie_b = pd.to_numeric(df[col_b], errors="coerce")
        mascara = serie_a.notna() & serie_b.notna()
        if mascara.sum() < 2:
            self._log(f"[CORREL] Dados insuficientes entre '{col_a}' e '{col_b}'.")
            return 0.0
        resultado = serie_a[mascara].corr(serie_b[mascara], method=metodo)
        self._log(f"[CORREL] '{col_a}' vs '{col_b}' ({metodo}): {resultado:.4f}.")
        return resultado

    def pearson(self, df: pd.DataFrame, col_a: str, col_b: str) -> float:
        """PEARSON: correlacao de Pearson (r)."""
        return self.correl(df, col_a, col_b, metodo="pearson")

    def spearman(self, df: pd.DataFrame, col_a: str, col_b: str) -> float:
        """SPEARMAN: correlacao de Spearman (rho)."""
        return self.correl(df, col_a, col_b, metodo="spearman")

    def indice_corresp(self, df: pd.DataFrame, coluna_retorno: str,
                       valor_procurado, coluna_busca: str,
                       colunas_extras: list = None) -> pd.DataFrame:
        """
        INDICE + CORRESP (INDEX-MATCH): para cada linha, busca valor_procurado
        na coluna_busca e retorna o valor correspondente de coluna_retorno.
        Equivalente a =INDICE(col_ret; CORRESP(valor; col_busca; 0)) do Excel.
        """
        df = df.copy()
        saida = f"{coluna_retorno}_indice"

        # Se valor_procurado e uma coluna, usa linha a linha
        if isinstance(valor_procurado, str) and valor_procurado in df.columns:
            df[saida] = df[valor_procurado].apply(
                lambda v: self._match_single(df, coluna_retorno, v, coluna_busca)
            )
        else:
            # Valor fixo: busca geral
            mascara = df[coluna_busca] == valor_procurado
            encontrado = df.loc[mascara, coluna_retorno]
            if len(encontrado) > 0:
                df[saida] = encontrado.iloc[0]
            else:
                df[saida] = np.nan

        self._log(
            f"[INDICE_CORRESP] '{coluna_retorno}' por '{coluna_busca}' "
            f"(valor={valor_procurado}) -> '{saida}'."
        )
        return df

    def _match_single(self, df: pd.DataFrame, coluna_retorno: str,
                      valor, coluna_busca: str):
        """Busca INDEX-MATCH para um valor especifico."""
        if pd.isna(valor):
            return np.nan
        mascara = df[coluna_busca] == valor
        encontrado = df.loc[mascara, coluna_retorno]
        if len(encontrado) > 0:
            return encontrado.iloc[0]
        return np.nan

    # ── DESCRICAO ──────────────────────────────────────────────────────────

    def descricao_formula(self, nome: str) -> str:
        """Retorna descricao detalhada de uma formula."""
        info = self.CATALOGO.get(nome)
        if not info:
            return f"Formula '{nome}' nao encontrada."
        return (
            f"{nome}: {info['descricao']}\n"
            f"Parametros: {', '.join(info['params'])}"
        )

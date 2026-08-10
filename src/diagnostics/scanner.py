"""
Scanner de diagnostico: analisa um DataFrame e retorna todos os problemas
encontrados — formatos inconsistentes, nulos, duplicatas, fuzzy match,
tipos mistos, colunas problematicas, etc.

O scanner e READ-ONLY: nunca modifica o DataFrame, apenas observa.
"""

import re
from collections import Counter
import pandas as pd
import numpy as np


class DiagnosticIssue:
    """Representa um problema encontrado no dado."""

    GRAVIDADE = {"critico": 3, "aviso": 2, "info": 1}

    def __init__(self, categoria: str, coluna: str, descricao: str,
                 gravidade: str = "aviso", detalhes: dict = None):
        self.categoria = categoria
        self.coluna = coluna
        self.descricao = descricao
        self.gravidade = gravidade
        self.detalhes = detalhes or {}

    def __repr__(self):
        icone = {"critico": "!!!", "aviso": " ! ", "info": " i "}
        return f"[{icone.get(self.gravidade, ' ? ')}] {self.categoria} | '{self.coluna}': {self.descricao}"

    def to_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "coluna": self.coluna,
            "descricao": self.descricao,
            "gravidade": self.gravidade,
            "detalhes": self.detalhes,
        }


class DiagnosticScanner:
    """
    Scanner de diagnostico completo. Roda todas as checagens e retorna
    lista de DiagnosticIssue.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def escanear(self, df: pd.DataFrame) -> list:
        """Executa todas as checagens e retorna lista de problemas."""
        issues = []
        issues.extend(self._checar_nulos(df))
        issues.extend(self._checar_duplicatas(df))
        issues.extend(self._checar_colunas_vazias(df))
        issues.extend(self._checar_colunas_unnamed(df))
        issues.extend(self._checar_formato_decimal_ponto(df))
        issues.extend(self._checar_formatos_numericos(df))
        issues.extend(self._checar_tipo_coluna(df))
        issues.extend(self._checar_valores_suspeitos(df))
        issues.extend(self._checar_texto_inconsistente(df))
        issues.extend(self._checar_fuzzy_match(df))

        issues.sort(key=lambda x: self.DiagnosticIssue.GRAVIDADE.get(x.gravidade, 0), reverse=True)
        return issues

    # ── NULOS ──────────────────────────────────────────────────────────────

    def _checar_nulos(self, df: pd.DataFrame) -> list:
        issues = []
        total = len(df)
        for col in df.columns:
            nulos = df[col].isna().sum()
            if nulos == 0:
                continue
            pct = nulos / total * 100
            if pct == 100:
                grav = "critico"
            elif pct > 30:
                grav = "critico"
            elif pct > 10:
                grav = "aviso"
            else:
                grav = "info"
            issues.append(DiagnosticIssue(
                "NULOS", col,
                f"{nulos} valores nulos ({pct:.1f}% da base)",
                grav, {"quantidade": nulos, "percentual": round(pct, 2)},
            ))
        return issues

    # ── DUPLICATAS ─────────────────────────────────────────────────────────

    def _checar_duplicatas(self, df: pd.DataFrame) -> list:
        issues = []
        duplicatas = df.duplicated().sum()
        if duplicatas > 0:
            pct = duplicatas / len(df) * 100
            grav = "critico" if pct > 20 else "aviso" if pct > 5 else "info"
            issues.append(DiagnosticIssue(
                "DUPLICATAS", "(todas as colunas)",
                f"{duplicatas} linhas totalmente duplicadas ({pct:.1f}%)",
                grav, {"quantidade": int(duplicatas), "percentual": round(pct, 2)},
            ))

        for col in df.columns:
            dup_col = df[col].duplicated().sum()
            unicos = df[col].nunique(dropna=True)
            if dup_col > 0 and unicos < len(df) * 0.5:
                issues.append(DiagnosticIssue(
                    "DUPLICATA_COLUNA", col,
                    f"Coluna tem apenas {unicos} valores unicos ({dup_col} repetidos)",
                    "info", {"unicos": unicos, "repetidos": int(dup_col)},
                ))
        return issues

    # ── COLUNAS VAZIAS / UNNAMED ───────────────────────────────────────────

    def _checar_colunas_vazias(self, df: pd.DataFrame) -> list:
        issues = []
        total = len(df)
        for col in df.columns:
            nulos = df[col].isna().sum()
            if nulos == total:
                issues.append(DiagnosticIssue(
                    "COLUNA_VAZIA", col,
                    "Coluna 100% vazia — provavelmente erro de mapeamento",
                    "critico",
                ))
            elif nulos > total * 0.9:
                issues.append(DiagnosticIssue(
                    "COLUNA_VAZIA", col,
                    f"Coluna com {nulos/total*100:.0f}% de valores nulos",
                    "aviso",
                ))
        return issues

    def _checar_colunas_unnamed(self, df: pd.DataFrame) -> list:
        issues = []
        for col in df.columns:
            if str(col).startswith("Unnamed"):
                issues.append(DiagnosticIssue(
                    "COLUNA_UNNAMED", col,
                    "Coluna 'Unnamed' — provavel linha de titulo incorreta no CSV original",
                    "aviso",
                ))
        return issues

    # ── NUMEROS: PONTO DECIMAL QUE DEVERIA SER VIRGULA ─────────────────────

    def _checar_formato_decimal_ponto(self, df: pd.DataFrame) -> list:
        """
        Detecta colunas de texto que contem numeros decimais com PONTO
        como separador decimal (ex: 1234.56) quando deveriam usar VIRGULA
        no formato brasileiro (ex: 1234,56).
        """
        issues = []
        for col in df.columns:
            if df[col].dtype != object:
                continue
            amostra = df[col].dropna().astype(str).str.strip()
            if amostra.empty or len(amostra) < 5:
                continue

            # Numeros com ponto decimal: 1234.56, 0.75, -3.14
            padrao_ponto_decimal = re.compile(r"^-?\d+\.\d{1,6}$")
            matches_ponto = amostra.apply(lambda x: bool(padrao_ponto_decimal.match(x)))
            n_ponto = matches_ponto.sum()

            # Numeros com virgula decimal: 1234,56
            padrao_virgula_decimal = re.compile(r"^-?\d+,\d{1,6}$")
            matches_virgula = amostra.apply(lambda x: bool(padrao_virgula_decimal.match(x)))
            n_virgula = matches_virgula.sum()

            # Numeros inteiros puros
            padrao_inteiro = re.compile(r"^-?\d+$")
            matches_inteiro = amostra.apply(lambda x: bool(padrao_inteiro.match(x)))
            n_inteiro = matches_inteiro.sum()

            total_numericos = n_ponto + n_virgula + n_inteiro

            if total_numericos < 3:
                continue

            # CENARIO 1: Mais numeros com ponto do que com virgula -> sugere converter
            if n_ponto > n_virgula and n_ponto >= 3:
                pct_ponto = n_ponto / len(amostra) * 100

                # Detecta quantas casas decimais estao presentes
                casas_detectadas = set()
                for val in amostra[matches_ponto].head(20):
                    partes = val.split(".")
                    if len(partes) == 2:
                        casas_detectadas.add(len(partes[1]))

                casas_str = ", ".join(str(c) for c in sorted(casas_detectadas))
                issues.append(DiagnosticIssue(
                    "NUMERO_PONTO_DECIMAL", col,
                    f"Coluna contem {n_ponto} numeros com PONTO decimal ({pct_ponto:.0f}% da amostra). "
                    f"No formato brasileiro, deveria ser VIRGULA (ex: 1234,56 em vez de 1234.56). "
                    f"Casas decimais detectadas: {casas_str}",
                    "aviso",
                    {
                        "qtd_ponto_decimal": int(n_ponto),
                        "qtd_virgula_decimal": int(n_virgula),
                        "qtd_inteiros": int(n_inteiro),
                        "casas_decimais": list(sorted(casas_detectadas)),
                        "sugestao": f"Usar opcao 'Converter texto para numero interno' ou "
                                   f"'Formato brasileiro' para corrigir",
                        "exemplos_ponto": amostra[matches_ponto].head(5).tolist(),
                    },
                ))

            # CENARIO 2: Mix de ponto e virgula -> formatacao inconsistente
            elif n_ponto > 0 and n_virgula > 0:
                issues.append(DiagnosticIssue(
                    "NUMERO_PONTO_DECIMAL", col,
                    f"Formato numerico INCONSISTENTE: {n_ponto} valores com ponto decimal "
                    f"e {n_virgula} com virgula decimal na mesma coluna",
                    "critico",
                    {
                        "qtd_ponto_decimal": int(n_ponto),
                        "qtd_virgula_decimal": int(n_virgula),
                        "sugestao": "Unificar formato antes de manipular",
                    },
                ))

        return issues

    # ── FORMATOS NUMERICOS (MOEDA, %, ETC) ─────────────────────────────────

    def _checar_formatos_numericos(self, df: pd.DataFrame) -> list:
        issues = []
        for col in df.columns:
            if df[col].dtype == object:
                amostra = df[col].dropna().head(500)
                if amostra.empty:
                    continue

                tem_sinal_moeda = amostra.astype(str).str.contains(r"R\$", regex=False).any()
                tem_porcentagem = amostra.astype(str).str.contains(r"%", regex=False).any()
                tem_milhar_ponto_virgula = amostra.astype(str).str.contains(
                    r"^\d{1,3}(\.\d{3})+,\d+$", regex=True
                ).any()

                formatos = []
                if tem_sinal_moeda:
                    formatos.append("moeda (R$)")
                if tem_porcentagem:
                    formatos.append("porcentagem (%)")
                if tem_milhar_ponto_virgula:
                    formatos.append("milhar brasileiro (1.234,56)")

                if formatos:
                    issues.append(DiagnosticIssue(
                        "FORMATO_ESPECIAL", col,
                        f"Formato especial detectado: {', '.join(formatos)}",
                        "info", {"formatos": formatos},
                    ))
        return issues

    # ── TIPO DA COLUNA: NUMERO COMO TEXTO / TEXTO COMO NUMERO ─────────────

    def _checar_tipo_coluna(self, df: pd.DataFrame) -> list:
        issues = []
        for col in df.columns:
            amostra = df[col].dropna().head(1000)
            if amostra.empty or len(amostra) < 10:
                continue

            if df[col].dtype == object:
                self._checar_coluna_texto_deveria_ser_numero(amostra, col, issues)
            else:
                self._checar_coluna_numero_deveria_ser_texto(df[col], amostra, col, issues)

        return issues

    def _checar_coluna_texto_deveria_ser_numero(self, amostra: pd.Series, col: str, issues: list):
        """Detecta colunas de texto que na realidade contem numeros."""
        textos = amostra.astype(str).str.strip()

        # Padrao: numeros puros ou com decimais
        padrao_num = re.compile(r"^-?\d+([.,]\d+)?$")
        n_numericos = textos.apply(lambda x: bool(padrao_num.match(x))).sum()
        pct_numericos = n_numericos / len(textos) * 100

        if pct_numericos >= 80 and n_numericos >= 10:
            # Quase tudo numerico -> deveria ser tipo numero
            issues.append(DiagnosticIssue(
                "TIPO_TEXTO_NUMERO", col,
                f"Coluna e TEXTO mas {pct_numericos:.0f}% dos valores sao numericamente validos "
                f"({n_numericos}/{len(textos)}). Sugestao: converter para numero.",
                "aviso",
                {
                    "formato_atual": "texto/object",
                    "sugestao": "numero/float",
                    "exemplos": textos.head(5).tolist(),
                },
            ))
            return

        # Detecta: a maioria e numero, mas tem uns few outliers de texto
        if pct_numericos >= 50 and pct_numericos < 80:
            nao_numericos = textos[~textos.apply(lambda x: bool(padrao_num.match(x)))]
            exemplos = nao_numericos.unique()[:5].tolist()
            issues.append(DiagnosticIssue(
                "TIPO_TEXTO_NUMERO", col,
                f"Coluna e TEXTO com {pct_numericos:.0f}% numericos, mas {len(nao_numericos)} "
                f"valores nao sao numeros: {exemplos}. Possivel valor invalido ou tipo incorreto.",
                "aviso",
                {
                    "formato_atual": "texto/object",
                    "sugestao": "verificar valores nao numericos antes de converter",
                    "valores_nao_numericos": exemplos,
                },
            ))

        # Detecta: a maioria NAO e numero -> ok como texto, mas tem muitos numeros misturados
        elif 10 <= pct_numericos < 50:
            issues.append(DiagnosticIssue(
                "TIPO_TEXTO_NUMERO", col,
                f"Coluna e TEXTO com apenas {pct_numericos:.0f}% numericos ({n_numericos}/{len(textos)}). "
                f"Valores mistos — verificar se a coluna deveria ser numero.",
                "info",
                {
                    "formato_atual": "texto/object",
                    "exemplos_numericos": amostra[amostra.astype(str).str.match(padrao_num)].head(5).tolist(),
                },
            ))

    def _checar_coluna_numero_deveria_ser_texto(self, serie: pd.Series, amostra: pd.Series, col: str, issues: list):
        """Detecta colunas numericas que deveriam ser texto (codigo, CPF, telefone, etc)."""
        # So se a coluna ja e numerica (int/float)
        if serie.dtype not in (np.int64, np.float64, int, float):
            return

        # Se tem muitos valores unicos relativos ao total -> pode ser codigo/identificador
        unicos = serie.nunique()
        total = serie.count()
        if total == 0:
            return

        razao_unicos = unicos / total

        # Heuristica 1: valores inteiros longos (8+ digitos) parecem codigos/CPF/CNPJ
        if serie.dtype in (np.int64, int):
            valores_str = serie.dropna().astype(str)
            digitos_medios = valores_str.str.len().mean()
            if digitos_medios >= 8:
                issues.append(DiagnosticIssue(
                    "TIPO_NUMERO_TEXTO", col,
                    f"Coluna NUMERICA com media de {digitos_medios:.0f} digitos por valor. "
                    f"Parece CODIGO/IDENTIFICADOR (CPF, CNPJ, matricula) e nao valor numerico. "
                    f"Sugestao: converter para texto.",
                    "aviso",
                    {
                        "formato_atual": "numero",
                        "sugestao": "texto",
                        "digitos_medios": round(digitos_medios, 1),
                        "exemplos": valores_str.head(5).tolist(),
                    },
                ))
                return

        # Heuristica 2: todos inteiros, alta razao de unicos, sem zeros a esquerda
        if serie.dtype in (np.int64, int) and razao_unicos > 0.9:
            issues.append(DiagnosticIssue(
                "TIPO_NUMERO_TEXTO", col,
                f"Coluna NUMERICA com {unicos} valores unicos ({razao_unicos*100:.0f}% unicos). "
                f"Parece identificador/codigo, nao medida. Considere converter para texto.",
                "info",
                {
                    "formato_atual": "numero",
                    "sugestao": "verificar se e codigo (texto) ou valor (numero)",
                    "unicos": unicos,
                },
            ))

        # Heuristica 3: float com todos os valores inteiros (1.0, 2.0, 3.0)
        elif serie.dtype in (np.float64, float):
            inteiros = (serie.dropna() == serie.dropna().astype(int)).sum()
            total_float = serie.dropna().count()
            if total_float > 0 and inteiros / total_float > 0.95:
                issues.append(DiagnosticIssue(
                    "TIPO_NUMERO_TEXTO", col,
                    f"Coluna FLOAT com {inteiros/total_float*100:.0f}% valores inteiros ({inteiros}/{total_float}). "
                    f"Pode ser INT ou texto. Considere converter para inteiro ou texto.",
                    "info",
                    {
                        "formato_atual": "float",
                        "sugestao": "int ou texto",
                    },
                ))

    # ── VALORES SUSPEITOS ──────────────────────────────────────────────────

    def _checar_valores_suspeitos(self, df: pd.DataFrame) -> list:
        issues = []
        suspeitos = {
            "", "-", "--", "---", ".", "..", "...", "N/A", "NA", "n/a",
            "NULL", "null", "None", "none", "SEM DADO", "SEM VALOR",
            "NAO INFORMADO", "NAO DISPONIVEL", "0000-00-00", "00/00/0000",
            "S/N", "SN", "NI", "NR", "N/D", "N/R",
        }

        for col in df.columns:
            if df[col].dtype != object:
                continue
            valores = df[col].dropna().astype(str).str.strip().str.upper()
            encontrados = {}
            for s in suspeitos:
                count = (valores == s).sum()
                if count > 0:
                    encontrados[s] = int(count)

            if encontrados:
                total_suspeitos = sum(encontrados.values())
                issues.append(DiagnosticIssue(
                    "VALOR_SUSPEITO", col,
                    f"{total_suspeitos} valores suspeitos: {encontrados}",
                    "aviso" if total_suspeitos > 10 else "info",
                    {"valores": encontrados},
                ))
        return issues

    # ── TEXTO INCONSISTENTE ────────────────────────────────────────────────

    def _checar_texto_inconsistente(self, df: pd.DataFrame) -> list:
        issues = []
        for col in df.columns:
            if df[col].dtype != object:
                continue
            valores = df[col].dropna().astype(str).str.strip()
            if valores.empty:
                continue

            # Espacos incorretos
            tem_espaco_inicio = valores.str.match(r"^\s+").any()
            tem_espaco_fim = valores.str.match(r"\s+$").any()
            tem_espaco_meio = valores.str.contains(r"\s{2,}", regex=True).any()

            problemas = []
            if tem_espaco_inicio:
                problemas.append("espacos no inicio")
            if tem_espaco_fim:
                problemas.append("espacos no fim")
            if tem_espaco_meio:
                problemas.append("espacos extras no meio")

            if problemas:
                issues.append(DiagnosticIssue(
                    "TEXTO_ESPACO", col,
                    f"Espacos incorretos: {', '.join(problemas)}",
                    "info",
                ))

            # Caixa inconsistente
            maiusculas = (valores == valores.str.upper()).sum()
            minusculas = (valores == valores.str.lower()).sum()
            title_case = (valores == valores.str.title()).sum()
            total = len(valores)

            if maiusculas > total * 0.3 and minusculas > total * 0.3:
                issues.append(DiagnosticIssue(
                    "TEXTO_CASO", col,
                    f"Caixa INCONSISTENTE: {maiusculas} maiusculas, {minusculas} minusculas, "
                    f"{title_case} title case. Padronizar para um formato unico.",
                    "aviso",
                ))
            elif maiusculas > total * 0.8 and total > 5:
                issues.append(DiagnosticIssue(
                    "TEXTO_CASO", col,
                    f"Coluna predominantemente MAIUSCULO ({maiusculas/total*100:.0f}%)",
                    "info",
                ))

            # Acentuacao inconsistente
            tem_acento = valores.str.contains(r"[áàâãéêíóôõúç]", regex=True).any()
            tem_sem_acento = valores.str.contains(r"[a-zA-Z]", regex=True).any()
            if tem_acento and tem_sem_acento:
                # Verificar se existem versoes com e sem acento do mesmo termo
                pass  # Complexo demais para heuristica simples, fica no fuzzy match

        return issues

    # ── FUZZY MATCH COMPLETO ───────────────────────────────────────────────

    def _checar_fuzzy_match(self, df: pd.DataFrame) -> list:
        """
        Busca abrangente por padroes similares:
        - Erros de digitacao (teclado, troca de letras, acentos)
        - Siglas vs nomes completos
        - Nomes proprios com grafias diferentes
        - Abreviacoes inconsistentes
        """
        issues = []
        for col in df.columns:
            if df[col].dtype != object:
                continue
            valores = df[col].dropna().astype(str).str.strip().str.upper().unique()
            if len(valores) < 2 or len(valores) > 1000:
                continue

            grupos = self._agrupar_similares(valores)

            if grupos:
                # Filtrar grupos que tem mais de 1 variante
                grupos_filtrados = {k: v for k, v in grupos.items() if len(v) > 1}

                if grupos_filtrados:
                    total_pares = sum(len(v) - 1 for v in grupos_filtrados.values())
                    issues.append(DiagnosticIssue(
                        "FUZZY_MATCH", col,
                        f"{len(grupos_filtrados)} grupo(s) com valores similares "
                        f"({total_pares} variantes possiveis)",
                        "aviso",
                        {
                            "grupos": {k: v[:6] for k, v in list(grupos_filtrados.items())[:10]},
                            "sugestao": "Usar opcao 'Unificar valores similares' para corrigir",
                        },
                    ))

        return issues

    def _agrupar_similares(self, valores: np.ndarray) -> dict:
        """Agrupa valores similares usando multiplas metricas."""
        valores_lista = list(valores)
        pai = {v: v for v in valores_lista}

        def encontrar(x):
            while pai[x] != x:
                pai[x] = pai[pai[x]]
                x = pai[x]
            return x

        def unir(x, y):
            rx, ry = encontrar(x), encontrar(y)
            if rx != ry:
                pai[ry] = rx

        n = len(valores_lista)
        # Para listas grandes, otimiza: so compara ate 300
        limite = min(n, 300)

        for i in range(limite):
            for j in range(i + 1, limite):
                a, b = valores_lista[i], valores_lista[j]

                # Metrica 1: bigram similarity
                sim_bg = self._bigram_similarity(a, b)

                # Metrica 2: edicao normalizada
                sim_ed = self._edit_distance_normalized(a, b)

                # Metrica 3: tem a mesma "raiz" (primeiras N letras)
                sim_raiz = self._raiz_similar(a, b)

                # Combinacao: se qualquer metrica for forte o suficiente
                score = max(sim_bg, sim_ed, sim_raiz)
                if score >= 0.72:
                    unir(a, b)

        # Agrupar por raiz
        grupos = {}
        for v in valores_lista:
            raiz = encontrar(v)
            if raiz not in grupos:
                grupos[raiz] = []
            grupos[raiz].append(v)

        return grupos

    @staticmethod
    def _bigram_similarity(a: str, b: str) -> float:
        """Similaridade por bigramas (sequencias de 2 caracteres)."""
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        def bg(s):
            return [s[i:i+2] for i in range(len(s) - 1)]
        bg_a, bg_b = bg(a), bg(b)
        if not bg_a or not bg_b:
            return 1.0 if a in b or b in a else 0.0
        inter = sum(1 for x in bg_a if x in bg_b)
        total = len(bg_a) + len(bg_b)
        return (2.0 * inter) / total if total > 0 else 0.0

    @staticmethod
    def _edit_distance_normalized(a: str, b: str) -> float:
        """Distancia de Levenshtein normalizada (0=igual, 1=muito diferente)."""
        if a == b:
            return 1.0
        la, lb = len(a), len(b)
        if la == 0 or lb == 0:
            return 0.0

        # Matriz de programacao dinamica
        matriz = [[0] * (lb + 1) for _ in range(la + 1)]
        for i in range(la + 1):
            matriz[i][0] = i
        for j in range(lb + 1):
            matriz[0][j] = j

        for i in range(1, la + 1):
            for j in range(1, lb + 1):
                custo = 0 if a[i-1] == b[j-1] else 1
                matriz[i][j] = min(
                    matriz[i-1][j] + 1,
                    matriz[i][j-1] + 1,
                    matriz[i-1][j-1] + custo,
                )

        distancia = matriz[la][lb]
        max_len = max(la, lb)
        return 1.0 - (distancia / max_len) if max_len > 0 else 1.0

    @staticmethod
    def _raiz_similar(a: str, b: str) -> float:
        """
        Compara as raizes dos palavras (primeiras letras, consoantes raiz).
        util para: MORAIS/MORAES, JOSE/JOS, LUIZ/LUIS, PAULO/PAUL
        """
        def extrair_raiz(palavra):
            # Remove vogais repetidas, mantem consoantes e primeira letra
            if len(palavra) <= 2:
                return palavra
            raiz = palavra[0]
            for i in range(1, len(palavra)):
                if palavra[i] != palavra[i-1]:
                    raiz += palavra[i]
            return raiz

        raiz_a = extrair_raiz(a)
        raiz_b = extrair_raiz(b)

        if raiz_a == raiz_b:
            return 0.95

        # Compara primeiras N letras (ate 4)
        for n in range(min(len(a), len(b), 4), 1, -1):
            if a[:n] == b[:n]:
                return 0.75 + (n - 2) * 0.05

        return 0.0

    DiagnosticIssue = DiagnosticIssue

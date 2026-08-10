"""
Formatador de relatorios de diagnostico: transforma a lista de issues
em texto legivel, tabelas resumidas, e sugestoes automaticas de tratamento.
"""


class DiagnosticReport:
    """Formata o resultado do scanner em relatorio legivel + sugestoes."""

    def __init__(self, issues: list):
        self.issues = issues

    def resumo(self) -> str:
        """Resumo geral: contagem por gravidade e categoria."""
        if not self.issues:
            return "  Nenhum problema encontrado. Base parece saudavel."

        criticos = [i for i in self.issues if i.gravidade == "critico"]
        avisos = [i for i in self.issues if i.gravidade == "aviso"]
        infos = [i for i in self.issues if i.gravidade == "info"]

        linhas = []
        linhas.append(f"  Total de problemas: {len(self.issues)}")
        linhas.append(f"    Criticos: {len(criticos)}")
        linhas.append(f"    Avisos:   {len(avisos)}")
        linhas.append(f"    Info:     {len(infos)}")

        categorias = {}
        for i in self.issues:
            categorias[i.categoria] = categorias.get(i.categoria, 0) + 1
        linhas.append("")
        linhas.append("  Por categoria:")
        for cat, count in sorted(categorias.items(), key=lambda x: -x[1]):
            linhas.append(f"    {cat}: {count}")

        return "\n".join(linhas)

    def detalhado(self) -> str:
        """Relatorio detalhado com todos os problemas."""
        if not self.issues:
            return "  Nenhum problema encontrado."

        linhas = []
        ordem_grav = {"critico": 0, "aviso": 1, "info": 2}
        issues_ordenados = sorted(self.issues, key=lambda x: ordem_grav.get(x.gravidade, 3))

        for i, issue in enumerate(issues_ordenados, 1):
            icone = {"critico": "[!!!]", "aviso": "[ ! ]", "info": "[ i ]"}
            linhas.append(f"  {i:>3}. {icone.get(issue.gravidade, ' ? ')} {issue.categoria}")
            linhas.append(f"       Coluna: {issue.coluna}")
            linhas.append(f"       {issue.descricao}")

            if issue.detalhes:
                for chave, valor in issue.detalhes.items():
                    if isinstance(valor, list) and len(valor) > 3:
                        linhas.append(f"       {chave}: {valor[:5]}... (mais {len(valor)-5})")
                    else:
                        linhas.append(f"       {chave}: {valor}")
            linhas.append("")

        return "\n".join(linhas)

    def sugerir_tratamentos(self) -> list:
        """
        Gera lista de etapas sugeridas (no formato do Pipeline) com base
        nos problemas encontrados.
        """
        etapas_sugeridas = []
        categorias = {i.categoria for i in self.issues}

        if "NULOS" in categorias:
            cols_nulos = [i.coluna for i in self.issues if i.categoria == "NULOS"]
            etapas_sugeridas.append({
                "operacao": "remover_colunas_vazias",
                "params": {"limiar": 1.0},
                "descricao": "Remover colunas totalmente vazias",
            })

        if "COLUNA_VAZIA" in categorias:
            etapas_sugeridas.append({
                "operacao": "remover_colunas_vazias",
                "params": {"limiar": 1.0},
                "descricao": "Remover colunas 100% vazias",
            })

        if "DUPLICATAS" in categorias:
            etapas_sugeridas.append({
                "operacao": "remover_duplicatas",
                "params": {"normalizar": True},
                "descricao": "Remover linhas duplicadas",
            })

        if "FORMATO_NUMERICO" in categorias:
            cols_formato = [i.coluna for i in self.issues if i.categoria == "FORMATO_NUMERICO"]
            etapas_sugeridas.append({
                "operacao": "numero_interno",
                "params": {"colunas": cols_formato, "casas": 2},
                "descricao": f"Converter textos numéricos para numero: {cols_formato}",
            })

        if "VALOR_SUSPEITO" in categorias:
            for issue in self.issues:
                if issue.categoria == "VALOR_SUSPEITO":
                    valores_suspeitos = list(issue.detalhes.get("valores", {}).keys())
                    mapeamento = {v: "" for v in valores_suspeitos}
                    etapas_sugeridas.append({
                        "operacao": "substituir_valores",
                        "params": {"colunas": [issue.coluna], "mapeamento": mapeamento},
                        "descricao": f"Limpar valores suspeitos em '{issue.coluna}': {valores_suspeitos}",
                    })

        if "TEXTO_ESPACO" in categorias:
            cols_espaco = [i.coluna for i in self.issues if i.categoria == "TEXTO_ESPACO"]
            etapas_sugeridas.append({
                "operacao": "normalizar_texto",
                "params": {"colunas": cols_espaco, "modo": "upper"},
                "descricao": f"Normalizar espacos e caixa em: {cols_espaco}",
            })

        if "FUZZY_MATCH" in categorias:
            for issue in self.issues:
                if issue.categoria == "FUZZY_MATCH":
                    pares = issue.detalhes.get("pares", [])
                    if pares:
                        mapeamento = {}
                        for a, b, _ in pares:
                            mapeamento.setdefault(a, []).append(b)
                        etapas_sugeridas.append({
                            "operacao": "unificar_valores",
                            "params": {"coluna": issue.coluna, "mapeamento": mapeamento},
                            "descricao": f"Unificar valores similares em '{issue.coluna}'",
                        })

        return etapas_sugeridas

    def para_arquivo(self) -> str:
        """Gera conteudo para salvar em arquivo .txt."""
        linhas = []
        linhas.append("=" * 70)
        linhas.append("  RELATORIO DE DIAGNOSTICO — ETL NGR-SEE")
        linhas.append("=" * 70)
        linhas.append("")
        linhas.append(self.resumo())
        linhas.append("")
        linhas.append("-" * 70)
        linhas.append("  DETALHAMENTO")
        linhas.append("-" * 70)
        linhas.append(self.detalhado())
        linhas.append("-" * 70)
        linhas.append("  SUGESTOES DE TRATAMENTO")
        linhas.append("-" * 70)
        etapas = self.sugerir_tratamentos()
        if etapas:
            for i, etapa in enumerate(etapas, 1):
                linhas.append(f"  {i}. {etapa['descricao']}")
        else:
            linhas.append("  Nenhuma acao sugerida.")
        linhas.append("=" * 70)
        return "\n".join(linhas)

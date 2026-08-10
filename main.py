"""
Sistema de ETL — NGR-SEE

Fluxo:
  1. Menu inicial (carregar CSV ou converter XLSX)
  2. Diagnostico automatico da base
  3. Sugestoes de tratamento (com base no diagnostico)
  4. Limpeza / Manipulacao / Formulas
  5. Validacao
  6. Exportacao

Uso: python main.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.loaders import CSVLoader, ExcelConverter
from src.cleaning import CleaningRules
from src.pipeline import PipelineContext, Pipeline
from src.diagnostics import DiagnosticScanner, DiagnosticReport
from src.validation import DataValidator
from src.export import PowerBIExporter
from src.integrations import AuditLogger
from src.utils import configurar_logger

DIRETORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
PASTA_RAW = os.path.join(DIRETORIO_SCRIPT, "data", "raw")
PASTA_PROCESSED = os.path.join(DIRETORIO_SCRIPT, "data", "processed")


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITARIOS DE MENU
# ═══════════════════════════════════════════════════════════════════════════

def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def listar_arquivos(pasta: str = None) -> list:
    pasta = pasta or PASTA_RAW
    if not os.path.exists(pasta):
        return []
    return sorted(f for f in os.listdir(pasta)
                  if f.lower().endswith((".csv", ".xlsx", ".xls")))


def listar_csvs() -> list:
    if not os.path.exists(PASTA_RAW):
        return []
    return sorted(f for f in os.listdir(PASTA_RAW) if f.lower().endswith(".csv"))


def escolher_arquivo(arquivos: list, titulo: str = "Arquivos disponiveis") -> str:
    print(f"\n  {titulo}:")
    for i, nome in enumerate(arquivos, 1):
        caminho = os.path.join(PASTA_RAW, nome)
        if os.path.exists(caminho):
            tam = os.path.getsize(caminho)
            unidade = "MB" if tam > 1024 * 1024 else "KB"
            tam_fmt = tam / (1024 * 1024) if unidade == "MB" else tam / 1024
            print(f"  {i:>3}. {nome}  ({tam_fmt:.1f} {unidade})")
        else:
            print(f"  {i:>3}. {nome}")
    while True:
        opcao = input("\n  Numero do arquivo: ").strip()
        if opcao.isdigit() and 1 <= int(opcao) <= len(arquivos):
            return arquivos[int(opcao) - 1]
        print("  Opcao invalida.")


def escolher_colunas(colunas: list, pergunta: str) -> list:
    print(f"\n  {pergunta}")
    for i, col in enumerate(colunas, 1):
        print(f"  {i:>3}. {col}")
    print("    0. Pular / nenhuma")
    entrada = input("  Numeros (virgula): ").strip()
    if entrada in ("0", ""):
        return []
    try:
        indices = [int(x.strip()) for x in entrada.split(",")]
        return [colunas[i - 1] for i in indices if 1 <= i <= len(colunas)]
    except (ValueError, IndexError):
        print("  Entrada invalida.")
        return []


def sim_nao(pergunta: str) -> bool:
    return input(f"  {pergunta} (s/n): ").strip().lower() in ("s", "sim", "y", "yes")


def mostrar_estado(ctx: PipelineContext, titulo="Estado atual"):
    print(f"\n  --- {titulo} ---")
    print(f"  Linhas: {len(ctx.data)} | Colunas: {len(ctx.data.columns)}")
    if not ctx.data.empty:
        print(f"  Colunas: {list(ctx.data.columns)}")


# ═══════════════════════════════════════════════════════════════════════════
#  FLUXO: MENU INICIAL (CARREGAR / CONVERTER)
# ═══════════════════════════════════════════════════════════════════════════

def menu_inicial_carregar(ctx: PipelineContext, logger) -> bool:
    """Retorna True se carregou dados com sucesso."""
    print("\n" + "=" * 60)
    print("  CARREGAR DADOS")
    print("=" * 60)
    print("  1. Carregar CSV (de data/raw/)")
    print("  2. Converter Excel (.xlsx) para CSV e carregar")
    print("  3. Carregar de outra pasta")
    print("  0. Sair")
    opcao = input("\n  Opcao: ").strip()

    if opcao == "0":
        return False

    if opcao == "1":
        arquivos = listar_csvs()
        if not arquivos:
            print(f"\n  Nenhum .csv em '{PASTA_RAW}'.")
            print("  Copie os arquivos para essa pasta e rode novamente.")
            return False

        nome = escolher_arquivo(arquivos, "CSVs disponiveis")
        caminho = os.path.join(PASTA_RAW, nome)
        loader = CSVLoader(caminho, logger=logger)
        colunas_disponiveis = loader.listar_colunas()

        print(f"\n  Colunas em '{nome}':")
        for col in colunas_disponiveis:
            print(f"    - {col}")

        if sim_nao("  Carregar todas as colunas?"):
            colunas_sel = None
        else:
            colunas_sel = escolher_colunas(colunas_disponiveis, "Quais colunas?")
            if not colunas_sel:
                print("  Carregando todas.")
            else:
                colunas_sel = colunas_sel

        df = loader.carregar(colunas=colunas_sel)
        ctx.set_data(df, f"CSV carregado: {nome}")
        return True

    elif opcao == "2":
        # Converter XLSX -> CSV
        arquivos_xlsx = [f for f in listar_arquivos() if f.lower().endswith((".xlsx", ".xls"))]
        if not arquivos_xlsx:
            print(f"\n  Nenhum .xlsx em '{PASTA_RAW}'.")
            print("  Copie os arquivos Excel para essa pasta.")
            return False

        nome = escolher_arquivo(arquivos_xlsx, "Excel disponiveis")
        caminho = os.path.join(PASTA_RAW, nome)
        converter = ExcelConverter(logger=logger)

        sheets = converter.listar_sheets(caminho)
        if len(sheets) > 1:
            print(f"\n  Abas encontradas:")
            for i, s in enumerate(sheets, 1):
                print(f"    {i}. {s}")
            print(f"    0. Converter todas")
            esc = input("  Escolha a aba: ").strip()
            if esc == "0":
                caminhos = converter.converter_todas_sheets(caminho, PASTA_RAW)
                if caminhos:
                    print(f"\n  {len(caminhos)} CSVs gerados em data/raw/:")
                    for c in caminhos:
                        print(f"    - {os.path.basename(c)}")
                    return menu_inicial_carregar(ctx, logger)
                return False
            elif esc.isdigit() and 1 <= int(esc) <= len(sheets):
                sheet = sheets[int(esc) - 1]
            else:
                sheet = sheets[0]
        else:
            sheet = sheets[0] if sheets else 0

        nome_csv = input(f"  Nome para o CSV (padrao: {os.path.splitext(nome)[0]}): ").strip()
        if not nome_csv:
            nome_csv = os.path.splitext(nome)[0]

        caminho_csv = converter.converter(caminho, PASTA_RAW, sheet=sheet, nome_saida=nome_csv)
        print(f"\n  CSV gerado: {os.path.basename(caminho_csv)}")

        loader = CSVLoader(caminho_csv, logger=logger)
        df = loader.carregar()
        ctx.set_data(df, f"Excel convertido e carregado: {nome}")
        return True

    elif opcao == "3":
        pasta = input("  Caminho da pasta: ").strip()
        if not os.path.isdir(pasta):
            print("  Pasta nao encontrada.")
            return False
        arquivos = sorted(f for f in os.listdir(pasta) if f.lower().endswith(".csv"))
        if not arquivos:
            print("  Nenhum .csv na pasta.")
            return False
        nome = escolher_arquivo(arquivos, "CSVs na pasta")
        caminho = os.path.join(pasta, nome)
        loader = CSVLoader(caminho, logger=logger)
        df = loader.carregar()
        ctx.set_data(df, f"CSV carregado: {nome}")
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════════
#  FLUXO: DIAGNOSTICO
# ═══════════════════════════════════════════════════════════════════════════

def fluxo_diagnostico(ctx: PipelineContext, logger) -> list:
    """Roda diagnostico e retorna etapas sugeridas."""
    print("\n" + "=" * 60)
    print("  DIAGNOSTICO DA BASE")
    print("=" * 60)
    print("  Analisando dados...")

    scanner = DiagnosticScanner(logger=logger)
    issues = scanner.escanear(ctx.data)

    report = DiagnosticReport(issues)
    print("\n" + report.resumo())

    if issues:
        print("\n  Ver detalhes? (mostra todos os problemas encontrados)")
        if sim_nao("  Mostrar detalhes?"):
            print("\n" + report.detalhado())

        etapas_sugeridas = report.sugerir_tratamentos()
        if etapas_sugeridas:
            print("\n  --- SUGESTOES DE TRATAMENTO ---")
            for i, etapa in enumerate(etapas_sugeridas, 1):
                print(f"  {i}. {etapa['descricao']}")
            print(f"  0. Ignorar sugestoes e tratar manualmente")

            return etapas_sugeridas
    else:
        print("\n  Base saudavel! Nenhum problema critico encontrado.")

    return []


# ═══════════════════════════════════════════════════════════════════════════
#  FLUXO: LIMPEZA
# ═══════════════════════════════════════════════════════════════════════════

def menu_limpeza(ctx: PipelineContext, pipeline: Pipeline) -> list:
    etapas = []

    while True:
        print("\n" + "=" * 60)
        print("  LIMPEZA DE DADOS")
        print("=" * 60)
        print("  1. Formatar numeros (virgula brasileira)")
        print("  2. Converter texto para numero interno")
        print("  3. Detectar duplicatas")
        print("  4. Remover duplicatas")
        print("  5. Encontrar valores similares (fuzzy match)")
        print("  6. Unificar valores similares")
        print("  7. Remover colunas totalmente vazias")
        print("  8. Tratar valores nulos (preencher/remover)")
        print("  9. Substituir valores (exato)")
        print(" 10. Substituir por regex")
        print(" 11. Normalizar texto (maiusculo/minusculo)")
        print(" 12. Corrigir tipo de coluna")
        print("  0. Voltar")
        opcao = input("\n  Opcao: ").strip()

        if opcao == "0":
            break

        colunas = list(ctx.data.columns)

        if opcao == "1":
            cols = escolher_colunas(colunas, "Colunas para formato brasileiro:")
            if cols:
                casas = input("  Casas decimais (padrao 2): ").strip()
                etapas.append({"operacao": "formatar_brasileiro",
                               "params": {"colunas": cols, "casas": int(casas) if casas else 2}})

        elif opcao == "2":
            cols = escolher_colunas(colunas, "Colunas para converter em numero:")
            if cols:
                etapas.append({"operacao": "numero_interno",
                               "params": {"colunas": cols, "casas": 2}})

        elif opcao == "3":
            cols = escolher_colunas(colunas, "Colunas para checar (vazio = todas):")
            etapas.append({"operacao": "detectar_duplicatas",
                           "params": {"colunas": cols or None, "normalizar": True}})

        elif opcao == "4":
            cols = escolher_colunas(colunas, "Colunas para checar (vazio = todas):")
            etapas.append({"operacao": "remover_duplicatas",
                           "params": {"colunas": cols or None, "normalizar": True}})

        elif opcao == "5":
            col = input("  Coluna para fuzzy match: ").strip()
            if col and col in colunas:
                limiar = input("  Limiar (0.0-1.0, padrao 0.85): ").strip()
                etapas.append({"operacao": "valores_similares",
                               "params": {"coluna": col, "limiar": float(limiar) if limiar else 0.85}})

        elif opcao == "6":
            col = input("  Coluna para unificar: ").strip()
            if col and col in colunas:
                regras = CleaningRules(ctx.logger)
                sugestoes = regras.sugerir_unificacao(ctx.data, col)
                if sugestoes:
                    print("  Sugestoes automaticas:")
                    for correto, vars in sugestoes.items():
                        print(f"    {correto} <- {vars}")
                    if sim_nao("  Usar sugestoes automaticas?"):
                        mapeamento = sugestoes
                    else:
                        mapeamento = {}
                else:
                    mapeamento = {}

                if not mapeamento:
                    print("  Adicione pares (CORRETO -> VARIANTE). 'fim' para terminar.")
                    while True:
                        certo = input("  Valor CORRETO (ou 'fim'): ").strip()
                        if certo.lower() == "fim":
                            break
                        variante = input(f"  Variante de '{certo}': ").strip()
                        mapeamento.setdefault(certo, []).append(variante)

                if mapeamento:
                    etapas.append({"operacao": "unificar_valores",
                                   "params": {"coluna": col, "mapeamento": mapeamento}})

        elif opcao == "7":
            limiar = input("  Limiar (0.0-1.0, padrao 1.0): ").strip()
            etapas.append({"operacao": "remover_colunas_vazias",
                           "params": {"limiar": float(limiar) if limiar else 1.0}})

        elif opcao == "8":
            cols = escolher_colunas(colunas, "Colunas com nulos:")
            if cols:
                print("\n  Como tratar?")
                print("    1. Valor fixo (0, '-', 'NAO INFORMADO', etc)")
                print("    2. Mediana (apenas numeros)")
                print("    3. Moda (valor mais frequente)")
                print("    4. Remover linhas com nulo")
                print("    5. Deixar vazio")
                estrategia = input("  Opcao: ").strip()

                if estrategia == "4":
                    etapas.append({"operacao": "remover_nulos", "params": {"colunas": cols}})
                elif estrategia == "5":
                    etapas.append({"operacao": "preencher_nulos",
                                   "params": {"estrategias": {c: "" for c in cols}}})
                else:
                    estrategias = {}
                    for c in cols:
                        if estrategia == "1":
                            v = input(f"    Valor para '{c}': ").strip()
                            estrategias[c] = v if v else ""
                        elif estrategia == "2":
                            estrategias[c] = "mediana"
                        else:
                            estrategias[c] = "moda"
                    etapas.append({"operacao": "preencher_nulos",
                                   "params": {"estrategias": estrategias}})

        elif opcao == "9":
            cols = escolher_colunas(colunas, "Colunas para substituicao:")
            if cols:
                mapeamento = {}
                while True:
                    antigo = input("  Valor antigo (ou 'fim'): ").strip()
                    if antigo.lower() == "fim":
                        break
                    novo = input(f"  Novo valor para '{antigo}': ").strip()
                    mapeamento[antigo] = novo
                if mapeamento:
                    etapas.append({"operacao": "substituir_valores",
                                   "params": {"colunas": cols, "mapeamento": mapeamento}})

        elif opcao == "10":
            cols = escolher_colunas(colunas, "Colunas para regex:")
            if cols:
                padrao = input("  Padrao regex: ").strip()
                novo = input("  Substituicao: ").strip()
                etapas.append({"operacao": "substituir_regex",
                               "params": {"colunas": cols, "padrao": padrao, "novo": novo}})

        elif opcao == "11":
            cols = escolher_colunas(colunas, "Colunas de texto:")
            if cols:
                modo = input("  Modo (1=MAIUSCULO, 2=minusculo): ").strip()
                m = "upper" if modo != "2" else "lower"
                etapas.append({"operacao": "normalizar_texto",
                               "params": {"colunas": cols, "modo": m}})

        elif opcao == "12":
            cols = escolher_colunas(colunas, "Colunas para corrigir tipo:")
            if cols:
                tipos = {}
                for c in cols:
                    print(f"  '{c}' — 1:numero  2:texto  3:data")
                    t = input("    Tipo: ").strip()
                    tipos[c] = {"1": "numero", "2": "texto", "3": "data"}.get(t, "texto")
                etapas.append({"operacao": "corrigir_tipo", "params": {"tipos": tipos}})

        if etapas:
            mostrar_estado(ctx, "Apos etapa")

    return etapas


# ═══════════════════════════════════════════════════════════════════════════
#  FLUXO: MANIPULACAO / FORMULAS
# ═══════════════════════════════════════════════════════════════════════════

def menu_manipulacao(ctx: PipelineContext, pipeline: Pipeline) -> list:
    engine = FormulaEngine(ctx.logger)
    etapas = []

    while True:
        print("\n" + "=" * 60)
        print("  MANIPULACAO / FORMULAS EXCEL")
        print("=" * 60)
        print("  --- Busca ---")
        print("  1. PROCV (VLOOKUP)")
        print("  2. PROCV agrupado")
        print("  3. CORRESP (MATCH)")
        print("  --- Texto ---")
        print("  4. ESQUERDA (LEFT)")
        print("  5. DIREITA (RIGHT)")
        print("  6. MEIO (MID)")
        print("  7. TAMANHO (LEN)")
        print("  8. CONCATENAR")
        print("  9. SUBSTITUIR (SUBSTITUTE)")
        print("  --- Logica ---")
        print(" 10. SE (IF)")
        print("  --- Numeros ---")
        print(" 11. ARRED (ROUND)")
        print(" 12. CONT.SE (COUNTIF)")
        print(" 13. SOMASE (SUMIF)")
        print(" 14. Coluna calculada (expressao)")
        print("  --- Tabelas ---")
        print(" 15. Registrar tabela referencia")
        print(" 16. Juntar tabela (JOIN)")
        print("  0. Voltar")
        opcao = input("\n  Opcao: ").strip()

        if opcao == "0":
            break

        colunas = list(ctx.data.columns)

        if opcao == "1":
            tabelas = ctx.list_tabelas()
            if not tabelas:
                print("  Registre uma tabela de referencia primeiro (opcao 15).")
                continue
            print(f"  Tabelas: {tabelas}")
            tab = input("  Tabela referencia: ").strip()
            print(f"  Colunas atuais: {colunas}")
            chave = input("  Coluna CHAVE atual: ").strip()
            tab_df = ctx.get_tabela(tab)
            if tab_df.empty:
                print("  Tabela nao encontrada.")
                continue
            print(f"  Colunas ref '{tab}': {list(tab_df.columns)}")
            chave_ref = input("  Coluna CHAVE ref: ").strip()
            valor_ref = input("  Coluna VALOR a puxar: ").strip()
            padrao = input("  Se nao encontrar (vazio = vazio): ").strip()
            etapas.append({"operacao": "procv", "params": {
                "tabela_origem": tab, "coluna_chave": chave,
                "coluna_chave_origem": chave_ref, "coluna_valor_origem": valor_ref,
                "padrao": padrao,
            }})

        elif opcao == "2":
            tabelas = ctx.list_tabelas()
            if not tabelas:
                print("  Registre uma tabela de referencia primeiro.")
                continue
            print(f"  Tabelas: {tabelas}")
            tab = input("  Tabela referencia: ").strip()
            print(f"  Colunas atuais: {colunas}")
            chave = input("  Coluna CHAVE atual: ").strip()
            tab_df = ctx.get_tabela(tab)
            print(f"  Colunas ref '{tab}': {list(tab_df.columns)}")
            chave_ref = input("  Coluna CHAVE ref: ").strip()
            valor_ref = input("  Coluna VALOR ref: ").strip()
            func = input("  Funcao (soma/media/contagem/min/max/mediana): ").strip() or "soma"
            etapas.append({"operacao": "procv_agrupado", "params": {
                "tabela_origem": tab, "coluna_chave": chave,
                "coluna_chave_origem": chave_ref, "coluna_valor_origem": valor_ref,
                "funcao": func,
            }})

        elif opcao == "3":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna de busca: ").strip()
            valor = input("  Valor a encontrar: ").strip()
            etapas.append({"operacao": "corresp", "params": {"valor": valor, "coluna_busca": col}})

        elif opcao == "4":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            n = int(input("  N caracteres: ").strip())
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "esquerda", "params": {"coluna": col, "n": n, "nova_coluna": nova}})

        elif opcao == "5":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            n = int(input("  N caracteres: ").strip())
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "direita", "params": {"coluna": col, "n": n, "nova_coluna": nova}})

        elif opcao == "6":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            inicio = int(input("  Posicao inicial (1-based): ").strip())
            n = int(input("  N caracteres: ").strip())
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "meio", "params": {"coluna": col, "inicio": inicio, "n": n, "nova_coluna": nova}})

        elif opcao == "7":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "tamanho", "params": {"coluna": col, "nova_coluna": nova}})

        elif opcao == "8":
            cols = escolher_colunas(colunas, "Colunas para concatenar:")
            if cols:
                sep = input("  Separador (vazio=nenhum): ").strip()
                nome = input("  Nome coluna resultado: ").strip() or "concat"
                etapas.append({"operacao": "concatenar",
                               "params": {"colunas": cols, "separador": sep, "nova_coluna": nome}})

        elif opcao == "9":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            antigo = input("  Texto antigo: ").strip()
            novo = input("  Texto novo: ").strip()
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "substituir_texto",
                           "params": {"coluna": col, "antigo": antigo, "novo": novo, "nova_coluna": nova}})

        elif opcao == "10":
            print(f"\n  Colunas: {colunas}")
            print("  Condicao: col_a > 100, col_b == 'SIM', col_c.notna()")
            cond = input("  Condicao: ").strip()
            v_verd = input("  Se VERDADEIRO: ").strip()
            v_fals = input("  Se FALSO: ").strip()
            nome = input("  Nome coluna (padrao: resultado_se): ").strip() or "resultado_se"
            etapas.append({"operacao": "se", "params": {
                "condicao": cond, "valor_verdadeiro": v_verd,
                "valor_falso": v_fals, "nova_coluna": nome,
            }})

        elif opcao == "11":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            casas = input("  Casas decimais (padrao 0): ").strip()
            nova = input("  Nome nova coluna (vazio=auto): ").strip() or None
            etapas.append({"operacao": "arred",
                           "params": {"coluna": col, "casas": int(casas) if casas else 0, "nova_coluna": nova}})

        elif opcao == "12":
            print(f"  Colunas: {colunas}")
            col = input("  Coluna: ").strip()
            crit = input("  Criterio (>100, APROVADO, !=0): ").strip()
            etapas.append({"operacao": "cont_se", "params": {"coluna": col, "criterio": crit}})

        elif opcao == "13":
            print(f"  Colunas: {colunas}")
            col_val = input("  Coluna VALORES: ").strip()
            col_crit = input("  Coluna CRITERIOS: ").strip()
            crit = input("  Criterio: ").strip()
            etapas.append({"operacao": "somase",
                           "params": {"coluna_valores": col_val, "coluna_criterios": col_crit, "criterio": crit}})

        elif opcao == "14":
            mostrar_estado(ctx)
            print("\n  Expressoes: col_a + col_b, col_a / col_b * 100,")
            print("  np.where(col_a > 10, 'alto', 'baixo'), col_a.str.upper()")
            nome = input("  Nome nova coluna: ").strip()
            expr = input("  Expressao: ").strip()
            if nome and expr:
                etapas.append({"operacao": "coluna_calculada",
                               "params": {"nome": nome, "expressao": expr}})

        elif opcao == "15":
            arquivos = listar_csvs()
            if not arquivos:
                print("  Nenhum CSV disponivel.")
                continue
            print("  Selecione o arquivo para registrar como referencia:")
            nome_tab = escolher_arquivo(arquivos)
            caminho = os.path.join(PASTA_RAW, nome_tab)
            loader_temp = CSVLoader(caminho, logger=ctx.logger)
            df_ref = loader_temp.carregar()
            nome_reg = input(f"  Nome para registrar (padrao: {os.path.splitext(nome_tab)[0]}): ").strip()
            if not nome_reg:
                nome_reg = os.path.splitext(nome_tab)[0]
            ctx.registrar_tabela(nome_reg, df_ref)

        elif opcao == "16":
            tabelas = ctx.list_tabelas()
            if not tabelas:
                print("  Registre tabelas primeiro (opcao 15).")
                continue
            print(f"  Tabelas: {tabelas}")
            tab = input("  Tabela para juntar: ").strip()
            print(f"  Colunas atuais: {colunas}")
            chave = input("  Coluna CHAVE (JOIN ON): ").strip()
            tipo = input("  Tipo (left/inner/outer, padrao left): ").strip() or "left"
            etapas.append({"operacao": "juntar",
                           "params": {"tabela": tab, "coluna_chave": chave, "tipo": tipo}})

        if etapas:
            mostrar_estado(ctx, "Apos etapa")

    return etapas


# ═══════════════════════════════════════════════════════════════════════════
#  PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════

def main():
    logger = configurar_logger()
    ctx = PipelineContext(logger=logger)
    pipeline = Pipeline(ctx, logger=logger)
    audit = AuditLogger()

    print("\n" + "=" * 60)
    print("  SISTEMA DE ETL — NGR-SEE")
    print("=" * 60)

    # ── 1. CARREGAR ────────────────────────────────────────────────────────
    if not menu_inicial_carregar(ctx, logger):
        return

    df_original = ctx.get_data()
    ctx.registrar_snapshot_inicial()
    audit.registrar_etapa("carga", {"linhas": len(ctx.data), "colunas": list(ctx.data.columns)}, "ok")

    # ── 2. DIAGNOSTICO ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  DIAGNOSTICO AUTOMATICO")
    print("=" * 60)

    etapas_sugeridas = fluxo_diagnostico(ctx, logger)
    audit.registrar_etapa("diagnostico", {"problemas": len(etapas_sugeridas)}, "ok")

    # ── 3. APLICAR SUGESTOES ──
    if etapas_sugeridas:
        print("\n  Deseja aplicar as sugestoes automaticas?")
        print("  (voce podera ajustar manualmente depois)")
        if sim_nao("  Aplicar sugestoes?"):
            print(f"\n  Executando {len(etapas_sugeridas)} sugestao(es)...")
            resultados = pipeline.executar_etapas(etapas_sugeridas)
            for i, r in enumerate(resultados, 1):
                print(f"    {i}. {r}")
            mostrar_estado(ctx, "Apos sugestoes aplicadas")

    # ── 4. LIMPEZA ─────────────────────────────────────────────────────────
    if sim_nao("\n  Deseja aplicar limpeza adicional?"):
        etapas_limpeza = menu_limpeza(ctx, pipeline)
        if etapas_limpeza:
            print(f"\n  Executando {len(etapas_limpeza)} etapa(s)...")
            resultados = pipeline.executar_etapas(etapas_limpeza)
            for i, r in enumerate(resultados, 1):
                print(f"    {i}. {r}")

    # ── 5. MANIPULACAO / FORMULAS ──────────────────────────────────────────
    if sim_nao("\n  Deseja aplicar manipulacao / formulas?"):
        etapas_manip = menu_manipulacao(ctx, pipeline)
        if etapas_manip:
            print(f"\n  Executando {len(etapas_manip)} etapa(s)...")
            resultados = pipeline.executar_etapas(etapas_manip)
            for i, r in enumerate(resultados, 1):
                print(f"    {i}. {r}")

    # ── 6. VALIDACAO ───────────────────────────────────────────────────────
    validator = DataValidator(logger=logger)
    resultado = validator.validar(ctx.data, linhas_minimas_esperadas=1)

    if not resultado["aprovado"]:
        print("\n  Alertas de validacao:")
        for alerta in resultado["alertas"]:
            print(f"    - {alerta}")
        if not sim_nao("  Exportar mesmo assim?"):
            print("  Exportacao cancelada.")
            return

    # ── 7. EXPORTAR ────────────────────────────────────────────────────────
    nome_base = input("\n  Nome para o arquivo de saida: ").strip()
    if not nome_base:
        nome_base = "etl_exportado"

    exporter = PowerBIExporter(PASTA_PROCESSED, logger=logger)
    caminho_final = exporter.exportar(ctx.data, nome_base)

    # ── 8. RELATORIO FINAL ────────────────────────────────────────────────
    print(ctx.relatorio_final())

    # ── 9. AUDIT ───────────────────────────────────────────────────────────
    audit.finalizar(
        arquivo_entrada=df_original.columns[0] if not df_original.empty else "",
        arquivo_saida=caminho_final,
        linhas_entrada=len(df_original),
        linhas_saida=len(ctx.data),
        status="sucesso",
    )

    print(f"\n  Arquivo exportado: {caminho_final}")
    print("\n" + ctx.relatorio())
    logger.info("Execucao finalizada com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Execucao interrompida.")
    except Exception as e:
        print(f"\n  Erro: {e}")
        raise

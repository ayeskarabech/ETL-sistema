"""
App Web — ETL NGR-SEE
FastAPI + Jinja2 + Glassmorphism
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.loaders import CSVLoader, ExcelConverter
from src.cleaning import CleaningRules
from src.pipeline import PipelineContext, Pipeline
from src.diagnostics import DiagnosticScanner, DiagnosticReport
from src.validation import DataValidator
from src.export import PowerBIExporter
from src.utils import configurar_logger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_RAW = os.path.join(BASE_DIR, "..", "data", "raw")
PASTA_PROCESSED = os.path.join(BASE_DIR, "..", "data", "processed")
PASTA_UPLOADS = os.path.join(BASE_DIR, "..", "data", "uploads")

os.makedirs(PASTA_RAW, exist_ok=True)
os.makedirs(PASTA_PROCESSED, exist_ok=True)
os.makedirs(PASTA_UPLOADS, exist_ok=True)

app = FastAPI(title="ETL NGR-SEE", docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

sessions: dict = {}


def get_session(session_id: str):
    if session_id not in sessions:
        logger = configurar_logger()
        ctx = PipelineContext(logger=logger)
        pipeline = Pipeline(ctx, logger=logger)
        sessions[session_id] = {
            "ctx": ctx,
            "pipeline": pipeline,
            "logger": logger,
            "arquivo": None,
            "etapas_limpeza": [],
            "etapas_manip": [],
            "diagnostico": None,
            "etapas_sugeridas": [],
        }
    return sessions[session_id]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    session_id = str(uuid.uuid4())[:8]
    sessao = get_session(session_id)
    response = RedirectResponse(url=f"/app/{session_id}", status_code=302)
    return response


@app.get("/app/{session_id}", response_class=HTMLResponse)
async def app_page(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    colunas = list(ctx.data.columns) if not ctx.data.empty else []
    tem_dados = not ctx.data.empty
    arquivo = sessao.get("arquivo")

    return templates.TemplateResponse(request, "base.html", {
        "session_id": session_id,
        "colunas": colunas,
        "tem_dados": tem_dados,
        "arquivo": arquivo,
        "pasta_processed": PASTA_PROCESSED,
    })


@app.post("/upload/{session_id}")
async def upload_file(request: Request, session_id: str, arquivo: UploadFile = File(...)):
    sessao = get_session(session_id)

    ext = os.path.splitext(arquivo.filename)[1].lower()
    nome_seguro = f"{session_id}_{arquivo.filename}"
    caminho = os.path.join(PASTA_UPLOADS, nome_seguro)

    CHUNK_SIZE = 1024 * 1024
    total_bytes = 0
    with open(caminho, "wb") as f:
        while True:
            chunk = await arquivo.read(CHUNK_SIZE)
            if not chunk:
                break
            f.write(chunk)
            total_bytes += len(chunk)

    sessao["arquivo"] = arquivo.filename
    sessao["caminho_upload"] = caminho
    sessao["extensao"] = ext
    sessao["upload_status"] = "salvo"

    return JSONResponse({
        "ok": True,
        "mensagem": f"Arquivo '{arquivo.filename}' salvo ({total_bytes / 1024 / 1024:.1f} MB). Clique em 'Carregar' para processar.",
        "caminho": caminho,
    })


@app.post("/load/{session_id}")
async def load_file(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    caminho = sessao.get("caminho_upload")
    ext = sessao.get("extensao", "")
    arquivo = sessao.get("arquivo", "")

    if not caminho or not os.path.exists(caminho):
        return JSONResponse({"ok": False, "mensagem": "Nenhum arquivo salvo. Faca upload primeiro."}, status_code=400)

    sessao["upload_status"] = "carregando"

    def _carregar():
        if ext in (".xlsx", ".xls"):
            converter = ExcelConverter(logger=sessao["logger"])
            sheets = converter.listar_sheets(caminho)
            caminho_csv = converter.converter(caminho, PASTA_UPLOADS, sheet=sheets[0], nome_saida=os.path.splitext(os.path.basename(caminho))[0])
            loader = CSVLoader(caminho_csv, logger=sessao["logger"])
        else:
            loader = CSVLoader(caminho, logger=sessao["logger"])
        return loader.carregar()

    try:
        df = await asyncio.to_thread(_carregar)
        ctx.set_data(df, f"Arquivo carregado: {arquivo}")
        ctx.registrar_snapshot_inicial()
        sessao["upload_status"] = "ok"

        return JSONResponse({
            "ok": True,
            "linhas": len(df),
            "colunas": list(df.columns),
            "mensagem": f"Arquivo '{arquivo}' carregado com sucesso.",
        })
    except Exception as e:
        sessao["upload_status"] = "erro"
        return JSONResponse({"ok": False, "mensagem": str(e)}, status_code=400)


@app.get("/upload_status/{session_id}")
async def upload_status(request: Request, session_id: str):
    sessao = get_session(session_id)
    return JSONResponse({
        "ok": True,
        "status": sessao.get("upload_status", "nenhum"),
        "arquivo": sessao.get("arquivo"),
    })


@app.get("/diagnostico/{session_id}")
async def diagnostico(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    if ctx.data.empty:
        return JSONResponse({"ok": False, "mensagem": "Nenhum dado carregado."}, status_code=400)

    scanner = DiagnosticScanner(logger=sessao["logger"])
    issues = scanner.escanear(ctx.data)
    report = DiagnosticReport(issues)

    etapas_sugeridas = report.sugerir_tratamentos() if issues else []
    sessao["etapas_sugeridas"] = etapas_sugeridas

    return JSONResponse({
        "ok": True,
        "problemas": len(issues),
        "resumo": report.resumo(),
        "detalhado": report.detalhado() if issues else "",
        "sugestoes": [
            {"descricao": e.get("descricao", ""), "operacao": e.get("operacao", ""), "params": e.get("params", {})}
            for e in etapas_sugeridas
        ],
    })


@app.post("/aplicar_sugestoes/{session_id}")
async def aplicar_sugestoes(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]
    pipeline = sessao["pipeline"]

    if not sessao["etapas_sugeridas"]:
        return JSONResponse({"ok": False, "mensagem": "Nenhuma sugestao disponivel."}, status_code=400)

    resultados = pipeline.executar_etapas(sessao["etapas_sugeridas"])
    logs = pipeline.flush_log()

    return JSONResponse({
        "ok": True,
        "resultados": [str(r) for r in resultados],
        "linhas": len(ctx.data),
        "colunas": list(ctx.data.columns),
    })


@app.post("/limpeza/{session_id}")
async def adicionar_limpeza(request: Request, session_id: str):
    data = await request.json()
    sessao = get_session(session_id)

    etapa = {"operacao": data["operacao"], "params": data["params"]}
    sessao["etapas_limpeza"].append(etapa)

    return JSONResponse({"ok": True, "mensagem": f"Etapa '{data['operacao']}' adicionada."})


@app.post("/executar_limpeza/{session_id}")
async def executar_limpeza(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]
    pipeline = sessao["pipeline"]

    if not sessao["etapas_limpeza"]:
        return JSONResponse({"ok": False, "mensagem": "Nenhuma etapa de limpeza pendente."}, status_code=400)

    resultados = pipeline.executar_etapas(sessao["etapas_limpeza"])
    logs = pipeline.flush_log()
    sessao["etapas_limpeza"] = []

    return JSONResponse({
        "ok": True,
        "resultados": [str(r) for r in resultados],
        "linhas": len(ctx.data),
        "colunas": list(ctx.data.columns),
    })


@app.post("/manipulacao/{session_id}")
async def adicionar_manipulacao(request: Request, session_id: str):
    data = await request.json()
    sessao = get_session(session_id)

    etapa = {"operacao": data["operacao"], "params": data["params"]}
    sessao["etapas_manip"].append(etapa)

    return JSONResponse({"ok": True, "mensagem": f"Etapa '{data['operacao']}' adicionada."})


@app.post("/executar_manipulacao/{session_id}")
async def executar_manipulacao(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]
    pipeline = sessao["pipeline"]

    if not sessao["etapas_manip"]:
        return JSONResponse({"ok": False, "mensagem": "Nenhuma etapa de manipulacao pendente."}, status_code=400)

    resultados = pipeline.executar_etapas(sessao["etapas_manip"])
    logs = pipeline.flush_log()
    sessao["etapas_manip"] = []

    return JSONResponse({
        "ok": True,
        "resultados": [str(r) for r in resultados],
        "linhas": len(ctx.data),
        "colunas": list(ctx.data.columns),
    })


@app.get("/preview/{session_id}")
async def preview(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    if ctx.data.empty:
        return JSONResponse({"ok": False, "mensagem": "Nenhum dado."}, status_code=400)

    df = ctx.data.head(50)
    colunas = list(df.columns)
    linhas = df.fillna("").values.tolist()

    return JSONResponse({
        "ok": True,
        "colunas": colunas,
        "linhas": linhas,
        "total_linhas": len(ctx.data),
        "total_colunas": len(ctx.data.columns),
    })


@app.get("/listar_pastas")
async def listar_pastas(caminho: str = ""):
    if not caminho:
        caminho = os.path.expanduser("~")
    try:
        itens = []
        for nome in sorted(os.listdir(caminho)):
            completo = os.path.join(caminho, nome)
            if os.path.isdir(completo):
                itens.append({"nome": nome, "caminho": completo})
        pai = os.path.dirname(caminho.rstrip(os.sep))
        return JSONResponse({
            "ok": True,
            "caminho": caminho,
            "pai": pai if pai != caminho else None,
            "pastas": itens,
        })
    except PermissionError:
        return JSONResponse({"ok": False, "mensagem": "Sem permissao de acesso."}, status_code=403)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "mensagem": "Caminho nao encontrado."}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "mensagem": str(e)}, status_code=400)


@app.get("/exportar/{session_id}")
async def exportar(request: Request, session_id: str, pasta: str = ""):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    if ctx.data.empty:
        return JSONResponse({"ok": False, "mensagem": "Nenhum dado para exportar."}, status_code=400)

    validator = DataValidator(logger=sessao["logger"])
    resultado = validator.validar(ctx.data, linhas_minimas_esperadas=1)

    pasta_destino = pasta.strip() if pasta.strip() else PASTA_PROCESSED
    if not os.path.isdir(pasta_destino):
        try:
            os.makedirs(pasta_destino, exist_ok=True)
        except Exception as e:
            return JSONResponse({"ok": False, "mensagem": f"Erro ao criar pasta: {e}"}, status_code=400)

    exporter = PowerBIExporter(pasta_destino, logger=sessao["logger"])
    nome_base = f"etl_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    caminho = exporter.exportar(ctx.data, nome_base)

    return JSONResponse({
        "ok": True,
        "aprovado": resultado["aprovado"],
        "alertas": resultado.get("alertas", []),
        "arquivo": os.path.basename(caminho),
        "caminho_completo": caminho,
        "pasta_destino": pasta_destino,
        "linhas": len(ctx.data),
        "colunas": len(ctx.data.columns),
    })


@app.get("/historico/{session_id}")
async def historico(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    return JSONResponse({
        "ok": True,
        "historico": ctx.historico,
        "relatorio": ctx.relatorio_final(),
    })


@app.get("/diagnostico_final/{session_id}")
async def diagnostico_final(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    if ctx.data.empty:
        return JSONResponse({"ok": False, "mensagem": "Nenhum dado carregado."}, status_code=400)

    import pandas as pd

    def snapshot_dict(df, snapshot_inicial=None):
        """Gera dict com metricas do DataFrame."""
        if snapshot_inicial:
            return {
                "linhas": snapshot_inicial.get("linhas", 0),
                "colunas": snapshot_inicial.get("colunas", 0),
                "nulos": snapshot_inicial.get("total_nulos", 0),
                "duplicatas": snapshot_inicial.get("duplicatas", 0),
                "memoria": snapshot_inicial.get("memoria_mb", 0),
                "colunas_lista": snapshot_inicial.get("nomes_colunas", []),
            }
        return {
            "linhas": len(df),
            "colunas": len(df.columns),
            "nulos": int(df.isna().sum().sum()),
            "duplicatas": int(df.duplicated().sum()),
            "memoria": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
            "colunas_lista": list(df.columns),
        }

    inicial = snapshot_dict(ctx.data, ctx._snapshot_inicial) if ctx._snapshot_inicial else snapshot_dict(ctx.data)
    final = snapshot_dict(ctx.data)

    historico_rico = []
    for h in ctx.historico:
        entry = dict(h)
        # Adiciona lista de colunas de antes/depois para diff
        entry["colunas_antes_list"] = h.get("colunas", [])
        entry["colunas_depois_list"] = h.get("colunas", [])
        historico_rico.append(entry)

    return JSONResponse({
        "ok": True,
        "inicial": inicial,
        "final": final,
        "historico": historico_rico,
    })


@app.get("/estado/{session_id}")
async def estado(request: Request, session_id: str):
    sessao = get_session(session_id)
    ctx = sessao["ctx"]

    return JSONResponse({
        "ok": True,
        "linhas": len(ctx.data),
        "colunas": len(ctx.data.columns),
        "nomes_colunas": list(ctx.data.columns),
        "tem_dados": not ctx.data.empty,
    })

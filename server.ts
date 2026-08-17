import express, { Request, Response } from "express";
import multer from "multer";
import path from "path";
import fs from "fs";
import crypto from "crypto";
import cors from "cors";

import { CSVLoader } from "./src/loaders/csvLoader";
import { ExcelConverter } from "./src/loaders/excelConverter";
import { PipelineContext } from "./src/pipeline/context";
import { Pipeline } from "./src/pipeline/workflow";
import { DiagnosticScanner } from "./src/diagnostics/scanner";
import { DiagnosticReport } from "./src/diagnostics/report";
import { DataValidator } from "./src/validation/validator";
import { PowerBIExporter } from "./src/export/csvExporter";
import { Logger } from "./src/utils/logger";
import { PipelineStep, SuggestedStep } from "./src/types";

const app = express();
const PORT = 3000;

const BASE_DIR = process.cwd();
const PASTA_RAW = path.join(BASE_DIR, "data", "raw");
const PASTA_PROCESSED = path.join(BASE_DIR, "data", "processed");
const PASTA_UPLOADS = path.join(BASE_DIR, "data", "uploads");

fs.mkdirSync(PASTA_RAW, { recursive: true });
fs.mkdirSync(PASTA_PROCESSED, { recursive: true });
fs.mkdirSync(PASTA_UPLOADS, { recursive: true });

app.use(cors());
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ extended: true, limit: "50mb" }));

// Static files
app.use("/static", express.static(path.join(BASE_DIR, "app", "static")));

interface SessionState {
  ctx: PipelineContext;
  pipeline: Pipeline;
  logger: Logger;
  arquivo?: string;
  caminho_upload?: string;
  extensao?: string;
  upload_status: string;
  etapas_limpeza: PipelineStep[];
  etapas_manip: PipelineStep[];
  etapas_sugeridas: SuggestedStep[];
}

const sessions = new Map<string, SessionState>();

function getSid(req: Request): string {
  const sid = req.params.session_id;
  if (Array.isArray(sid)) return sid[0] || "default";
  return sid || "default";
}

function getSession(sessionId: string): SessionState {
  if (!sessions.has(sessionId)) {
    const logger = new Logger();
    const ctx = new PipelineContext(logger);
    const pipeline = new Pipeline(ctx, logger);
    sessions.set(sessionId, {
      ctx,
      pipeline,
      logger,
      upload_status: "nenhum",
      etapas_limpeza: [],
      etapas_manip: [],
      etapas_sugeridas: [],
    });
  }
  return sessions.get(sessionId)!;
}

// Multer storage configuration
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, PASTA_UPLOADS);
  },
  filename: (req, file, cb) => {
    const sessionId = getSid(req);
    cb(null, `${sessionId}_${file.originalname}`);
  },
});

const upload = multer({ storage, limits: { fileSize: 200 * 1024 * 1024 } });

// Routes
app.get("/", (req: Request, res: Response) => {
  const sessionId = crypto.randomBytes(4).toString("hex");
  res.redirect(`/app/${sessionId}`);
});

app.get("/app/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  const colunas = ctx.data ? ctx.data.columns : [];
  const temDados = ctx.data && ctx.data.data.length > 0;
  const arquivo = sessao.arquivo || "";

  const templatePath = path.join(BASE_DIR, "app", "templates", "base.html");
  if (!fs.existsSync(templatePath)) {
    res.status(404).send("Template não encontrado.");
    return;
  }

  let html = fs.readFileSync(templatePath, "utf8");

  // Template variable interpolation
  html = html.replace(/\{\{\s*session_id\s*\}\}/g, sessionId);
  html = html.replace(/\{\{\s*pasta_processed\s*\}\}/g, PASTA_PROCESSED);
  html = html.replace(/\{\{\s*colunas\s*\|\s*tojson\s*\}\}/g, JSON.stringify(colunas));
  html = html.replace(/\{\{\s*tem_dados\s*\}\}/g, String(temDados));
  html = html.replace(/\{\{\s*arquivo\s*\}\}/g, arquivo);

  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.send(html);
});

app.post("/upload/:session_id", upload.single("arquivo"), (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);

  if (!req.file) {
    res.status(400).json({ ok: false, mensagem: "Nenhum arquivo enviado." });
    return;
  }

  const ext = path.extname(req.file.originalname).toLowerCase();
  sessao.arquivo = req.file.originalname;
  sessao.caminho_upload = req.file.path;
  sessao.extensao = ext;
  sessao.upload_status = "salvo";

  const sizeMb = (req.file.size / 1024 / 1024).toFixed(1);
  res.json({
    ok: true,
    mensagem: `Arquivo '${req.file.originalname}' salvo (${sizeMb} MB). Clique em 'Carregar' para processar.`,
    caminho: req.file.path,
  });
});

app.post("/load/:session_id", async (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  const caminho = sessao.caminho_upload;
  const ext = sessao.extensao || "";
  const arquivo = sessao.arquivo || "";

  if (!caminho || !fs.existsSync(caminho)) {
    res.status(400).json({ ok: false, mensagem: "Nenhum arquivo salvo. Faça upload primeiro." });
    return;
  }

  sessao.upload_status = "carregando";

  try {
    let df;
    if (ext === ".xlsx" || ext === ".xls") {
      const converter = new ExcelConverter(sessao.logger);
      const sheets = converter.listarSheets(caminho);
      const baseName = path.basename(caminho, path.extname(caminho));
      const caminhoCsv = converter.converter(caminho, PASTA_UPLOADS, sheets[0], baseName);
      const loader = new CSVLoader(caminhoCsv, sessao.logger);
      df = loader.carregar();
    } else {
      const loader = new CSVLoader(caminho, sessao.logger);
      df = loader.carregar();
    }

    ctx.setData(df, `Arquivo carregado: ${arquivo}`);
    ctx.registrarSnapshotInicial();
    sessao.upload_status = "ok";

    res.json({
      ok: true,
      linhas: df.data.length,
      colunas: df.columns,
      mensagem: `Arquivo '${arquivo}' carregado com sucesso.`,
    });
  } catch (e: any) {
    sessao.upload_status = "erro";
    res.status(400).json({ ok: false, mensagem: e.message || "Erro ao carregar arquivo." });
  }
});

app.get("/upload_status/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  res.json({
    ok: true,
    status: sessao.upload_status,
    arquivo: sessao.arquivo,
  });
});

app.get("/diagnostico/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  if (!ctx.data || ctx.data.data.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhum dado carregado." });
    return;
  }

  const scanner = new DiagnosticScanner(sessao.logger);
  const issues = scanner.escanear(ctx.data);
  const report = new DiagnosticReport(issues);

  const etapasSugeridas = report.sugerirTratamentos();
  sessao.etapas_sugeridas = etapasSugeridas;

  res.json({
    ok: true,
    problemas: issues.length,
    resumo: report.resumo(),
    detalhado: issues.length > 0 ? report.detalhado() : "",
    sugestoes: etapasSugeridas.map((e) => ({
      descricao: e.descricao || "",
      operacao: e.operacao || "",
      params: e.params || {},
    })),
  });
});

app.post("/aplicar_sugestoes/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;
  const pipeline = sessao.pipeline;

  if (!sessao.etapas_sugeridas || sessao.etapas_sugeridas.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhuma sugestão disponível." });
    return;
  }

  const resultados: string[] = [];
  for (const s of sessao.etapas_sugeridas) {
    const resStep = pipeline.executarUmaEtapa(s.operacao, s.params);
    resultados.push(resStep.mensagem);
  }

  res.json({
    ok: true,
    resultados,
    linhas: ctx.data.data.length,
    colunas: ctx.data.columns,
  });
});

app.post("/limpeza/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const { operacao, params } = req.body;

  if (!operacao) {
    res.status(400).json({ ok: false, mensagem: "Operação não informada." });
    return;
  }

  sessao.etapas_limpeza.push({ operacao, params: params || {} });
  res.json({ ok: true, mensagem: `Etapa '${operacao}' adicionada.` });
});

app.post("/executar_limpeza/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;
  const pipeline = sessao.pipeline;

  if (!sessao.etapas_limpeza || sessao.etapas_limpeza.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhuma etapa de limpeza pendente." });
    return;
  }

  const resultados: string[] = [];
  for (const etapa of sessao.etapas_limpeza) {
    const resStep = pipeline.executarUmaEtapa(etapa.operacao, etapa.params);
    resultados.push(resStep.mensagem);
  }

  sessao.etapas_limpeza = [];

  res.json({
    ok: true,
    resultados,
    linhas: ctx.data.data.length,
    colunas: ctx.data.columns,
  });
});

app.post("/manipulacao/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const { operacao, params } = req.body;

  if (!operacao) {
    res.status(400).json({ ok: false, mensagem: "Operação não informada." });
    return;
  }

  sessao.etapas_manip.push({ operacao, params: params || {} });
  res.json({ ok: true, mensagem: `Etapa '${operacao}' adicionada.` });
});

app.post("/executar_manipulacao/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;
  const pipeline = sessao.pipeline;

  if (!sessao.etapas_manip || sessao.etapas_manip.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhuma etapa de manipulação pendente." });
    return;
  }

  const resultados: string[] = [];
  for (const etapa of sessao.etapas_manip) {
    const resStep = pipeline.executarUmaEtapa(etapa.operacao, etapa.params);
    resultados.push(resStep.mensagem);
  }

  sessao.etapas_manip = [];

  res.json({
    ok: true,
    resultados,
    linhas: ctx.data.data.length,
    colunas: ctx.data.columns,
  });
});

app.get("/preview/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  if (!ctx.data || ctx.data.data.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhum dado." });
    return;
  }

  const amostra = ctx.data.data.slice(0, 50);
  const colunas = ctx.data.columns;
  const linhas = amostra.map((row) => colunas.map((col) => row[col] ?? ""));

  res.json({
    ok: true,
    colunas,
    linhas,
    total_linhas: ctx.data.data.length,
    total_colunas: colunas.length,
  });
});

app.get("/listar_pastas", (req: Request, res: Response) => {
  let caminho = (req.query.caminho as string) || "";
  if (!caminho) {
    caminho = BASE_DIR;
  }

  try {
    if (!fs.existsSync(caminho)) {
      res.status(404).json({ ok: false, mensagem: "Caminho não encontrado." });
      return;
    }

    const entries = fs.readdirSync(caminho, { withFileTypes: true });
    const pastas = entries
      .filter((e) => e.isDirectory())
      .map((e) => ({
        nome: e.name,
        caminho: path.join(caminho, e.name),
      }))
      .sort((a, b) => a.nome.localeCompare(b.nome));

    const pai = path.dirname(caminho);

    res.json({
      ok: true,
      caminho,
      pai: pai !== caminho ? pai : null,
      pastas,
    });
  } catch (e: any) {
    res.status(400).json({ ok: false, mensagem: e.message });
  }
});

app.get("/exportar/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;
  const pastaParam = (req.query.pasta as string) || "";
  const formato = ((req.query.formato as string) || "powerbi").toLowerCase() as "powerbi" | "csv" | "excel";
  const shouldDownload = req.query.download === "true" || req.query.download === "1";

  if (!ctx.data || ctx.data.data.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhum dado para exportar." });
    return;
  }

  const validator = new DataValidator(sessao.logger);
  const resultado = validator.validar(ctx.data, undefined, 1);

  const pastaDestino = pastaParam.trim() ? pastaParam.trim() : PASTA_PROCESSED;
  try {
    fs.mkdirSync(pastaDestino, { recursive: true });
  } catch (e: any) {
    res.status(400).json({ ok: false, mensagem: `Erro ao criar pasta: ${e.message}` });
    return;
  }

  const exporter = new PowerBIExporter(pastaDestino, sessao.logger);
  const nomeBase = `etl_${sessionId}`;
  const validFormat = ["powerbi", "csv", "excel"].includes(formato) ? formato : "powerbi";
  const caminho = exporter.exportar(ctx.data, nomeBase, validFormat);
  const nomeArquivo = path.basename(caminho);

  if (shouldDownload) {
    res.download(caminho, nomeArquivo);
    return;
  }

  res.json({
    ok: true,
    aprovado: resultado.aprovado,
    alertas: resultado.alertas,
    formato: validFormat,
    arquivo: nomeArquivo,
    caminho_completo: caminho,
    pasta_destino: pastaDestino,
    linhas: ctx.data.data.length,
    colunas: ctx.data.columns.length,
    download_url: `/download_export/${sessionId}?formato=${validFormat}`,
  });
});

app.get("/download_export/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;
  const formato = ((req.query.formato as string) || "powerbi").toLowerCase() as "powerbi" | "csv" | "excel";

  if (!ctx.data || ctx.data.data.length === 0) {
    res.status(400).send("Nenhum dado carregado para download.");
    return;
  }

  const exporter = new PowerBIExporter(PASTA_PROCESSED, sessao.logger);
  const nomeBase = `etl_${sessionId}`;
  const validFormat = ["powerbi", "csv", "excel"].includes(formato) ? formato : "powerbi";
  const caminho = exporter.exportar(ctx.data, nomeBase, validFormat);
  const nomeArquivo = path.basename(caminho);

  res.download(caminho, nomeArquivo);
});

app.get("/historico/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  res.json({
    ok: true,
    historico: ctx.historico,
    relatorio: ctx.relatorioFinal(),
  });
});

app.get("/diagnostico_final/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  if (!ctx.data || ctx.data.data.length === 0) {
    res.status(400).json({ ok: false, mensagem: "Nenhum dado carregado." });
    return;
  }

  const snap = ctx.getSnapshotInicial();

  const getSnapshotMetrics = (df = ctx.data) => {
    let nulos = 0;
    const seen = new Set<string>();
    let dups = 0;
    for (const r of df.data) {
      const k = df.columns.map((c) => String(r[c] ?? "")).join("|||");
      if (seen.has(k)) dups++;
      else seen.add(k);

      for (const col of df.columns) {
        const v = r[col];
        if (v === null || v === undefined || v === "") nulos++;
      }
    }
    const mem = Number(((JSON.stringify(df.data).length * 2) / 1024 / 1024).toFixed(2));
    return {
      linhas: df.data.length,
      colunas: df.columns.length,
      nulos,
      duplicatas: dups,
      memoria: mem,
      colunas_lista: [...df.columns],
    };
  };

  const inicial = snap
    ? {
        linhas: snap.linhas,
        colunas: snap.colunas,
        nulos: snap.total_nulos,
        duplicatas: snap.duplicatas,
        memoria: snap.memoria_mb,
        colunas_lista: snap.nomes_colunas,
      }
    : getSnapshotMetrics(ctx.data);

  const final = getSnapshotMetrics(ctx.data);

  res.json({
    ok: true,
    inicial,
    final,
    historico: ctx.historico,
  });
});

app.get("/estado/:session_id", (req: Request, res: Response) => {
  const sessionId = getSid(req);
  const sessao = getSession(sessionId);
  const ctx = sessao.ctx;

  res.json({
    ok: true,
    linhas: ctx.data ? ctx.data.data.length : 0,
    colunas: ctx.data ? ctx.data.columns.length : 0,
    nomes_colunas: ctx.data ? ctx.data.columns : [],
    tem_dados: !!(ctx.data && ctx.data.data.length > 0),
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`ETL NGR-SEE Server running on http://0.0.0.0:${PORT}`);
});

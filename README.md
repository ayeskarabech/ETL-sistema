# RoboEdu — ETL & Tratamento de Dados

Sistema para carregar, diagnosticar, limpar e exportar bases de dados (CSV/Excel) prontas para Power BI.

![RoboEdu Interface](app/static/img/RoboEdu%202.0.png)

---

## v1.0 — Interface Inicial

Primeira versao funcional com menu no terminal (CLI).

**Funcionalidades:**
- Carregamento de CSV com deteccao automatica de encoding e separador
- Diagnostico basico de dados (nulos, duplicatas)
- Limpeza e manipulacao via comandos
- Exportacao para CSV

**Como rodar:**
```
python main.py
```

---

## v2.0 — Interface Web Otimizada

Reescrita completa com interface web, motor DuckDB para bases grandes e suporte a Parquet.

**Funcionalidades novas:**
- Interface web (FastAPI + SPA) com drag-and-drop
- Diagnostico avancado com fuzzy match e sugestoes automaticas
- Motor DuckDB para JOINs, PROCV e agregacoes em bases de 200MB+
- Leitura em chunks para arquivos grandes
- Cache automatico em Parquet para re-leituras
- Exportacao CSV, XLSX e Parquet
- Preview de dados com tabela scrollavel
- Historico completo de transformacoes aplicadas

**Como rodar:**
```
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Acesse http://localhost:8000

**Dependencias:**
```
pip install -r requirements.txt
```

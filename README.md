# Sistema de ETL — NGR-SEE

Sistema completo de ETL com diagnostico automatico, limpeza, manipulacao
via formulas Excel, e exportacao para Power BI. Menu interativo de terminal.

## Como rodar

1. Instale o Python: https://www.python.org/downloads/
2. Instale as dependencias:
   ```
   pip install -r requirements.txt
   ```
3. Copie os arquivos `.csv` ou `.xlsx` para a pasta `data/raw/`
4. Rode:
   ```
   python main.py
   ```
5. Siga o menu — diagnostico, limpeza, formulas, validacao, exportacao

## Fluxo do sistema

```
1. CARREGAR
   ├── CSV (detecta encoding/separador automaticamente)
   └── Excel (converte .xlsx -> .csv automaticamente)

2. DIAGNOSTICO AUTOMATICO
   ├── Nulos (quantidade, localizacao, %)
   ├── Duplicatas (exatas e por coluna)
   ├── Formatos numericos mistos (1.234,56 vs 1234.56 vs R$)
   ├── Colunas vazias / Unnamed
   ├── Tipos mistos (numeros e textos na mesma coluna)
   ├── Valores suspeitos (vazio, '-', 'N/A', 'NULL', etc)
   ├── Espacos incorretos no texto
   └── Fuzzy match (erros de digitacao: "Moraes" vs "Morais")
   → Gera SUGESTOES DE TRATAMENTO automaticas

3. LIMPEZA (manual ou via sugestoes)
   ├── Formato brasileiro (virgula decimal, ponto milhar)
   ├── Converter texto para numero
   ├── Duplicatas (detectar / remover)
   ├── Fuzzy match (encontrar / unificar valores similares)
   ├── Nulos (preencher: mediana, moda, valor fixo, remover, deixar vazio)
   ├── Substituicao (exata ou por regex)
   ├── Normalizar texto (MAIUSCULO / minusculo)
   └── Corrigir tipo (numero / texto / data)

4. MANIPULACAO / FORMULAS EXCEL
   ├── PROCV (VLOOKUP) — busca vertical entre tabelas
   ├── PROCV agrupado — VLOOKUP com soma/media
   ├── CORRESP (MATCH) — posicao de valor
   ├── ESQUERDA / DIREITA / MEIO (LEFT/RIGHT/MID)
   ├── TAMANHO (LEN), CONCATENAR, SUBSTITUIR
   ├── SE (IF), CONT.SE (COUNTIF), SOMASE (SUMIF)
   ├── ARRED (ROUND)
   ├── Coluna calculada (expressao livre)
   ├── Registrar tabela referencia
   └── JOIN (left/inner/outer)

5. VALIDACAO
   └── Checagens automaticas antes de exportar

6. EXPORTACAO
   └── CSV UTF-8 com BOM, snake_case, pronto pro Power BI
```

## Estrutura de pastas

```
etl_ngr_see/
├── main.py                      <- ponto de entrada
├── requirements.txt             <- dependencias
├── README.md
├── data/
│   ├── raw/                     <- CSVs e Excels de entrada
│   ├── processed/               <- CSVs tratados (saida)
│   └── logs/                    <- logs de execucao
└── src/
    ├── loaders/
    │   ├── csv_loader.py        <- leitura CSV (encoding/separador auto)
    │   └── excel_converter.py   <- conversor XLSX -> CSV
    ├── cleaning/
    │   ├── data_cleaner.py      <- limpeza base
    │   ├── rules.py             <- regras (brasileiro, duplicatas, fuzzy)
    │   └── normalizers.py       <- normalizacao texto/numeros
    ├── formulas/
    │   └── engine.py            <- formulas Excel (PROCV, SE, etc)
    ├── pipeline/
    │   ├── context.py           <- estado compartilhado
    │   └── workflow.py          <- executor de etapas
    ├── diagnostics/
    │   ├── scanner.py           <- scanner de diagnostico
    │   └── report.py            <- formatador de relatorio
    ├── integrations/
    │   └── supabase_client.py   <- Supabase (preparado, nao ativo)
    ├── validation/
    │   └── validator.py         <- validacao pos-limpeza
    ├── export/
    │   └── csv_exporter.py      <- exportacao Power BI
    └── utils/
        └── logger.py            <- logging
```

## Diagnostico

O diagnostico roda automaticamente ao carregar a base e identifica:

| Problema | Gravidade | Exemplo |
|----------|-----------|---------|
| Coluna 100% vazia | Critico | Coluna sem dado nenhum |
| +30% nulos | Critico | Coluna com muitos buracos |
| Formatos mistos | Aviso | `1.234,56` e `1234.56` na mesma coluna |
| Duplicatas | Aviso | Linhas identicas |
| Fuzzy match | Aviso | `Moraes` / `Morais` (erros de digitacao) |
| Valores suspeitos | Info | `-`, `N/A`, `NULL`, `...` |
| Espacos extras | Info | ` texto ` com espacos no inicio/fim |

## Formulas disponiveis

| Formula | Excel | Funcao |
|---------|-------|--------|
| PROCV | VLOOKUP | Busca vertical entre tabelas |
| CORRESP | MATCH | Posicao de valor na coluna |
| ESQUERDA | LEFT | Extrair N caracteres do inicio |
| DIREITA | RIGHT | Extrair N caracteres do final |
| MEIO | MID | Extrair de posicao com tamanho |
| TAMANHO | LEN | Contar caracteres |
| CONCATENAR | CONCAT | Juntar colunas |
| SUBSTITUIR | SUBSTITUTE | Trocar texto na celula |
| SE | IF | Logica condicional |
| CONT.SE | COUNTIF | Contar por criterio |
| SOMASE | SUMIF | Somar por criterio |
| ARRED | ROUND | Arredondar numero |

## Integracao Supabase (opcional)

Para ativar o registro de acoes no Supabase:

1. Crie conta em https://supabase.com
2. Descomente `supabase` no `requirements.txt` e instale
3. Crie a tabela `etl_logs` (schema SQL esta em `src/integrations/supabase_client.py`)
4. Chame `SupabaseClient.ativar(url, chave)` no codigo

Enquanto nao configurado, o sistema grava tudo localmente em logs.

## Atalho de duplo clique (Windows)

Crie `rodar_etl.bat` na mesma pasta do `main.py`:

```bat
@echo off
python main.py
pause
```

## Divergencias frequentes

**"Nao achei nenhum arquivo"**
O sistema agora aceita `.csv` e `.xlsx` na pasta `data/raw/`.

**"Quero converter Excel para CSV sem rodar o ETL"**
Use a opcao 2 do menu inicial — converte e ja carrega.

**"A base tem muitos problemas e nao sei por onde comecar"**
O diagnostico automatico resolve: roda sozinho e sugere o que fazer.

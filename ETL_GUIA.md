# ETL NGR-SEE — Guia Completo de Uso

## Sumario

1. [Inicio rapido](#1-inicio-rapido)
2. [Fluxo geral do sistema](#2-fluxo-geral-do-sistema)
3. [Menu 1: Carregar dados](#3-menu-1-carregar-dados)
4. [Menu 2: Diagnostico automatico](#4-menu-2-diagnostico-automatico)
5. [Menu 3: Limpeza](#5-menu-3-limpeza)
6. [Menu 4: Manipulacao / Formulas Excel](#6-menu-4-manipulacao--formulas-excel)
7. [Validacao e exportacao](#7-validacao-e-exportacao)
8. [Catalogo completo de funcoes](#8-catalogo-completo-de-funcoes)
9. [Exemplos praticos passo a passo](#9-exemplos-praticos-passo-a-passo)
10. [Integracao Supabase](#10-integracao-supabase)
11. [Divergencias frequentes](#11-divergencias-frequentes)

---

## 1. Inicio rapido

```bash
pip install -r requirements.txt
python main.py
```

Coloque CSVs ou Excels em `data/raw/` e siga o menu.

---

## 2. Fluxo geral do sistema

```
CARREGAR -> DIAGNOSTICO -> LIMPEZA -> MANIPULACAO -> VALIDAR -> EXPORTAR
   |              |             |            |            |           |
 CSV/Excel   auto-scan    regras      formulas      checagens    CSV final
```

O sistema e sequencial: cada etapa recebe o resultado da anterior.

---

## 3. Menu 1: Carregar dados

### 3.1 CSV (opcao 1)
- Detecta automaticamente encoding (UTF-8, Latin-1, CP1252)
- Detecta automaticamente separador (; ou ,)
- Permite escolher quais colunas carregar
- Arquivos grandes (>50MB) sao lidos em pedaços

### 3.2 Excel para CSV (opcao 2)
- Leitura de arquivos .xlsx e .xls
- Lista todas as abas (sheets) do arquivo
- Permite escolher qual aba converter
- Converte para CSV UTF-8 com BOM
- Salva o CSV em `data/raw/` para uso posterior

### 3.3 Outra pasta (opcao 3)
- Carrega CSV de qualquer pasta no computador

---

## 4. Menu 2: Diagnostico automatico

Roda automaticamente apos carregar os dados. Analisa a base inteira e retorna:

### 4.1 Deteccao de numeros com ponto decimal

| Problema | Gravidade | Exemplo | O que detecta |
|----------|-----------|---------|---------------|
| NUMERO_PONTO_DECIMAL | Aviso | `1234.56` | Numeros decimais usando PONTO que deveriam usar VIRGULA no formato brasileiro |
| NUMERO_PONTO_DECIMAL | Critico | Mix `1234.56` e `1234,56` | Formatacao inconsistente na mesma coluna |

O scanner identifica:
- Quantos valores usam ponto decimal vs virgula decimal
- Quantas casas decimais estao presentes (1, 2, 3...)
- Sugere automaticamente a opcao de limpeza correta

### 4.2 Deteccao de tipo incorreto da coluna

| Problema | O que detecta | Exemplo |
|----------|---------------|---------|
| TIPO_TEXTO_NUMERO | Coluna de texto que deveria ser numero | Coluna "valor" com "1234.56" como string |
| TIPO_NUMERO_TEXTO | Coluna numero que deveria ser texto | Coluna "CPF" com 12345678901 como int |

Regras de deteccao:
- **Texto -> Numero**: Se >=80% dos valores sao numericamente validos
- **Texto -> Numero (parcial)**: Se 50-80% sao numeros, identifica os outliers
- **Numero -> Texto**: Se valores tem 8+ digitos (parece CPF/CNPJ/matricula)
- **Numero -> Texto**: Se 95%+ valores sao inteiros mas tipo e float

### 4.3 Outros diagnostico

| Problema | Descricao |
|----------|-----------|
| NULOS | Colunas com valores nulos (classificado por %) |
| DUPLICATAS | Linhas identicas ou colunas com muitos repetidos |
| COLUNA_VAZIA | Coluna 100% ou >90% nula |
| COLUNA_UNNAMED | Coluna com nome "Unnamed" (erro de CSV) |
| FORMATO_ESPECIAL | Moeda R$, porcentagem %, milhar brasileiro |
| VALOR_SUSPEITO | Valores como `-`, `N/A`, `NULL`, `...`, `S/N` |
| TEXTO_ESPACO | Espacos no inicio, fim, ou meio do texto |
| TEXTO_CASO | Caixa inconsistente (MAIUSCULO vs minusculo) |
| FUZZY_MATCH | Valores parecidos (erros de digitacao, grafias diferentes) |

### 4.4 Fuzzy Match — como funciona

O scanner busca por padroes similares usando 3 metricas:

1. **Bigram Similarity**: Compara sequencias de 2 caracteres
2. **Distancia de Edicao (Levenshtein)**: Quantas edicoes para transformar A em B
3. **Similaridade por Raiz**: Compara raizes das palavras (primeiras letras + consoantes)

Exemplos que o fuzzy match detecta:
- `MORAIS` / `MORAES` (troca de terminacao)
- `JOSE` / `JOS` (abreviacao)
- `LUIZ` / `LUIS` (grafia alternativa)
- `SAO PAULO` / `S PAULO` / `SP` (sigla vs nome)
- `S/A` / `SA` / `S.A.` (abreviacao de empresa)
- `RECIFE` / `RECIFE ` (espaco extra)
- `M` / `M.` / `MASCULINO` (abreviacao vs nome completo)

O fuzzy match agrupa automaticamente variantes e sugere unificacao.

---

## 5. Menu 3: Limpeza

### 5.1 Formatar numeros (opcao 1)
Converte colunas de texto para formato brasileiro: `1.234,56`

**Quando usar**: Quando o diagnostico detecta NUMERO_PONTO_DECIMAL

```
Opcao 1 -> Escolher colunas -> Definir casas decimais (padrao: 2)
```

### 5.2 Converter texto para numero interno (opcao 2)
Converte strings brasileiras para float do Python: `"1.234,56"` -> `1234.56`

**Quando usar**: Quando precisa manipular os valores (soma, media, etc)

### 5.3 Detectar duplicatas (opcao 3)
Marca linhas duplicadas com coluna auxiliar `_duplicata`

### 5.4 Remover duplicatas (opcao 4)
Remove linhas duplicadas diretamente, mantendo a primeira ocorrencia

### 5.5 Encontrar valores similares (opcao 5)
Roda fuzzy match em uma coluna especifica e mostra pares encontrados

### 5.6 Unificar valores similares (opcao 6)
- Roda fuzzy match automatico
- Mostra sugestoes de unificacao
- Permite aceitar sugestoes ou criar manualmente
- Exemplo: `MORAIS` <- `["MORAES", "MORIAS"]` unifica tudo para `MORAIS`

### 5.7 Remover colunas totalmente vazias (opcao 7)
Remove colunas onde todos os valores sao nulos

### 5.8 Tratar valores nulos (opcao 8)
5 opcoes de tratamento:
1. **Valor fixo**: Preenche com texto/numero escolhido (`0`, `-`, `NAO INFORMADO`)
2. **Mediana**: Preenche com mediana (apenas numeros)
3. **Moda**: Preenche com valor mais frequente
4. **Remover linhas**: Deleta linhas que tem nulo
5. **Deixar vazio**: Mantem NaN

### 5.9 Substituir valores exatos (opcao 9)
Substituicao direta: `valor_antigo` -> `valor_novo`

### 5.10 Substituir por regex (opcao 10)
Substituicao usando expressoes regulares

Exemplos:
- Remover caracteres nao numericos: `[^0-9]` -> ``
- Extrair apenas numeros: `[0-9]` (usar opcao extrair do cleaning)

### 5.11 Normalizar texto (opcao 11)
Converte toda a coluna para MAIUSCULO ou minusculo

### 5.12 Corrigir tipo de coluna (opcao 12)
Converte entre: numero, texto, data

---

## 6. Menu 4: Manipulacao / Formulas Excel

### 6.1 Busca e referencia

#### PROCV (VLOOKUP) — opcao 1
Busca vertical entre tabelas.

**Fluxo**:
1. Registrar tabela de referencia (opcao 15)
2. Escolher coluna CHAVE na tabela atual
3. Escolher coluna CHAVE e coluna VALOR na referencia
4. Sistema cria nova coluna com os valores encontrados

**Exemplo**: Se tabela A tem "codigo_escola" e tabela B tem "codigo_escola" + "nome_escola", PROCV puxa o nome da escola para tabela A.

#### PROCV agrupado — opcao 2
PROCV com funcao de agregacao (soma, media, contagem, min, max, mediana).

**Exemplo**: Somar todas as notas de uma escola e trazer o total para cada linha.

#### CORRESP (MATCH) — opcao 3
Retorna posicao (indice) onde um valor aparece na coluna.

### 6.2 Texto

#### ESQUERDA (LEFT) — opcao 4
Extrai N caracteres do inicio da string.

**Exemplo**: `ESQUERDA("12345678", 3)` -> `"123"`

#### DIREITA (RIGHT) — opcao 5
Extrai N caracteres do final.

**Exemplo**: `DIREITA("12345678", 4)` -> `"5678"`

#### MEIO (MID) — opcao 6
Extrai N caracteres a partir de uma posicao.

**Exemplo**: `MEIO("12345678", 3, 4)` -> `"3456"` (posicao 3, 4 caracteres)

#### TAMANHO (LEN) — opcao 7
Conta caracteres de uma string.

#### CONCATENAR — opcao 8
Junta texto de multiplas colunas.

**Exemplo**: Concatenar "nome" + " " + "sobrenome" -> "nome sobrenome"

#### SUBSTITUIR (SUBSTITUTE) — opcao 9
Troca texto dentro da celula.

**Exemplo**: Substituir "S/A" por "SA" em toda a coluna

### 6.3 Logica

#### SE (IF) — opcao 10
Logica condicional.

**Exemplo**: `SE(nota >= 7, "APROVADO", "REPROVADO")`

**Sintaxe da condicao**: Usa expressoes pandas:
- `coluna_a > 100`
- `coluna_b == 'SIM'`
- `coluna_c.notna()`
- `(coluna_a > 10) & (coluna_b == 'SIM')`

### 6.4 Numeros

#### ARRED (ROUND) — opcao 11
Arredonda para N casas decimais.

#### CONT.SE (COUNTIF) — opcao 12
Conta celulas que atendem um criterio.

**Criterios**: `>100`, `APROVADO`, `!=0`, `>=50`

#### SOMASE (SUMIF) — opcao 13
Soma valores onde a coluna criterio atende a condicao.

### 6.5 Expressao livre — opcao 14
Permite escrever qualquer expressao pandas/numpy.

**Exemplos**:
- `col_a + col_b` (soma)
- `col_a / col_b * 100` (porcentagem)
- `np.where(col_a > 10, 'alto', 'baixo')` (condicional)
- `col_a.str.upper()` (normalizar)
- `col_a.str.len()` (tamanho)
- `col_a * 1.1` (acrescimo de 10%)

### 6.6 Tabelas

#### Registrar tabela referencia — opcao 15
Carrega outro CSV como tabela de referencia para PROCV/JOIN.

#### Juntar tabela (JOIN) — opcao 16
Junta duas tabelas por uma coluna chave.

**Tipos**:
- `left`: Mantem todas as linhas da tabela atual
- `inner`: Mantem apenas linhas que existem nas duas
- `outer`: Mantem todas as linhas de ambas

---

## 7. Validacao e exportacao

### Validacao
Apos limpeza e manipulacao, o sistema roda checagens automaticas:
- Colunas obrigatórias presentes
- Volume minimo de linhas
- Colunas totalmente vazias
- Colunas "Unnamed"
- Duplicatas remanescentes

### Exportacao
- CSV em UTF-8 com BOM (acentuacao funciona no Excel/Power BI)
- Nomes de coluna em snake_case
- Arquivo com timestamp (nunca sobrescreve)
- Salvo em `data/processed/`

---

## 8. Catalogo completo de funcoes

### Limpeza

| # | Funcao | Descricao |
|---|--------|-----------|
| 1 | Formatar brasileiro | `1234.56` -> `1.234,56` |
| 2 | Numero interno | `"1.234,56"` -> `1234.56` (float) |
| 3 | Detectar duplicatas | Marca linhas duplicadas |
| 4 | Remover duplicatas | Deleta linhas duplicadas |
| 5 | Fuzzy match | Encontra valores parecidos |
| 6 | Unificar valores | Agrupa variantes |
| 7 | Colunas vazias | Remove colunas sem dado |
| 8 | Tratar nulos | Preenche ou remove |
| 9 | Substituir valor | Troca exata |
| 10 | Substituir regex | Troca por padrao |
| 11 | Normalizar texto | MAIUSCULO/minusculo |
| 12 | Corrigir tipo | numero/texto/data |

### Formulas Excel

| # | Formula | Excel Equiv. | Descricao |
|---|---------|-------------|-----------|
| 1 | PROCV | VLOOKUP | Busca vertical |
| 2 | PROCV agrupado | VLOOKUP+SUM | Busca com agregacao |
| 3 | CORRESP | MATCH | Posicao do valor |
| 4 | ESQUERDA | LEFT | N caracteres inicio |
| 5 | DIREITA | RIGHT | N caracteres final |
| 6 | MEIO | MID | Extrair de posicao |
| 7 | TAMANHO | LEN | Contar caracteres |
| 8 | CONCATENAR | CONCAT | Juntar colunas |
| 9 | SUBSTITUIR | SUBSTITUTE | Trocar texto |
| 10 | SE | IF | Condicao |
| 11 | ARRED | ROUND | Arredondar |
| 12 | CONT.SE | COUNTIF | Contar por criterio |
| 13 | SOMASE | SUMIF | Somar por criterio |
| 14 | Expr. livre | - | Expressao pandas |

---

## 9. Exemplos praticos passo a passo

### Exemplo 1: Base com numeros em formato errado

**Situacao**: Coluna "valor" tem `1.234,56` e `1234.56` misturados

**Solucao**:
1. Diagnostico detecta: `NUMERO_PONTO_DECIMAL` (critico: formato inconsistente)
2. Limpeza -> Opcao 2: "Converter texto para numero interno"
3. Escolher coluna "valor"
4. Agora a coluna e float e pode ser manipulada

### Exemplo 2: Coluna de codigo numerico

**Situacao**: Coluna "codigo_escola" tem `12345678` (deveria ser texto)

**Solucao**:
1. Diagnostico detecta: `TIPO_NUMERO_TEXTO` (parece identificador)
2. Limpeza -> Opcao 12: "Corrigir tipo" -> escolher "texto"
3. Agora o codigo preserva zeros a esquerda e e tratado como texto

### Exemplo 3: Sobrenomes com erros de digitacao

**Situacao**: Coluna "responsavel" tem `MORAIS`, `MORAES`, `MORIAS`

**Solucao**:
1. Diagnostico detecta: `FUZZY_MATCH` com grupo `MORAIS <- [MORAES, MORIAS]`
2. Aceitar sugestao automatica OU
3. Limpeza -> Opcao 6: "Unificar valores similares" -> escolher coluna
4. Sistema mostra sugestoes, usuario confirma
5. Todos os valores viram `MORAIS`

### Exemplo 4: Tratar nulos com valor padrao

**Situacao**: Coluna "telefone" tem valores vazios

**Solucao**:
1. Diagnostico detecta: `NULOS` na coluna "telefone"
2. Limpeza -> Opcao 8: "Tratar nulos"
3. Escolher coluna "telefone"
4. Opcao 1: "Valor fixo" -> digitar `NAO INFORMADO`
5. Todos os nulos viram `NAO INFORMADO`

### Exemplo 5: PROCV entre duas bases

**Situacao**: Tem tabela de matriculas e tabela de escolas, precisa puxar o nome da escola

**Solucao**:
1. Manipulacao -> Opcao 15: "Registrar tabela referencia" -> escolher CSV de escolas
2. Manipulacao -> Opcao 1: "PROCV"
3. Tabela referencia: `escolas`
4. Coluna CHAVE atual: `codigo_escola`
5. Coluna CHAVE ref: `codigo`
6. Coluna VALOR ref: `nome`
7. Nova coluna `nome_escola` e criada com os nomes encontrados

---

## 10. Integracao Supabase

### Como ativar

1. Criar conta em https://supabase.com
2. Criar projeto
3. Rodar o schema SQL (esta em `src/integrations/supabase_client.py`):
   ```sql
   CREATE TABLE etl_logs (
     id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
     created_at TIMESTAMPTZ DEFAULT NOW(),
     sessao_id TEXT NOT NULL,
     arquivo_entrada TEXT,
     arquivo_saida TEXT,
     linhas_entrada INTEGER,
     linhas_saida INTEGER,
     etapas_executadas JSONB,
     duracao_segundos FLOAT,
     status TEXT,
     observacoes TEXT
   );
   ```
4. Instalar pacote: `pip install supabase`
5. Chamar: `SupabaseClient.ativar("URL_DO_PROJETO", "CHAVE_ANON")`

### O que registra
- Arquivo de entrada e saida
- Quantidade de linhas antes/depois
- Todas as etapas executadas (em JSON)
- Duracao total
- Status (sucesso/erro)

### Enquanto nao configurado
O sistema grava tudo localmente em `data/logs/`.

---

## 11. Divergencias frequentes

**"O diagnostico achou muitos problemas"**
Nao e problema — e o sistema te economizando horas de trabalho manual.
Leia as sugestoes e aplique na ordem sugerida.

**"Quero converter so uma coluna de Excel"**
Use o menu de limpeza (opcao 12: corrigir tipo).

**"Fuzzy match achou muitos falsos positivos"
Normal. O fuzzy match e conservador (limiar 0.72). Revise os grupos
e ignore os que nao fazem sentido.

**"Preciso rodar o mesmo ETL toda semana"**
O sistema gera log de cada execucao. Anote as opcoes que usou
e rode novamente — mas atencao: cada exportacao gera arquivo novo
com timestamp, entao nao sobrescreve nada.

**"Quero ver o historico de execucoes"**
Se o Supabase estiver ativo, consulte a tabela `etl_logs`.
Se nao, veja os arquivos em `data/logs/`.

/* ═══════════════════════════════════════════════════════════════════
   ETL NGR-SEE — Interatividade (sidebar only)
   ═══════════════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    initNav();
});

/* ── NAV SIDEBAR ───────────────────────────────────────────────── */
function initNav() {
    const navItems = document.querySelectorAll('.nav-item[data-tab]');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = item.dataset.tab;

            // Ativa nav
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Mostra painel
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            const panel = document.getElementById(target);
            if (panel) panel.classList.add('active');

            // Auto-carrega diagnostico final ao entrar na aba resultado
            if (target === 'tab-resultado') {
                carregarDiagnosticoFinal();
            }
        });
    });
}

/* ── UTILS ─────────────────────────────────────────────────────── */
function showPanel(id) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const panel = document.getElementById(id);
    if (panel) panel.classList.add('active');

    const nav = document.querySelector(`.nav-item[data-tab="${id}"]`);
    if (nav) nav.classList.add('active');
}

function showNotification(msg, tipo = 'info') {
    const notif = document.createElement('div');
    notif.className = `notification notification-${tipo}`;
    notif.innerHTML = `<span>${msg}</span>`;
    notif.style.cssText = `
        position: fixed; top: 20px; right: 20px; z-index: 2000;
        padding: 14px 24px; border-radius: 12px;
        background: rgba(255,255,255,0.85); backdrop-filter: blur(20px);
        border: 1px solid rgba(31,67,140,0.1); box-shadow: 0 8px 30px rgba(31,67,140,0.12);
        font-family: 'Inter', sans-serif; font-size: 0.9rem; font-weight: 500;
        animation: fadeIn 0.3s ease;
    `;
    if (tipo === 'success') notif.style.borderLeft = '4px solid #2ECC71';
    else if (tipo === 'error') notif.style.borderLeft = '4px solid #E74C3C';
    else notif.style.borderLeft = '4px solid #1F438C';

    document.body.appendChild(notif);
    setTimeout(() => notif.remove(), 4000);
}

function fmtNum(n) {
    if (n === null || n === undefined) return '0';
    return Number(n).toLocaleString('pt-BR');
}

function variacao(atual, anterior) {
    if (!anterior) return '';
    const diff = atual - anterior;
    const pct = ((diff / anterior) * 100).toFixed(1);
    if (diff === 0) return '<span class="stat-change neutral">sem alteracao</span>';
    const sinal = diff > 0 ? '+' : '';
    const cls = diff > 0 ? 'positive' : 'negative';
    return `<span class="stat-change ${cls}">${sinal}${fmtNum(diff)} (${sinal}${pct}%)</span>`;
}

function describePasso(h) {
    const op = h.operacao || '';
    const cols = h.colunas_depois_list || [];
    const colsAntes = h.colunas_antes_list || [];

    const adicionadas = cols.filter(c => !colsAntes.includes(c));
    const removidas = colsAntes.filter(c => !cols.includes(c));

    let detalhes = [];

    if (adicionadas.length) detalhes.push(`Coluna(s) adicionada(s): <b>${adicionadas.join(', ')}</b>`);
    if (removidas.length) detalhes.push(`Coluna(s) removida(s): <b>${removidas.join(', ')}</b>`);

    // Descrever operacao
    const descricoes = {
        'CSV carregado': 'Arquivo CSV carregado na memoria',
        'Arquivo convertido': 'Arquivo Excel convertido para CSV e carregado',
        'Duplicatas detectadas': 'Duplicatas identificadas na base',
        'Duplicatas removidas': 'Linhas duplicadas removidas',
        'Colunas vazias removidas': 'Colunas totalmente vazias removidas',
        'Nulos tratados': 'Valores nulos preenchidos/removidos',
        'Nulos removidos': 'Linhas com valores nulos removidas',
        'Substituicao': 'Valores substituidos conforme mapeamento',
        'Texto': 'Texto normalizado (maiusculo/minusculo)',
        'Tipos': 'Tipos de dados corrigidos',
        'Formato brasileiro': 'Numeros convertidos para formato brasileiro',
        'Numero interno': 'Texto convertido para numero interno',
        'Unificado': 'Valores similares unificados',
        'PROCV': 'PROCV executado (VLOOKUP)',
        'PROCV agrupado': 'PROCV agrupado executado',
        'ESQUERDA': 'Funcao ESQUERDA aplicada',
        'DIREITA': 'Funcao DIREITA aplicada',
        'MEIO': 'Funcao MEIO aplicada',
        'TAMANHO': 'Funcao TAMANHO aplicada',
        'CONCATENAR': 'Colunas concatenadas',
        'SUBST': 'Texto substituido na coluna',
        'SE': 'Funcao SE aplicada (IF)',
        'ARRED': 'Funcao ARRED aplicada (ROUND)',
        'Calculada': 'Coluna calculada por expressao',
        'Coluna': 'Coluna adicionada/renomeada/removida',
        'Renomeado': 'Colunas renomeadas',
        'Removidas': 'Colunas removidas',
        'Filtro': 'Filtro aplicado nas linhas',
        'Ordenado': 'Dados ordenados',
        'Colunas reordenadas': 'Ordem das colunas alterada',
        'Primeiras': 'Mantidas as N primeiras linhas',
        'Ultimas': 'Mantidas as N ultimas linhas',
        'JOIN': 'Tabelas unidas (JOIN)',
        'Agregacao': 'Dados agregados (GROUP BY)',
    };

    let descOp = op;
    for (const [chave, texto] of Object.entries(descricoes)) {
        if (op.includes(chave)) { descOp = texto; break; }
    }

    return { descOp, detalhes };
}

/* ── DIAGNOSTICO FINAL ─────────────────────────────────────────── */
async function carregarDiagnosticoFinal() {
    const loading = document.getElementById('diag-final-loading');
    const conteudo = document.getElementById('diag-final-conteudo');
    loading.style.display = 'block';
    conteudo.style.display = 'none';

    try {
        const r = await fetch(`/diagnostico_final/${SID}`);
        const j = await r.json();
        if (!j.ok) {
            loading.innerHTML = `<div style="color:var(--text-muted); font-size:0.9rem">${j.mensagem || 'Erro ao carregar diagnostico.'}</div>`;
            return;
        }

        loading.style.display = 'none';
        conteudo.style.display = 'block';

        const ini = j.inicial || {};
        const fin = j.final || {};

        // Estado Inicial
        document.getElementById('df-linhas-antes').textContent = fmtNum(ini.linhas || 0);
        document.getElementById('df-colunas-antes').textContent = ini.colunas || 0;
        document.getElementById('df-nulos-antes').textContent = fmtNum(ini.nulos || 0);
        document.getElementById('df-dups-antes').textContent = fmtNum(ini.duplicatas || 0);
        document.getElementById('df-mem-antes').textContent = ini.memoria || 0;

        // Estado Final
        document.getElementById('df-linhas-depois').textContent = fmtNum(fin.linhas || 0);
        document.getElementById('df-colunas-depois').textContent = fin.colunas || 0;
        document.getElementById('df-nulos-depois').textContent = fmtNum(fin.nulos || 0);
        document.getElementById('df-dups-depois').textContent = fmtNum(fin.duplicatas || 0);
        document.getElementById('df-mem-depois').textContent = fin.memoria || 0;

        // Variacoes
        const varLinhas = (fin.linhas || 0) - (ini.linhas || 0);
        const varColunas = (fin.colunas || 0) - (ini.colunas || 0);
        const varNulos = (fin.nulos || 0) - (ini.nulos || 0);
        const varDups = (fin.duplicatas || 0) - (ini.duplicatas || 0);

        document.getElementById('df-var-linhas').innerHTML =
            `<span style="color:${varLinhas < 0 ? '#E74C3C' : varLinhas > 0 ? '#2ECC71' : 'inherit'}">${varLinhas > 0 ? '+' : ''}${fmtNum(varLinhas)}</span>`;
        document.getElementById('df-var-linhas-pct').innerHTML = variacao(fin.linhas || 0, ini.linhas || 0);

        document.getElementById('df-var-colunas').innerHTML =
            `<span style="color:${varColunas < 0 ? '#E74C3C' : varColunas > 0 ? '#2ECC71' : 'inherit'}">${varColunas > 0 ? '+' : ''}${fmtNum(varColunas)}</span>`;
        document.getElementById('df-var-nulos').innerHTML =
            `<span style="color:${varNulos > 0 ? '#E74C3C' : varNulos < 0 ? '#2ECC71' : 'inherit'}">${varNulos > 0 ? '+' : ''}${fmtNum(varNulos)}</span>`;
        document.getElementById('df-var-dups').innerHTML =
            `<span style="color:${varDups > 0 ? '#E74C3C' : varDups < 0 ? '#2ECC71' : 'inherit'}">${varDups > 0 ? '+' : ''}${fmtNum(varDups)}</span>`;

        // Colunas adicionadas/removidas
        const colIni = ini.colunas_lista || [];
        const colFin = fin.colunas_lista || [];
        const adicionadas = colFin.filter(c => !colIni.includes(c));
        const removidas = colIni.filter(c => !colFin.includes(c));

        const colInfo = document.getElementById('df-colunas-info');
        if (adicionadas.length || removidas.length) {
            let html = '';
            if (adicionadas.length) {
                html += `<div style="margin-bottom:8px"><span class="badge badge-success">+${adicionadas.length} adicionada(s)</span> ${adicionadas.map(c => `<span class="badge badge-info">${c}</span>`).join(' ')}</div>`;
            }
            if (removidas.length) {
                html += `<div><span class="badge badge-danger">-${removidas.length} removida(s)</span> ${removidas.map(c => `<span class="badge badge-warning">${c}</span>`).join(' ')}</div>`;
            }
            colInfo.innerHTML = html;
            document.getElementById('df-colunas-box').style.display = 'block';
        } else {
            document.getElementById('df-colunas-box').style.display = 'none';
        }

        // Historico detalhado
        const histDiv = document.getElementById('df-historico');
        const historico = j.historico || [];

        if (!historico.length) {
            histDiv.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.85rem">Nenhuma operacao executada ainda</div>';
        } else {
            histDiv.innerHTML = historico.map((h, i) => {
                const { descOp, detalhes } = describePasso(h);
                const diffLinhas = (h.linhas_depois || 0) - (h.linhas_antes || 0);
                const diffCols = (h.colunas_depois || 0) - (h.colunas_antes || 0);
                const iconCls = diffLinhas < 0 ? 'red' : diffLinhas > 0 ? 'green' : diffCols !== 0 ? 'yellow' : 'blue';

                let linhasExtra = '';
                if (diffLinhas !== 0 || diffCols !== 0) {
                    const partes = [];
                    if (diffLinhas !== 0) partes.push(`${diffLinhas > 0 ? '+' : ''}${fmtNum(diffLinhas)} linhas`);
                    if (diffCols !== 0) partes.push(`${diffCols > 0 ? '+' : ''}${diffCols} colunas`);
                    linhasExtra = `<div style="margin-top:4px; font-size:0.75rem"><span class="badge ${diffLinhas < 0 ? 'badge-danger' : diffLinhas > 0 ? 'badge-success' : 'badge-info'}">${partes.join(' | ')}</span></div>`;
                }

                let detalhesHtml = '';
                if (detalhes.length) {
                    detalhesHtml = `<div style="margin-top:6px; font-size:0.78rem; color:var(--text-muted)">${detalhes.join('<br>')}</div>`;
                }

                return `
                    <div class="item" style="flex-direction:column; align-items:flex-start; padding:14px 16px">
                        <div style="display:flex; align-items:center; gap:10px; width:100%">
                            <div class="item-icon ${iconCls}" style="flex-shrink:0">${i + 1}</div>
                            <div style="flex:1">
                                <div style="font-weight:600; font-size:0.88rem; color:var(--text-primary)">${h.operacao || '(sem descricao)'}</div>
                                <div style="font-size:0.78rem; color:var(--text-muted); margin-top:2px">
                                    ${h.linhas_antes || 0} linhas, ${h.colunas_antes || 0} colunas
                                    <span style="margin:0 4px">&#8594;</span>
                                    ${h.linhas_depois || 0} linhas, ${h.colunas_depois || 0} colunas
                                </div>
                                ${linhasExtra}
                                ${detalhesHtml}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

    } catch (e) {
        loading.innerHTML = `<div style="color:var(--text-muted); font-size:0.9rem">Erro ao carregar: ${e.message}</div>`;
    }
}

/* ── UPLOAD ────────────────────────────────────────────────────── */
async function uploadFile(file) {
    const uploadArea = document.getElementById('upload-area');
    const fd = new FormData();
    fd.append('arquivo', file);
    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    uploadArea.querySelector('.upload-text').innerHTML = 'Carregando<span class="loading-dots"></span>';
    uploadArea.querySelector('.upload-hint').textContent = `${sizeMB} MB — arquivos grandes podem levar alguns minutos`;
    uploadArea.style.pointerEvents = 'none';

    // Timeout maior para arquivos massivos (10 min)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);

    try {
        const r = await fetch(`/upload/${SID}`, {
            method: 'POST',
            body: fd,
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        const j = await r.json();
        if (j.ok) {
            document.getElementById('upload-status').style.display = 'block';
            document.getElementById('upload-nome').textContent = file.name;
            document.getElementById('upload-linhas').textContent = fmtNum(j.linhas);
            const colDiv = document.getElementById('upload-colunas');
            colDiv.innerHTML = j.colunas.map(c => `<span class="badge badge-info">${c}</span>`).join('');
            uploadArea.querySelector('.upload-icon').innerHTML = '&#10003;';
            uploadArea.querySelector('.upload-text').textContent = 'Arquivo carregado!';
            uploadArea.querySelector('.upload-hint').textContent = '';
            updateEstado();
            showNotification('Arquivo carregado com sucesso!', 'success');
        } else {
            showNotification('Erro: ' + j.mensagem, 'error');
            uploadArea.querySelector('.upload-text').textContent = 'Arraste ou clique para selecionar';
            uploadArea.querySelector('.upload-hint').textContent = 'Formatos aceitos: .csv, .xlsx, .xls';
            uploadArea.style.pointerEvents = '';
        }
    } catch (e) {
        clearTimeout(timeoutId);
        if (e.name === 'AbortError') {
            showNotification('Tempo esgotado. Arquivo muito grande ou conexao lenta.', 'error');
        } else {
            showNotification('Erro de conexao: ' + e.message, 'error');
        }
        uploadArea.querySelector('.upload-text').textContent = 'Arraste ou clique para selecionar';
        uploadArea.querySelector('.upload-hint').textContent = 'Formatos aceitos: .csv, .xlsx, .xls';
        uploadArea.style.pointerEvents = '';
    }
}
    } catch (e) {
        showNotification('Erro de conexao: ' + e.message, 'error');
        uploadArea.querySelector('.upload-text').textContent = 'Arraste ou clique para selecionar';
        uploadArea.querySelector('.upload-hint').textContent = 'Formatos aceitos: .csv, .xlsx, .xls';
        uploadArea.style.pointerEvents = '';
    }
}

/* ── DIAGNOSTICO ─────────────────────────────────────────────── */
async function runDiagnostico() {
    document.getElementById('diag-loading').style.display = 'block';
    document.getElementById('diag-result').style.display = 'none';
    document.getElementById('btn-diag').disabled = true;

    try {
        const r = await fetch(`/diagnostico/${SID}`);
        const j = await r.json();
        document.getElementById('diag-loading').style.display = 'none';
        document.getElementById('btn-diag').disabled = false;

        if (j.ok) {
            document.getElementById('diag-result').style.display = 'block';
            document.getElementById('diag-count').textContent = j.problemas;
            document.getElementById('diag-sugestoes-count').textContent = j.sugestoes.length;
            document.getElementById('diag-status').innerHTML = j.problemas === 0
                ? '<span class="badge badge-success">Saudavel</span>'
                : '<span class="badge badge-warning">Atencao</span>';
            document.getElementById('diag-resumo').textContent = j.resumo;

            if (j.sugestoes.length) {
                document.getElementById('diag-sugestoes-box').style.display = 'block';
                const list = document.getElementById('diag-sugestoes-list');
                list.innerHTML = j.sugestoes.map((s, i) => `
                    <div class="item">
                        <div class="item-info">
                            <div class="item-icon yellow">&#9888;</div>
                            <div>
                                <div style="font-weight:500; font-size:0.88rem">${s.descricao || s.operacao}</div>
                                <div style="font-size:0.78rem; color:var(--text-muted)">${s.operacao}</div>
                            </div>
                        </div>
                        <span class="badge badge-warning">sugestao</span>
                    </div>
                `).join('');
            } else {
                document.getElementById('diag-sugestoes-box').style.display = 'none';
            }
        } else {
            showNotification(j.mensagem, 'error');
        }
    } catch (e) {
        document.getElementById('diag-loading').style.display = 'none';
        document.getElementById('btn-diag').disabled = false;
        showNotification('Erro: ' + e.message, 'error');
    }
}

async function aplicarSugestoes() {
    try {
        const r = await fetch(`/aplicar_sugestoes/${SID}`, { method: 'POST' });
        const j = await r.json();
        if (j.ok) {
            showNotification(`${j.resultados.length} sugestao(es) aplicada(s)!`, 'success');
            updateEstado();
        } else {
            showNotification(j.mensagem, 'error');
        }
    } catch (e) { showNotification('Erro: ' + e.message, 'error'); }
}

/* ── LIMPEZA ─────────────────────────────────────────────────── */
function getMultiSelect(id) {
    const el = document.getElementById(id);
    if (!el) return [];
    return Array.from(el.selectedOptions).map(o => o.value);
}

function adicionarLimpeza() {
    const op = document.getElementById('limp-operacao').value;
    if (!op) { showNotification('Selecione uma operacao', 'error'); return; }

    let params = {};
    switch (op) {
        case 'remover_duplicatas':
            params = { colunas: getMultiSelect('lp-col') || null };
            break;
        case 'remover_nulos':
            params = { colunas: getMultiSelect('lp-col') };
            break;
        case 'preencher_nulos': {
            const cols = getMultiSelect('lp-col');
            const val = document.getElementById('lp-valor')?.value || '';
            const est = {};
            cols.forEach(c => est[c] = val || '');
            params = { estrategias: est };
            break;
        }
        case 'remover_colunas_vazias':
            params = { limiar: parseFloat(document.getElementById('lp-limiar')?.value || 1) };
            break;
        case 'substituir_valores': {
            const cols = getMultiSelect('lp-col');
            const ant = document.getElementById('lp-antigo')?.value;
            const nov = document.getElementById('lp-novo')?.value;
            const map = {}; if (ant) map[ant] = nov;
            params = { colunas: cols, mapeamento: map };
            break;
        }
        case 'substituir_regex':
            params = { colunas: getMultiSelect('lp-col'), padrao: document.getElementById('lp-padrao')?.value, novo: document.getElementById('lp-novo')?.value };
            break;
        case 'normalizar_texto':
            params = { colunas: getMultiSelect('lp-col'), modo: document.getElementById('lp-modo')?.value };
            break;
        case 'corrigir_tipo':
            params = { tipos: { [document.getElementById('lp-col')?.value]: document.getElementById('lp-tipo')?.value } };
            break;
        case 'unificar_valores': {
            const col = document.getElementById('lp-col')?.value;
            const certo = document.getElementById('lp-certo')?.value;
            const vars = (document.getElementById('lp-variantes')?.value || '').split(',').map(s=>s.trim()).filter(Boolean);
            const map = {}; if (certo) map[certo] = vars;
            params = { coluna: col, mapeamento: map };
            break;
        }
        case 'formatar_brasileiro':
            params = { colunas: getMultiSelect('lp-col'), casas: parseInt(document.getElementById('lp-casas')?.value || 2) };
            break;
    }

    etapasLimpeza.push({ operacao: op, params });
    renderFilaLimpeza();
    showNotification(`Etapa "${op}" adicionada`, 'success');
}

function renderFilaLimpeza() {
    const div = document.getElementById('limp-fila');
    if (!etapasLimpeza.length) {
        div.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.85rem">Nenhuma etapa adicionada</div>';
        return;
    }
    div.innerHTML = etapasLimpeza.map((e, i) => `
        <div class="item">
            <div class="item-info">
                <div class="item-icon blue">${i+1}</div>
                <div>
                    <div style="font-weight:500; font-size:0.88rem">${e.operacao}</div>
                    <div style="font-size:0.78rem; color:var(--text-muted)">${JSON.stringify(e.params).substring(0,80)}</div>
                </div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="etapasLimpeza.splice(${i},1);renderFilaLimpeza()">&#10005;</button>
        </div>
    `).join('');
}

async function executarLimpeza() {
    if (!etapasLimpeza.length) { showNotification('Nenhuma etapa pendente', 'error'); return; }

    for (const e of etapasLimpeza) {
        await fetch(`/limpeza/${SID}`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(e)
        });
    }

    try {
        const r = await fetch(`/executar_limpeza/${SID}`, { method: 'POST' });
        const j = await r.json();
        if (j.ok) {
            etapasLimpeza = [];
            renderFilaLimpeza();
            document.getElementById('limp-result').style.display = 'block';
            document.getElementById('limp-result-list').innerHTML = j.resultados.map(r => `
                <div class="item">
                    <div class="item-info">
                        <div class="item-icon green">&#10003;</div>
                        <div style="font-size:0.88rem">${r}</div>
                    </div>
                </div>
            `).join('');
            updateEstado();
            showNotification('Limpeza executada com sucesso!', 'success');
        } else {
            showNotification(j.mensagem, 'error');
        }
    } catch (e) { showNotification('Erro: ' + e.message, 'error'); }
}

/* ── MANIPULACAO ─────────────────────────────────────────────── */
function adicionarManipulacao() {
    const op = document.getElementById('manip-operacao').value;
    if (!op) { showNotification('Selecione uma operacao', 'error'); return; }

    let params = {};
    const g = id => document.getElementById(id)?.value;

    switch (op) {
        case 'esquerda': case 'direita':
            params = { coluna: g('mp-col'), n: parseInt(g('mp-n')), nova_coluna: g('mp-nova') || undefined };
            break;
        case 'meio':
            params = { coluna: g('mp-col'), inicio: parseInt(g('mp-inicio')), n: parseInt(g('mp-n')), nova_coluna: g('mp-nova') || undefined };
            break;
        case 'tamanho':
            params = { coluna: g('mp-col'), nova_coluna: g('mp-nova') || undefined };
            break;
        case 'concatenar': {
            const cols = getMultiSelect('mp-col');
            params = { colunas: cols, separador: g('mp-sep') || '', nova_coluna: g('mp-nova') || 'concat' };
            break;
        }
        case 'substituir_texto':
            params = { coluna: g('mp-col'), antigo: g('mp-antigo'), novo: g('mp-novo'), nova_coluna: g('mp-nova') || undefined };
            break;
        case 'se':
            params = { condicao: g('mp-cond'), valor_verdadeiro: g('mp-vv'), valor_falso: g('mp-vf'), nova_coluna: g('mp-nova') || 'resultado_se' };
            break;
        case 'arred':
            params = { coluna: g('mp-col'), casas: parseInt(g('mp-casas')), nova_coluna: g('mp-nova') || undefined };
            break;
        case 'cont_se':
            params = { coluna: g('mp-col'), criterio: g('mp-crit') };
            break;
        case 'somase':
            params = { coluna_valores: g('mp-colval'), coluna_criterios: g('mp-colcrit'), criterio: g('mp-crit') };
            break;
        case 'coluna_calculada':
            params = { nome: g('mp-nova'), expressao: g('mp-expr') };
            break;
        case 'adicionar_coluna':
            params = { nome: g('mp-nome'), valor: g('mp-valor') };
            break;
        case 'renomear_coluna':
            params = { mapeamento: { [g('mp-col')]: g('mp-novo') } };
            break;
        case 'remover_coluna':
            params = { colunas: [g('mp-col')] };
            break;
        case 'ordenar_por':
            params = { colunas: [g('mp-col')], ascendente: g('mp-asc') === 'true' };
            break;
        case 'reordenar_colunas':
            params = { ordem: g('mp-ordem').split(',').map(s=>s.trim()) };
            break;
        case 'filtrar_linhas':
            params = { condicao: g('mp-cond') };
            break;
        case 'juntar':
            params = { tabela: g('mp-tabela'), coluna_chave: g('mp-col'), tipo: g('mp-tipo') };
            break;
        case 'agregar':
            params = { colunas_grupo: g('mp-grupo').split(',').map(s=>s.trim()), coluna_alvo: g('mp-col'), funcao: g('mp-func') };
            break;
        case 'procv':
            params = { tabela_origem: g('mp-tabela'), coluna_chave: g('mp-col'), coluna_chave_origem: g('mp-chaveref'), coluna_valor_origem: g('mp-valorref') };
            break;
        case 'indice_corresp': {
            let vp = g('mp-valorproc');
            // Se o valor procurado e o nome de uma coluna existente, usa como coluna
            const colunasAtuais = typeof COLUNAS !== 'undefined' ? COLUNAS : [];
            if (colunasAtuais.includes(vp)) { /* mantem como string, sera interpretado como coluna */ }
            params = { coluna_retorno: g('mp-colret'), valor_procurado: vp, coluna_busca: g('mp-colbusca') };
            break;
        }
        case 'corresp':
            params = { valor: g('mp-valor'), coluna_busca: g('mp-col') };
            break;
        case 'harmonica':
            params = { coluna: g('mp-col') };
            break;
        case 'correl':
            params = { col_a: g('mp-cola'), col_b: g('mp-colb'), metodo: g('mp-metodo') || 'pearson' };
            break;
        case 'pearson':
            params = { col_a: g('mp-cola'), col_b: g('mp-colb') };
            break;
        case 'spearman':
            params = { col_a: g('mp-cola'), col_b: g('mp-colb') };
            break;
    }

    etapasManip.push({ operacao: op, params });
    renderFilaManip();
    showNotification(`Etapa "${op}" adicionada`, 'success');
}

function renderFilaManip() {
    const div = document.getElementById('manip-fila');
    if (!etapasManip.length) {
        div.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:0.85rem">Nenhuma etapa adicionada</div>';
        return;
    }
    div.innerHTML = etapasManip.map((e, i) => `
        <div class="item">
            <div class="item-info">
                <div class="item-icon blue">${i+1}</div>
                <div>
                    <div style="font-weight:500; font-size:0.88rem">${e.operacao}</div>
                    <div style="font-size:0.78rem; color:var(--text-muted)">${JSON.stringify(e.params).substring(0,80)}</div>
                </div>
            </div>
            <button class="btn btn-ghost btn-sm" onclick="etapasManip.splice(${i},1);renderFilaManip()">&#10005;</button>
        </div>
    `).join('');
}

async function executarManipulacao() {
    if (!etapasManip.length) { showNotification('Nenhuma etapa pendente', 'error'); return; }

    for (const e of etapasManip) {
        await fetch(`/manipulacao/${SID}`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(e)
        });
    }

    try {
        const r = await fetch(`/executar_manipulacao/${SID}`, { method: 'POST' });
        const j = await r.json();
        if (j.ok) {
            etapasManip = [];
            renderFilaManip();
            document.getElementById('manip-result').style.display = 'block';
            document.getElementById('manip-result-list').innerHTML = j.resultados.map(r => `
                <div class="item">
                    <div class="item-info">
                        <div class="item-icon green">&#10003;</div>
                        <div style="font-size:0.88rem">${r}</div>
                    </div>
                </div>
            `).join('');
            updateEstado();
            showNotification('Manipulacao executada com sucesso!', 'success');
        } else {
            showNotification(j.mensagem, 'error');
        }
    } catch (e) { showNotification('Erro: ' + e.message, 'error'); }
}

/* ── PREVIEW ────────────────────────────────────────────────── */
async function carregarPreview() {
    try {
        const r = await fetch(`/preview/${SID}`);
        const j = await r.json();
        if (!j.ok) { showNotification(j.mensagem, 'error'); return; }

        document.getElementById('preview-box').style.display = 'block';
        document.getElementById('preview-thead').innerHTML = '<tr>' + j.colunas.map(c => `<th>${c}</th>`).join('') + '</tr>';
        document.getElementById('preview-tbody').innerHTML = j.linhas.map(l =>
            '<tr>' + l.map(v => `<td>${v !== null && v !== undefined ? v : ''}</td>`).join('') + '</tr>'
        ).join('');
        document.getElementById('preview-count').textContent = j.linhas.length;
        document.getElementById('preview-total').textContent = j.total_linhas;
    } catch (e) { showNotification('Erro: ' + e.message, 'error'); }
}

/* ── EXPORTAR ───────────────────────────────────────────────── */
async function exportarDados() {
    try {
        const r = await fetch(`/exportar/${SID}`);
        const j = await r.json();
        if (j.ok) {
            document.getElementById('export-result').style.display = 'block';
            document.getElementById('export-file').textContent = j.arquivo;
            showNotification('Exportado com sucesso!', 'success');
        } else {
            showNotification(j.mensagem, 'error');
        }
    } catch (e) { showNotification('Erro: ' + e.message, 'error'); }
}

/* ── ESTADO ──────────────────────────────────────────────────── */
async function updateEstado() {
    try {
        const r = await fetch(`/estado/${SID}`);
        const j = await r.json();
        if (j.ok && j.tem_dados) {
            document.getElementById('estado-badge').style.display = '';
            document.getElementById('estado-linhas').textContent = fmtNum(j.linhas);
            document.getElementById('estado-colunas').textContent = j.colunas;
            window.COLUNAS = j.nomes_colunas;
        }
    } catch (e) {}
}

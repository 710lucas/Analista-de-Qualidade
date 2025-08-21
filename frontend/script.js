// Configurações e variáveis globais
const DEFAULT_API_KEY = 'AIzaSyDVosqOZH2DwbuStQUUL0qDXREMG_2fgLQ';
const DEFAULT_OPENAI_KEY = 'sk-proj-...'; // Adicionar chave OpenAI padrão se necessário
let currentResults = null;
let problemsChart = null;
let qualityChart = null;

// Elementos DOM
const elements = {
    form: document.getElementById('analysisForm'),
    repoUrl: document.getElementById('repoUrl'),
    apiKey: document.getElementById('apiKey'),
    modelSelect: document.getElementById('modelSelect'),
    apiKeyHelp: document.getElementById('apiKeyHelp'),
    analyzeBtn: document.getElementById('analyzeBtn'),
    loadingSection: document.getElementById('loadingSection'),
    loadingStatus: document.getElementById('loadingStatus'),
    progressFill: document.getElementById('progressFill'),
    resultsSection: document.getElementById('resultsSection'),
    repoInfo: document.getElementById('repoInfo'),
    downloadBtn: document.getElementById('downloadBtn'),
    newAnalysisBtn: document.getElementById('newAnalysisBtn'),
    recommendationsGrid: document.getElementById('recommendationsGrid'),
    uploadArea: document.getElementById('uploadArea'),
    jsonFileInput: document.getElementById('jsonFileInput'),
    selectFileBtn: document.getElementById('selectFileBtn')
};

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    initializeTabs();
    initializeFormTabs();
    initializeFileUpload();
});

function initializeEventListeners() {
    elements.form.addEventListener('submit', handleFormSubmit);
    elements.downloadBtn.addEventListener('click', downloadReport);
    elements.newAnalysisBtn.addEventListener('click', startNewAnalysis);
    
    // Event listener para mudança de modelo
    if (elements.modelSelect) {
        elements.modelSelect.addEventListener('change', updateApiKeyHelp);
        updateApiKeyHelp(); // Atualizar na inicialização
    }
}

function updateApiKeyHelp() {
    const selectedModel = elements.modelSelect.value;
    const helpText = elements.apiKeyHelp;
    
    if (selectedModel === 'gemini') {
        helpText.textContent = 'Se não informada, será usada a chave padrão do Gemini';
        elements.apiKey.placeholder = 'Chave API do Google Gemini (opcional)';
    } else if (selectedModel === 'gpt4-mini') {
        helpText.textContent = 'Chave API da OpenAI obrigatória para GPT-4 Mini';
        elements.apiKey.placeholder = 'Chave API da OpenAI (obrigatória)';
    }
}

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function initializeFormTabs() {
    const formTabButtons = document.querySelectorAll('.form-tab-btn');
    formTabButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.getAttribute('data-form-tab');
            switchFormTab(tabName);
        });
    });
}

function initializeFileUpload() {
    // Event listeners para upload de arquivo
    if (elements.selectFileBtn) {
        elements.selectFileBtn.addEventListener('click', () => {
            elements.jsonFileInput.click();
        });
    }

    if (elements.jsonFileInput) {
        elements.jsonFileInput.addEventListener('change', handleFileSelect);
    }

    if (elements.uploadArea) {
        // Drag and drop
        elements.uploadArea.addEventListener('click', () => {
            elements.jsonFileInput.click();
        });

        elements.uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            elements.uploadArea.classList.add('dragover');
        });

        elements.uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            elements.uploadArea.classList.remove('dragover');
        });

        elements.uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            elements.uploadArea.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });
    }
}

function switchFormTab(tabName) {
    // Remover classe active de todos os botões e painéis
    document.querySelectorAll('.form-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.form-tab-content').forEach(panel => panel.classList.remove('active'));
    
    // Adicionar classe active ao botão e painel selecionados
    document.querySelector(`[data-form-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}AnalysisTab`).classList.add('active');
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    if (!file.type.includes('json') && !file.name.endsWith('.json')) {
        alert('Por favor, selecione um arquivo JSON válido.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const jsonData = JSON.parse(e.target.result);
            console.log('JSON carregado:', jsonData);
            
            // Validar se é um arquivo de análise válido
            if (!jsonData.analises || !jsonData.repositorio_url) {
                alert('O arquivo JSON não parece ser uma análise válida. Verifique se contém as seções "analises" e "repositorio_url".');
                return;
            }
            
            // Mostrar os resultados
            currentResults = jsonData;
            displayResults(jsonData);
            
        } catch (error) {
            console.error('Erro ao processar JSON:', error);
            alert('Erro ao processar o arquivo JSON. Verifique se o arquivo é válido.');
        }
    };
    
    reader.readAsText(file);
}

function switchTab(tabName) {
    // Remover classe active de todos os botões e painéis
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    
    // Adicionar classe active ao botão e painel selecionados
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}Details`).classList.add('active');
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const repoUrl = elements.repoUrl.value.trim();
    const selectedModel = elements.modelSelect.value;
    const apiKey = elements.apiKey.value.trim();
    
    if (!repoUrl) {
        alert('Por favor, insira a URL do repositório');
        return;
    }
    
    // Validar chave API para GPT-4 Mini
    if (selectedModel === 'gpt4-mini' && !apiKey) {
        alert('Chave API da OpenAI é obrigatória para usar GPT-4 Mini');
        return;
    }
    
    // Usar chave padrão para Gemini se não fornecida
    const finalApiKey = apiKey || (selectedModel === 'gemini' ? DEFAULT_API_KEY : '');
    
    await runAnalysis(repoUrl, finalApiKey, selectedModel);
}

async function runAnalysis(repoUrl, apiKey, model) {
    showLoading();
    
    try {
        // Simular progresso da análise
        await simulateProgress();
        
        // Executar análise real
        const results = await executeAnalysis(repoUrl, apiKey, model);
        
        if (results.status === 'erro' || results.erro) {
            throw new Error(results.erro_geral || results.erro || 'Erro desconhecido na análise');
        }
        
        currentResults = results;
        displayResults(results);
        
    } catch (error) {
        console.error('Erro na análise:', error);
        alert(`Erro durante a análise: ${error.message}`);
        hideLoading();
    }
}

async function executeAnalysis(repoUrl, apiKey, model) {
    try {
        // Para debug, vamos primeiro tentar com dados simulados
        console.log('Executando análise para:', repoUrl, 'com modelo:', model);
        
        // Dados simulados para teste
        const simulatedData = {
            "repositorio_url": repoUrl,
            "timestamp": new Date().toISOString(),
            "status": "sucesso",
            "tempo_execucao": "0:01:23",
            "modelo_usado": model,
            "analises": {
                "seguranca": {
                    "nivel_seguranca": "Médio",
                    "quantidade_vulnerabilidades": 3,
                    "quantidade_funcoes_sem_tratamento": 2,
                    "recomendacoes": [
                        "Implementar validação de entrada nos formulários",
                        "Adicionar sanitização de dados",
                        "Utilizar HTTPS em todas as comunicações"
                    ]
                },
                "desempenho": {
                    "nivel_desempenho": "Alto",
                    "quantidade_estruturas_ineficientes": 1,
                    "quantidade_funcoes_longas": 2,
                    "recomendacoes": [
                        "Otimizar consultas ao banco de dados",
                        "Implementar cache de dados",
                        "Reduzir complexidade de funções longas"
                    ]
                },
                "confiabilidade": {
                    "nivel_confiabilidade": "Médio",
                    "quantidade_problemas_erros": 4,
                    "quantidade_violacoes_padroes": 3,
                    "recomendacoes": [
                        "Adicionar tratamento de exceções",
                        "Implementar logging estruturado",
                        "Seguir padrões de codificação"
                    ]
                },
                "testes": {
                    "percentual_cobertura_estimado": 75,
                    "quantidade_testes": 45,
                    "quantidade_funcionalidades_sem_teste": 8,
                    "recomendacoes": [
                        "Aumentar cobertura de testes para 90%",
                        "Implementar testes de integração",
                        "Adicionar testes automatizados"
                    ]
                }
            }
        };
        
        // Comentar esta linha para usar dados reais
        // return simulatedData;
        
        // Fazer requisição para a API real
        const response = await fetch('/api/analyze-sync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_url: repoUrl,
                api_key: apiKey,
                model: model
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.erro || `Erro HTTP: ${response.status}`);
        }

        const results = await response.json();
        console.log('Resposta da API:', results);
        
        // Se a resposta não tem a estrutura esperada, usar dados simulados
        if (!results.analises) {
            console.warn('Dados incompletos da API, usando dados simulados');
            return simulatedData;
        }
        
        return results;
        
    } catch (error) {
        console.error('Erro na requisição:', error);
        throw error;
    }
}

async function simulateProgress() {
    const steps = [
        { message: 'Baixando repositório...', progress: 20 },
        { message: 'Extraindo arquivos...', progress: 40 },
        { message: 'Analisando segurança...', progress: 60 },
        { message: 'Analisando desempenho...', progress: 75 },
        { message: 'Analisando confiabilidade...', progress: 85 },
        { message: 'Analisando testes...', progress: 95 },
        { message: 'Finalizando análise...', progress: 100 }
    ];
    
    for (const step of steps) {
        elements.loadingStatus.textContent = step.message;
        elements.progressFill.style.width = step.progress + '%';
        await new Promise(resolve => setTimeout(resolve, 500));
    }
}

function showLoading() {
    elements.loadingSection.style.display = 'block';
    elements.resultsSection.style.display = 'none';
    elements.form.style.display = 'none';
}

function hideLoading() {
    elements.loadingSection.style.display = 'none';
    elements.form.style.display = 'block';
}

function displayResults(results) {
    console.log('Resultados recebidos:', results); // Debug log
    
    elements.loadingSection.style.display = 'none';
    elements.resultsSection.style.display = 'block';
    
    // Esconder o formulário quando mostrar resultados
    document.querySelector('.analysis-form').style.display = 'none';
    
    // Informações do repositório
    displayRepoInfo(results);
    
    // Métricas do dashboard
    displayMetrics(results);
    
    // Gráficos
    displayCharts(results);
    
    // Recomendações
    displayRecommendations(results);
    
    // Detalhes técnicos
    displayTechnicalDetails(results);
}

function displayRepoInfo(results) {
    const repoName = extractRepoName(results.repositorio_url);
    const analysisTime = new Date(results.timestamp).toLocaleString('pt-BR');
    const modelUsed = results.modelo_usado || 'N/A';
    const modelDisplay = modelUsed === 'gemini' ? 'Google Gemini 2.0 Flash' : 
                        modelUsed === 'gpt4-mini' ? 'OpenAI GPT-4 Mini' : modelUsed;
    
    elements.repoInfo.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
            <div>
                <strong>Repositório:</strong> ${repoName}<br>
                <strong>Analisado em:</strong> ${analysisTime}
            </div>
            <div>
                <strong>Modelo usado:</strong> ${modelDisplay}<br>
                <strong>Tempo de execução:</strong> ${results.tempo_execucao}<br>
                <strong>Status:</strong> <span class="status-${results.status}">${results.status}</span>
            </div>
        </div>
    `;
}

function displayMetrics(results) {
    console.log('Exibindo métricas para:', results); // Debug log
    
    const analises = results.analises || {};
    console.log('Análises extraídas:', analises); // Debug log
    
    // Segurança
    const seguranca = analises.seguranca.metricas || {};
    console.log('Dados de segurança:', seguranca); // Debug log
    updateMetricCard('security', {
        // score: calculateScore(seguranca.nivel_risco || 'N/A'),
        score: seguranca.nivel_risco == 'Alto' ? 'C' :
               seguranca.nivel_risco == 'Médio' ? 'B' :
               'A',
        issues: seguranca.vulnerabilidades_encontradas || 0,
        functions: seguranca.funcoes_sem_tratamento || 0
    });
    
    // Desempenho
    const desempenho = analises.desempenho.metricas || {};
    console.log('Dados de desempenho:', desempenho); // Debug log
    updateMetricCard('performance', {
        // score: calculateScore(desempenho.score_performance || 'N/A'),
        score: desempenho.score_performance + "%",
        structures: desempenho.estruturas_ineficientes || 0,
        functions: desempenho.funcoes_longas || 0
    });
    
    // Confiabilidade
    const confiabilidade = analises.confiabilidade.metricas || {};
    console.log('Dados de confiabilidade:', confiabilidade); // Debug log
    updateMetricCard('reliability', {
        // score: calculateScore(confiabilidade.nivel_confiabilidade || 'N/A'),
        score: confiabilidade.nivel_confiabilidade,
        errors: confiabilidade.problemas_tratamento_erros || 0,
        violations: confiabilidade.violacoes_padroes || 0
    });
    
    // Testes
    const testes = analises.testes.metricas || {};
    console.log('Dados de testes:', testes); // Debug log
    const coveragePercent = testes.cobertura_estimada || 0;
    updateMetricCard('testing', {
        score: coveragePercent + '%',
        coverage: coveragePercent,
        count: testes.quantidade_testes || 0
    });
}

function updateMetricCard(type, data) {
    console.log(`Atualizando métrica ${type} com dados:`, data); // Debug log
    
    const scoreElement = document.getElementById(`${type}Score`);
    
    if (!scoreElement) {
        console.error(`Elemento ${type}Score não encontrado!`);
        return;
    }
    
    switch(type) {
        case 'security':
            scoreElement.textContent = data.score;
            scoreElement.className = `metric-value ${getQualityClass(data.score)}`;
            
            const securityIssues = document.getElementById('securityIssues');
            const securityFunctions = document.getElementById('securityFunctions');
            
            if (securityIssues) securityIssues.textContent = `${data.issues} vulnerabilidades`;
            if (securityFunctions) securityFunctions.textContent = `${data.functions} funções sem tratamento`;
            break;
            
        case 'performance':
            scoreElement.textContent = data.score;
            scoreElement.className = `metric-value ${getQualityClass(data.score)}`;
            
            const performanceStructures = document.getElementById('performanceStructures');
            const performanceFunctions = document.getElementById('performanceFunctions');
            
            if (performanceStructures) performanceStructures.textContent = `${data.structures} estruturas ineficientes`;
            if (performanceFunctions) performanceFunctions.textContent = `${data.functions} funções longas`;
            break;
            
        case 'reliability':
            scoreElement.textContent = data.score;
            scoreElement.className = `metric-value ${getQualityClass(data.score)}`;
            
            const reliabilityErrors = document.getElementById('reliabilityErrors');
            const reliabilityViolations = document.getElementById('reliabilityViolations');
            
            if (reliabilityErrors) reliabilityErrors.textContent = `${data.errors} problemas de erro`;
            if (reliabilityViolations) reliabilityViolations.textContent = `${data.violations} violações de padrão`;
            break;
            
        case 'testing':
            scoreElement.textContent = data.score;
            scoreElement.className = `metric-value ${getQualityClass(data.coverage)}`;
            
            const testingCoverage = document.getElementById('testingCoverage');
            const testingCount = document.getElementById('testingCount');
            
            if (testingCoverage) testingCoverage.textContent = `${data.coverage}% cobertura`;
            if (testingCount) testingCount.textContent = `${data.count} testes`;
            break;
    }
}

function displayCharts(results) {
    displayProblemsChart(results);
    displayQualityChart(results);
}

function displayProblemsChart(results) {
    const ctx = document.getElementById('problemsChart').getContext('2d');
    
    if (problemsChart) {
        problemsChart.destroy();
    }
    
    const analises = results.analises || {};
    const seguranca = analises.seguranca.metricas || {};
    const desempenho = analises.desempenho.metricas || {};
    const confiabilidade = analises.confiabilidade.metricas || {};
    const testes = analises.testes.metricas || {};

    console.log('dados segurança problems chart', seguranca)
    console.log('dados desempenho problems chart', desempenho)
    console.log('dados confiabilidade problems chart', confiabilidade)
    console.log('dados testes problems chart', testes)

    const data = {
        labels: ['Segurança', 'Desempenho', 'Confiabilidade', 'Testes'],
        datasets: [{
            label: 'Problemas Encontrados',
            data: [
                (seguranca.vulnerabilidades_encontradas || 0) + (seguranca.funcoes_sem_tratamento || 0),
                (desempenho.estruturas_ineficientes || 0) + (desempenho.funcoes_longas || 0),
                (confiabilidade.problemas_tratamento_erros || 0) + (confiabilidade.violacoes_padroes || 0),
                testes.funcionalidades_sem_teste || 0
            ],
            backgroundColor: [
                'rgba(231, 76, 60, 0.6)',
                'rgba(243, 156, 18, 0.6)',
                'rgba(39, 174, 96, 0.6)',
                'rgba(52, 152, 219, 0.6)'
            ],
            borderColor: [
                'rgba(231, 76, 60, 1)',
                'rgba(243, 156, 18, 1)',
                'rgba(39, 174, 96, 1)',
                'rgba(52, 152, 219, 1)'
            ],
            borderWidth: 2
        }]
    };
    
    problemsChart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            }
        }
    });
}

function displayQualityChart(results) {
    const ctx = document.getElementById('qualityChart').getContext('2d');
    
    if (qualityChart) {
        qualityChart.destroy();
    }
    
    const analises = results.analises || {};
    const seguranca = analises.seguranca.metricas || {};
    const desempenho = analises.desempenho.metricas || {};
    const confiabilidade = analises.confiabilidade.metricas || {};
    const testes = analises.testes.metricas || {};

    console.log('dados segurança quality chart', seguranca)
    console.log('dados desempenho quality chart', desempenho)
    console.log('dados confiabilidade quality chart', confiabilidade)
    console.log('dados testes quality chart', testes)

    const data = {
        labels: ['Segurança', 'Desempenho', 'Confiabilidade', 'Testes'],
        datasets: [{
            label: 'Qualidade (%)',
            data: [
                getNumericScore(seguranca.nivel_risco),
                getNumericScore(desempenho.score_performance),
                getNumericScore(confiabilidade.nivel_confiabilidade),
                testes.cobertura_estimada || 0
            ],
            backgroundColor: 'rgba(102, 126, 234, 0.6)',
            borderColor: 'rgba(102, 126, 234, 1)',
            borderWidth: 2,
            fill: true
        }]
    };
    
    qualityChart = new Chart(ctx, {
        type: 'radar',
        data: data,
        options: {
            responsive: true,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function displayRecommendations(results) {
    const analises = results.analises;
    const categories = ['seguranca', 'desempenho', 'confiabilidade', 'testes'];
    const categoryNames = ['Segurança', 'Desempenho', 'Confiabilidade', 'Testes'];
    
    let html = '';
    
    categories.forEach((category, index) => {
        let recommendations = analises[category]?.dados_completos.recomendacoes || [];

        console.log('Recomendações de ' + categoryNames[index] + ':', recommendations);

        // Garantir que recommendations seja sempre um array
        if (typeof recommendations === 'string') {
            // Se for uma string, dividir por quebras de linha ou vírgulas
            recommendations = recommendations.split(/[,\n]/).filter(r => r.trim());
        } else if (!Array.isArray(recommendations)) {
            recommendations = [];
        }
        
        if (recommendations.length > 0) {
            html += `
                <div class="recommendation-card ${category}">
                    <h4><i class="fas fa-${getIconForCategory(category)}"></i> ${categoryNames[index]}</h4>
                    <ul>
                        ${recommendations.map(rec => `<li>${rec.trim()}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
    });
    
    if (html === '') {
        html = '<div class="no-recommendations">Nenhuma recomendação disponível no momento.</div>';
    }
    
    elements.recommendationsGrid.innerHTML = html;
}

function displayTechnicalDetails(results) {
    const analises = results.analises;
    
    // Detalhes de Segurança
    document.getElementById('securityDetails').innerHTML = createDetailsHTML(analises.seguranca.metricas, 'segurança');
    
    // Detalhes de Desempenho
    document.getElementById('performanceDetails').innerHTML = createDetailsHTML(analises.desempenho.metricas, 'desempenho');
    
    // Detalhes de Confiabilidade
    document.getElementById('reliabilityDetails').innerHTML = createDetailsHTML(analises.confiabilidade.metricas, 'confiabilidade');
    
    // Detalhes de Testes
    document.getElementById('testingDetails').innerHTML = createDetailsHTML(analises.testes.metricas, 'testes');
}

function createDetailsHTML(analysisData, category) {
    let html = '';
    
    Object.keys(analysisData).forEach(key => {
        if (key !== 'recomendacoes') {
            const value = analysisData[key];
            const formattedKey = formatDetailKey(key);
            
            html += `
                <div class="detail-item">
                    <h5>${formattedKey}</h5>
                    <p>${formatDetailValue(value)}</p>
                </div>
            `;
        }
    });
    
    return html;
}

// Funções auxiliares
function calculateScore(nivel) {
    switch(nivel) {
        case nivel>50 || nivel == 'Alto' : return 'A+';
        case (nivel>30 && nivel<50) || nivel == 'Médio' : return 'B';
        case nivel<30 || nivel == 'Baixo': return 'C';
        default: return 'N/A';
    }
}

function getNumericScore(nivel) {

    if(typeof nivel === 'number') 
        return nivel

    switch(nivel) {
        case 'Alto': return 85;
        case 'Médio': return 65;
        case 'Baixo': return 40;
        default: return 0;
    }
}

function getQualityClass(scoreOrLevel) {
    if (typeof scoreOrLevel === 'number') {
        if (scoreOrLevel >= 80) return 'quality-excellent';
        if (scoreOrLevel >= 60) return 'quality-good';
        if (scoreOrLevel >= 40) return 'quality-average';
        if (scoreOrLevel >= 20) return 'quality-poor';
        return 'quality-critical';
    } else {
        switch(scoreOrLevel) {
            case 'A+': return 'quality-excellent';
            case 'B': return 'quality-good';
            case 'C': return 'quality-poor';
            default: return 'quality-average';
        }
    }
}

function getIconForCategory(category) {
    const icons = {
        seguranca: 'shield-alt',
        desempenho: 'tachometer-alt',
        confiabilidade: 'check-circle',
        testes: 'vial'
    };
    return icons[category] || 'info-circle';
}

function extractRepoName(url) {
    const match = url.match(/github\.com\/([^\/]+\/[^\/]+)/);
    return match ? match[1] : url;
}

function formatDetailKey(key) {
    return key.replace(/_/g, ' ')
              .replace(/([a-z])([A-Z])/g, '$1 $2')
              .replace(/\b\w/g, l => l.toUpperCase());
}

function formatDetailValue(value) {
    if (typeof value === 'number') {
        return value.toLocaleString('pt-BR');
    }
    if (Array.isArray(value)) {
        return value.join(', ');
    }
    return String(value);
}

function downloadReport() {
    if (!currentResults) {
        alert('Nenhum resultado disponível para download');
        return;
    }
    
    const dataStr = JSON.stringify(currentResults, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `analise-qualidade-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
}

function startNewAnalysis() {
    elements.resultsSection.style.display = 'none';
    elements.form.style.display = 'block';
    
    // Mostrar a seção de análise
    document.querySelector('.analysis-form').style.display = 'block';
    
    // Limpar campos
    elements.repoUrl.value = '';
    elements.apiKey.value = '';
    elements.jsonFileInput.value = '';
    elements.modelSelect.value = 'gemini'; // Resetar para Gemini
    updateApiKeyHelp(); // Atualizar texto de ajuda
    currentResults = null;
    
    // Voltar para a tab de nova análise
    switchFormTab('new');
    
    // Limpar gráficos
    if (problemsChart) {
        problemsChart.destroy();
        problemsChart = null;
    }
    if (qualityChart) {
        qualityChart.destroy();
        qualityChart = null;
    }
}

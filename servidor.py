#!/usr/bin/env python3
"""
Servidor Flask para o Analisador de Qualidade de Código
Fornece uma API REST para o frontend web.
"""

import os
import json
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import queue
import logging

# Importar o analisador
from analisador_qualidade import RepositoryAnalyzer

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Permitir CORS para desenvolvimento

# Chave padrão do Gemini
DEFAULT_API_KEY = os.getenv('DEFAULT_API_KEY')

# Armazenar análises em andamento
active_analyses = {}

class AnalysisStatus:
    """Classe para rastrear o status de uma análise."""
    def __init__(self, analysis_id):
        self.id = analysis_id
        self.status = 'iniciando'
        self.progress = 0
        self.message = 'Preparando análise...'
        self.result = None
        self.error = None
        self.started_at = datetime.now()

def run_analysis_worker(analysis_id, repo_url, api_key, model='gemini'):
    """Worker thread para executar a análise."""
    try:
        status = active_analyses[analysis_id]
        
        # Criar analisador
        status.message = 'Inicializando analisador...'
        status.progress = 10
        analyzer = RepositoryAnalyzer(api_key, model)
        
        # Executar análise
        status.message = 'Executando análise...'
        status.progress = 20
        results = analyzer.run_analysis(repo_url)
        
        # Processar resultados
        status.message = 'Processando resultados...'
        status.progress = 90
        processed_results = analyzer._make_json_serializable(results)
        
        # Finalizar
        status.status = 'concluido'
        status.progress = 100
        status.message = 'Análise concluída!'
        status.result = processed_results
        
        logger.info(f"Análise {analysis_id} concluída com sucesso usando {model}")
        
    except Exception as e:
        logger.error(f"Erro na análise {analysis_id}: {str(e)}")
        status.status = 'erro'
        status.error = str(e)
        status.message = f'Erro na análise: {str(e)}'

@app.route('/')
def index():
    """Servir o arquivo HTML principal."""
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Servir arquivos estáticos do frontend."""
    return send_from_directory('frontend', filename)

@app.route('/api/analyze', methods=['POST'])
def start_analysis():
    """Iniciar uma nova análise."""
    try:
        data = request.get_json()
        
        if not data or 'repo_url' not in data:
            return jsonify({'erro': 'URL do repositório é obrigatória'}), 400
        
        repo_url = data['repo_url'].strip()
        api_key = data.get('api_key', '').strip() or DEFAULT_API_KEY
        model = data.get('model', 'gemini').strip()
        
        # Validar modelo
        if model not in ['gemini', 'gpt4-mini']:
            return jsonify({'erro': 'Modelo inválido. Use "gemini" ou "gpt4-mini"'}), 400
        
        # Validar URL
        if not repo_url.startswith(('http://', 'https://')):
            return jsonify({'erro': 'URL inválida'}), 400
        
        # Gerar ID único para a análise
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Criar status da análise
        status = AnalysisStatus(analysis_id)
        active_analyses[analysis_id] = status
        
        # Iniciar thread de análise
        thread = threading.Thread(
            target=run_analysis_worker,
            args=(analysis_id, repo_url, api_key, model)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Análise {analysis_id} iniciada para {repo_url} usando {model}")
        
        return jsonify({
            'analysis_id': analysis_id,
            'status': 'iniciado',
            'message': f'Análise iniciada com sucesso usando {model}'
        })
        
    except Exception as e:
        logger.error(f"Erro ao iniciar análise: {str(e)}")
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500

@app.route('/api/status/<analysis_id>', methods=['GET'])
def get_analysis_status(analysis_id):
    """Obter o status de uma análise."""
    try:
        if analysis_id not in active_analyses:
            return jsonify({'erro': 'Análise não encontrada'}), 404
        
        status = active_analyses[analysis_id]
        
        response = {
            'analysis_id': analysis_id,
            'status': status.status,
            'progress': status.progress,
            'message': status.message,
            'started_at': status.started_at.isoformat()
        }
        
        if status.status == 'concluido' and status.result:
            response['result'] = status.result
            # Remover da memória após entregar o resultado
            del active_analyses[analysis_id]
        elif status.status == 'erro':
            response['error'] = status.error
            # Remover da memória após entregar o erro
            del active_analyses[analysis_id]
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro ao obter status: {str(e)}")
        return jsonify({'erro': f'Erro interno: {str(e)}'}), 500

@app.route('/api/analyze-sync', methods=['POST'])
def analyze_sync():
    """Análise síncrona para compatibilidade."""
    try:
        data = request.get_json()
        
        if not data or 'repo_url' not in data:
            return jsonify({'erro': 'URL do repositório é obrigatória'}), 400
        
        repo_url = data['repo_url'].strip()
        api_key = data.get('api_key', '').strip() or DEFAULT_API_KEY
        model = data.get('model', 'gemini').strip()
        
        # Validar modelo
        if model not in ['gemini', 'gpt4-mini']:
            return jsonify({'erro': 'Modelo inválido. Use "gemini" ou "gpt4-mini"'}), 400
        
        # Validar URL
        if not repo_url.startswith(('http://', 'https://')):
            return jsonify({'erro': 'URL inválida'}), 400
        
        logger.info(f"Iniciando análise síncrona para {repo_url} usando {model}")
        
        # Executar análise
        analyzer = RepositoryAnalyzer(api_key, model)
        results = analyzer.run_analysis(repo_url)
        processed_results = analyzer._make_json_serializable(results)
        
        logger.info(f"Análise síncrona concluída para {repo_url} usando {model}")
        
        return jsonify(processed_results)
        
    except Exception as e:
        logger.error(f"Erro na análise síncrona: {str(e)}")
        return jsonify({'erro': f'Erro na análise: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint de saúde da API."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'active_analyses': len(active_analyses)
    })

@app.errorhandler(404)
def not_found(error):
    """Handler para 404."""
    return jsonify({'erro': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handler para 500."""
    logger.error(f"Erro interno: {str(error)}")
    return jsonify({'erro': 'Erro interno do servidor'}), 500

# Limpeza periódica de análises antigas
def cleanup_old_analyses():
    """Remove análises antigas da memória."""
    import threading
    import time
    
    def cleanup_worker():
        while True:
            try:
                current_time = datetime.now()
                to_remove = []
                
                for analysis_id, status in active_analyses.items():
                    # Remove análises com mais de 1 hora
                    if (current_time - status.started_at).total_seconds() > 3600:
                        to_remove.append(analysis_id)
                
                for analysis_id in to_remove:
                    del active_analyses[analysis_id]
                    logger.info(f"Análise antiga {analysis_id} removida da memória")
                
            except Exception as e:
                logger.error(f"Erro na limpeza: {str(e)}")
            
            time.sleep(300)  # Verificar a cada 5 minutos
    
    cleanup_thread = threading.Thread(target=cleanup_worker)
    cleanup_thread.daemon = True
    cleanup_thread.start()

if __name__ == '__main__':
    # Iniciar limpeza automática
    cleanup_old_analyses()
    
    # Determinar se está em modo de desenvolvimento
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"Iniciando servidor na porta {port}")
    logger.info(f"Modo debug: {debug_mode}")
    logger.info(f"Frontend disponível em: http://localhost:{port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True
    )

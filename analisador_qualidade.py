#!/usr/bin/env python3
"""
Analisador de Qualidade de Código
Automatiza a análise de repositórios GitHub usando múltiplos crews especializados.
"""

import os
import json
import tempfile
import zipfile
import requests
import shutil
import hashlib
import secrets
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

# Imports do CrewAI
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
from crewai import Crew, Agent, LLM, Task


class RepositoryAnalyzer:
    """Classe principal para análise de qualidade de repositórios."""
    
    def __init__(self, api_key: str, model: str = "gemini"):
        """Inicializa o analisador com a chave da API e modelo especificado."""
        self.api_key = api_key
        self.model = model
        self.extracted_dir = None
        self.llm = None
        self.tools = {}
        self._setup_environment()
        self._setup_llm()
        self._setup_tools()
    
    def _make_json_serializable(self, obj):
        """Converte objetos para formato JSON serializável."""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            # Para objetos com atributos, converter para dict
            return self._make_json_serializable(obj.__dict__)
        elif hasattr(obj, 'json'):
            # Se tem método json, usar ele
            return obj.json
        elif hasattr(obj, 'raw'):
            # Se tem atributo raw, usar ele
            return str(obj.raw)
        else:
            # Para outros tipos, converter para string
            try:
                json.dumps(obj)  # Testar se é serializável
                return obj
            except TypeError:
                return str(obj)
    
    def _process_analysis_data(self, analysis_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa e simplifica os dados de análise para dashboard."""
        processed = {
            "metricas": {},
            "recomendacoes": "",
            "dados_completos": data
        }
        
        # Extrair métricas numéricas baseadas no tipo de análise
        if analysis_type == "seguranca":
            processed["metricas"] = {
                "funcoes_sem_tratamento": data.get("quantidade_funcoes_sem_tratamento", 0),
                "vulnerabilidades_encontradas": data.get("quantidade_vulnerabilidades", 0),
                "nivel_risco": self._calculate_security_risk_level(data)
            }
        elif analysis_type == "desempenho":
            processed["metricas"] = {
                "estruturas_ineficientes": data.get("quantidade_estruturas_ineficientes", 0),
                "funcoes_longas": data.get("quantidade_funcoes_longas", 0),
                "score_performance": self._calculate_performance_score(data)
            }
        elif analysis_type == "confiabilidade":
            processed["metricas"] = {
                "problemas_tratamento_erros": data.get("quantidade_problemas_erros", 0),
                "violacoes_padroes": data.get("quantidade_violacoes_padroes", 0),
                "nivel_confiabilidade": data.get("nivel_confiabilidade", "Não avaliado")
            }
        elif analysis_type == "testes":
            processed["metricas"] = {
                "quantidade_testes": data.get("quantidade_testes", 0),
                "funcionalidades_sem_teste": data.get("quantidade_funcionalidades_sem_teste", 0),
                "cobertura_estimada": data.get("percentual_cobertura_estimado", 0)
            }
        
        # Formatar recomendações como texto legível
        recomendacoes = data.get("recomendacoes", [])
        if isinstance(recomendacoes, list):
            processed["recomendacoes"] = "\n".join([f"• {rec}" for rec in recomendacoes])
        elif isinstance(recomendacoes, str):
            processed["recomendacoes"] = recomendacoes
        else:
            processed["recomendacoes"] = "Nenhuma recomendação disponível"
        
        return processed
    
    def _calculate_security_risk_level(self, data: Dict[str, Any]) -> str:
        """Calcula o nível de risco de segurança."""
        funcoes_sem_tratamento = data.get("quantidade_funcoes_sem_tratamento", 0)
        vulnerabilidades = data.get("quantidade_vulnerabilidades", 0)
        
        total_issues = funcoes_sem_tratamento + vulnerabilidades
        
        if total_issues == 0:
            return "Baixo"
        elif total_issues <= 3:
            return "Médio"
        else:
            return "Alto"
    
    def _calculate_performance_score(self, data: Dict[str, Any]) -> int:
        """Calcula o score de performance (0-100)."""
        estruturas_ineficientes = data.get("quantidade_estruturas_ineficientes", 0)
        funcoes_longas = data.get("quantidade_funcoes_longas", 0)
        
        total_issues = estruturas_ineficientes + funcoes_longas
        
        # Score base 100, diminui 10 pontos por cada problema
        score = max(0, 100 - (total_issues * 10))
        return score
    
    def _setup_environment(self):
        """Configura as variáveis de ambiente necessárias."""
        if self.model == "gemini":
            os.environ['GOOGLE_API_KEY'] = self.api_key
            os.environ['GEMINI_API_KEY'] = self.api_key
        elif self.model == "gpt4-mini":
            os.environ['OPENAI_API_KEY'] = self.api_key
    
    def _setup_llm(self):
        """Configura o modelo LLM."""
        if self.model == "gemini":
            self.llm = LLM(
                model="gemini/gemini-2.0-flash",
                temperature=0.0,
                api_key=self.api_key,
            )
        elif self.model == "gpt4-mini":
            self.llm = LLM(
                model="openai/gpt-4.1-mini",
                temperature=0.0,
                api_key=self.api_key,
            )
        else:
            raise ValueError(f"Modelo não suportado: {self.model}")
    
    def _setup_tools(self):
        """Configura as ferramentas personalizadas para análise de arquivos."""
        
        # Input schemas
        class FileReaderInput(BaseModel):
            filename: str = Field(..., description="Nome do arquivo que deve ser lido e retornado o conteúdo")
        
        class FileSearchInput(BaseModel):
            search_term: str = Field(..., description="Termo de busca para encontrar arquivos")
        
        class FileListInput(BaseModel):
            filter_extension: str = Field(default="", description="Filtro por extensão de arquivo")
        
        # FileReaderTool
        class FileReaderTool(BaseTool):
            model_config = {"extra": "allow"}
            name: str = "FileReader"
            description: str = "Ferramenta para ler o conteúdo de um arquivo específico do repositório."
            args_schema: Type[BaseModel] = FileReaderInput
            
            def __init__(self, analyzer):
                super().__init__()
                self.analyzer = analyzer
            
            def _run(self, filename: str) -> str:
                try:
                    if not self.analyzer.extracted_dir:
                        return "Erro: Diretório de arquivos não foi configurado."
                    
                    found_files = []
                    for root, dirs, files in os.walk(self.analyzer.extracted_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, self.analyzer.extracted_dir)
                            
                            if (file == filename or file.endswith(filename) or 
                                filename in file or filename in rel_path or 
                                rel_path.endswith(filename) or os.path.basename(filename) == file):
                                found_files.append((file_path, rel_path, file))
                    
                    if not found_files:
                        return f"Arquivo '{filename}' não encontrado no repositório."
                    
                    file_path, rel_path, file = found_files[0]
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        return f"Conteúdo do arquivo {rel_path}:\n\n{content}"
                    except UnicodeDecodeError:
                        try:
                            with open(file_path, 'r', encoding='latin-1') as f:
                                content = f.read()
                            return f"Conteúdo do arquivo {rel_path}:\n\n{content}"
                        except Exception as e:
                            return f"Erro ao ler o arquivo {rel_path}: {str(e)}"
                except Exception as e:
                    return f"Erro ao procurar o arquivo {filename}: {str(e)}"
        
        # FileSearchTool
        class FileSearchTool(BaseTool):
            model_config = {"extra": "allow"}
            name: str = "FileSearch"
            description: str = "Ferramenta para buscar arquivos por termo parcial."
            args_schema: Type[BaseModel] = FileSearchInput
            
            def __init__(self, analyzer):
                super().__init__()
                self.analyzer = analyzer
            
            def _run(self, search_term: str) -> str:
                try:
                    if not self.analyzer.extracted_dir:
                        return "Erro: Diretório de arquivos não foi configurado."
                    
                    matching_files = []
                    search_lower = search_term.lower()
                    
                    for root, dirs, files in os.walk(self.analyzer.extracted_dir):
                        for file in files:
                            rel_path = os.path.relpath(os.path.join(root, file), self.analyzer.extracted_dir)
                            if search_lower in file.lower() or search_lower in rel_path.lower():
                                matching_files.append(rel_path)
                    
                    if matching_files:
                        files_str = "\n".join(sorted(matching_files))
                        return f"Arquivos encontrados com o termo '{search_term}':\n\n{files_str}"
                    else:
                        return f"Nenhum arquivo encontrado com o termo '{search_term}'"
                except Exception as e:
                    return f"Erro ao buscar arquivos: {str(e)}"
        
        # FileListTool
        class FileListTool(BaseTool):
            model_config = {"extra": "allow"}
            name: str = "FileList"
            description: str = "Ferramenta para listar todos os arquivos do repositório."
            args_schema: Type[BaseModel] = FileListInput
            
            def __init__(self, analyzer):
                super().__init__()
                self.analyzer = analyzer
            
            def _run(self, filter_extension: str = "") -> str:
                try:
                    if not self.analyzer.extracted_dir:
                        return "Erro: Diretório de arquivos não foi configurado."
                    
                    files_list = []
                    for root, dirs, files in os.walk(self.analyzer.extracted_dir):
                        for file in files:
                            if not filter_extension or file.endswith(filter_extension):
                                rel_path = os.path.relpath(os.path.join(root, file), self.analyzer.extracted_dir)
                                files_list.append(rel_path)
                    
                    if files_list:
                        files_str = "\n".join(sorted(files_list))
                        filter_msg = f" (filtrado por {filter_extension})" if filter_extension else ""
                        return f"Arquivos encontrados no repositório{filter_msg}:\n\n{files_str}"
                    else:
                        return f"Nenhum arquivo encontrado com o filtro especificado: {filter_extension}"
                except Exception as e:
                    return f"Erro ao listar arquivos: {str(e)}"
        
        # Criar instâncias das ferramentas
        self.tools['file_reader'] = FileReaderTool(self)
        self.tools['file_search'] = FileSearchTool(self)
        self.tools['file_list'] = FileListTool(self)
    
    def _generate_secure_filename(self, repo_url: str) -> str:
        """Gera um nome de arquivo seguro com hash e salt."""
        # Gerar salt aleatório
        salt = secrets.token_hex(16)
        
        # Criar hash do URL + salt + timestamp
        timestamp = str(datetime.now().timestamp())
        data_to_hash = f"{repo_url}{salt}{timestamp}".encode('utf-8')
        hash_object = hashlib.sha256(data_to_hash)
        file_hash = hash_object.hexdigest()[:16]  # Primeiros 16 caracteres
        
        return f"repo_{file_hash}_{salt[:8]}.zip"
    
    def _cleanup_temp_files(self):
        """Remove arquivos temporários."""
        try:
            # Remover arquivo ZIP temporário
            if self.temp_zip_file and os.path.exists(self.temp_zip_file):
                os.remove(self.temp_zip_file)
                print(f"🗑️ Arquivo ZIP temporário removido: {self.temp_zip_file}")
                self.temp_zip_file = None
            
            # Remover diretório extraído
            if self.extracted_dir and os.path.exists(self.extracted_dir):
                shutil.rmtree(self.extracted_dir)
                print(f"🗑️ Diretório temporário removido: {self.extracted_dir}")
                self.extracted_dir = None
                
        except Exception as e:
            print(f"⚠️ Erro ao limpar arquivos temporários: {str(e)}")
    
    def download_repository(self, repo_url: str) -> bool:
        """Baixa o repositório a partir da URL."""
        try:
            # Converter URL do GitHub para link de download direto
            if "github.com" in repo_url:
                if repo_url.endswith('.git'):
                    repo_url = repo_url[:-4]
                if repo_url.endswith('/'):
                    repo_url = repo_url[:-1]
                download_url = f"{repo_url}/archive/refs/heads/main.zip"
            else:
                download_url = repo_url
            
            print(f"📥 Baixando repositório de: {download_url}")
            response = requests.get(download_url, timeout=30)
            
            if response.status_code == 200:
                # Gerar nome de arquivo seguro
                self.temp_zip_file = self._generate_secure_filename(repo_url)
                
                with open(self.temp_zip_file, "wb") as f:
                    f.write(response.content)
                print(f"✅ Repositório baixado: {self.temp_zip_file}")
                return self._extract_repository(self.temp_zip_file)
            else:
                print(f"❌ Erro ao baixar repositório: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao baixar repositório: {str(e)}")
            return False
    
    def _extract_repository(self, zip_filename: str) -> bool:
        """Extrai o arquivo ZIP do repositório."""
        try:
            self.extracted_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(self.extracted_dir)
            
            print(f"📂 Repositório extraído em: {self.extracted_dir}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao extrair repositório: {str(e)}")
            return False
    
    def _create_file_selector_crew(self) -> Crew:
        """Cria o crew de selecionar arquivos importantes para a analise"""
        agent = Agent(
            role="analista_de_arquivos_importantes",
            goal="""Selecionar arquivos relevantes para a análise de qualidade de código.""",
            backstory="""Você é um especialista em analisar arquivos em um projeto de software. 
                Você deve indicar quais são os arquivos mais importantes de serem analisados.
                Procure por arquivos de código-fonte, como .py, .js, .java, etc.
                Procure por arquivos de configuração.
                Informe, pelo menos, 10 arquivos, mas indique mais se houver.
                Não informe mais de 20 arquivos.
            """,
            tools=list(self.tools.values()),
            llm=self.llm
        )

        class TaskOutput (BaseModel):
            arquivos_importantes : list[str]
            quantidade_arquivos_importantes : int

        task = Task(
            description="""Analise o repositório em busca de arquivos importantes.
                Use FileList para ver arquivos e FileSearch para localizar arquivos específicos.
                Use FileReader para analisar os arquivos
                Identifique: arquivos de configuração, scripts de build, etc.
                Informe, pelo menos, 10 arquivos, mas indique mais se houver.
                Não informe mais de 20 arquivos.
            """,
            expected_output="""JSON com:
            - arquivos_importantes: lista de arquivos importantes (nome dos arquivos)
            - quantidade_arquivos_importantes: número""",
            agent=agent,
            llm=self.llm,
            output_json=TaskOutput
        )

        return Crew(agents=[agent], tasks=[task], llm=self.llm, verbose=True)

    def _create_security_crew(self) -> Crew:
        """Cria o crew de análise de segurança."""
        agent = Agent(
            role="analista_de_seguranca",
            goal="""Analisar código fonte em busca de falhas de segurança, focando em:
            1. Funções sem tratamento adequado de dados sensíveis
            2. Vulnerabilidades SAST conhecidas""",
            backstory="Especialista em segurança de software com foco em análise estática de código.",
            tools=list(self.tools.values()),
            llm=self.llm
        )

        class TaskOutput (BaseModel):
            funcoes_sem_tratamento : str
            vulnerabilidades_sast : str
            quantidade_funcoes_sem_tratamento : int
            quantidade_vulnerabilidades : int
            recomendacoes : list[str]

        task = Task(
            description="""Analise o repositório em busca de vulnerabilidades de segurança.
            Use FileList para ver arquivos, FileReader para analisar código.
            Identifique: funções sem tratamento de dados sensíveis, vulnerabilidades SAST.
            Analise somente os arquivos importantes para sua analise.
            os arquivos importantes são: {arquivos_importantes}
            """,
            expected_output="""JSON com:
            - funcoes_sem_tratamento: lista de funções problemáticas
            - vulnerabilidades_sast: lista de vulnerabilidades encontradas  
            - quantidade_funcoes_sem_tratamento: número
            - quantidade_vulnerabilidades: número
            - recomendacoes: lista de melhorias""",
            agent=agent,
            llm=self.llm,
            output_json=TaskOutput
        )
        
        return Crew(agents=[agent], tasks=[task], llm=self.llm, verbose=True)
    
    def _create_performance_crew(self) -> Crew:
        """Cria o crew de análise de desempenho."""
        agent = Agent(
            role="analista_de_desempenho",
            goal="""Analisar desempenho do código, focando em:
            1. Uso de estruturas de dados ineficientes
            2. Funções/métodos longos e complexos""",
            backstory="Especialista em otimização de performance e eficiência de código.",
            tools=list(self.tools.values()),
            llm=self.llm
        )

        class TaskOutput (BaseModel):
            estruturas_ineficientes : str
            funcoes_longas : str
            quantidade_estruturas_ineficientes : int
            quantidade_funcoes_longas : int
            recomendacoes : list[str]

        task = Task(
            description="""Analise o repositório em busca de problemas de desempenho.
            Use FileList para ver arquivos, FileReader para analisar código.
            Identifique: estruturas de dados ineficientes, funções muito longas.
            os arquivos importantes são: {arquivos_importantes}
            """,
            expected_output="""JSON com:
            - estruturas_ineficientes: lista de problemas encontrados
            - funcoes_longas: lista de funções com muitas linhas
            - quantidade_estruturas_ineficientes: número
            - quantidade_funcoes_longas: número
            - recomendacoes: lista de melhorias""",
            agent=agent,
            llm=self.llm,
            output_json=TaskOutput
        )
        
        return Crew(agents=[agent], tasks=[task], llm=self.llm, verbose=True)
    
    def _create_reliability_crew(self) -> Crew:
        """Cria o crew de análise de confiabilidade."""
        agent = Agent(
            role="analista_de_confiabilidade",
            goal="""Analisar confiabilidade do código, focando em:
            1. Cobertura de tratamento de erros
            2. Aderência a padrões de codificação""",
            backstory="Especialista em qualidade e confiabilidade de software.",
            tools=list(self.tools.values()),
            llm=self.llm
        )

        class TaskOutput (BaseModel):
            funcoes_sem_tratamento : str
            vulnerabilidades_sast : str
            quantidade_funcoes_sem_tratamento : int
            quantidade_vulnerabilidades : int
            recomendacoes : list[str]

        task = Task(
            description="""Analise o repositório em busca de problemas de confiabilidade.
            Use FileList para ver arquivos, FileReader para analisar código.
            Identifique: funções sem tratamento de erros, violações de padrões.
            Os arquivos importantes são: {arquivos_importantes}
            """,
            expected_output="""JSON com:
            - problemas_tratamento_erros: lista de problemas encontrados
            - violacoes_padroes: lista de violações de padrões
            - quantidade_problemas_erros: número
            - quantidade_violacoes_padroes: número
            - nivel_confiabilidade: Alto/Médio/Baixo
            - recomendacoes: lista de melhorias""",
            agent=agent,
            llm=self.llm,
            output_json=TaskOutput
        )
        
        return Crew(agents=[agent], tasks=[task], llm=self.llm, verbose=True)
    
    def _create_testing_crew(self) -> Crew:
        """Cria o crew de análise de testes."""
        agent = Agent(
            role="analista_de_testes",
            goal="""Analisar cobertura de testes, focando em:
            1. Cobertura do código por testes unitários
            2. Número de testes por funcionalidade""",
            backstory="Especialista em estratégias de teste e qualidade de software.",
            tools=list(self.tools.values()),
            llm=self.llm
        )

        class TaskOutput (BaseModel):
            arquivos_teste : str
            funcionalidades_sem_teste : str
            quantidade_testes : int
            quantidade_funcionalidades_sem_teste : int
            percentual_cobertura_estimado : int
            recomendacoes : list[str]

        task = Task(
            description="""Analise o repositório em busca de testes e cobertura.
            Use FileList para ver arquivos, FileSearch para buscar testes, FileReader para analisar.
            Identifique: arquivos de teste, funcionalidades sem testes.
            Os arquivos importantes são: {arquivos_importantes}
            """,
            expected_output="""JSON com:
            - arquivos_teste: lista de arquivos de teste encontrados
            - funcionalidades_sem_teste: lista de funcionalidades sem cobertura
            - quantidade_testes: número
            - quantidade_funcionalidades_sem_teste: número
            - percentual_cobertura_estimado: número
            - recomendacoes: lista de melhorias""",
            agent=agent,
            llm=self.llm,
            output_json=TaskOutput
        )
        
        return Crew(agents=[agent], tasks=[task], llm=self.llm, verbose=True)
    
    def run_analysis(self, repo_url: str) -> Dict[str, Any]:
        """Executa a análise completa do repositório."""
        start_time = datetime.now()
        
        print("🚀 Iniciando análise de qualidade de código...")
        
        # Download e extração do repositório
        if not self.download_repository(repo_url):
            return {"erro": "Falha ao baixar ou extrair o repositório"}
        
        results = {
            "repositorio_url": repo_url,
            "timestamp": start_time.isoformat(),
            "status": "sucesso",
            "modelo_usado": self.model,
            "analises": {}
        }
        
        try:
            # Executar análises
            crews = {
                "seguranca": self._create_security_crew(),
                "desempenho": self._create_performance_crew(),
                "confiabilidade": self._create_reliability_crew(),
                "testes": self._create_testing_crew()
            }

            print("analisando arquivos importantes")

            crew_arquivos_importantes = self._create_file_selector_crew()
            arquivos_importantes_result = crew_arquivos_importantes.kickoff()

            print(f"resultado arquivos importantes:{arquivos_importantes_result}")

            arquivos_importantes = arquivos_importantes_result['arquivos_importantes']

            # print("==================arquivos importantes são:", arquivos_importantes)

            # return {}

            for analysis_type, crew in crews.items():
                print(f"📊 Executando análise de {analysis_type}...")
                try:
                    result = crew.kickoff(inputs={'arquivos_importantes' : arquivos_importantes})
                    # Converter CrewOutput para formato serializável e parsear JSON
                    try:
                        parsed_data = None
                        
                        # Se o resultado tem um atributo 'json' ou 'raw', usar ele
                        if hasattr(result, 'json') and result.json:
                            if isinstance(result.json, str):
                                parsed_data = json.loads(result.json)
                            else:
                                parsed_data = result.json
                        elif hasattr(result, 'raw'):
                            # Tentar parsear o raw como JSON
                            import re
                            raw_content = str(result.raw)
                            json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                            if json_match:
                                parsed_data = json.loads(json_match.group())
                        elif isinstance(result, str):
                            # Procurar por JSON no resultado
                            import re
                            json_match = re.search(r'\{.*\}', result, re.DOTALL)
                            if json_match:
                                parsed_data = json.loads(json_match.group())
                        else:
                            # Converter para string e tentar extrair JSON
                            result_str = str(result)
                            import re
                            json_match = re.search(r'\{.*\}', result_str, re.DOTALL)
                            if json_match:
                                parsed_data = json.loads(json_match.group())
                        
                        # Se conseguiu parsear, processar os dados
                        if parsed_data:
                            results["analises"][analysis_type] = self._process_analysis_data(analysis_type, parsed_data)
                        else:
                            results["analises"][analysis_type] = {"erro": "Não foi possível extrair dados JSON", "resultado_bruto": str(result)}
                            
                    except Exception as parse_error:
                        print(f"⚠️ Erro ao processar resultado de {analysis_type}: {str(parse_error)}")
                        results["analises"][analysis_type] = {"erro_processamento": str(parse_error), "resultado_bruto": str(result)}
                        
                except Exception as e:
                    print(f"❌ Erro na análise de {analysis_type}: {str(e)}")
                    results["analises"][analysis_type] = {"erro": str(e)}
            
        except Exception as e:
            results["status"] = "erro_parcial"
            results["erro_geral"] = str(e)
        
        finally:
            # Limpeza completa de arquivos temporários
            self._cleanup_temp_files()
        
        end_time = datetime.now()
        results["tempo_execucao"] = str(end_time - start_time)
        
        # Gerar resumo do dashboard
        results["dashboard"] = self._generate_dashboard_summary(results.get("analises", {}))
        
        print("✅ Análise concluída!")
        return results
    
    def _generate_dashboard_summary(self, analises: Dict[str, Any]) -> Dict[str, Any]:
        """Gera um resumo para dashboard com métricas consolidadas."""
        dashboard = {
            "resumo_geral": {},
            "metricas_por_categoria": {},
            "score_geral": 0,
            "status_geral": "Não avaliado"
        }
        
        total_problemas = 0
        categorias_avaliadas = 0
        
        for categoria, dados in analises.items():
            if "metricas" in dados:
                metricas = dados["metricas"]
                dashboard["metricas_por_categoria"][categoria] = metricas
                
                # Contar problemas para score geral
                if categoria == "seguranca":
                    problemas = metricas.get("funcoes_sem_tratamento", 0) + metricas.get("vulnerabilidades_encontradas", 0)
                elif categoria == "desempenho":
                    problemas = metricas.get("estruturas_ineficientes", 0) + metricas.get("funcoes_longas", 0)
                elif categoria == "confiabilidade":
                    problemas = metricas.get("problemas_tratamento_erros", 0) + metricas.get("violacoes_padroes", 0)
                elif categoria == "testes":
                    problemas = metricas.get("funcionalidades_sem_teste", 0)
                
                total_problemas += problemas
                categorias_avaliadas += 1
        
        # Calcular score geral (0-100)
        if categorias_avaliadas > 0:
            score_base = 100
            penalidade_por_problema = 5
            dashboard["score_geral"] = max(0, score_base - (total_problemas * penalidade_por_problema))
            
            # Determinar status geral
            if dashboard["score_geral"] >= 80:
                dashboard["status_geral"] = "Excelente"
            elif dashboard["score_geral"] >= 60:
                dashboard["status_geral"] = "Bom"
            elif dashboard["score_geral"] >= 40:
                dashboard["status_geral"] = "Regular"
            else:
                dashboard["status_geral"] = "Necessita melhorias"
        
        dashboard["resumo_geral"] = {
            "total_problemas_encontrados": total_problemas,
            "categorias_analisadas": categorias_avaliadas,
            "score_qualidade": dashboard["score_geral"],
            "recomendacao_principal": self._get_main_recommendation(total_problemas)
        }
        
        return dashboard
    
    def _get_main_recommendation(self, total_problemas: int) -> str:
        """Retorna a recomendação principal baseada no número de problemas."""
        if total_problemas == 0:
            return "Código em excelente estado! Continue mantendo as boas práticas."
        elif total_problemas <= 5:
            return "Código em bom estado com poucos problemas. Revise as recomendações específicas."
        elif total_problemas <= 15:
            return "Código necessita melhorias. Priorize correções de segurança e performance."
        else:
            return "Código necessita revisão urgente. Implemente melhorias significativas na qualidade."


def main():
    """Função principal para uso como script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analisador de Qualidade de Código')
    parser.add_argument('repo_url', help='URL do repositório GitHub')
    parser.add_argument('--api-key', required=True, help='Chave da API')
    parser.add_argument('--model', choices=['gemini', 'gpt4-mini'], default='gemini', 
                       help='Modelo de IA a ser usado (padrão: gemini)')
    parser.add_argument('--output', '-o', help='Arquivo de saída JSON (opcional)')
    
    args = parser.parse_args()
    
    # Criar analisador e executar
    analyzer = RepositoryAnalyzer(args.api_key, args.model)
    results = analyzer.run_analysis(args.repo_url)

    # Garantir que os resultados sejam serializáveis
    results = analyzer._make_json_serializable(results)
    
    print("results:", results)
    
    # Salvar resultados
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"📄 Resultados salvos em: {args.output}")
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

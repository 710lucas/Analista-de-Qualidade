# Analisador de Qualidade de Repositórios

> Este projeto realiza a análise automatizada dos principais arquivos de um repositório de código, identificando características de qualidade de software como segurança, desempenho, confiabilidade e cobertura de testes.

## Para que serve?
O sistema permite que você avalie rapidamente a qualidade de projetos hospedados no GitHub, gerando relatórios detalhados e recomendações para melhoria. Ideal para times de desenvolvimento, revisão de código, auditoria e ensino.

## Estrutura do repositório
- `frontend/`: Interface web moderna para interação, upload de resultados e visualização dos relatórios.
- `servidor.py`: Backend Flask que processa a análise dos repositórios e expõe uma API REST.
- `requirements.txt`: Dependências Python necessárias.
- `Dockerfile`: Containerização do projeto.
- `.github/workflows/deploy.yml`: Automação de build/deploy via GitHub Actions.

## Como configurar e executar

### 1. Variáveis de Ambiente
O servidor exige as seguintes variáveis de ambiente para funcionar corretamente:

- `API_KEY_GEMINI`: Chave de API do Google Gemini (obrigatória para análise com modelo Gemini).
- `API_KEY_OPENAI`: Chave de API da OpenAI (obrigatória para análise com modelo GPT-4 Mini).
- `FLASK_ENV`: Define o modo de execução (`development` ou `production`).
- `PORT`: Porta do servidor Flask (padrão: 5000).

Você pode definir essas variáveis no seu ambiente ou em um arquivo `.env`.

### 2. Executando com Docker

```bash
docker build -t analisador-qualidade .
docker run -p 5000:5000 \
  -e FLASK_ENV=production \
  -e API_KEY_GEMINI=xxxx \
  -e API_KEY_OPENAI=xxxx \
  analisador-qualidade
```

### 3. Executando manualmente

```bash
pip install -r requirements.txt
export FLASK_ENV=development
export API_KEY_GEMINI=xxxx
export API_KEY_OPENAI=xxxx
python servidor.py
```

Abra o `frontend/index.html` no navegador ou acesse o endpoint do Flask para servir a interface.

## Como funciona
1. Informe a URL do repositório GitHub no frontend.
2. O backend baixa e analisa os principais arquivos do projeto.
3. São avaliadas características como:
   - **Segurança**: vulnerabilidades, funções sem tratamento, recomendações.
   - **Desempenho**: estruturas ineficientes, funções longas, sugestões de otimização.
   - **Confiabilidade**: problemas de erro, violações de padrão, robustez.
   - **Testes**: cobertura estimada, quantidade de testes, funcionalidades sem teste.
4. O resultado é exibido em dashboards, gráficos e pode ser baixado em JSON.

## Deploy automático
O deploy é realizado via GitHub Actions, conforme definido em `.github/workflows/deploy.yml`. Você pode adaptar o workflow para publicar em servidores, cloud ou executar testes automatizados.

## Requisitos
- Python 3.11+
- Docker (opcional)
- Chave de API Gemini/OpenAI (obrigatórias para análise)

## Licença
Este projeto é acadêmico e livre para uso e adaptação.

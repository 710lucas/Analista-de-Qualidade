# Dockerfile para o Analisador de Qualidade
FROM python:3.11
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY servidor.py ./
COPY frontend ./frontend
EXPOSE 5000
CMD ["python", "servidor.py"]

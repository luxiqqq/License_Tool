# FORZA L'ARCHITETTURA INTEL (AMD64)
# Questo è fondamentale per far girare il binario di ScanCode su Mac M1/M2/M3
FROM --platform=linux/amd64 python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    OLLAMA_HOST=0.0.0.0

WORKDIR /app

# 1. Dipendenze di sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl wget bzip2 xz-utils zlib1g \
    libxml2-dev libxslt1-dev libpopt0 libzstd1 libgomp1 libarchive-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. INSTALLAZIONE SCANCODE (Standalone in /opt)
# Usiamo la versione v32.4.1 e la nuova URL 'aboutcode-org'
WORKDIR /opt
# Creiamo la cartella prima per evitare problemi di nomi
RUN mkdir scancode-toolkit && \
    wget https://github.com/aboutcode-org/scancode-toolkit/releases/download/v32.4.1/scancode-toolkit-v32.4.1_py3.11-linux.tar.gz && \
    tar -xzf scancode-toolkit-v32.4.1_py3.11-linux.tar.gz -C scancode-toolkit --strip-components=1 && \
    rm scancode-toolkit-v32.4.1_py3.11-linux.tar.gz

# Aggiorniamo il PATH
ENV PATH=/opt/scancode-toolkit:$PATH

# 3. INSTALLAZIONE OLLAMA (Script ufficiale)
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# 4. Dipendenze Python
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia sorgenti e script
COPY app ./app
COPY start-container.sh /app/start-container.sh
RUN chmod +x /app/start-container.sh
RUN mkdir -p /app/data

EXPOSE 8000 11434

CMD ["/app/start-container.sh"]
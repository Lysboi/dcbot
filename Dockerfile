FROM python:3.11-slim

# FFmpeg kurulumu
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli dosyaları kopyala
COPY requirements.txt .
COPY bot.py .

# Python paketlerini yükle
RUN pip install -r requirements.txt

# Botu çalıştır
CMD ["python", "bot.py"] 
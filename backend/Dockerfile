FROM python:3.11-slim
 
# System deps for OpenCV
RUN apt-get update --fix-missing && apt-get install -y --fix-missing \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*
 
WORKDIR /app
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
COPY . .
 
EXPOSE 8000
 
CMD ["python", "detector.py"]
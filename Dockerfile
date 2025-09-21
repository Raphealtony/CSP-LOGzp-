FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements_streamlit.txt .
RUN pip install -r requirements_streamlit.txt
COPY streamlit_warnings_analyzer.py .
EXPOSE 8501
CMD ["streamlit","run","streamlit_warnings_analyzer.py","--server.address=0.0.0.0","--server.port=8501"]

FROM python:3.11-slim
WORKDIR /app

# Keep dependency installation cached when only application source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Both API and worker use this image; neither needs root privileges.
RUN useradd --create-home --uid 10001 platform
USER platform

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

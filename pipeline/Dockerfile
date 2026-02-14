FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
COPY templates/ templates/
COPY lennylogo.svg lennylogo.svg
RUN pip install --no-cache-dir -e ".[bot]"
CMD ["python", "-m", "pipeline.bot"]

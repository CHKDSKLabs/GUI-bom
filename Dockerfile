FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 7860

CMD ["L-BOM", "gui", "--host", "0.0.0.0", "--port", "7860", "--no-open-browser"]

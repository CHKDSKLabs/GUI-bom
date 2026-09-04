##FROM python:3.11-slim

FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    adduser \
    sudo 

RUN adduser --disabled-password goopy && \
    usermod -aG sudo goopy && \
    echo "goopy ALL=(ALL) NOPASSWD:ALL" | tee /etc/sudoers.d/goopy && \
    chmod 440 /etc/sudoers.d/goopy

USER goopy

RUN sudo apt-get update && sudo apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-dev \
    build-essential \
    curl \
    && sudo rm -rf /var/lib/apt/lists/*

RUN sudo curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    sudo python3 get-pip.py --break-system-packages && \
    sudo rm get-pip.py

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN sudo python -m pip install --upgrade pip && sudo python -m pip install .

EXPOSE 7860

CMD ["l-bom", "gui", "--host", "0.0.0.0", "--port", "7860", "--no-open-browser"]

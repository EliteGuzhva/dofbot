FROM nvcr.io/nvidia/l4t-base:r34.1

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-venv \
    python3-pip

RUN python3 -m pip install -U pip && \
    python3 -m pip install ikpy smbus
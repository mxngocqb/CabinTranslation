# CabinTranslation — offline voice interpreter (GPU build; falls back to CPU at runtime if no GPU)
#   docker build -f pc/Dockerfile -t cabin .     (online, once; build context = repo root)
#   docker save cabin | gzip > cabin.tar.gz      (ship to the offline device)
#   docker run --gpus all -p 7860:7860 -v $PWD/models:/app/models cabin
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 python3.12-venv python3-pip \
    build-essential cmake git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python3.12 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY pc/requirements.txt .
RUN CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=75;80;86;89;90" pip install --no-cache-dir llama-cpp-python==0.3.36 \
 && pip install --no-cache-dir -r requirements.txt
COPY vendor ./vendor
RUN pip install --no-cache-dir --no-deps ./vendor/ViFastTts

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH HF_HUB_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False
WORKDIR /app
COPY cabin ./cabin
COPY scripts ./scripts
COPY pc ./pc
EXPOSE 7860
CMD ["python", "pc/app.py", "--host", "0.0.0.0", "--port", "7860"]

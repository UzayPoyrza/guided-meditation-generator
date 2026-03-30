FROM public.ecr.aws/lambda/python:3.12 AS base

# Install tar and xz to extract ffmpeg static binary
RUN dnf install -y tar xz && dnf clean all

# Download and install static ffmpeg
RUN curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
    -o /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    cp /tmp/ffmpeg-*-amd64-static/ffmpeg /usr/local/bin/ffmpeg && \
    cp /tmp/ffmpeg-*-amd64-static/ffprobe /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg*

# Copy requirements and install
COPY requirements-lambda.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements-lambda.txt

# Copy application code
COPY handler.py ${LAMBDA_TASK_ROOT}/
COPY tts_generate.py ${LAMBDA_TASK_ROOT}/

CMD ["handler.handler"]

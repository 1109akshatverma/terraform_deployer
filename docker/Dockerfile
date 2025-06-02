FROM hashicorp/terraform:latest

RUN apk add --no-cache python3 py3-pip py3-virtualenv curl bash gnupg

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install awscli boto3

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash || true

COPY orchestration.py /app/orchestration.py
WORKDIR /app

ENTRYPOINT []
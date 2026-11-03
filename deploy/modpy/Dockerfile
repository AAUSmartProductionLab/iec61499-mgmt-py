# The modules run in Python (modpy) on a Raspberry Pi: the robot modules (cell/modules/python).
# Built from the repository's root (Dockerfile.dockerignore keeps the context to what it copies):
#   docker build -f deploy/modpy/Dockerfile -t modpy .
FROM python:3.12-slim
RUN pip install --no-cache-dir "pydantic>=2.9,<3" "pyyaml>=6,<7" "asyncua>=1.1" "zeroconf>=0.132"
WORKDIR /modpy
COPY iec61499-skill-lib/modgen modgen
COPY module-py/modpy modpy
COPY cell/modules/python specs
# OPC UA, and the manifest the registration service fetches (--manifest).
EXPOSE 4840 8088
ENTRYPOINT ["python", "-m", "modpy", "serve"]
CMD ["specs/loading.yaml", "--announce"]

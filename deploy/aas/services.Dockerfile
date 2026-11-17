# This repository's Python services for the lab's AAS stack (compose.yaml here): the skill service
# (modreg serve: matching, planning and checking for the web UI, the process AAS) and the line's
# agents (python -m lineagents). Built from the repository's root; services.Dockerfile.dockerignore
# keeps the context to what is copied:
#   docker build -f deploy/aas/services.Dockerfile -t lab-services .
# Installed editable, so that the tools find the ontology and modlink where the repository has them.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY iec61499-mgmt-py/iec61499_mgmt iec61499-mgmt-py/iec61499_mgmt
COPY iec61499-skill-lib/modgen iec61499-skill-lib/modgen
COPY iec61499-skill-lib/ModLib iec61499-skill-lib/ModLib
COPY iec61499-skill-lib/stdtypes iec61499-skill-lib/stdtypes
COPY aas61499-tools/modsync aas61499-tools/modsync
COPY aas61499-tools/modreg aas61499-tools/modreg
COPY aas61499-tools/modplan aas61499-tools/modplan
COPY line-agents/lineagents line-agents/lineagents
COPY module-py/modpy module-py/modpy
# aas-model comes as the archive pyproject.toml pins, not from the submodule's checkout.
RUN pip install --no-cache-dir -e ".[opcua,registration,planning,agents]"
COPY ontology ontology
COPY cell/modules cell/modules
COPY iec61499-opcua-hmi/modlink iec61499-opcua-hmi/modlink
# The skill service, and the agents' orders over HTTP (POST /orders).
EXPOSE 8090 8095

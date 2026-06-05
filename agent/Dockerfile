FROM python:3.12-slim

WORKDIR /opt/agent

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY honeyswarm_agent ./honeyswarm_agent

# Needs the host Docker socket mounted (-v /var/run/docker.sock:/var/run/docker.sock)
# and the enrollment env vars (HONEYSWARM_URL, ENROLL_TOKEN).
VOLUME ["/var/lib/honeyswarm"]

CMD ["python", "-m", "honeyswarm_agent"]

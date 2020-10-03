FROM alpine:latest

RUN apk add --no-cache python3 python3-dev py3-pip py3-bcrypt py3-wheel py3-pyzmq gcc g++ make libffi-dev openssl-dev

ADD requirements.txt /opt/requirements.txt
RUN pip install -r /opt/requirements.txt

# Add Honeyswarm
ADD honeyswarm /opt/honeyswarm

WORKDIR /opt/
# Run the container
CMD ["gunicorn", "--bind=0.0.0.0:8080", "honeyswarm:app", "--reload", "-w", "4"]

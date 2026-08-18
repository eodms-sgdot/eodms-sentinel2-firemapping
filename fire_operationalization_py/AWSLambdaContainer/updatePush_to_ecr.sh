#!/bin/bash
podman build -f Dockerfile.awsLambdaPyCopy -t b12firepolys
podman tag localhost/b12firepolys:latest 411117364717.dkr.ecr.ca-central-1.amazonaws.com/eodms-sgdot/b12firepolys:latest
aws ecr get-login-password --region ca-central-1 | podman login --username AWS --password-stdin 411117364717.dkr.ecr.ca-central-1.amazonaws.com
podman push 411117364717.dkr.ecr.ca-central-1.amazonaws.com/eodms-sgdot/b12firepolys:latest

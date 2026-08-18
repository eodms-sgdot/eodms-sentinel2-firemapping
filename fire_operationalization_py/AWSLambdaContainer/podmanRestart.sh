#!/bin/bash
podman stop b12firepolys
podman rm b12firepolys
podman build -f Dockerfile.awsLambdaPyCopy -t b12firepolysimg
podman container create --name b12firepolys -p 9090:8080 b12firepolysimg lambda_function.lambda_handler
podman start b12firepolys

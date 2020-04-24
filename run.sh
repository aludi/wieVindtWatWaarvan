#!/bin/bash
cp docker/db/app.db .
cd docker
docker-compose up -d

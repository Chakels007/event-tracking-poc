#!/bin/sh
set -e

echo "Creating Kafka topics..."

docker exec kafka-poc kafka-topics \
  --create --if-not-exists \
  --bootstrap-server kafka:9092 \
  --replication-factor 1 --partitions 3 \
  --topic raw-events \
  --config retention.ms=604800000

docker exec kafka-poc kafka-topics \
  --create --if-not-exists \
  --bootstrap-server kafka:9092 \
  --replication-factor 1 --partitions 3 \
  --topic processed-events \
  --config retention.ms=604800000

docker exec kafka-poc kafka-topics \
  --create --if-not-exists \
  --bootstrap-server kafka:9092 \
  --replication-factor 1 --partitions 10 \
  --topic user-aggregates \
  --config retention.ms=2592000000 \
  --config cleanup.policy=compact

echo "Topics ready."

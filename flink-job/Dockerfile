FROM flink:1.18

# Install Python + PyFlink dependencies
USER root
RUN apt-get update && apt-get install -y python3 python3-pip curl wget && \
    pip3 install apache-flink==1.18.1 && \
    ln -s /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

# Download Kafka Connector to lib directory (where Flink picks it up automatically)
RUN cd /opt/flink/lib && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.1-1.18/flink-sql-connector-kafka-3.0.1-1.18.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/kafka/kafka-clients/3.6.0/kafka-clients-3.6.0.jar

# Copy PyFlink job code into container
WORKDIR /opt/flink-job
COPY event_processor.py .

# Expose UI port (JobManager image will use 8081)
EXPOSE 8081

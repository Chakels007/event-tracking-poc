# Event Tracking POC - Bally's

A real-time event processing system using Apache Kafka, Apache Flink, and Node.js. This POC demonstrates end-to-end event tracking with validation, enrichment, and aggregation capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Producer (Node.js)                                             │
│  - Generates synthetic events                                   │
│  - Sends to Kafka raw-events topic                              │
│  - API on localhost:3000                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Apache Kafka 3.x (KRaft Mode)                                  │
│  Topics:                                                        │
│  - raw-events (input)                                           │
│  - processed-events (output)                                    │
│  - user-aggregates (output)                                     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Apache Flink 1.18.1 (PyFlink)                                  │
│  Processing Pipeline:                                          │
│  1. Parse & validate events                                    │
│  2. Enrich with user tier & scoring                            │
│  3. Aggregate by user (1-minute tumbling windows)              │
│  4. Output to processed-events & user-aggregates               │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
- **Git** (for cloning)
- **PowerShell** (on Windows)

## Quick Start (5 minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/Chakels007/event-tracking-poc.git
cd event-tracking-poc
```

### 2. Start Infrastructure
```powershell
docker compose up -d --build
```

### 3. Create Kafka Topics
```powershell
./create-topics.sh
```

### 4. Submit Flink Job
```powershell
Start-Sleep -Seconds 30
docker exec flink-jm flink run -py /opt/flink-job/event_processor.py
```

### 5. Verify Job is Running
```powershell
docker exec flink-jm flink list
```

You should see: `Bally's Event Tracking POC (RUNNING)`

## Services

### Flink Dashboard
- **URL:** http://localhost:8081
- **Purpose:** Monitor jobs, tasks, metrics, and throughput
- **Features:** Job details, task manager status, checkpoint info

### Producer API
- **URL:** http://localhost:3000
- **Port:** 3000

#### Endpoints:

**Generate Test Event**
```powershell
Invoke-WebRequest -Uri http://localhost:3000/generate -UseBasicParsing
```

**Send Custom Event**
```powershell
$body = @{
    userId = "user-1"
    eventType = "purchase"
    timestamp = "2026-03-10T12:00:00Z"
    metadata = @{page = "/checkout"}
} | ConvertTo-Json

Invoke-WebRequest -Uri http://localhost:3000/events -Method POST `
    -ContentType "application/json" -Body $body -UseBasicParsing
```

**Health Check**
```powershell
Invoke-WebRequest -Uri http://localhost:3000/health -UseBasicParsing
```

### Kafka Topics

**Raw Events (Input)**
```powershell
docker exec kafka-poc kafka-console-consumer --bootstrap-server localhost:9092 `
    --topic raw-events --from-beginning --max-messages 5
```

**Processed Events (Output)**
```powershell
docker exec kafka-poc kafka-console-consumer --bootstrap-server localhost:9092 `
    --topic processed-events --from-beginning --max-messages 5
```

**User Aggregates (Output)**
```powershell
docker exec kafka-poc kafka-console-consumer --bootstrap-server localhost:9092 `
    --topic user-aggregates --from-beginning --max-messages 5
```

## Project Structure

```
event-tracking-poc/
├── docker-compose.yml          # Orchestration config
├── create-topics.sh            # Kafka topic creation
├── README.md                   # This file
├── flink-job/
│   ├── Dockerfile              # Flink container with PyFlink
│   ├── event_processor.py       # Main Flink job (processing logic)
│   └── requirements.txt         # Python dependencies
└── producer/
    ├── server.js               # Node.js Express API
    ├── package.json            # Node dependencies
    └── README.md               # Producer documentation
```

## Event Processing Pipeline

### 1. Raw Event
```json
{
  "eventId": "abc-123",
  "userId": "user-1",
  "eventType": "page_view",
  "timestamp": "2026-03-10T12:00:00Z",
  "metadata": {"page": "/products"},
  "ingestedAt": "2026-03-10T12:00:01Z"
}
```

### 2. Validation
- Checks required fields
- Validates event types: `page_view`, `click`, `purchase`, `login`
- Filters invalid events

### 3. Enrichment
Adds:
- `eventScore`: Based on event type (purchase: 100, click: 10, page_view: 1, login: 5)
- `userTier`: Based on user ID (user-1 → gold, others → bronze)
- `processedAt`: Current timestamp

### 4. Aggregation
Groups by user ID over 1-minute tumbling windows:
- Total events in window
- Purchase count
- Total score

## Docker Commands

**Start Services**
```powershell
docker compose up -d
```

**Stop Services**
```powershell
docker compose down
```

**Stop and Clean Data**
```powershell
docker compose down -v
```

**View Logs**
```powershell
docker compose logs -f flink-jobmanager
docker compose logs -f kafka-poc
docker compose logs -f producer
```

**Container Status**
```powershell
docker compose ps
```

## Common Commands

**List Running Flink Jobs**
```powershell
docker exec flink-jm flink list
```

**Stop Flink Job**
```powershell
docker exec flink-jm flink cancel <JOB_ID>
```

**Restart Entire System**
```powershell
docker compose down -v
docker compose up -d --build
Start-Sleep -Seconds 30
./create-topics.sh
docker exec flink-jm flink run -py /opt/flink-job/event_processor.py
```

## Configuration

Edit `docker-compose.yml` to modify:
- Flink parallelism
- Kafka replication factor
- Container resources
- Port mappings

Edit `flink-job/event_processor.py` to modify:
- Event scoring logic
- User tier calculation
- Window duration (currently 1 minute)
- Output topics

## Troubleshooting

### Job Not Running
```powershell
docker compose logs flink-jobmanager --tail 50
```

### Kafka Topics Not Created
```powershell
./create-topics.sh
```

### Connection Timeout on Producer
- Ensure all containers are running: `docker compose ps`
- Wait 30 seconds for services to stabilize
- Check producer logs: `docker compose logs producer`

### No Events in Output Topics
- Generate test events: `Invoke-WebRequest -Uri http://localhost:3000/generate`
- Check raw-events topic has data
- Check Flink job is running: `docker exec flink-jm flink list`
- View Flink logs for errors

## Development

### Modify Flink Job
1. Edit `flink-job/event_processor.py`
2. Rebuild: `docker compose down && docker compose up -d --build`
3. Resubmit job: `docker exec flink-jm flink run -py /opt/flink-job/event_processor.py`

### Add New Event Type
1. Add to `VALID_EVENT_TYPES` in `event_processor.py`
2. Add score to `EVENT_SCORES`
3. Rebuild and restart

## Performance

- **Throughput:** Processes 1000+ events/second (depends on hardware)
- **Latency:** ~100ms end-to-end (producer → Kafka → Flink → output)
- **Window Duration:** 1 minute (configurable)
- **Parallelism:** 2 task slots (configurable)

## Deployment to Production

For production deployment:
1. Use managed Kafka (AWS MSK, Confluent Cloud, etc.)
2. Deploy Flink on Kubernetes or cloud platform
3. Add authentication (Kerberos, OAuth2)
4. Enable monitoring (Prometheus, Grafana)
5. Configure proper resource limits
6. Use external state backends (Redis, RocksDB)
7. Implement error handling and dead-letter queues

## License

MIT

## Support

For issues or questions:
1. Check logs: `docker compose logs`
2. Review troubleshooting section
3. Open an issue on GitHub

---

**Last Updated:** March 10, 2026

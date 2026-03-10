#!/usr/bin/env python3
"""
Bally's Event Tracking POC - PyFlink Processor
Kafka → Validation → Enrichment → Aggregation → Kafka (exactly-once)
"""

import json
import logging
from datetime import datetime
from typing import NamedTuple, Optional

from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.functions import AggregateFunction, ProcessWindowFunction
from pyflink.common.typeinfo import Types
from pyflink.datastream.window import TumblingEventTimeWindows, Time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
KAFKA_BOOTSTRAP = 'kafka:9092'
RAW_TOPIC = 'raw-events'
PROCESSED_TOPIC = 'processed-events'
AGGREGATES_TOPIC = 'user-aggregates'

# Event models
class RawEvent(NamedTuple):
    eventId: str
    userId: str
    eventType: str
    timestamp: str
    metadata: dict
    ingestedAt: str

class ProcessedEvent(NamedTuple):
    eventId: str
    userId: str
    eventType: str
    timestamp: str
    eventScore: int
    userTier: str
    processedAt: str
    metadata: dict

class UserAggregate(NamedTuple):
    userId: str
    windowStart: str
    windowEnd: str
    totalEvents: int
    purchaseCount: int
    totalScore: int

VALID_EVENT_TYPES = {'page_view', 'click', 'purchase', 'login'}
EVENT_SCORES = {
    'purchase': 100,
    'click': 10,
    'page_view': 1,
    'login': 5
}

def parse_event(event_str: str) -> Optional[RawEvent]:
    """Parse and validate raw event."""
    try:
        data = json.loads(event_str)
        if not all(k in data for k in ['eventId', 'userId', 'eventType', 'timestamp']):
            return None
        
        # Basic validation
        if data['eventType'] not in VALID_EVENT_TYPES:
            logger.warning(f"Invalid event type: {data['eventType']}")
            return None
            
        return RawEvent(
            eventId=data['eventId'],
            userId=data['userId'],
            eventType=data['eventType'],
            timestamp=data['timestamp'],
            metadata=data.get('metadata', {}),
            ingestedAt=data.get('ingestedAt', '')
        )
    except json.JSONDecodeError:
        logger.warning(f"Invalid JSON: {event_str[:100]}...")
        return None

def enrich_event(event: RawEvent) -> ProcessedEvent:
    """Business logic: scoring and enrichment."""
    score = EVENT_SCORES.get(event.eventType, 0)
    user_tier = 'bronze'  # Simulate Redis lookup
    if event.userId.startswith('user-1'):
        user_tier = 'gold'
    
    return ProcessedEvent(
        eventId=event.eventId,
        userId=event.userId,
        eventType=event.eventType,
        timestamp=event.timestamp,
        eventScore=score,
        userTier=user_tier,
        processedAt=datetime.now().isoformat(),
        metadata=event.metadata
    )

class UserMetricsAccumulator(NamedTuple):
    total_events: int = 0
    purchase_count: int = 0
    total_score: int = 0

class UserMetricsAggregator(AggregateFunction):
    def create_accumulator(self):
        return UserMetricsAccumulator(0, 0, 0)

    def add(self, value: ProcessedEvent, accumulator: UserMetricsAccumulator):
        return UserMetricsAccumulator(
            total_events=accumulator.total_events + 1,
            purchase_count=accumulator.purchase_count + (1 if value.eventType == "purchase" else 0),
            total_score=accumulator.total_score + value.eventScore
        )

    def get_result(self, accumulator: UserMetricsAccumulator):
        return accumulator

    def merge(self, acc1: UserMetricsAccumulator, acc2: UserMetricsAccumulator):
        return UserMetricsAccumulator(
            total_events=acc1.total_events + acc2.total_events,
            purchase_count=acc1.purchase_count + acc2.purchase_count,
            total_score=acc1.total_score + acc2.total_score
        )

class UserMetricsWindow(ProcessWindowFunction):
    def process(self, key, context, elements):
        acc = list(elements)[0]
        window_start = datetime.fromtimestamp(context.window().start / 1000).isoformat()
        window_end = datetime.fromtimestamp(context.window().end / 1000).isoformat()
        
        yield UserAggregate(
            userId=key,
            windowStart=window_start,
            windowEnd=window_end,
            totalEvents=acc.total_events,
            purchaseCount=acc.purchase_count,
            totalScore=acc.total_score
        )

def main():
    # Execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(2)
    
    # Checkpointing (exactly-once)
    env.enable_checkpointing(30000, CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_min_pause_between_checkpoints(10000)
    
    # Kafka source
    kafka_consumer = FlinkKafkaConsumer(
        topics=RAW_TOPIC,
        deserialization_schema=SimpleStringSchema(),
        properties={
            'bootstrap.servers': KAFKA_BOOTSTRAP,
            'group.id': 'event-processor',
            'auto.offset.reset': 'latest'
        }
    )
    
    stream = env.add_source(kafka_consumer)
    
    # Processing pipeline
    raw_events = stream.map(parse_event, output_type=Types.PICKLED_BYTE_ARRAY())
    valid_events = raw_events.filter(lambda x: x is not None)
    
    processed_events = valid_events.map(enrich_event, 
                                       output_type=Types.PICKLED_BYTE_ARRAY())
    
    # Windowed aggregation
    windowed = processed_events \
        .key_by(lambda x: x.userId) \
        .window(TumblingEventTimeWindows.of(Time.minutes(1))) \
        .aggregate(
            UserMetricsAggregator(),
            UserMetricsWindow(),
            output_type=Types.PICKLED_BYTE_ARRAY()
        )
    
    # Individual events sink
    processed_events.map(lambda x: json.dumps(x._asdict())) \
        .add_sink(FlinkKafkaProducer(
            topic=PROCESSED_TOPIC,
            serialization_schema=SimpleStringSchema(),
            producer_config={
                'bootstrap.servers': KAFKA_BOOTSTRAP,
                'acks': 'all'
            }
        ))
    
    # Aggregates sink
    windowed.map(lambda x: json.dumps(x._asdict())) \
        .add_sink(FlinkKafkaProducer(
            topic=AGGREGATES_TOPIC,
            serialization_schema=SimpleStringSchema(),
            producer_config={
                'bootstrap.servers': KAFKA_BOOTSTRAP,
                'acks': 'all'
            }
        ))
    
    # Print for demo (remove in prod)
    processed_events.map(lambda x: f"PROCESSED: {json.dumps(x._asdict())}").print()
    windowed.map(lambda x: f"AGGREGATE: {json.dumps(x._asdict())}").print()
    
    env.execute("Bally's Event Tracking POC")

if __name__ == '__main__':
    main()

import express from 'express';
import { Kafka } from 'kafkajs';
import { v4 as uuid } from 'uuid';
import Joi from 'joi';

const app = express();
app.use(express.json());

const kafka = new Kafka({
  clientId: 'event-producer',
  brokers: (process.env.KAFKA_BROKERS || 'kafka:9092').split(','),
});

const producer = kafka.producer({
  createPartitionsTopicIfMissing: true,
  idempotent: true,
  maxInFlightRequests: 1,
  retries: 3,
  acks: '1'
});

const RAW_TOPIC = 'raw-events';

// Schema validation
const eventSchema = Joi.object({
  userId: Joi.string().required(),
  eventType: Joi.string().valid('page_view', 'click', 'purchase', 'login').required(),
  timestamp: Joi.string().isoDate().required(),
  metadata: Joi.object().optional()
});

await producer.connect();
console.log('🚀 Event Producer ready on http://localhost:3000');

app.post('/events', async (req, res) => {
  const { error, value } = eventSchema.validate(req.body);
  
  if (error) {
    return res.status(400).json({ error: error.details[0].message });
  }

  const event = {
    eventId: uuid(),
    ...value,
    ingestedAt: new Date().toISOString()
  };

  try {
    await producer.send({
      topic: RAW_TOPIC,
      messages: [{
        key: event.userId,
        value: JSON.stringify(event)
      }]
    });
    
    res.status(200).json({ 
      status: 'sent', 
      eventId: event.eventId,
      userId: event.userId 
    });
  } catch (err) {
    console.error('Producer error:', err);
    res.status(503).json({ error: 'Kafka unavailable' });
  }
});

// Synthetic events for testing
app.get('/generate', async (req, res) => {
  const eventTypes = ['page_view', 'click', 'purchase', 'login'];
  const pages = ['/', '/home', '/products', '/checkout'];
  
  const event = {
    userId: `user-${Math.floor(Math.random() * 10) + 1}`,
    eventType: eventTypes[Math.floor(Math.random() * eventTypes.length)],
    timestamp: new Date().toISOString(),
    metadata: {
      page: pages[Math.floor(Math.random() * pages.length)],
      sessionId: uuid().slice(0, 8)
    }
  };

  try {
    await producer.send({
      topic: RAW_TOPIC,
      messages: [{ key: event.userId, value: JSON.stringify(event) }]
    });
    res.json({ status: 'generated', event });
  } catch (err) {
    res.status(503).json({ error: err.message });
  }
});

app.get('/health', (req, res) => res.status(200).json({ status: 'healthy' }));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`📡 Producer listening on port ${PORT}`);
});

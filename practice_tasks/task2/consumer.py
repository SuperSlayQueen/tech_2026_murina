import time
import pika
import redis
import json
import config
import metrics


def run_rabbitmq():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=config.RABBITMQ_HOST)
    )
    ch = connection.channel()
    ch.queue_declare(queue=config.QUEUE_NAME)

    received = 0
    end = time.time() + config.TEST_DURATION

    def callback(ch, method, props, body):
        nonlocal received
        data = json.loads(body)
        metrics.record_latency(data["ts"])
        received += 1

    ch.basic_consume(queue=config.QUEUE_NAME,
                     on_message_callback=callback,
                     auto_ack=True)

    while time.time() < end:
        connection.process_data_events(time_limit=1)

    connection.close()
    return received


def run_redis():
    r = redis.Redis(host=config.REDIS_HOST)

    received = 0
    end = time.time() + config.TEST_DURATION

    while time.time() < end:
        msg = r.rpop(config.QUEUE_NAME)
        if msg:
            data = json.loads(msg)
            metrics.record_latency(data["ts"])
            received += 1

    return received
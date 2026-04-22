import time
import pika
import redis
import config
import json


def make_message(size):
    payload = "x" * (size - 20)
    return json.dumps({
        "ts": time.time(),
        "data": payload
    })


def run_rabbitmq(size, rate):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=config.RABBITMQ_HOST)
    )
    ch = connection.channel()
    ch.queue_declare(queue=config.QUEUE_NAME)

    interval = 1 / rate
    end = time.time() + config.TEST_DURATION

    sent = 0

    while time.time() < end:
        msg = make_message(size)
        ch.basic_publish("", config.QUEUE_NAME, msg)
        sent += 1
        time.sleep(interval)

    connection.close()
    return sent


def run_redis(size, rate):
    r = redis.Redis(host=config.REDIS_HOST)

    interval = 1 / rate
    end = time.time() + config.TEST_DURATION

    sent = 0

    while time.time() < end:
        msg = make_message(size)
        r.lpush(config.QUEUE_NAME, msg)
        sent += 1
        time.sleep(interval)

    return sent
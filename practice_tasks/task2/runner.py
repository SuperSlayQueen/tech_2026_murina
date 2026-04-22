import csv
import time
import config
import producer
import consumer
import metrics


def run_test(broker, size, rate):
    print(f"\nRunning: {broker} | size={size} | rate={rate}")

    metrics.reset()

    start = time.time()

    if broker == "rabbitmq":
        import threading

        t = threading.Thread(target=consumer.run_rabbitmq)
        t.start()

        sent = producer.run_rabbitmq(size, rate)
        t.join()

        received = consumer.run_rabbitmq()

    else:
        import threading

        t = threading.Thread(target=consumer.run_redis)
        t.start()

        sent = producer.run_redis(size, rate)
        t.join()

        received = consumer.run_redis()

    avg, p95, max_l = metrics.get_metrics()

    duration = config.TEST_DURATION
    throughput = received / duration

    return {
        "broker": broker,
        "size": size,
        "rate": rate,
        "sent": sent,
        "received": received,
        "lost": sent - received,
        "throughput": throughput,
        "avg_latency": avg,
        "p95_latency": p95,
        "max_latency": max_l
    }


def main():
    with open("results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "broker", "size", "rate",
            "sent", "received", "lost",
            "throughput",
            "avg_latency", "p95_latency", "max_latency"
        ])
        writer.writeheader()

        for broker in config.BROKERS:
            for size in config.MESSAGE_SIZES:
                for rate in config.RATES:
                    result = run_test(broker, size, rate)
                    writer.writerow(result)

    print("\nDONE → results.csv")


if __name__ == "__main__":
    main()
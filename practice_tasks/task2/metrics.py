import time
import statistics

latencies = []

def record_latency(start_time):
    latencies.append(time.time() - start_time)

def get_metrics():
    if not latencies:
        return 0, 0, 0

    avg = sum(latencies) / len(latencies)
    p95 = statistics.quantiles(latencies, n=100)[94]
    max_l = max(latencies)

    return avg, p95, max_l

def reset():
    global latencies
    latencies = []
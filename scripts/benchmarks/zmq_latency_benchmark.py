import time
import statistics
import zmq

PUB_URL = "tcp://127.0.0.1:5555"
SUB_URL = "tcp://127.0.0.1:5556"
TOPIC = "bench.latency"
SAMPLES = 100

def main():
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    sub = ctx.socket(zmq.SUB)
    sub.subscribe(TOPIC)
    sub.connect(SUB_URL)
    pub.connect(PUB_URL)
    # warm-up
    time.sleep(0.2)

    times = []
    for i in range(SAMPLES):
        payload = f"{TOPIC} {i}"
        t0 = time.perf_counter()
        pub.send_string(payload)
        msg = sub.recv_string()
        if msg.startswith(TOPIC):
            times.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.01)

    ctx.term()
    if times:
        print({
            "count": len(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "avg_ms": statistics.mean(times),
            "p95_ms": statistics.quantiles(times, n=100)[94],
        })
    else:
        print({"count": 0})

if __name__ == "__main__":
    main()
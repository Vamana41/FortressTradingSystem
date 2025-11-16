import time
import statistics
import requests

URL = "http://127.0.0.1:5000/api/v1/ping"
SAMPLES = 50

def main():
    times = []
    for _ in range(SAMPLES):
        t0 = time.perf_counter()
        try:
            r = requests.get(URL, timeout=2)
            r.raise_for_status()
        except Exception:
            continue
        times.append((time.perf_counter() - t0) * 1000)
        time.sleep(0.05)
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
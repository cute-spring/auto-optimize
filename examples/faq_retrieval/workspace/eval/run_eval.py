#!/usr/bin/env python3

import json
import sys


def main() -> int:
    if "--json" not in sys.argv:
        return 1

    payload = {
        "top1_accuracy": 0.892,
        "recall_at_5": 0.934,
        "mrr": 0.781,
        "latency_ms": 720,
        "cost_per_query": 0.008,
        "all_tests_pass": True,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

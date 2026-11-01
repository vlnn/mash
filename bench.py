import argparse
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

WORDS = (
    "ssh prod web staging k8s ctx kube grafana latency api notes folder email work "
    "find py rm logs tail grep deploy config context weight kg body paper reading ml "
    "book snow crash jira ticket wrap code standup release notes кава coffee"
).split()

STRESS_WORDS = ["prod", "prd", "pro", "p", "staging", "stg", "st", "s"]

QUERIES = ["prod", "stg k8", "grf lat", "weight", "#re", "work/ ctx", "", "dply"]
STRESS_QUERIES = ["p", "s", "pr st", "prd stg"]


def make_record(rng, vocabulary):
    head = " ".join(rng.sample(vocabulary, rng.randint(1, 4)))
    tag = rng.choice(["", " #body", " #reading", " #ml"])
    body = " ".join(rng.sample(vocabulary, rng.randint(1, 8)))
    return f"{head}{tag} -> {body}\n"


def node_for(rng, root):
    depth = rng.choices([0, 1, 2], weights=[5, 3, 1])[0]
    parts = [rng.choice(["work", "body", "infra", "home"]) for _ in range(depth)]
    path = os.path.join(root, *parts) if parts else root
    os.makedirs(path, exist_ok=True)
    return path


def generate(root, count, stress=False):
    rng = random.Random(count)
    vocabulary = STRESS_WORDS if stress else WORDS
    for i in range(count):
        node = node_for(rng, root)
        with open(os.path.join(node, f"r{i}.txt"), "w", encoding="utf-8") as f:
            f.write(make_record(rng, vocabulary))


def raw_read(root):
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.endswith(".txt"):
                with open(os.path.join(dirpath, name), encoding="utf-8") as f:
                    f.read()
                seen += 1
    return seen


def time_raw(root, runs):
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        raw_read(root)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def time_cli(root, python, query, runs):
    command = [python, "-S", "-m", "mash.cli", "--alfred", query]
    env = dict(os.environ, MASH_FOLDER=root, PYTHONPATH=os.path.dirname(__file__))
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run(command, env=env, capture_output=True, check=True)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def time_startup(python, runs):
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run([python, "-S", "-c", "pass"], check=True)
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def cli_available():
    return os.path.exists(os.path.join(os.path.dirname(__file__), "mash", "cli.py"))


def report(sizes, python, runs, stress):
    queries = STRESS_QUERIES if stress else QUERIES
    print(f"python startup: {time_startup(python, runs):.0f} ms")
    for count in sizes:
        root = tempfile.mkdtemp(prefix="mash-bench-")
        try:
            generate(root, count, stress)
            raw = time_raw(root, runs)
            line = f"{count:>6} records  raw walk+read {raw:6.1f} ms"
            if cli_available():
                per_query = [time_cli(root, python, q, runs) for q in queries]
                slowest = max(per_query)
                slowest_query = queries[per_query.index(slowest)]
                line += f"  keystroke {statistics.median(per_query):6.1f} ms"
                line += f"  (max {slowest:.0f} ms on {slowest_query!r})"
            print(line)
        finally:
            shutil.rmtree(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--sizes", default="1000,5000,20000")
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--stress", action="store_true")
    args = parser.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]
    report(sizes, args.python, args.runs, args.stress)


if __name__ == "__main__":
    main()

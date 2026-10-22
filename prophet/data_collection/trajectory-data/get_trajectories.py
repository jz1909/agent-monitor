
import duckdb, hashlib, io, os, tarfile

REPO = "hf://datasets/kendx/Harbor-Adapter"
OUT = "trials"
con = duckdb.connect()

# Step 1: use the small manifest to pick one SWE-bench trial per model.
# Sorting by task_name makes most models land on the same task, for easy comparison.
picks = con.sql(f"""
    SELECT DISTINCT ON (model)
           model, agent, benchmark, task_name, trial_ids[1] AS trial_id
    FROM '{REPO}/harbor_adapters.manifest.parquet'
    WHERE benchmark ILIKE '%swe%bench%'
    ORDER BY model, task_name
""").fetchall()

print(f"Picked {len(picks)} trials:")
by_bench = {}
for model, agent, bench, task, tid in picks:
    print(f"  {model:28} {agent:12} {bench:20} {task}")
    by_bench.setdefault(bench, []).append((model, agent, task, tid))

# Step 2: download only those trials from the big trajectory files
os.makedirs(OUT, exist_ok=True)
for bench, items in by_bench.items():
    info = {tid: (model, agent, task) for model, agent, task, tid in items}
    ids = "', '".join(info)
    print(f"\nFetching {len(info)} trials from {bench} (can take a minute)...")
    rows = con.sql(f"""
        SELECT trial_id, archive, archive_sha256
        FROM '{REPO}/data/harbor_adapters/{bench}/*.parquet'
        WHERE trial_id IN ('{ids}')
    """).fetchall()

    # Step 3: verify the checksum and unpack each trial into its own folder
    for tid, archive, sha in rows:
        if hashlib.sha256(archive).hexdigest() != sha:
            print("  checksum mismatch, skipping", tid)
            continue
        model, agent, task = info[tid]
        dest = os.path.join(OUT, f"{model}__{agent}__{task.replace('/', '_')}")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            tar.extractall(dest)
        print("  saved", dest)
"""Merge v1 + v2 (classified) + v4 verified datasets into the final attempt_5 dataset.
Dedup by repo_full_name. Report per-cell coverage.
"""
import json, os, collections

HERE = "/home/vmihaylov/java_8_11_17_to_java_21"

files = [
    f"{HERE}/attempt_5/lineage_dataset_classified.json",  # v1+v2 with family_at_oldest
    f"{HERE}/attempt_5/lineage_dataset_v4.json",          # v4 verified (when ready)
]

all_entries = []
for f in files:
    if os.path.exists(f):
        all_entries.extend(json.load(open(f)))

seen = {}
for e in all_entries:
    # prefer later (more recent) entries
    seen[e["repo_full_name"]] = e
data = list(seen.values())

out = f"{HERE}/attempt_5/java21-migration-dataset.json"
json.dump(data, open(out, "w"), indent=2)
print(f"final dataset: {len(data)} entries → {out}")

by_cell = collections.Counter((e["oldest_java_version"], e.get("family_at_oldest")) for e in data)
print("\nby (oldest_java, family) cell:")
for k in sorted(by_cell, key=lambda x: (x[0], x[1] or "zz")):
    print(f"  {k}: {by_cell[k]}")

strict = [e for e in data if {s["java_version"] for s in e.get("verified_lineage", []) if s.get("build_pass")} >= {8, 11, 17, 21}]
print(f"\nstrict 4-way (J8 + J11 + J17 + J21 all buildable): {len(strict)}")

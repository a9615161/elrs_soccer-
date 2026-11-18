"""Generic runner for link-simulation experiments (Step 5.3).

YAML fields: name, seeds, duration_s, protocols, sweep, [fixed], [skip].
`sweep` maps Scenario fields to value lists; nested `jammer: {type: [...], duty: [...]}`
and `ge: {burst: [...], err: [...]}` are expanded too. Seeds are derived from
(name, parameters without the protocol, repetition) so every protocol sees the same
channel realisation. Output: data/results/<name>/<commit>.parquet (+ config, env).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.common import git_commit, load_yaml, result_dir  # noqa: E402
from sim.linksim import Scenario, run  # noqa: E402


def _expand(sweep: dict) -> list[dict]:
    axes = []
    for key, val in sweep.items():
        if isinstance(val, dict):  # nested: jammer / ge
            sub = [dict(zip(val.keys(), combo)) for combo in itertools.product(*val.values())]
            axes.append([(key, s) for s in sub])
        else:
            axes.append([(key, v) for v in val])
    return [dict(combo) for combo in itertools.product(*axes)]


def _skip(params: dict, rules: list[dict]) -> bool:
    """Drop combinations matching any rule, e.g. {"jammer.duty": 0, "jammer.coverage": [0.25, 0.5]}."""
    for rule in rules or []:
        hit = True
        for k, want in rule.items():
            obj = params
            for part in k.split("."):
                obj = obj.get(part) if isinstance(obj, dict) else None
            if obj not in (want if isinstance(want, list) else [want]):
                hit = False
                break
        if hit:
            return True
    return False


def seed_for(name: str, params: dict, rep: int) -> int:
    key = json.dumps({k: v for k, v in params.items() if k != "protocol"}, sort_keys=True)
    return int.from_bytes(hashlib.sha256(f"{name}|{key}|{rep}".encode()).digest()[:8], "little")


def jobs(cfg: dict) -> list[dict]:
    out = []
    for params in _expand(cfg.get("sweep", {})):
        if _skip(params, cfg.get("skip")):
            continue
        for proto in cfg["protocols"]:
            p = {**cfg.get("fixed", {}), **params, "protocol": proto}
            for rep in range(cfg["seeds"]):
                out.append({"params": p, "rep": rep, "seed": seed_for(cfg["name"], p, rep)})
    return out


def _flat(params: dict) -> dict:
    flat = {}
    for k, v in params.items():
        if isinstance(v, dict):
            flat.update({f"{k}.{kk}": vv for kk, vv in v.items()})
        else:
            flat[k] = v
    return flat


def run_job(job_and_duration):
    job, duration = job_and_duration
    p = dict(job["params"])
    ge = p.pop("ge", None)
    if isinstance(ge, dict):
        ge = None if ge.get("err", 0) <= 0 else (ge["burst"], ge["err"])
    sc = Scenario(seed=job["seed"], duration_s=duration, ge=ge, **p)
    res = run(sc)
    row = {**_flat(job["params"]), "rep": job["rep"], "seed": job["seed"], **res.metrics}
    row["gap_ms"] = [g[0] for g in res.gaps]
    row["excess_ms"] = [g[1] for g in res.gaps]
    row["gap_failsafe"] = [g[2] for g in res.gaps]
    return row


def run_config(cfg: dict, workers: int, resume: bool) -> Path:
    out = result_dir(cfg["name"], cfg)
    path = out / f"{git_commit()}.parquet"
    todo = jobs(cfg)
    done_rows = []
    if resume and path.exists():
        prev = pd.read_parquet(path)
        done = set(prev["seed"].astype(str) + "|" + prev["protocol"])
        done_rows = prev.to_dict("records")
        todo = [j for j in todo if f"{j['seed']}|{j['params']['protocol']}" not in done]
    rows = list(done_rows)
    with Pool(workers) as pool:
        it = pool.imap_unordered(run_job, [(j, cfg["duration_s"]) for j in todo], chunksize=4)
        for i, row in enumerate(tqdm(it, total=len(todo), desc=cfg["name"], mininterval=5)):
            rows.append(row)
            if (i + 1) % 2000 == 0:  # checkpoint for --resume
                pd.DataFrame(rows).to_parquet(path, index=False)
    pd.DataFrame(rows).to_parquet(path, index=False)
    print(f"wrote {path} ({len(rows)} runs)")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SIM_WORKERS", 16)))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--seeds", type=int, help="override seeds (quick runs)")
    args = ap.parse_args()
    cfg = load_yaml(args.config)
    if args.seeds:
        cfg["seeds"] = args.seeds
    run_config(cfg, args.workers, args.resume)


if __name__ == "__main__":
    main()

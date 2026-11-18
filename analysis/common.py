"""Shared helpers for analysis scripts: config loading, result paths, statistics."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def git_commit() -> str:
    try:
        rev = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short=10", "HEAD"],
                                      stderr=subprocess.DEVNULL, text=True).strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD"]).returncode != 0
        return rev + ("-dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nocommit"


def result_dir(exp: str, cfg: dict) -> Path:
    """data/results/<exp>/ with a copy of the config and environment info."""
    d = RESULTS / exp
    d.mkdir(parents=True, exist_ok=True)
    commit = git_commit()
    (d / f"{commit}.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    env = {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
           "commit": commit}
    (d / f"{commit}.env.json").write_text(json.dumps(env, indent=2))
    return d


def latest_result(exp: str, suffix: str) -> Path:
    files = sorted((RESULTS / exp).glob(f"*{suffix}.parquet"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"no results for {exp}; run `make exp EXP={exp}` first")
    return files[-1]


def wilson(k, n, conf: float = 0.95):
    """Wilson score interval for a binomial proportion. Works on arrays."""
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    z = stats.norm.ppf(0.5 + conf / 2)
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half

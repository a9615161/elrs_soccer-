#!/usr/bin/env python3
"""Record when each file was produced, for files that predate the first commit.

git does not keep file mtimes, so before the first commit the filesystem times
are frozen into docs/file_dates.tsv (path, mtime, size, sha256). Everything
else is rendered from that TSV, so re-rendering does not depend on the current
mtimes:

    python tools/file_dates.py snapshot   # once, before editing anything
    python tools/file_dates.py render     # docs/FILE_DATES.md + blocks in E*.md

After the first commit, `git log --format=%ci -- <path>` gives the dates instead.
"""
from __future__ import annotations

import csv
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "docs" / "file_dates.tsv"
MD = ROOT / "docs" / "FILE_DATES.md"
EXPDOCS = ROOT / "docs" / "experiments"

# experiment record -> result directories under data/results/
EXP_DIRS = {
    "E1": ["e1_orthogonality", "e1_saturation"],
    "E2": ["e2_prediction"],
    "E3": ["e3_forgery"],
    "E4": ["e4_bit_budget"],
    "E5": ["e5_baseline"],
    "E6": ["e6_drift"],
    "E7": ["e7_blackout", "e7_reboot", "e7_burst"],
    "E8": ["e8_jamming", "e8_key", "e8_syncjam"],
    "E9": ["e9_multidrone"],
    "E10": ["e10_cost"],
}
# per-experiment notes on provenance (shown in FILE_DATES.md and the E*.md block)
EXP_NOTES = {
    "E5": "輸出時間（2026-11-02 17:43）早於 `sim/linksim.py` 最後修改（18:23），"
          "E5 有 import linksim，因此這份輸出不一定對應 commit 中的 linksim；需重跑確認。",
}
BEGIN = "<!-- file-dates:begin (tools/file_dates.py render) -->"
END = "<!-- file-dates:end -->"
ARCHIVE = "data/results_archive/2026-10-27_pre41/"


def tracked_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard"], text=True)
    skip = {"docs/file_dates.tsv", "docs/FILE_DATES.md", "tools/file_dates.py"}
    return sorted(p for p in out.splitlines() if p not in skip)


def snapshot(force: bool) -> None:
    if TSV.exists() and not force:
        sys.exit(f"{TSV.relative_to(ROOT)} exists; the snapshot is frozen (use --force to retake)")
    rows = []
    for p in tracked_files():
        f = ROOT / p
        st = f.stat()
        ts = datetime.fromtimestamp(st.st_mtime).astimezone()
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rows.append([p, ts.isoformat(timespec="seconds"), st.st_size, sha])
    taken = datetime.now().astimezone().isoformat(timespec="seconds")
    with TSV.open("w", newline="") as fh:
        fh.write(f"# snapshot taken {taken}; mtime = filesystem modification time\n")
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["path", "mtime", "bytes", "sha256"])
        w.writerows(rows)
    print(f"wrote {TSV.relative_to(ROOT)} ({len(rows)} files)")


def load() -> tuple[str, list[dict]]:
    lines = TSV.read_text().splitlines()
    header = lines[0].lstrip("# ")
    rows = list(csv.DictReader(lines[1:], delimiter="\t"))
    return header, rows


def fmt_t(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")


def fmt_b(n: str) -> str:
    n = int(n)
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def group_of(p: str) -> str:
    if p.startswith("data/results/"):
        return "data/results/" + p.split("/")[2]
    if p.startswith(ARCHIVE):
        return ARCHIVE + p[len(ARCHIVE):].split("/")[0]
    if p.startswith("data/logs/"):
        return "data/logs"
    if p.startswith("docs/"):
        return "docs"
    top = p.split("/")[0]
    return top if "/" in p else "（根目錄）"


def table(rows: list[dict], strip: str = "", same: dict | None = None) -> list[str]:
    out = ["| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |" + (" 備註 |" if same is not None else ""),
           "|---|---|---|---|" + ("---|" if same is not None else "")]
    for r in rows:
        name = r["path"][len(strip):] if strip and r["path"].startswith(strip) else r["path"]
        line = f"| `{name}` | {fmt_t(r['mtime'])} | {fmt_b(r['bytes'])} | `{r['sha256'][:12]}` |"
        if same is not None:
            line += f" {same.get(r['path'], '')} |"
        out.append(line)
    return out


def identical_to_archive(rows: list[dict]) -> dict[str, str]:
    by_path = {r["path"]: r for r in rows}
    notes = {}
    for r in rows:
        if r["path"].startswith("data/results/") and not r["path"].endswith(".env.json"):
            twin = by_path.get(ARCHIVE + r["path"][len("data/results/"):])
            if twin and twin["sha256"] == r["sha256"]:
                notes[r["path"]] = "與 10-27 封存版逐位元相同"
    return notes


def render() -> None:
    header, rows = load()
    same = identical_to_archive(rows)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[group_of(r["path"])].append(r)

    md = ["# 檔案產生時間（首次 commit 前快照）", "",
          f"來源：`docs/file_dates.tsv`（{header}）。",
          "時間為檔案系統的最後修改時間（CST, UTC+8），即該檔最後一次被寫出的時間；"
          "結果檔與圖表＝產生時間，程式與文件＝最後編輯時間。git 不保存 mtime，"
          "所以首次 commit 前的時間以此表為準，之後以 `git log` 為準。",
          "",
          "- 2026-10-27：初版模型的結果，封存於 `data/results_archive/2026-10-27_pre41/`。",
          "- 2026-11-02：以 ExpressLRS 4.1.0 模型重跑的全部結果（`data/results/`），"
          "執行紀錄在 `data/logs/rerun41.log`、`rerun41b.log`。",
          "- 2026-11-18：本表與 `tools/file_dates.py`，以及 `docs/experiments/` 中的「資料產生時間」區塊。"
          "E*.md 與 README.md 在快照後只加了該區塊，表中時間是加區塊前的內容時間。",
          "", "## 各實驗資料時間", "",
          "| 實驗 | 資料檔（parquet/yaml） | 圖表與摘要（plots/） | 備註 |", "|---|---|---|---|"]
    for exp, dirs in EXP_DIRS.items():
        data_t, plot_t = [], []
        for d in dirs:
            for r in groups.get("data/results/" + d, []):
                (plot_t if "/plots/" in r["path"] else data_t).append(r["mtime"])
        rng = lambda ts: "—" if not ts else (
            fmt_t(min(ts)) if fmt_t(min(ts)) == fmt_t(max(ts)) else f"{fmt_t(min(ts))} – {fmt_t(max(ts))[11:] if min(ts)[:10] == max(ts)[:10] else fmt_t(max(ts))}")
        md.append(f"| [{exp}](experiments/{exp}.md) | {rng(data_t)} | {rng(plot_t)} | {EXP_NOTES.get(exp, '')} |")
    md += ["", "「與 10-27 封存版逐位元相同」表示 4.1.0 重跑後輸出沒有變：E1 全部、E2 的 `nocommit.parquet`（兩者不經過鏈路模型）。", ""]

    natural = lambda g: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", g)]
    order = sorted(groups, key=lambda g: (
        0 if g.startswith("data/results/") else 1 if g.startswith(ARCHIVE) else 2 if g == "data/logs" else 3,
        natural(g)))
    section = None
    titles = ["## 目前結果 `data/results/`", "## 封存結果 `data/results_archive/2026-10-27_pre41/`",
              "## 執行紀錄 `data/logs/`", "## 程式、設定與文件"]
    for g in order:
        s = 0 if g.startswith("data/results/") else 1 if g.startswith(ARCHIVE) else 2 if g == "data/logs" else 3
        if s != section:
            section = s
            md += [titles[s], ""]
        md += [f"### `{g}`", ""]
        md += table(groups[g], strip=g + "/" if s < 3 and g != "（根目錄）" else "",
                    same=same if s == 0 else None)
        md.append("")
    MD.write_text("\n".join(md))
    print(f"wrote {MD.relative_to(ROOT)}")

    for exp, dirs in EXP_DIRS.items():
        block = [BEGIN, "## 資料產生時間", "",
                 "以下時間為檔案寫出時間（CST），取自首次 commit 前的快照 `docs/file_dates.tsv`；完整清單見 [FILE_DATES.md](../FILE_DATES.md)。", ""]
        if exp in EXP_NOTES:
            block += [f"> 注意：{EXP_NOTES[exp]}", ""]
        for d in dirs:
            rs = groups.get("data/results/" + d, [])
            block += [f"`data/results/{d}/`", ""]
            block += [l.replace(" sha256 前 12 碼 |", "").replace("---|---|---|---|", "---|---|---|")
                      if i < 2 else re.sub(r" `[0-9a-f]{12}` \|", "", l)
                      for i, l in enumerate(table(rs, strip=f"data/results/{d}/", same=same))]
            block.append("")
        block.append(END)
        inject(EXPDOCS / f"{exp}.md", "\n".join(block))

    lines = [BEGIN, "## 資料產生時間", "",
             "| 實驗 | 資料 | 圖表 |", "|---|---|---|"]
    for exp, dirs in EXP_DIRS.items():
        data_t = [r["mtime"] for d in dirs for r in groups.get("data/results/" + d, []) if "/plots/" not in r["path"]]
        plot_t = [r["mtime"] for d in dirs for r in groups.get("data/results/" + d, []) if "/plots/" in r["path"]]
        f = lambda ts: "—" if not ts else fmt_t(max(ts))
        lines.append(f"| {exp} | {f(data_t)} | {f(plot_t)} |")
    lines += ["", "各欄為該實驗最後寫出的檔案時間；逐檔時間見 [FILE_DATES.md](../FILE_DATES.md)。"
              "2026-10-27 的舊結果在 `data/results_archive/2026-10-27_pre41/`。", END]
    inject(EXPDOCS / "README.md", "\n".join(lines))


def inject(path: Path, block: str) -> None:
    text = path.read_text()
    if BEGIN in text:
        text = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(text)
    print(f"updated {path.relative_to(ROOT)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "snapshot":
        snapshot(force="--force" in sys.argv)
    elif cmd == "render":
        render()
    else:
        sys.exit(__doc__)

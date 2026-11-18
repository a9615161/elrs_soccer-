# 檔案產生時間（首次 commit 前快照）

來源：`docs/file_dates.tsv`（snapshot taken 2026-11-18T17:10:52+08:00; mtime = filesystem modification time）。
時間為檔案系統的最後修改時間（CST, UTC+8），即該檔最後一次被寫出的時間；結果檔與圖表＝產生時間，程式與文件＝最後編輯時間。git 不保存 mtime，所以首次 commit 前的時間以此表為準，之後以 `git log` 為準。

- 2026-10-27：初版模型的結果，封存於 `data/results_archive/2026-10-27_pre41/`。
- 2026-11-02：以 ExpressLRS 4.1.0 模型重跑的全部結果（`data/results/`），執行紀錄在 `data/logs/rerun41.log`、`rerun41b.log`。
- 2026-11-18：本表與 `tools/file_dates.py`，以及 `docs/experiments/` 中的「資料產生時間」區塊。E*.md 與 README.md 在快照後只加了該區塊，表中時間是加區塊前的內容時間。

## 各實驗資料時間

| 實驗 | 資料檔（parquet/yaml） | 圖表與摘要（plots/） | 備註 |
|---|---|---|---|
| [E1](experiments/E1.md) | 2026-11-02 17:56 – 17:58 | 2026-11-02 18:22 |  |
| [E2](experiments/E2.md) | 2026-11-02 18:13 | — |  |
| [E3](experiments/E3.md) | 2026-11-02 18:13 | 2026-11-02 18:13 – 18:22 |  |
| [E4](experiments/E4.md) | — | 2026-11-02 18:39 |  |
| [E5](experiments/E5.md) | — | 2026-11-02 17:43 | 輸出時間（2026-11-02 17:43）早於 `sim/linksim.py` 最後修改（18:23），E5 有 import linksim，因此這份輸出不一定對應 commit 中的 linksim；需重跑確認。 |
| [E6](experiments/E6.md) | 2026-11-02 18:14 | 2026-11-02 18:14 – 18:22 |  |
| [E7](experiments/E7.md) | 2026-11-02 18:24 – 18:28 | 2026-11-02 18:32 |  |
| [E8](experiments/E8.md) | 2026-11-02 18:28 – 18:30 | 2026-11-02 18:32 |  |
| [E9](experiments/E9.md) | 2026-11-02 18:31 | 2026-11-02 18:32 |  |
| [E10](experiments/E10.md) | 2026-11-02 18:31 | 2026-11-02 18:32 |  |

「與 10-27 封存版逐位元相同」表示 4.1.0 重跑後輸出沒有變：E1 全部、E2 的 `nocommit.parquet`（兩者不經過鏈路模型）。

## 目前結果 `data/results/`

### `data/results/e1_orthogonality`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 17:56 | 202 B | `772759bb6894` |  |
| `nocommit.yaml` | 2026-11-02 17:56 | 230 B | `bcad10945e6d` | 與 10-27 封存版逐位元相同 |
| `nocommit_drone.parquet` | 2026-11-02 17:56 | 181.9 KB | `53fa550b97c4` | 與 10-27 封存版逐位元相同 |
| `nocommit_pairs.parquet` | 2026-11-02 17:56 | 39.5 KB | `7de9b388334f` | 與 10-27 封存版逐位元相同 |
| `plots/e1_adjacent_vs_M.png` | 2026-11-02 18:22 | 104.3 KB | `15b592eaeed8` | 與 10-27 封存版逐位元相同 |
| `plots/e1_channel_usage.png` | 2026-11-02 18:22 | 108.4 KB | `1c2bab8e94af` | 與 10-27 封存版逐位元相同 |
| `plots/e1_collision_vs_M.png` | 2026-11-02 18:22 | 97.5 KB | `7f3f2e8276f1` | 與 10-27 封存版逐位元相同 |
| `plots/e1_leakage_vs_M.png` | 2026-11-02 18:22 | 92.3 KB | `3c1d49758c6d` | 與 10-27 封存版逐位元相同 |
| `plots/e1_summary_drone.csv` | 2026-11-02 18:22 | 537 B | `2799301ed35e` | 與 10-27 封存版逐位元相同 |
| `plots/e1_summary_pairs.csv` | 2026-11-02 18:22 | 5.9 KB | `3366e811280b` | 與 10-27 封存版逐位元相同 |

### `data/results/e1_saturation`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 17:58 | 202 B | `772759bb6894` |  |
| `nocommit.yaml` | 2026-11-02 17:58 | 259 B | `40c998132df1` | 與 10-27 封存版逐位元相同 |
| `nocommit_drone.parquet` | 2026-11-02 17:58 | 568.1 KB | `94e727afa278` | 與 10-27 封存版逐位元相同 |
| `nocommit_pairs.parquet` | 2026-11-02 17:58 | 53.0 KB | `989e51f60714` | 與 10-27 封存版逐位元相同 |
| `plots/e1sat_grid.png` | 2026-11-02 18:22 | 307.7 KB | `38233792ee30` | 與 10-27 封存版逐位元相同 |
| `plots/e1sat_summary.csv` | 2026-11-02 18:22 | 19.7 KB | `a2be7cd8632f` | 與 10-27 封存版逐位元相同 |

### `data/results/e2_prediction`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:13 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:13 | 26.6 KB | `7aee44f88b97` | 與 10-27 封存版逐位元相同 |
| `nocommit.yaml` | 2026-11-02 18:13 | 183 B | `5412cec2d1a3` | 與 10-27 封存版逐位元相同 |
| `nocommit_unique.parquet` | 2026-11-02 18:13 | 1.5 KB | `24b856d64863` |  |

### `data/results/e3_forgery`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:13 | 202 B | `772759bb6894` |  |
| `nocommit.yaml` | 2026-11-02 18:13 | 217 B | `1355d0472c76` |  |
| `nocommit_cross.parquet` | 2026-11-02 18:13 | 3.4 KB | `eaed643c45d7` |  |
| `nocommit_forgery.parquet` | 2026-11-02 18:13 | 6.6 KB | `a04637c15334` |  |
| `nocommit_replay.parquet` | 2026-11-02 18:13 | 8.3 KB | `a6f11ad2a800` |  |
| `plots/e3_consecutive.csv` | 2026-11-02 18:13 | 1.6 KB | `ef79b7b53f8c` |  |
| `plots/e3_forgery_vs_W.png` | 2026-11-02 18:22 | 122.8 KB | `6ad7d326926c` |  |
| `plots/e3_replay.png` | 2026-11-02 18:22 | 74.8 KB | `bb3bd76f417b` |  |

### `data/results/e4_bit_budget`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `plots/e4_bit_budget.csv` | 2026-11-02 18:39 | 5.1 KB | `1faed61ef441` |  |
| `plots/e4_layout.png` | 2026-11-02 18:39 | 160.4 KB | `81ad8d803662` |  |

### `data/results/e5_baseline`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `plots/e5_checks.csv` | 2026-11-02 17:43 | 1.2 KB | `949a2a47cef1` |  |
| `plots/e5_lq_vs_per.csv` | 2026-11-02 17:43 | 3.5 KB | `0ceafe4ff6e8` |  |

### `data/results/e6_drift`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:14 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:14 | 36.2 KB | `46b373ab9c0b` |  |
| `nocommit.yaml` | 2026-11-02 18:14 | 363 B | `e1c31eb985c2` |  |
| `plots/e6_counter_bits.csv` | 2026-11-02 18:14 | 2.0 KB | `0ab52490bb1e` |  |
| `plots/e6_min_window.png` | 2026-11-02 18:22 | 218.1 KB | `6e2ba3ad85b7` |  |
| `plots/e6_summary.csv` | 2026-11-02 18:22 | 16.6 KB | `74d39dcaf25f` |  |

### `data/results/e7_blackout`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:24 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:26 | 1.2 MB | `09845a71fd5c` |  |
| `nocommit.yaml` | 2026-11-02 18:24 | 380 B | `ee3636a304a8` |  |
| `plots/e7_blackout_recovery.png` | 2026-11-02 18:32 | 209.2 KB | `bc656325d8f0` |  |
| `plots/e7_blackout_summary.csv` | 2026-11-02 18:32 | 52.1 KB | `fc08d45ec5f6` |  |

### `data/results/e7_burst`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:27 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:28 | 5.4 MB | `0c2657e25206` |  |
| `nocommit.yaml` | 2026-11-02 18:27 | 357 B | `0ea1d5548285` |  |
| `plots/e7_burst_failsafe_time.png` | 2026-11-02 18:32 | 218.0 KB | `101e167eebbd` |  |
| `plots/e7_burst_reacq_cdf.png` | 2026-11-02 18:32 | 220.1 KB | `7b417f232843` |  |
| `plots/e7_burst_reacq_summary.csv` | 2026-11-02 18:32 | 2.1 KB | `b8d738d5c16c` |  |

### `data/results/e7_reboot`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:26 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:26 | 155.3 KB | `0dc8a1558999` |  |
| `nocommit.yaml` | 2026-11-02 18:26 | 273 B | `df2aac009573` |  |
| `plots/e7_reboot_summary.csv` | 2026-11-02 18:32 | 3.0 KB | `d37e45df3ba3` |  |

### `data/results/e8_jamming`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:28 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:30 | 8.2 MB | `b6e8a6b5169b` |  |
| `nocommit.yaml` | 2026-11-02 18:28 | 528 B | `84e11c5b3310` |  |
| `plots/e8_failsafe_vs_duty.png` | 2026-11-02 18:32 | 141.7 KB | `28135b27e036` |  |
| `plots/e8_max_outage_vs_duty.png` | 2026-11-02 18:32 | 131.7 KB | `1982b79fd9c4` |  |
| `plots/e8_reacq_summary.csv` | 2026-11-02 18:32 | 2.0 KB | `31a8054bf2e0` |  |
| `plots/e8_summary.csv` | 2026-11-02 18:32 | 131.7 KB | `2e0b05401e3e` |  |

### `data/results/e8_key`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:30 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:30 | 677.1 KB | `fd6d31b396f0` |  |
| `nocommit.yaml` | 2026-11-02 18:30 | 482 B | `5c02f2305b56` |  |
| `plots/e8_key_summary.csv` | 2026-11-02 18:32 | 7.6 KB | `01a9f509166c` |  |

### `data/results/e8_syncjam`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:30 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:30 | 109.3 KB | `1cacfc25fb2d` |  |
| `nocommit.yaml` | 2026-11-02 18:30 | 318 B | `50c099ee40ff` |  |
| `plots/e8_syncjam_summary.csv` | 2026-11-02 18:32 | 1.5 KB | `b75a41580735` |  |

### `data/results/e9_multidrone`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:31 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:31 | 181.7 KB | `ba186ffe3f70` |  |
| `nocommit.yaml` | 2026-11-02 18:31 | 557 B | `0f702b934576` |  |
| `plots/e9_friendly_loss.png` | 2026-11-02 18:32 | 101.4 KB | `b6e044f85e91` |  |
| `plots/e9_offset.png` | 2026-11-02 18:32 | 178.5 KB | `afd937e44a15` |  |
| `plots/e9_offset_summary.csv` | 2026-11-02 18:32 | 7.6 KB | `60fd73327baa` |  |
| `plots/e9_summary.csv` | 2026-11-02 18:32 | 7.1 KB | `708e3ab74794` |  |

### `data/results/e10_cost`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 | 備註 |
|---|---|---|---|---|
| `nocommit.env.json` | 2026-11-02 18:31 | 202 B | `772759bb6894` |  |
| `nocommit.parquet` | 2026-11-02 18:31 | 230.3 KB | `d5834a2370d4` |  |
| `nocommit.yaml` | 2026-11-02 18:31 | 490 B | `77f57de5e432` |  |
| `plots/e10_feasibility.png` | 2026-11-02 18:32 | 118.6 KB | `fe1b71f67929` |  |
| `plots/e10_summary.csv` | 2026-11-02 18:32 | 37.9 KB | `dc6c76d33b11` |  |
| `plots/e10_threshold.csv` | 2026-11-02 18:32 | 2.2 KB | `fe90fa252302` |  |

## 封存結果 `data/results_archive/2026-10-27_pre41/`

### `data/results_archive/2026-10-27_pre41/e1_orthogonality`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 17:17 | 202 B | `772759bb6894` |
| `nocommit.yaml` | 2026-10-27 17:17 | 230 B | `bcad10945e6d` |
| `nocommit_drone.parquet` | 2026-10-27 17:17 | 181.9 KB | `53fa550b97c4` |
| `nocommit_pairs.parquet` | 2026-10-27 17:17 | 39.5 KB | `7de9b388334f` |
| `plots/e1_adjacent_vs_M.png` | 2026-10-27 17:17 | 104.3 KB | `15b592eaeed8` |
| `plots/e1_channel_usage.png` | 2026-10-27 17:17 | 108.4 KB | `1c2bab8e94af` |
| `plots/e1_collision_vs_M.png` | 2026-10-27 17:17 | 97.5 KB | `7f3f2e8276f1` |
| `plots/e1_leakage_vs_M.png` | 2026-10-27 17:17 | 92.3 KB | `3c1d49758c6d` |
| `plots/e1_summary_drone.csv` | 2026-10-27 17:17 | 537 B | `2799301ed35e` |
| `plots/e1_summary_pairs.csv` | 2026-10-27 17:17 | 5.9 KB | `3366e811280b` |

### `data/results_archive/2026-10-27_pre41/e1_saturation`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 16:52 | 202 B | `772759bb6894` |
| `nocommit.yaml` | 2026-10-27 16:52 | 259 B | `40c998132df1` |
| `nocommit_drone.parquet` | 2026-10-27 16:52 | 568.1 KB | `94e727afa278` |
| `nocommit_pairs.parquet` | 2026-10-27 16:52 | 53.0 KB | `989e51f60714` |
| `plots/e1sat_grid.png` | 2026-10-27 16:57 | 307.7 KB | `38233792ee30` |
| `plots/e1sat_summary.csv` | 2026-10-27 16:57 | 19.7 KB | `a2be7cd8632f` |

### `data/results_archive/2026-10-27_pre41/e2_prediction`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 22:23 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 22:23 | 26.6 KB | `7aee44f88b97` |
| `nocommit.yaml` | 2026-10-27 22:23 | 183 B | `5412cec2d1a3` |
| `nocommit_unique.parquet` | 2026-10-27 22:23 | 1.3 KB | `70f541b4799b` |

### `data/results_archive/2026-10-27_pre41/e3_forgery`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:17 | 202 B | `772759bb6894` |
| `nocommit.yaml` | 2026-10-27 21:17 | 198 B | `41960ba569d0` |
| `nocommit_cross.parquet` | 2026-10-27 21:22 | 3.4 KB | `bf8906af2869` |
| `nocommit_forgery.parquet` | 2026-10-27 21:21 | 6.4 KB | `9be43e705bb2` |
| `nocommit_replay.parquet` | 2026-10-27 21:21 | 6.2 KB | `5b2539eee590` |
| `plots/e3_forgery_vs_W.png` | 2026-10-27 21:28 | 101.9 KB | `799805d5fb24` |
| `plots/e3_replay.png` | 2026-10-27 21:28 | 73.9 KB | `e7e225b4424d` |

### `data/results_archive/2026-10-27_pre41/e4_bit_budget`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `plots/e4_bit_budget.csv` | 2026-10-27 21:18 | 1.7 KB | `a4f3161e35dc` |
| `plots/e4_layout.png` | 2026-10-27 21:18 | 92.3 KB | `ed677e6fb648` |

### `data/results_archive/2026-10-27_pre41/e5_baseline`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `plots/e5_checks.csv` | 2026-10-27 21:20 | 552 B | `450d057d7df9` |
| `plots/e5_lq_vs_per.csv` | 2026-10-27 21:20 | 1.7 KB | `a6e12206ec81` |

### `data/results_archive/2026-10-27_pre41/e6_drift`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:23 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 21:23 | 22.8 KB | `c778e9d2e90c` |
| `nocommit.yaml` | 2026-10-27 21:23 | 323 B | `8c263f93c124` |
| `plots/e6_min_window.png` | 2026-10-27 21:28 | 158.0 KB | `9330ce983f0c` |
| `plots/e6_summary.csv` | 2026-10-27 21:28 | 8.1 KB | `f6a988e9c217` |

### `data/results_archive/2026-10-27_pre41/e7_burst`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:29 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 21:31 | 1.7 MB | `8f85de7298d0` |
| `nocommit.yaml` | 2026-10-27 21:29 | 298 B | `e47f376d7d6c` |
| `plots/e7_burst_failsafe_time.png` | 2026-10-27 21:33 | 100.2 KB | `1122a66480ec` |
| `plots/e7_burst_reacq_cdf.png` | 2026-10-27 21:33 | 88.1 KB | `5657655258a7` |
| `plots/e7_burst_reacq_summary.csv` | 2026-10-27 21:33 | 888 B | `b8c5ef53f4fe` |

### `data/results_archive/2026-10-27_pre41/e8_jamming`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:31 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 21:33 | 2.5 MB | `fd05e49f1734` |
| `nocommit.yaml` | 2026-10-27 21:31 | 469 B | `1d8f2a3ca413` |
| `plots/e8_failsafe_vs_duty.png` | 2026-10-27 21:34 | 141.5 KB | `db33dd6a3e66` |
| `plots/e8_max_outage_vs_duty.png` | 2026-10-27 21:34 | 131.9 KB | `3a99fcdac60d` |
| `plots/e8_reacq_summary.csv` | 2026-10-27 21:34 | 809 B | `8a8a8fb61987` |
| `plots/e8_summary.csv` | 2026-10-27 21:33 | 49.1 KB | `ab0bdb942f4c` |

### `data/results_archive/2026-10-27_pre41/e9_multidrone`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:34 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 21:34 | 74.5 KB | `d79506e71a5c` |
| `nocommit.yaml` | 2026-10-27 21:34 | 367 B | `2609424c4028` |
| `plots/e9_friendly_loss.png` | 2026-10-27 21:35 | 101.0 KB | `7bda6dc999f9` |
| `plots/e9_summary.csv` | 2026-10-27 21:34 | 5.1 KB | `5453cd5f8399` |

### `data/results_archive/2026-10-27_pre41/e10_cost`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `nocommit.env.json` | 2026-10-27 21:29 | 202 B | `772759bb6894` |
| `nocommit.parquet` | 2026-10-27 21:29 | 117.8 KB | `7b8cea80cf3a` |
| `nocommit.yaml` | 2026-10-27 21:29 | 442 B | `139a601dab8b` |
| `plots/e10_feasibility.png` | 2026-10-27 21:30 | 108.9 KB | `e759e2440fab` |
| `plots/e10_summary.csv` | 2026-10-27 21:30 | 19.2 KB | `cd40cdf12bdc` |
| `plots/e10_threshold.csv` | 2026-10-27 21:30 | 1.1 KB | `c1f507ef41f1` |

## 執行紀錄 `data/logs/`

### `data/logs`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `plot_e1.txt` | 2026-11-02 18:22 | 5.2 KB | `264e4f9cc9b6` |
| `plot_e10.txt` | 2026-11-02 18:32 | 902 B | `c34f5a302a5f` |
| `plot_e1sat.txt` | 2026-11-02 18:22 | 3.6 KB | `342687eb4292` |
| `plot_e3.txt` | 2026-11-02 18:22 | 76 B | `c3a23a24e837` |
| `plot_e6.txt` | 2026-11-02 18:22 | 74 B | `5193a1b22d02` |
| `plot_e7.txt` | 2026-11-02 18:32 | 2.8 KB | `ed18df8b4d82` |
| `plot_e7_blackout.txt` | 2026-11-02 18:32 | 11.2 KB | `3860413a6647` |
| `plot_e8.txt` | 2026-11-02 18:32 | 6.0 KB | `60cfd23c1ffc` |
| `plot_e8_key.txt` | 2026-11-02 18:32 | 8.0 KB | `daf00ab467b2` |
| `plot_e9.txt` | 2026-11-02 18:32 | 4.4 KB | `c26ba6fe3fb1` |
| `rerun41.log` | 2026-11-02 18:22 | 153.5 KB | `0d00fa0a6fda` |
| `rerun41b.log` | 2026-11-02 18:32 | 10.6 KB | `65701bcf93e6` |

## 程式、設定與文件

### `analysis`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `analysis/__init__.py` | 2026-10-27 16:08 | 0 B | `e3b0c44298fc` |
| `analysis/common.py` | 2026-10-27 16:09 | 2.0 KB | `2c8b356b8284` |
| `analysis/e1_orthogonality.py` | 2026-10-27 16:46 | 8.1 KB | `b4cf7c83e1ac` |
| `analysis/e2_prediction.py` | 2026-10-27 22:24 | 6.3 KB | `5f0085326e34` |
| `analysis/e3_forgery.py` | 2026-11-02 17:38 | 7.7 KB | `3b195c84f17b` |
| `analysis/e4_bit_budget.py` | 2026-11-02 18:39 | 6.0 KB | `e32c722e3cee` |
| `analysis/e5_baseline.py` | 2026-11-02 17:42 | 5.3 KB | `179e2eb8f769` |
| `analysis/e6_drift.py` | 2026-11-02 17:38 | 4.8 KB | `e7920612f590` |
| `analysis/e9_multidrone.py` | 2026-11-02 17:42 | 6.2 KB | `60256f0a6f50` |

### `configs`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `configs/e10_cost.yaml` | 2026-11-02 17:38 | 525 B | `99f4715ab8cd` |
| `configs/e1_orthogonality.yaml` | 2026-10-27 16:46 | 483 B | `01f0aa6abfe4` |
| `configs/e1_saturation.yaml` | 2026-10-27 16:46 | 371 B | `9eb892d215e9` |
| `configs/e2_prediction.yaml` | 2026-10-27 21:06 | 347 B | `62aa0a3c46f6` |
| `configs/e3_forgery.yaml` | 2026-11-02 17:38 | 208 B | `b854c64ef1be` |
| `configs/e6_drift.yaml` | 2026-11-02 17:38 | 641 B | `b79c20ced83a` |
| `configs/e7_blackout.yaml` | 2026-11-02 17:38 | 395 B | `4db8635a5eaf` |
| `configs/e7_burst.yaml` | 2026-11-02 17:38 | 526 B | `9965176ba226` |
| `configs/e7_reboot.yaml` | 2026-11-02 17:38 | 251 B | `bf37f05c1326` |
| `configs/e8_jamming.yaml` | 2026-11-02 17:38 | 559 B | `cce1b175a701` |
| `configs/e8_key.yaml` | 2026-11-02 17:38 | 527 B | `ef963fb30993` |
| `configs/e8_syncjam.yaml` | 2026-11-02 17:38 | 369 B | `a86375dc2f46` |
| `configs/e9_multidrone.yaml` | 2026-11-02 17:38 | 769 B | `325168917173` |
| `configs/elrs_baseline.yaml` | 2026-11-02 17:36 | 11.2 KB | `28e36bec9ed4` |

### `docs`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `docs/experiments/E1.md` | 2026-10-27 21:31 | 3.7 KB | `14677e94ebde` |
| `docs/experiments/E10.md` | 2026-11-02 18:36 | 1.8 KB | `39e362ea80d6` |
| `docs/experiments/E2.md` | 2026-11-02 18:36 | 2.8 KB | `c628fd473e8c` |
| `docs/experiments/E3.md` | 2026-11-02 18:36 | 4.2 KB | `14c8e29d6f92` |
| `docs/experiments/E4.md` | 2026-11-02 18:36 | 2.4 KB | `098c0c769103` |
| `docs/experiments/E5.md` | 2026-11-02 18:36 | 2.3 KB | `a0834b58339c` |
| `docs/experiments/E6.md` | 2026-11-02 18:36 | 2.0 KB | `1e53fd238193` |
| `docs/experiments/E7.md` | 2026-11-02 18:36 | 4.3 KB | `3316dece3966` |
| `docs/experiments/E8.md` | 2026-11-02 18:36 | 2.9 KB | `1e6fe07c420c` |
| `docs/experiments/E9.md` | 2026-11-02 18:36 | 3.0 KB | `3baa9e42a9ac` |
| `docs/experiments/README.md` | 2026-11-02 18:36 | 3.5 KB | `ce0483e4fde3` |
| `docs/experiments/RESULTS_2026-11-02.md` | 2026-11-02 19:21 | 9.4 KB | `ae94385e21ea` |

### `libproto`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `libproto/CMakeLists.txt` | 2026-10-27 21:00 | 701 B | `b7236be51697` |
| `libproto/include/proto/crypto_backend.h` | 2026-10-27 20:59 | 1.5 KB | `a3ce10da189b` |
| `libproto/include/proto/hop.h` | 2026-10-27 16:44 | 2.6 KB | `cb241f260fc2` |
| `libproto/include/proto/hop_gap.h` | 2026-10-27 21:00 | 1.8 KB | `5ff4736a2ff5` |
| `libproto/include/proto/kdf.h` | 2026-10-27 16:06 | 757 B | `9664a7944bec` |
| `libproto/include/proto/packet.h` | 2026-10-27 20:59 | 2.1 KB | `cb528484dce5` |
| `libproto/include/proto/resync.h` | 2026-11-02 17:36 | 2.5 KB | `ad622f453008` |
| `libproto/src/crypto_backend.c` | 2026-10-27 20:59 | 836 B | `5b721e55c246` |
| `libproto/src/hop.c` | 2026-10-27 16:44 | 4.1 KB | `a5ebb92cb089` |
| `libproto/src/hop_gap.c` | 2026-10-27 16:44 | 3.4 KB | `5a6b52028a5f` |
| `libproto/src/kdf.c` | 2026-10-27 16:06 | 1.1 KB | `5671c2ddbb43` |
| `libproto/src/packet.c` | 2026-10-27 20:59 | 3.0 KB | `f57b264231bf` |
| `libproto/src/resync.c` | 2026-11-02 17:36 | 3.1 KB | `11c0f640ac0b` |
| `libproto/src/siphash.c` | 2026-10-27 16:06 | 2.0 KB | `3bd6caf7a0ba` |
| `libproto/tests/test_main.c` | 2026-10-27 21:00 | 10.2 KB | `05e3b52b35d1` |
| `libproto/tests/test_packet.inc` | 2026-10-27 21:01 | 5.8 KB | `b8643af65e8a` |

### `scripts`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `scripts/__init__.py` | 2026-10-27 16:25 | 0 B | `e3b0c44298fc` |
| `scripts/plot_e1.py` | 2026-10-27 16:47 | 7.1 KB | `8e648c5d4cc4` |
| `scripts/plot_e10.py` | 2026-11-02 17:39 | 2.9 KB | `56fbcbff2963` |
| `scripts/plot_e1sat.py` | 2026-10-27 16:47 | 4.0 KB | `863ea06bfb7d` |
| `scripts/plot_e3.py` | 2026-11-02 17:40 | 2.6 KB | `2a25cff9aac2` |
| `scripts/plot_e6.py` | 2026-11-02 17:39 | 2.1 KB | `a39efbfbb1f4` |
| `scripts/plot_e7.py` | 2026-11-02 17:39 | 4.2 KB | `b99af835f1b6` |
| `scripts/plot_e7_blackout.py` | 2026-11-02 17:39 | 3.5 KB | `503024f2dfe8` |
| `scripts/plot_e8.py` | 2026-10-27 21:32 | 2.8 KB | `d50b74c1496e` |
| `scripts/plot_e8_key.py` | 2026-11-02 17:39 | 1.5 KB | `b8812a436f3d` |
| `scripts/plot_e9.py` | 2026-11-02 17:39 | 3.7 KB | `3309df95f612` |
| `scripts/run_experiment.py` | 2026-10-27 21:05 | 4.7 KB | `2481f933c1ae` |

### `sim`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `sim/__init__.py` | 2026-10-27 16:08 | 0 B | `e3b0c44298fc` |
| `sim/baselines/__init__.py` | 2026-10-27 16:08 | 0 B | `e3b0c44298fc` |
| `sim/baselines/elrs_ota.py` | 2026-10-27 21:05 | 1.5 KB | `3443fe991e1f` |
| `sim/baselines/elrs_stock.py` | 2026-10-27 16:08 | 2.0 KB | `1cf1cb5339d8` |
| `sim/channel.py` | 2026-11-02 17:36 | 4.3 KB | `df0881a9a415` |
| `sim/linksim.py` | 2026-11-02 18:23 | 18.6 KB | `6912dd7b21ec` |
| `sim/phy.py` | 2026-11-02 17:36 | 3.5 KB | `e5fe17298593` |
| `sim/proto_ffi.py` | 2026-11-02 17:36 | 9.5 KB | `cabee5edc9b4` |

### `tests`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `tests/conftest.py` | 2026-10-27 16:08 | 98 B | `8659c4f6af34` |
| `tests/data/elrs_fhss_golden.json` | 2026-10-27 16:07 | 3.7 KB | `1da6b7f0d7a6` |
| `tests/test_elrs_stock.py` | 2026-10-27 21:05 | 1.3 KB | `8c1eca13cddc` |
| `tests/test_phy.py` | 2026-10-27 21:01 | 1.5 KB | `69ee4bf9419c` |
| `tests/test_proto_ffi.py` | 2026-10-27 16:08 | 2.0 KB | `f24e88681318` |
| `tests/test_scenarios.py` | 2026-11-02 18:33 | 6.7 KB | `bcf54480bd8d` |

### `tools`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `tools/bench_siphash.c` | 2026-10-27 21:25 | 701 B | `cbe27c71ad33` |
| `tools/gen_elrs_golden.sh` | 2026-10-27 16:07 | 1.7 KB | `acfefbb803d8` |

### `（根目錄）`

| 檔案 | 產生／最後修改 | 大小 | sha256 前 12 碼 |
|---|---|---|---|
| `.gitignore` | 2026-10-27 16:11 | 55 B | `23c05978f53a` |
| `Makefile` | 2026-11-02 17:38 | 2.1 KB | `cdb4afe9b75a` |
| `requirements.lock` | 2026-10-27 16:10 | 444 B | `822f44980339` |

# 軟體模擬實驗紀錄（ELRS 4.1.0 基準）

所有結果都由同一份模型重跑，協定時序與參數取自 ExpressLRS 4.1.0（commit a9d4a9cb），見 `configs/elrs_baseline.yaml`，每個值附檔案與行號。2026-10-27 的舊結果封存在 `data/results_archive/2026-10-27_pre41/`。

## 總表

| 實驗 | 主要發現 | 紀錄 |
|---|---|---|
| E1 正交跳頻 | 間距轉換 g=2：同頻與鄰頻碰撞為 0，全場 10 機每 hop 2.89 次 SipHash；4 輪 Feistel 有可量測偏差 | [E1](E1.md) |
| E2 序列預測（新版文件 E1） | 一個 SYNC 加中位數 3、最多 5 個 hop 即可還原 Stock 序列；Proposed 維持 1.26% ≈ 1/80 | [E2](E2.md) |
| E3 偽造與重放 | 偽造率全部符合理論；14-bit tag 在 500 Hz 約 33 s 一次；Stock 重放週期 3840 封包在模型中成立 | [E3](E3.md) |
| E4 位元預算 | Proposed 長度與 TOA 不變；ExpCtr 升 OTA8 後 LoRa 500／250／150 Hz 放不進原週期 | [E4](E4.md) |
| E5 基準時序 | 8 種速率的時序、LQ、failsafe、連線條件與原始碼一致（關卡通過，尚未實機比對） | [E5](E5.md) |
| E6 漂移與視窗 | W = 8 足夠；±50 ppm 失效界線 FLRC 1000 Hz 15 s、500 Hz 70 s；32-bit 信標計數器足夠 | [E6](E6.md) |
| E7 斷線恢復 | 超過 DisconnectTimeout 後 Proposed 明顯較快，但 FLRC 1000 Hz 10 s 與 5 種速率的重開機慢於 Stock | [E7](E7.md) |
| E8 干擾類型 | 只打 sync 頻道時，Stock 重連 0%、Proposed 100%（200 種子）；非選擇性全頻干擾差距很小 | [E8](E8.md) |
| E9 多機 | Proposed 對齊時友機損失為 0；偏差門檻 = P − TOA，完全不對齊最多 4.2%（Stock 23.5%） | [E9](E9.md) |
| E10 運算開銷 | LoRa 500 Hz 與 FLRC 1000 Hz 最緊，W = 8 時 c ≤ 44 µs；ESP 實測待補 | [E10](E10.md) |

## 本輪對模型的修正

| 項目 | 修正 | 影響 |
|---|---|---|
| 速率 | 4 → 8 種 | E4–E10 |
| 序列與 nonce 相位 | 改為一起歸零（`tx_main.cpp` L494-495），移除假性卡死 | Stock 的 E5、E7、E8、E9 |
| 連線條件 | 加入 PFD；minLq 依 hop interval | Stock 重連 |
| RX 時序 | TOCK 位置依 4.1.0 | E6、Proposed 模型 |
| Proposed 信標 | 加入會合頻道與信標；RX 重開機與漂移情境；信標改為 32-bit 計數器 + 30-bit 標籤 | E7–E10 |
| 視窗 W | 模擬預設 16 → 8 | E7–E9 |

## 共同假設（論文需列明）
- 固定開銷 100 µs、ISR 抖動 15 µs、PFD 初始相位 50 µs、鄰頻掉包機率 0.5 為**假設值**，待硬體校正。
- 干擾即掉包（未建模 SINR）；同頻碰撞雙方皆掉（無捕獲效應）。
- 運算時間以參數 c 表示；目前所有密碼運算都使用 SipHash-2-4。
- 信標週期、會合頻道數與輪替時間為本研究選定的值，尚未最佳化。

## 尚未完成
- 偽造 sync 的狀態操縱（新版文件 E2）與相關組合干擾
- Model Match 分組
- CRC16、AES-GCM、Ascon、Chaskey 後端
- 位元錯誤模型與未偵測錯誤率
- airtime 與 SX1280 datasheet 公式原文比對
- 新版文件 E11

## 狀態
2026-11-18 首次 commit，內容為 2026-11-02 的程式與結果。結果是在 commit 前產生的，所以檔名仍為 `nocommit_*`；各檔產生時間記在 [FILE_DATES.md](../FILE_DATES.md)（快照：`docs/file_dates.tsv`，含 sha256）。重跑一次後，結果檔名才會對應到 commit hash。

## 重現全部
```
make lib test test-c
.venv/bin/python analysis/e5_baseline.py
.venv/bin/python analysis/e4_bit_budget.py
make exp EXP=e1 && make exp EXP=e1sat && make exp EXP=e2 && make exp EXP=e3 && make exp EXP=e6
make exp EXP=e7blackout && make exp EXP=e7reboot && make exp EXP=e7
make exp EXP=e8 && make exp EXP=e8key && make exp EXP=e8syncjam
make exp EXP=e9 && make exp EXP=e10
```
各實驗的繪圖指令見各自的紀錄。

<!-- file-dates:begin (tools/file_dates.py render) -->
## 資料產生時間

| 實驗 | 資料 | 圖表 |
|---|---|---|
| E1 | 2026-11-02 17:58 | 2026-11-02 18:22 |
| E2 | 2026-11-02 18:13 | — |
| E3 | 2026-11-02 18:13 | 2026-11-02 18:22 |
| E4 | — | 2026-11-02 18:39 |
| E5 | — | 2026-11-02 17:43 |
| E6 | 2026-11-02 18:14 | 2026-11-02 18:22 |
| E7 | 2026-11-02 18:28 | 2026-11-02 18:32 |
| E8 | 2026-11-02 18:30 | 2026-11-02 18:32 |
| E9 | 2026-11-02 18:31 | 2026-11-02 18:32 |
| E10 | 2026-11-02 18:31 | 2026-11-02 18:32 |

各欄為該實驗最後寫出的檔案時間；逐檔時間見 [FILE_DATES.md](../FILE_DATES.md)。2026-10-27 的舊結果在 `data/results_archive/2026-10-27_pre41/`。
<!-- file-dates:end -->

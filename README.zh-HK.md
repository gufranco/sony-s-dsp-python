# S-DSP

以 Python 實現的 Sony S-DSP 聲音產生器，按晶片本身的三十二時鐘排程運行，並以 Nintendo《SNES Development Manual》中的暫存器映射和參數表為準。

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文（香港）

[![CI](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-s-dsp-python)](https://github.com/gufranco/sony-s-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

來自真實音樂傾印的 **240** 個暫存器狀態重播 **23,040** 個樣本，與 `snes_spc 0.9.0` 相比 **0** 個失敗，在主機上取得的 **104** 項檢查中有 **97** 項一致，在手冊中找到 **28** 段引文，**828** 項測試，**100%** 語句和分支覆蓋率，沒有依賴項

```python
import sdsp

dsp = sdsp.Chip("s-dsp", sdsp.Memory(fill=0)).reset()

for address, value in {0x0200: 0x00, 0x0201: 0x03, 0x0202: 0x00, 0x0203: 0x03}.items():
    dsp.memory.write8(address, value)
dsp.memory.write8(0x0300, 0xB3)
for offset in range(1, 9):
    dsp.memory.write8(0x0300 + offset, 0x77)

voice = {0x00: 0x7F, 0x01: 0x7F, 0x02: 0x00, 0x03: 0x10, 0x04: 0x00, 0x05: 0x8F, 0x06: 0xE0}
chip = {0x0C: 0x7F, 0x1C: 0x7F, 0x5D: 0x02, 0x6C: 0x20, 0x4C: 0x01}
for register, value in {**voice, **chip}.items():
    dsp.write(register, value)

print(dsp.render(16)[0::2])
print(f"ENVX {dsp.read(0x08):#04x}, OUTX {dsp.read(0x09):#04x}, ENDX {dsp.read(0x7C):#04x}")
```

```
[0, 0, 0, 0, 0, 0, 0, 0, 7057, 14110, 14110, 14110, 14110, 14110, 14110, 14110]
ENVX 0x7f, OUTX 0x37, ENDX 0x01
```

位於頁 `$02` 的樣本目錄把音源 0 指向 `$0300` 的一個 BRR 區塊。區塊標頭 `$B3` 設定移位 11、濾波器 0，以及結束和循環旗標，所以這個區塊重複同一個值。聲部 0 以音高 `$1000` 播放它，即每輸入一個樣本輸出一個樣本，並啟用 ADSR，起音速率為 F。`FLG` 為 `$20`，這會清除重設和靜音位元，並保持回聲寫入關閉。範例印出 16 個樣本的左聲道。頭 8 個是靜音，因為 KON 每隔一個樣本才讀取一次，而被觸發的聲部之後還要等 5 個樣本才開始解碼。起音速率 F 每步加 `$400`，所以包絡在第 8 個樣本到達一半，在第 9 個樣本到達最大值。ENDX 位元 0 被設定，因為該區塊帶有結束旗標。

## 安裝

| 需求 | 版本 |
|:--|:--|
| Python | 3.12 或更新 |
| git | 任何版本 |
| Docker | 只在從 [`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) 重建參考驅動程式時需要 |

```bash
git clone https://github.com/gufranco/sony-s-dsp-python.git
cd sony-s-dsp-python
python3 sdsp/doctor.py
```

這個套件只匯入標準程式庫的內容。[`conformance/corpus.json`](conformance/corpus.json) 已納入版本控制，所以語料庫在全新的簽出副本上就能運行。

診斷腳本會檢查機器和簽出副本、建立晶片、讀取一個未寫入的位址、計算語料庫的摘要，最後輸出一行結果。所有檢查通過時以 0 結束，否則以 1 結束。提交錯誤報告時，請貼上它的完整輸出。

```
  7 checks, nothing to report
```

安裝後的副本以 `sdsp-doctor` 提供相同的報告。

發佈版本遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根據提交歷史產生。每個發佈版本都有標籤，並列在[發佈頁面](https://github.com/gufranco/sony-s-dsp-python/releases)上。

## 介面

`sdsp.Chip(model, memory=None, seed=UNSET_SEED, gaussian=None)` 建立一個晶片。`model` 為必填。`memory` 可以是任何具有 `read8(address)` 和 `write8(address, value)` 的物件，省略時晶片會建立一個 `SparseMemory`。`seed` 設定每個暫存器、計數器、鎖存器、已解碼樣本和位置的開機圖樣，晶片會一直保持該圖樣，直至呼叫方呼叫 `reset()`。雜訊產生器永遠不會取到 0，這是其回饋無法離開的唯一值。建構函式從不呼叫 `reset()`，亦沒有任何選項令它呼叫。`gaussian` 以你自己的表取代插值核，並由 `check_kernel` 檢查。

| 型號 | 別名 | 聲部 | 暫存器 |
|:--|:--|:--|:--|
| `s-dsp` | `sdsp`, `sonysdsp`, `dsp`, `snesdsp` | 8 | 128 |

比對名稱時忽略大小寫、連字號和底線，所以 `SNES-DSP` 會建立 `s-dsp`。

### 呼叫

| 呼叫 | 效果 |
|:--|:--|
| `read(address)` | 傳回位於 `address & $7F` 的暫存器 |
| `write(address, value)` | 把 `value & $FF` 存到 `address & $7F`。寫入 KON 的值會鎖存到下一個 KON 樣本。寫入 ENDX 會把它清為 0 |
| `reset()` | 重設線在錄製語料庫所用的實作 `snes_spc` 中的動作：清除所有暫存器和所有鎖存器，把 `FLG` 設為 `$E0`、雜訊產生器設為 `$4000`、隔樣本切換位設為 1，並令全部八個聲部靜音。傳回該晶片 |
| `clock()` | 執行 `PIPELINE` 為目前時鐘指定的步驟，然後移到 32 個時鐘中的下一個 |
| `run(clocks)` | 執行 `clock()` 指定的次數 |
| `render(samples)` | 運行 `samples` 乘以 32 個時鐘，並以左右值交錯的形式傳回輸出，每個樣本兩個值 |
| `voice_1` 至 `voice_9`、`voice_3a`、`voice_3b`、`voice_3c`、`misc_27` 至 `misc_30`、`echo_22` 至 `echo_30` | `PIPELINE` 指定的步驟。由 `clock()` 呼叫，呼叫者無須自行呼叫 |

### 狀態

| 屬性 | 意義 |
|:--|:--|
| `model` | 標準型號名稱 |
| `memory` | 聲部和回聲緩衝區讀寫的 64 KB 音訊 RAM 物件 |
| `registers` | 以 `bytearray` 表示的 128 個暫存器 |
| `voices` | 八個 `Voice` 物件 |
| `phase` | 下一個運行的是 32 個時鐘中的哪一個，0 至 31 |
| `rendered` | 自上次 `render` 以來產生的輸出值 |
| `gaussian` | 這個晶片重新取樣時使用的插值核 |

一個 `Voice` 包含 `index`、`bit`、`base`，BRR 狀態在 `brr_address`、`brr_offset`、`buffer` 和 `buffer_position`，音高位置在 `interpolation`，包絡在 `envelope`、`hidden_envelope`、`envelope_mode` 和 `envelope_out`，以及 `key_on_delay`。

```python
import sdsp

for name, model in sdsp.MODELS.items():
    print(name, model.aliases, model.voices, model.registers)

print(sdsp.Chip("SNES-DSP").model)

for name in (None, "ym2612"):
    try:
        sdsp.Chip(name)
    except sdsp.UnknownModelError as error:
        print(error)
```

```
s-dsp ('sdsp', 'sonysdsp', 'dsp', 'snesdsp') 8 128
s-dsp
no model was named, and this package will not choose one for you. Name one of: s-dsp
ym2612 is not a model this package covers; it has s-dsp
```

```python
import sdsp

dsp = sdsp.Chip("s-dsp")
print(f"{dsp.read(0x6C):#04x} {dsp.read(0x7C):#04x} {dsp.read(0xEC):#04x}")
print(dsp.reset() is dsp, f"{dsp.read(0x6C):#04x} {dsp.read(0x7C):#04x}")

dsp.write(0x7C, 0xFF)
dsp.write(0x13, 0x1234)
print(
    f"{dsp.read(0x7C):#04x} {dsp.read(0x13):#04x}", dsp.phase, len(dsp.voices), dsp.voices[3].base
)
```

```
0x25 0x27 0x25
True 0xe0 0x00
0x00 0x34 0 8 48
```

重設之前，暫存器保存打亂的圖樣，而位址 `$EC` 讀取的是與 `$6C` 相同的暫存器。重設之後，`FLG` 為 `$E0`。寫入 ENDX 會將它清除，而超過一個位元組的值只保留低 8 位元。聲部 3 的暫存器從 `$30` 開始。

### 模組內容

| 名稱 | 內容 |
|:--|:--|
| `sdsp.MODELS` | `Model` 記錄，以標準名稱為鍵 |
| `sdsp.Model` | 型號記錄：`name`、`summary`、`voices`、`registers`、`aliases`，以及 `build(memory, **options)` |
| `sdsp.Memory(size=0x10000, fill=None, seed=UNSET_SEED)` | 平面音訊 RAM。`fill` 是一個位元組值或位元組串，沒有它時內容由 `seed` 打亂產生。位址在 16 位元處迴繞 |
| `sdsp.SparseMemory(seed=UNSET_SEED)` | 相同的約定，但不分配記憶體。未寫入的位址傳回由位址和 `seed` 混合而成的位元組，`cells` 保存已寫入的內容 |
| `sdsp.scramble(size, seed=UNSET_SEED)` | `Memory` 和暫存器檔案啟動時保存的打亂位元組 |
| `sdsp.UNSET_SEED` | 預設種子，`0x5A5A5A5A` |
| `sdsp.Voice` | 一個聲部及其狀態 |
| `sdsp.PIPELINE` | 排程：對 32 個時鐘中的每一個，列出運行的步驟，每項是一個步驟名稱，或一個步驟名稱加一個聲部編號 |
| `sdsp.VOICE_COUNT`、`sdsp.REGISTER_COUNT` | 8 和 128 |
| `sdsp.ENV_RELEASE`、`sdsp.ENV_ATTACK`、`sdsp.ENV_DECAY`、`sdsp.ENV_SUSTAIN` | 包絡階段，0 至 3，即 `Voice.envelope_mode` 保存的值 |
| `sdsp.COUNTER_RATES` | 包絡和噪音時鐘的 32 個週期，以樣本為單位，每個速率一個 |
| `sdsp.COUNTER_OFFSETS` | 把共用同一週期的速率錯開的 32 個偏移 |
| `sdsp.GAUSSIAN` | 有 512 項的插值核 |
| `sdsp.check_kernel(table)` | 以 tuple 傳回插值核，或引發 `NotAKernel`，並指出不符合的屬性和項目 |
| `sdsp.UnknownModelError` | 型號名稱缺失或未知時引發。訊息列出可接受的名稱 |
| `sdsp.NotAKernel` | 由 `check_kernel` 引發，`gaussian` 不符合時亦由 `Chip` 引發 |
| `sdsp.__version__` | 已安裝的版本 |

```python
import sdsp

print(sdsp.UNSET_SEED, sdsp.scramble(4).hex(), sdsp.scramble(4, seed=1).hex())
print(
    sdsp.Memory(fill=0x55).read8(0x1234),
    sdsp.Memory().read8(0x1234),
    sdsp.SparseMemory().read8(0x1234),
)
held = sdsp.SparseMemory()
held.write8(0x1_0005, 0x1FF)
print(held.read8(5), held.cells)
```

```
1515870810 eb6cefd8 f5b16522
85 145 94
255 {5: 255}
```

```python
import sdsp

print(len(sdsp.GAUSSIAN), sdsp.GAUSSIAN[:4], sdsp.GAUSSIAN[-1])
print(sdsp.COUNTER_RATES[:4], sdsp.COUNTER_RATES[-1], sdsp.COUNTER_OFFSETS[:4])

for broken in (sdsp.GAUSSIAN[:256], (0, 9, 3) + sdsp.GAUSSIAN[3:], [0] * 256 + [2048] * 256):
    try:
        sdsp.Chip("s-dsp", gaussian=broken)
    except sdsp.NotAKernel as error:
        print(error)

own = sdsp.Chip("s-dsp", gaussian=list(sdsp.GAUSSIAN))
print(own.gaussian == sdsp.GAUSSIAN, sdsp.Chip("s-dsp").gaussian is sdsp.GAUSSIAN)
```

```
512 (0, 0, 0, 0) 1305
(30721, 2048, 1536, 1280) 1 (1, 0, 1040, 536)
a kernel is 512 entries, one quarter of the curve; this one has 256
the curve rises from nothing to its peak and never dips; entry 1 is 9 and entry 2 is 3
the four taps of every position sum to 2048; at position 0 they sum to 4096
True True
```

速率 0 的週期為 30,721 個樣本，比計數器 30,720 的範圍更長，所以永不觸發。速率 31 每個樣本觸發一次。

### 命令列工具

| 命令 | 作用 | 結束代碼 |
|:--|:--|:--|
| `python3 sdsp/doctor.py` | 上文所述的機器和簽出副本報告 | 0 正常，1 有檢查失敗 |
| `python3 -m conformance.corpus [file]` | 重播語料庫中的每個案例，並比較輸出摘要 | 0 全部一致，1 有案例不一致，2 路徑上沒有語料庫 |
| `python3 -m conformance.capture <dump directory> <census out> [limit]` | 從你擁有的 `.spc` 傾印中讀出 128 個 DSP 暫存器，並寫出普查 | 0 已寫出，1 找不到傾印，2 參數錯誤或沒有目錄 |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | 把手冊下載到 `docs/` 並驗證其 SHA-256。`--check` 只驗證，不下載 | 0 已驗證，1 被拒絕或不相符 |
| `python3 -m conformance.quotes` | 在手冊中尋找 [`conformance/hardware.json`](conformance/hardware.json) 裏的每一段引文 | 0 每段引文都找到或這部機器上沒有手冊，1 其他情況 |
| `python3 -m conformance.speed` | 量度每秒 `clock()` 呼叫次數，下限為 90,000 | 0 高於下限，1 低於下限 |
| `python3 -m conformance.links` | 探測這份 README 中的每個位址 | 0 每個位址都有效，1 有位址傳回 HTTP 404 或 410 |
| `python3 -m conformance.package <wheel>` | 檢查已建置的 wheel 包含所有模組且不含測試 | 0 正常，1 有錯誤或沒有 wheel，2 沒有參數 |

## 三十二時鐘排程

一個樣本是 32 個時鐘，八個聲部以管線方式分佈在這些時鐘上。在任何一個時鐘，不同聲部執行不同步驟，而回聲單元和 KON、KOFF 鎖存器則在各自固定的時鐘上運行。每個樣本把所有聲部循環一次的模型能算出相同的音符，但在樣本中途讀取暫存器時，傳回的值會出錯。

```python
import sdsp

for clock in (0, 17, 22, 30):
    print(clock, sdsp.PIPELINE[clock])

dsp = sdsp.Chip("s-dsp").reset()
dsp.run(40)
print(dsp.phase, len(dsp.rendered))
print(len(dsp.render(3)), dsp.phase)
```

```
0 [('voice_5', 0), ('voice_2', 1)]
17 [('voice_1', 0), ('voice_7', 5), ('voice_4', 6)]
22 [('voice_3a', 0), ('voice_9', 6), ('voice_6', 7), 'echo_22']
30 ['misc_30', ('voice_3c', 0), 'echo_30']
8 2
6 8
```

在時鐘 17，聲部 0 開始查找目錄，同時聲部 5 寫入 ENDX，聲部 6 解碼並混入左聲道。聲部 0 的第三步分佈在時鐘 22、25 和 30。運行 40 個時鐘後，晶片完成了一個樣本，即一對立體聲值，而 `phase` 為 8。`render(3)` 從該處運行 96 個時鐘，並把 `phase` 留在原來的位置。

[`sdsp/core.py`](sdsp/core.py) 中的 `PIPELINE` 就是完整的表。`clock()` 執行它，順序不由其他任何東西決定。

## 型號

```python
import sdsp

dsp = sdsp.Chip("snesdsp", sdsp.Memory())
print(dsp.model, sdsp.MODELS[dsp.model].voices, sdsp.MODELS[dsp.model])
print(sdsp.Chip("sdsp").model, sdsp.Chip("sonysdsp").model, sdsp.Chip("dsp").model)
```

```
s-dsp 8 <Model s-dsp, 8 voices>
s-dsp s-dsp s-dsp
```

只有一個型號。S-DSP 與 SPC700 一同位於 S-SMP 音訊單元內，從未單獨出售，所以沒有已知的修訂版可供建模。透過別名取得的晶片使用標準名稱。

## 是否正確

| 項目 | 依據 | 證據類型 |
|:--|:--|:--|
| 暫存器映射 | Nintendo 的表 3-7-1，涵蓋這個型號指定的每個位址 | 製造商 |
| 速率表 | 表 3-7-4，噪音時鐘，全部 32 行 | 製造商 |
| 起音時間 | 表 3-7-2，全部 16 行 | 製造商 |
| 衰減和延音時間 | 表 3-7-2，全部 39 行，對照手冊沒有印出的一個終點 | 製造商，相對 |
| 整個晶片的輸出 | 240 個案例，23,040 個樣本，對照 `snes_spc 0.9.0` | 第二個實現 |
| 主機檢查 | Shay Green 的 `spc_dsp6` 卡帶中 104 個判定有 97 個一致 | 在主機上取得的值 |
| 插值核 | 長度、形狀和四個抽頭之和 | 只有自我檢查，沒有實物 |

[`conformance/hardware.json`](conformance/hardware.json) 記錄手冊中的每個數字及其頁碼，[`conformance/hardware.test.py`](conformance/hardware.test.py) 把它們與驅動晶片時的實際行為及套件匯出的表比較。手冊的文字層到了圖表就中斷，所以每個表都是從渲染出的頁面圖像讀出的。`python3 -m conformance.quotes` 在手冊中找到 28 段引文。

### 噪音時鐘確定速率表

表 3-7-4 為 32 個噪音時鐘值各印出一個頻率。每個頻率都是 32,000 除以 `COUNTER_RATES` 的一項，所以這個表逐項確定。全部 32 項的誤差都在 3% 或 0.5 Hz 以內，取兩者中較大者。起音一欄以第二種方式確定同一個表：一次起音是 64 步，所以最慢的速率需時 4.096 秒，而印出的 16 個時間全部一致。

### 手冊略去的終點

衰減和延音兩欄只給出時間，沒有給出下降所量度到的電平。把印出的 39 個時間各自除以這個模型在該速率下的週期，得出 576 至 600 個節拍，差距不到 5%。推算出的終點約為 590 個節拍，記錄在 [`conformance/divergences.json`](conformance/divergences.json) 中，沒有內建到模型。

### 插值核

插值核位於晶片內部，從未被傾印，以印刷表格的形式流傳，所以沒有檔案可計算摘要。[`conformance/carried.json`](conformance/carried.json) 以 SHA-256 固定套件所帶的值，這能偵測到修改，但不能說明這個表是否就是晶片內的那個。

`check_kernel` 以插值器的需要來檢查提供的表：

| 屬性 | 晶片為何需要它 |
|:--|:--|
| 512 項 | 插值器的索引最高到 `forward + 256` |
| 每個抽頭都是有號 16 位元字 | 乘法是有號 16 位元乘法 |
| 從 0 上升且從不回落 | 回落會令曲線反轉 |
| 每個位置的四個抽頭之和為 2048，誤差在 0.2% 以內 | 否則聲部的音量會取決於它落在兩個樣本之間的哪個位置 |

兩個不同的表都可以通過，所以通過只表示這個表有可能是晶片內的那個。插值核保存在每個晶片上，所以同一個程序中的兩個晶片可以帶不同的表。

### 音訊的來源

Shay Green 的 `snes_spc 0.9.0`，即 snes9x 在 `apu/bapu/dsp/SPC_DSP.cpp` 所帶的版本，決定手冊沒有涵蓋的一切，也就是音訊本身。與它一致，就是與那個程式一致，[`conformance/divergences.json`](conformance/divergences.json) 把這一點列為第一項，嚴重程度為高。`spc_dsp6` 卡帶出自同一作者，所以兩者是一個來源，而不是兩個。

這個卡帶帶有檢查，其預期值是在主機上取得的。透過 [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python) 中的音訊單元驅動，其中 104 項在這裏得出判定，97 項一致，7 項不一致。[`conformance/cartridge.json`](conformance/cartridge.json) 保存每個判定，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 按原因把那 7 項分組。

### 語料庫

一個 SPC 傾印包含 64 KB 音訊 RAM，即音樂本身，以及 128 個 DSP 暫存器，即驅動程式設定晶片的方式。[`conformance/capture.py`](conformance/capture.py) 只讀取暫存器，並略過 RAM。

[`conformance/corpus.json`](conformance/corpus.json) 分三步建立：

1. 來自真實傾印的 240 個暫存器狀態，涵蓋 70 個樣本目錄頁、11 種回聲延遲和 1,402 個使用 ADSR 包絡的聲部。
2. 以每個案例一個種子產生的樣本數據，放在各狀態的目錄和音源編號所指的位置。
3. 每個案例由 [`conformance/ref/`](conformance/ref) 中的參考驅動程式渲染 96 個樣本，並以輸出的 SHA-256 儲存。

`python3 -m conformance.corpus` 重播全部 240 個案例，最後輸出 `240 agreed, 0 did not`。

要讀取你自己的收藏，`python3 -m conformance.capture /path/to/spc/collection census.json 500` 會為它找到的頭 500 個傾印寫出普查。普查以及由它建立的任何東西都留在你的機器上。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出尚未解決的問題，每項都附有可以解決它的量度。

## 參與開發

| 需要 | 位置 |
|:--|:--|
| 所有關卡檢查及其運行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 給編程代理的同一份資料 | [AGENTS.md](AGENTS.md) |
| 這個儲存庫與同系列其他儲存庫共用的標準 | [FAMILY.md](FAMILY.md) |
| 錯誤報告 | [GitHub Issues](https://github.com/gufranco/sony-s-dsp-python/issues) |
| 安全報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 sdsp/core.test.py
```

每個模組旁邊都有一個以它命名的測試檔案，每個都可以如上所示單獨運行。覆蓋率是一道硬性關卡檢查，要求 100% 語句和分支覆蓋率。修改 `PIPELINE` 或任何改變輸出的東西，除了單元測試之外，還需要運行 `python3 -m conformance.corpus`。

## 參考資料

- *SNES Development Manual, Book I*，第 3 節，Nintendo of America Inc.，未註明日期。240 頁，21,022,582 位元組，SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。它不可轉發，也不在這個儲存庫中。`python3 -m conformance.documents` 從 https://archive.org/download/SNESDevManual/book1_text.pdf 把它下載到 `docs/`，並拒絕任何其他檔案。Sony 沒有為這個晶片發佈數據手冊。
- Shay Green 的 `snes_spc 0.9.0`，即 snes9x 1.63 在 `apu/bapu/dsp/SPC_DSP.cpp` 所帶的版本，用於語料庫的音訊。[`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) 從 snes9x 的 `1.63` 標籤建置它；儲存庫中沒有附帶副本。
- Shay Green 的 `spc_dsp6` 測試卡帶，用於 [`conformance/cartridge.json`](conformance/cartridge.json) 中的 104 個主機判定。

## 引用

[CITATION.cff](CITATION.cff) 在每次發佈時由加蓋套件版本的腳本更新。

## 授權

MIT。見 [LICENSE](LICENSE)。

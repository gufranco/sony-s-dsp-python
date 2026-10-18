# S-DSP

Sony S-DSPサウンドジェネレータのPython実装です。実チップと同じ32クロックのスケジュールで動作し、NintendoのSNES Development Manualにあるレジスタマップとパラメータ表に照らして検証しています。

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-s-dsp-python)](https://github.com/gufranco/sony-s-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

実際の音楽ダンプから取った**240**個のレジスタ状態を**23,040**サンプル分再生し、`snes_spc 0.9.0`に対する不一致は**0**件、コンソール上で取得したチェック**104**件のうち**97**件が一致、マニュアル内で所在を確認した引用が**28**件、テストが**823**件、ステートメントとブランチのカバレッジが**100%**、依存関係はありません。

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

ページ`$02`のサンプルディレクトリは、ソース0を`$0300`にある1つのBRRブロックに向けています。そのヘッダ`$B3`はシフト11、フィルタ0、エンドフラグとループフラグを設定するので、ブロックは1つの値を繰り返します。ボイス0はこれをピッチ`$1000`で再生します。これは入力1サンプルにつき出力1サンプルで、ADSRは有効、アタックレートはFです。`FLG`は`$20`で、リセットビットとミュートビットをクリアし、エコー書き込みはオフのままにします。この例は16サンプル分の左チャンネルを表示します。最初の8サンプルが無音なのは、KONが1サンプルおきに読み取られ、キーオンされたボイスはその後デコードを始めるまで5サンプル待つからです。アタックレートFは1ステップごとに`$400`を加えるので、エンベロープはサンプル8で半分、サンプル9で最大に達します。ブロックがエンドフラグを持っていたので、ENDXのビット0がセットされます。

## インストール

| 要件 | バージョン |
|:--|:--|
| Python | 3.12以降 |
| git | 任意 |
| Docker | [`conformance/ref/Dockerfile`](conformance/ref/Dockerfile)からリファレンスドライバを再ビルドする場合のみ |

```bash
git clone https://github.com/gufranco/sony-s-dsp-python.git
cd sony-s-dsp-python
python3 sdsp/doctor.py
```

このパッケージは標準ライブラリ以外を何もインポートしません。[`conformance/corpus.json`](conformance/corpus.json)はリポジトリで管理されているので、新しくチェックアウトした直後からコーパスを実行できます。

ドクターはマシンとチェックアウトを確認し、チップを構築し、未書き込みのアドレスを1つ読み、コーパスのダイジェストを取り、1行で終わります。すべてのチェックが通れば0で、そうでなければ1で終了します。バグ報告には出力全体を貼り付けてください。

```
  7 checks, nothing to report
```

インストール済みのコピーでは、同じレポートを`sdsp-doctor`で得られます。

リリースは[Semantic Versioning](https://semver.org/)に従い、semantic-releaseがコミット履歴から作成します。各リリースにはタグが付き、[リリースページ](https://github.com/gufranco/sony-s-dsp-python/releases)に掲載されます。

## インターフェース

`sdsp.Chip(model, memory=None, seed=UNSET_SEED, gaussian=None)`はチップを1つ構築します。`model`は必須です。`memory`は`read8(address)`と`write8(address, value)`を持つ任意のオブジェクトで、省略するとチップが`SparseMemory`を構築します。`seed`はすべてのレジスタ、カウンタ、ラッチ、デコード済みサンプルと位置の電源投入時のパターンを設定し、チップは呼び出し側が`reset()`を呼ぶまでそのパターンを保持します。ノイズジェネレータが0として引かれることはありません。0はそのフィードバックが抜け出せない唯一の値です。コンストラクタが`reset()`を呼ぶことはなく、呼ばせるオプションもありません。`gaussian`は補間カーネルを独自のテーブルに置き換え、そのテーブルは`check_kernel`で検査されます。

| モデル | 別名 | ボイス数 | レジスタ数 |
|:--|:--|:--|:--|
| `s-dsp` | `sdsp`, `sonysdsp`, `dsp`, `snesdsp` | 8 | 128 |

名前は大文字小文字、ハイフン、アンダースコアを無視して照合されるので、`SNES-DSP`で`s-dsp`が構築されます。

### 呼び出し

| 呼び出し | 効果 |
|:--|:--|
| `read(address)` | `address & $7F`のレジスタを返します |
| `write(address, value)` | `value & $FF`を`address & $7F`に格納します。KONへの書き込みは次のKONサンプルまでラッチされます。ENDXへの書き込みはENDXを0にクリアします |
| `reset()` | コーパスを記録した実装である`snes_spc`でのリセットラインの動作です。すべてのレジスタとすべてのラッチをクリアし、`FLG`を`$E0`に、ノイズジェネレータを`$4000`に、1サンプルおきのトグルを1に設定し、8つのボイスすべてを無音にします。チップを返します |
| `clock()` | 現在のクロックについて`PIPELINE`が指定するステップを実行し、32クロックのうち次のクロックに進みます |
| `run(clocks)` | `clock()`をその回数だけ実行します |
| `render(samples)` | `samples`の32倍のクロックを実行し、出力を左右の値を交互に並べて、1サンプルにつき2つ返します |
| `voice_1`から`voice_9`、`voice_3a`、`voice_3b`、`voice_3c`、`misc_27`から`misc_30`、`echo_22`から`echo_30` | `PIPELINE`が指定するステップです。`clock()`がこれらを呼び出すので、呼び出し側が呼ぶ必要はありません |

### 状態

| 属性 | 意味 |
|:--|:--|
| `model` | 正規のモデル名 |
| `memory` | ボイスとエコーバッファが読み書きする64 KBのオーディオRAMオブジェクト |
| `registers` | `bytearray`としての128個のレジスタ |
| `voices` | 8つの`Voice`オブジェクト |
| `phase` | 32クロックのうち次に実行されるクロック、0から31 |
| `rendered` | 最後の`render`以降に生成された出力値 |
| `gaussian` | このチップがリサンプリングに使うカーネル |

`Voice`は`index`、`bit`、`base`を持ちます。BRRの状態は`brr_address`、`brr_offset`、`buffer`、`buffer_position`に、ピッチ位置は`interpolation`に、エンベロープは`envelope`、`hidden_envelope`、`envelope_mode`、`envelope_out`に保持し、ほかに`key_on_delay`を持ちます。

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

リセット前のレジスタはスクランブルされたパターンを保持しており、アドレス`$EC`は`$6C`と同じレジスタを読みます。リセット後は`FLG`が`$E0`を保持します。ENDXへの書き込みはENDXをクリアし、1バイトより広い値は下位8ビットが残ります。ボイス3のレジスタは`$30`から始まります。

### モジュールの内容

| 名前 | 内容 |
|:--|:--|
| `sdsp.MODELS` | 正規名をキーとする`Model`レコード |
| `sdsp.Model` | モデルレコードです。`name`、`summary`、`voices`、`registers`、`aliases`、`build(memory, **options)`を持ちます |
| `sdsp.Memory(size=0x10000, fill=None, seed=UNSET_SEED)` | フラットなオーディオRAMです。`fill`はバイト値またはバイト列で、指定しない場合は内容が`seed`からスクランブルされます。アドレスは16ビットで折り返します |
| `sdsp.SparseMemory(seed=UNSET_SEED)` | 同じ契約で、メモリを確保しません。未書き込みのアドレスはアドレスと`seed`から混ぜたバイトを返し、書き込まれた内容は`cells`が保持します |
| `sdsp.scramble(size, seed=UNSET_SEED)` | `Memory`とレジスタファイルが起動時に保持するスクランブルされたバイト |
| `sdsp.UNSET_SEED` | デフォルトのシード、`0x5A5A5A5A` |
| `sdsp.Voice` | 1つのボイスとその状態 |
| `sdsp.PIPELINE` | スケジュールです。32クロックそれぞれについて実行されるステップを持ち、各ステップはステップ名、またはステップ名とボイス番号です |
| `sdsp.VOICE_COUNT`, `sdsp.REGISTER_COUNT` | 8と128 |
| `sdsp.ENV_RELEASE`, `sdsp.ENV_ATTACK`, `sdsp.ENV_DECAY`, `sdsp.ENV_SUSTAIN` | エンベロープのフェーズで、`Voice.envelope_mode`が保持する形の0から3 |
| `sdsp.COUNTER_RATES` | エンベロープクロックとノイズクロックの32個の周期で、サンプル単位、レートごとに1つ |
| `sdsp.COUNTER_OFFSETS` | 周期を共有するレートをずらす32個のオフセット |
| `sdsp.GAUSSIAN` | 512エントリの補間カーネル |
| `sdsp.check_kernel(table)` | カーネルをタプルとして返すか、失敗した性質とエントリを示す`NotAKernel`を送出します |
| `sdsp.UnknownModelError` | モデル名がない場合や未知の場合に送出されます。メッセージには受け付ける名前が列挙されます |
| `sdsp.NotAKernel` | `check_kernel`が送出し、`gaussian`がその検査に失敗したときは`Chip`も送出します |
| `sdsp.__version__` | インストールされているバージョン |

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

レート0の周期は30,721サンプルで、カウンタの範囲である30,720より長いので、発火することはありません。レート31は毎サンプル発火します。

### コマンドラインツール

| コマンド | 動作 | 終了コード |
|:--|:--|:--|
| `python3 sdsp/doctor.py` | 上記のマシンとチェックアウトのレポート | 0は問題なし、1はチェックの失敗 |
| `python3 -m conformance.corpus [file]` | コーパスの全ケースを再生し、出力のダイジェストを比較します | 0はすべて一致、1は不一致のケースあり、2はそのパスにコーパスなし |
| `python3 -m conformance.capture <dump directory> <census out> [limit]` | 手元にある`.spc`ダンプから128個のDSPレジスタを読み取り、全数調査を書き出します | 0は書き出し完了、1はダンプが見つからない、2は引数の誤りまたはディレクトリなし |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]` | マニュアルを`docs/`に取得し、そのSHA-256を検証します。`--check`は取得せずに検証します | 0は検証済み、1は拒否または一致なし |
| `python3 -m conformance.quotes` | [`conformance/hardware.json`](conformance/hardware.json)にある引用文をすべてマニュアル内で探します | 0はすべての引用の所在を確認したか、このマシンにマニュアルがない、1はそれ以外 |
| `python3 -m conformance.speed` | 1秒あたりの`clock()`呼び出し回数を、下限90,000に対して計測します | 0は下限以上、1は下限未満 |
| `python3 -m conformance.links` | このREADMEのすべてのアドレスを調べます | 0はすべてのアドレスが有効、1はHTTP 404または410を返すアドレスあり |
| `python3 -m conformance.package <wheel>` | ビルドしたwheelがすべてのモジュールを含み、テストを含まないことを確認します | 0は問題なし、1は不備ありまたはwheelなし、2は引数なし |

## 32クロックのスケジュール

1サンプルは32クロックで、8つのボイスはその間にパイプライン化されています。どのクロックでも、ボイスごとに異なるステップが実行され、エコーユニットとKONおよびKOFFのラッチはそれぞれ専用の固定クロックで動作します。1サンプルにつき一度ボイスをループするモデルは、同じ音を計算しますが、サンプルの途中でレジスタを読んだときに返る値を誤ります。

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

クロック17では、ボイス0がディレクトリの参照を始め、同時にボイス5がENDXに書き込み、ボイス6がデコードして左チャンネルにミックスします。ボイス0の3番目のステップは、クロック22、25、30に分かれています。40クロック後、チップは1サンプル、つまりステレオの1ペアを完了しており、`phase`は8です。`render(3)`はそこから96クロックを実行し、`phase`を元の位置のままにします。

[`sdsp/core.py`](sdsp/core.py)の`PIPELINE`がテーブル全体です。`clock()`はこれを実行し、順序を決めるものはほかにありません。

## モデル

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

モデルは1つです。S-DSPはS-SMPオーディオユニットの中でSPC700の隣に置かれ、単体で販売されたことはないので、モデル化できる既知のリビジョンはありません。別名で得たチップは正規名を持ちます。

## 正しいか

| 対象 | 照合先 | 根拠の種類 |
|:--|:--|:--|
| レジスタマップ | Nintendoの表3-7-1、このモデルが名前を付けるすべてのアドレス | メーカー |
| レート表 | 表3-7-4のノイズクロック、全32行 | メーカー |
| アタック時間 | 表3-7-2、全16行 | メーカー |
| ディケイ時間とサステイン時間 | 表3-7-2、全39行、マニュアルに記載のない終点1つに対して | メーカー、相対値 |
| チップ全体の出力 | 240ケース、23,040サンプル、`snes_spc 0.9.0`に対して | 別の実装 |
| コンソールでのチェック | Shay Greenの`spc_dsp6`カートリッジの判定104件のうち97件が一致 | コンソール上で取得した値 |
| 補間カーネル | 長さ、形状、4タップの合計 | 自己チェックのみ、成果物なし |

[`conformance/hardware.json`](conformance/hardware.json)はマニュアルの各数値をそのページとともに保持し、[`conformance/hardware.test.py`](conformance/hardware.test.py)はそれらを、駆動したパートの動作とパッケージが公開する表に照らして確認します。マニュアルのテキストレイヤーは図表の手前で途切れているので、すべての表はレンダリングしたページ画像から読み取りました。`python3 -m conformance.quotes`はマニュアル内で28個の引用文の所在を確認します。

### ノイズクロックがレート表を固定する

表3-7-4は、32個のノイズクロック値それぞれの周波数を記載しています。各値は32,000を`COUNTER_RATES`の1エントリで割ったものなので、表はエントリごとに固定されます。32個すべてが、3パーセントと0.5 Hzのうち大きい方の範囲内で一致します。アタックの列は同じ表を別の方法で固定します。アタックは64ステップなので、最も遅いレートでは4.096秒かかり、記載された16個の時間はすべて一致します。

### マニュアルが省いている終点

ディケイとサステインの列は、減衰をどのレベルまで測ったかを示さずに時間を記載しています。記載された39個の時間それぞれを、そのレートに対するこのモデルの周期で割ると、576から600ティックになり、ばらつきは5パーセント未満です。復元した約590ティックの終点は[`conformance/divergences.json`](conformance/divergences.json)に記録してあり、モデルには組み込んでいません。

### 補間カーネル

カーネルはダイ上にあり、ダンプされたことがなく、印刷された表として出回っているので、ダイジェストを取るファイルがありません。[`conformance/carried.json`](conformance/carried.json)はパッケージが持つ値をSHA-256で固定しています。これは編集を検出しますが、その表がチップのものかどうかについては何も示しません。

`check_kernel`は、与えられた表を補間器が必要とする条件に照らして検査します。

| 性質 | チップがそれを必要とする理由 |
|:--|:--|
| 512エントリ | 補間器は`forward + 256`までインデックスします |
| すべてのタップが符号付き16ビットワード | 乗算が符号付き16ビットです |
| 0から上昇し、決して下がらない | 下がるとカーブが反転します |
| 各位置の4タップの合計が2048で、誤差0.2パーセント以内 | そうでないと、ボイスの音量が2つのサンプルの間のどこに位置するかに左右されます |

異なる2つの表が通ることもあるので、通ったということは、その表がチップのものでありうるという意味です。カーネルはチップごとに保持されるので、1つのプロセス内の2つのチップが異なる表を持つことができます。

### オーディオの出どころ

Shay Greenによる`snes_spc 0.9.0`は、snes9xが`apu/bapu/dsp/SPC_DSP.cpp`に収録しているもので、マニュアルが及ばないすべて、つまりオーディオそのものを決めています。これとの一致はそのプログラムとの一致であり、[`conformance/divergences.json`](conformance/divergences.json)はそのことを最初のエントリとして、重大度highで記録しています。`spc_dsp6`カートリッジも同じ作者によるものなので、この2つは2つではなく1つの情報源です。

カートリッジは、コンソール上で取得した期待値を持つチェックを収録しています。[sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python)のオーディオユニットを通して駆動すると、そのうち104件がここで判定に至り、97件が一致し、7件が一致しません。[`conformance/cartridge.json`](conformance/cartridge.json)がすべての判定を保持し、[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)が7件を原因別にまとめています。

### コーパス

SPCダンプは、音楽そのものである64 KBのオーディオRAMと、ドライバがチップをどう設定したかを示す128個のDSPレジスタを保持しています。[`conformance/capture.py`](conformance/capture.py)はレジスタだけを読み、RAMは読み飛ばします。

[`conformance/corpus.json`](conformance/corpus.json)は3つのステップで構築されます。

1. 実際のダンプから取った240個のレジスタ状態です。70個のサンプルディレクトリページ、11種類のエコー遅延、ADSRエンベロープを使う1,402個のボイスを含みます。
2. ケースごとのシードから生成したサンプルデータです。各状態のディレクトリ番号とソース番号が指す位置に配置します。
3. [`conformance/ref/`](conformance/ref)のリファレンスドライバがケースごとにレンダリングした96サンプルです。出力のSHA-256として保存します。

`python3 -m conformance.corpus`は240件すべてを再生し、`240 agreed, 0 did not`で終わります。

手元のコレクションを読むには、`python3 -m conformance.capture /path/to/spc/collection census.json 500`を実行します。見つかった最初の500個のダンプについて全数調査を書き出します。全数調査とそこから作ったものはすべて、あなたのマシンの中にとどまります。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md)は未解決の事項を、それを解決する計測とともに列挙しています。

## 開発

| 必要なもの | 場所 |
|:--|:--|
| すべてのゲートと実行順序 | [CONTRIBUTING.md](CONTRIBUTING.md) |
| コーディングエージェント向けの同じ内容 | [AGENTS.md](AGENTS.md) |
| このリポジトリがファミリーのほかのリポジトリと共有する標準 | [FAMILY.md](FAMILY.md) |
| バグ報告 | [GitHub Issues](https://github.com/gufranco/sony-s-dsp-python/issues) |
| セキュリティ報告 | [SECURITY.md](SECURITY.md) |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 sdsp/core.test.py
```

各モジュールの隣には、そのモジュールにちなんだ名前のテストファイルがあり、上記のようにそれぞれ単独で実行できます。カバレッジはステートメントとブランチの100%を必須とするゲートです。`PIPELINE`への変更や出力を変える変更には、ユニットテストに加えて`python3 -m conformance.corpus`も必要です。

## 参考文献

- *SNES Development Manual, Book I*, Section 3, Nintendo of America Inc., 日付なし。240ページ、21,022,582バイト、SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。再配布はできず、このリポジトリには含まれていません。`python3 -m conformance.documents`がこれを https://archive.org/download/SNESDevManual/book1_text.pdf から`docs/`にダウンロードし、それ以外のファイルは拒否します。Sonyはこのチップのデータシートを公開していません。
- Shay Greenによる`snes_spc 0.9.0`です。snes9x 1.63が`apu/bapu/dsp/SPC_DSP.cpp`に収録している形のもので、コーパスのオーディオに使います。[`conformance/ref/Dockerfile`](conformance/ref/Dockerfile)がsnes9xの`1.63`タグからビルドし、コピーは同梱していません。
- Shay Greenの`spc_dsp6`テストカートリッジです。[`conformance/cartridge.json`](conformance/cartridge.json)にある104件のコンソール判定に使います。

## 引用

[CITATION.cff](CITATION.cff)は、パッケージのバージョンを刻むスクリプトによってリリースごとに更新されます。

## ライセンス

MITです。[LICENSE](LICENSE)を参照してください。

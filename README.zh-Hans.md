# S-DSP

用 Python 实现的 Sony S-DSP 声音发生器，按照芯片本身的三十二时钟调度运行，并以 Nintendo《SNES Development Manual》中的寄存器映射和参数表为准。

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sony-s-dsp-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sony-s-dsp-python)](https://github.com/gufranco/sony-s-dsp-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

来自真实音乐转储的 **240** 个寄存器状态重放 **23,040** 个采样，与 `snes_spc 0.9.0` 对比 **0** 处不一致，在主机上取得的 **104** 项检查全部一致，在手册中定位到 **28** 处引文，**832** 个测试，**100%** 语句与分支覆盖率，无依赖

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

位于页 `$02` 的采样目录把音源 0 指向 `$0300` 处的一个 BRR 块。块头 `$B3` 设定移位 11、滤波器 0，以及结束和循环标志，因此该块重复同一个值。声部 0 以音高 `$1000` 播放它，即每输入一个采样输出一个采样，同时开启 ADSR，起音速率为 F。`FLG` 为 `$20`，这会清除复位位和静音位，并保持回声写入关闭。示例打印 16 个采样的左声道。前 8 个是静音，因为 KON 每隔一个采样读取一次，被按下的声部随后还要等待 5 个采样才开始解码。起音速率 F 每步增加 `$400`，所以包络在第 8 个采样达到一半，在第 9 个采样达到满值。ENDX 的位 0 被置位，因为该块带有结束标志。

## 安装

| 要求   | 版本                                                                                     |
| :----- | :--------------------------------------------------------------------------------------- |
| Python | 3.12 或更高                                                                              |
| git    | 任意                                                                                     |
| Docker | 仅在从 [`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) 重新构建参考驱动时需要 |

```bash
git clone https://github.com/gufranco/sony-s-dsp-python.git
cd sony-s-dsp-python
python3 sdsp/doctor.py
```

本包只导入标准库中的内容。[`conformance/corpus.json`](conformance/corpus.json) 已纳入版本控制，因此全新检出即可运行语料库。

诊断脚本检查机器和检出副本，构建芯片，读取一个未写入的地址，计算语料库的摘要，最后输出一行结果。所有检查通过时退出码为 0，否则为 1。提交缺陷报告时，请粘贴它的完整输出。

```
  7 checks, nothing to report
```

安装后的副本通过 `sdsp-doctor` 提供同样的报告。

版本发布遵循 [Semantic Versioning](https://semver.org/)，由 semantic-release 根据提交历史生成。每个版本都打了标签，并列在[发布页面](https://github.com/gufranco/sony-s-dsp-python/releases)上。

## 接口

`sdsp.Chip(model, memory=None, seed=UNSET_SEED, gaussian=None)` 构建一个芯片。`model` 为必填。`memory` 可以是任何具有 `read8(address)` 和 `write8(address, value)` 的对象，省略时芯片会构建一个 `SparseMemory`。`seed` 设定每个寄存器、计数器、锁存器、已解码样本和位置的上电图案，芯片会一直保持该图案，直到调用方调用 `reset()`。噪声发生器永远不会取到 0，这是其反馈无法离开的唯一值。构造函数从不调用 `reset()`，也没有任何选项让它调用。`gaussian` 用你自己的表替换插值核，并由 `check_kernel` 检查。

| 型号    | 别名                                 | 声部 | 寄存器 |
| :------ | :----------------------------------- | :--- | :----- |
| `s-dsp` | `sdsp`, `sonysdsp`, `dsp`, `snesdsp` | 8    | 128    |

名称匹配时忽略大小写、连字符和下划线，因此 `SNES-DSP` 构建的是 `s-dsp`。

### 调用

| 调用                                                                                                       | 作用                                                                                                                                                                            |
| :--------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `read(address)`                                                                                            | 返回 `address & $7F` 处的寄存器                                                                                                                                                 |
| `write(address, value)`                                                                                    | 把 `value & $FF` 存入 `address & $7F`。写入 KON 的值会被锁存，等待下一个 KON 采样。写入 ENDX 会将其清零                                                                         |
| `reset()`                                                                                                  | 复位线在录制语料库所用的实现 `snes_spc` 中的作用：清除所有寄存器和所有锁存器，把 `FLG` 设为 `$E0`、噪声发生器设为 `$4000`、隔样本切换位设为 1，并让全部八个声部静音。返回该芯片 |
| `clock()`                                                                                                  | 运行 `PIPELINE` 为当前时钟指定的步骤，并移到 32 个时钟中的下一个                                                                                                                |
| `run(clocks)`                                                                                              | 执行该次数的 `clock()`                                                                                                                                                          |
| `render(samples)`                                                                                          | 运行 `samples` 乘以 32 个时钟，并以左右值交错的形式返回输出，每个采样两个值                                                                                                     |
| `voice_1` 到 `voice_9`、`voice_3a`、`voice_3b`、`voice_3c`、`misc_27` 到 `misc_30`、`echo_22` 到 `echo_30` | `PIPELINE` 指定的步骤。由 `clock()` 调用它们，调用方无需调用                                                                                                                    |

### 状态

| 属性        | 含义                                        |
| :---------- | :------------------------------------------ |
| `model`     | 规范型号名称                                |
| `memory`    | 声部和回声缓冲区读写的 64 KB 音频 RAM 对象  |
| `registers` | 以 `bytearray` 表示的 128 个寄存器          |
| `voices`    | 八个 `Voice` 对象                           |
| `phase`     | 下一个运行的是 32 个时钟中的哪一个，0 到 31 |
| `rendered`  | 自上次 `render` 以来产生的输出值            |
| `gaussian`  | 该芯片重采样所用的核                        |

一个 `Voice` 保存 `index`、`bit`、`base`，`brr_address`、`brr_offset`、`buffer` 和 `buffer_position` 中的 BRR 状态，`interpolation` 中的音高位置，`envelope`、`hidden_envelope`、`envelope_mode` 和 `envelope_out` 中的包络，以及 `key_on_delay`。

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

复位前，寄存器保存的是打乱后的图案，地址 `$EC` 读到的寄存器与 `$6C` 相同。复位后 `FLG` 为 `$E0`。写入 ENDX 会将其清零，宽于一个字节的值只保留低 8 位。声部 3 的寄存器从 `$30` 开始。

### 模块内容

| 名称                                                                        | 内容                                                                                              |
| :-------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------ |
| `sdsp.MODELS`                                                               | 以规范名称为键的 `Model` 记录                                                                     |
| `sdsp.Model`                                                                | 一条型号记录：`name`、`summary`、`voices`、`registers`、`aliases` 以及 `build(memory, **options)` |
| `sdsp.Memory(size=0x10000, fill=None, seed=UNSET_SEED)`                     | 平坦的音频 RAM。`fill` 是一个字节值或字节串，省略时内容由 `seed` 打乱生成。地址在 16 位处回绕     |
| `sdsp.SparseMemory(seed=UNSET_SEED)`                                        | 契约相同，但不分配内存。未写入的地址返回由地址和 `seed` 混合得到的字节，`cells` 保存已写入的内容  |
| `sdsp.scramble(size, seed=UNSET_SEED)`                                      | `Memory` 和寄存器文件上电时持有的打乱字节                                                         |
| `sdsp.UNSET_SEED`                                                           | 默认种子，`0x5A5A5A5A`                                                                            |
| `sdsp.Voice`                                                                | 一个声部及其状态                                                                                  |
| `sdsp.PIPELINE`                                                             | 调度表：对 32 个时钟中的每一个，列出运行的步骤，每项是一个步骤名，或一个步骤名加一个声部编号      |
| `sdsp.VOICE_COUNT`, `sdsp.REGISTER_COUNT`                                   | 8 和 128                                                                                          |
| `sdsp.ENV_RELEASE`, `sdsp.ENV_ATTACK`, `sdsp.ENV_DECAY`, `sdsp.ENV_SUSTAIN` | 包络阶段，0 到 3，即 `Voice.envelope_mode` 所保存的值                                             |
| `sdsp.COUNTER_RATES`                                                        | 包络时钟和噪声时钟的 32 个周期，以采样为单位，每个速率一个                                        |
| `sdsp.COUNTER_OFFSETS`                                                      | 让周期相同的速率彼此错开的 32 个偏移                                                              |
| `sdsp.GAUSSIAN`                                                             | 512 项插值核                                                                                      |
| `sdsp.check_kernel(table)`                                                  | 以元组形式返回核，或抛出 `NotAKernel`，指明未通过的属性和表项                                     |
| `sdsp.UnknownModelError`                                                    | 型号名称缺失或未知时抛出。消息列出可接受的名称                                                    |
| `sdsp.NotAKernel`                                                           | 由 `check_kernel` 抛出；当 `gaussian` 未通过检查时，也由 `Chip` 抛出                              |
| `sdsp.__version__`                                                          | 已安装的版本                                                                                      |

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

速率 0 的周期为 30,721 个采样，比计数器的范围 30,720 更长，因此永远不会触发。速率 31 每个采样都触发。

### 命令行工具

| 命令                                                                   | 作用                                                                                 | 退出码                                           |
| :--------------------------------------------------------------------- | :----------------------------------------------------------------------------------- | :----------------------------------------------- |
| `python3 sdsp/doctor.py`                                               | 上文所述的机器和检出副本报告                                                         | 0 无问题，1 有检查未通过                         |
| `python3 -m conformance.corpus [file]`                                 | 重放语料库中的每个用例并比较输出摘要                                                 | 0 全部一致，1 有用例不一致，2 该路径下没有语料库 |
| `python3 -m conformance.capture <dump directory> <census out> [limit]` | 从你拥有的 `.spc` 转储中读出 128 个 DSP 寄存器并写出普查                             | 0 已写出，1 未找到转储，2 参数错误或目录不存在   |
| `python3 -m conformance.documents [--check] [--only SUBSTRING]`        | 把手册下载到 `docs/` 并校验其 SHA-256。`--check` 只校验不下载                        | 0 校验通过，1 被拒绝或不匹配                     |
| `python3 -m conformance.quotes`                                        | 在手册中查找 [`conformance/hardware.json`](conformance/hardware.json) 里的每个引用句 | 0 每条引文都已定位或本机没有手册，否则为 1       |
| `python3 -m conformance.speed`                                         | 测量每秒 `clock()` 调用次数，下限为 90,000                                           | 0 高于下限，1 低于下限                           |
| `python3 -m conformance.links`                                         | 探测本 README 中的每个地址                                                           | 0 所有地址都可访问，1 有地址返回 HTTP 404 或 410 |
| `python3 -m conformance.package <wheel>`                               | 检查构建出的 wheel 包含每个模块且不含测试                                            | 0 无问题，1 有故障或没有 wheel，2 未给参数       |

## 三十二时钟调度

一个采样为 32 个时钟，八个声部以流水线方式分布在这些时钟上。在任意一个时钟，不同声部运行不同的步骤，回声单元以及 KON 和 KOFF 锁存器则在各自固定的时钟上运行。每个采样只遍历一次声部的模型能算出相同的音符，但在采样中途读取寄存器时，会得到错误的值。

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

在时钟 17，声部 0 开始查找目录，同时声部 5 写入 ENDX，声部 6 解码并混入左声道。声部 0 的第三步被拆分到时钟 22、25 和 30 上。运行 40 个时钟后，芯片完成了一个采样，即一对立体声值，此时 `phase` 为 8。`render(3)` 从这里运行 96 个时钟，结束时 `phase` 保持原值。

[`sdsp/core.py`](sdsp/core.py) 中的 `PIPELINE` 就是整张表。`clock()` 运行它，顺序不由其他任何东西决定。

## 型号

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

只有一个型号。S-DSP 位于 S-SMP 音频单元内部，与 SPC700 并列，从未单独出售，因此没有已知的修订版可供建模。通过别名得到的芯片使用规范名称。

## 它是否正确

| 内容           | 依据                                               | 证据类型           |
| :------------- | :------------------------------------------------- | :----------------- |
| 寄存器映射     | Nintendo 的表 3-7-1，本型号命名的每个地址          | 制造商             |
| 速率表         | 表 3-7-4，噪声时钟，全部 32 行                     | 制造商             |
| 起音时间       | 表 3-7-2，全部 16 行                               | 制造商             |
| 衰减和延音时间 | 表 3-7-2，全部 39 行，对照一个手册未印出的终点     | 制造商，相对       |
| 整个芯片的输出 | 240 个用例，23,040 个采样，对照 `snes_spc 0.9.0`   | 另一个实现         |
| 主机检查       | Shay Green 的 `spc_dsp6` 卡带中 104 项判定全部一致 | 在主机上取得的值   |
| 插值核         | 长度、形状以及四个抽头之和                         | 仅自检，无原始资料 |

[`conformance/hardware.json`](conformance/hardware.json) 记录手册中的每个数字及其页码，[`conformance/hardware.test.py`](conformance/hardware.test.py) 将它们与驱动芯片时的实际行为及本包导出的表进行比较。手册的文本层在这些数字处中断，因此每张表都是从渲染后的页面图像上读取的。`python3 -m conformance.quotes` 在手册中定位 28 个引用句。

### 噪声时钟锁定速率表

表 3-7-4 为 32 个噪声时钟值各印出一个频率。每个频率都等于 32,000 除以 `COUNTER_RATES` 的一项，所以这张表被逐项锁定。全部 32 项的误差都在 3% 或 0.5 Hz 以内，取两者中较大者。起音一栏以第二种方式锁定同一张表：一次起音为 64 步，因此最慢的速率需要 4.096 秒，印出的 16 个时间全部一致。

### 手册未给出的终点

衰减和延音两栏给出了时间，但没有给出下降所测量到的电平。把 39 个印出的时间分别除以本模型对应速率的周期，得到 576 到 600 个节拍，离散度小于 5%。推算出的终点约为 590 个节拍，记录在 [`conformance/divergences.json`](conformance/divergences.json) 中，没有内置到模型里。

### 插值核

插值核位于芯片晶片上，从未被转储过，以印刷表格的形式流传，因此没有可计算摘要的文件。[`conformance/carried.json`](conformance/carried.json) 以 SHA-256 锁定本包携带的值，这能检测出修改，但不能说明这张表是否就是芯片里的那张。

`check_kernel` 按插值器的需要检查所提供的表：

| 属性                                            | 芯片为何需要它                                     |
| :---------------------------------------------- | :------------------------------------------------- |
| 512 项                                          | 插值器的索引最高到 `forward + 256`                 |
| 每个抽头都是有符号 16 位字                      | 乘法是有符号 16 位乘法                             |
| 从 0 开始上升且从不下降                         | 一次下降会让曲线反向                               |
| 每个位置的四个抽头之和为 2048，误差在 0.2% 以内 | 否则声部的音量会取决于它落在两个采样之间的哪个位置 |

两张不同的表都可能通过，所以通过只表示这张表可能是芯片里的那张。插值核保存在每个芯片上，因此同一进程中的两个芯片可以携带不同的表。

### 音频来自何处

Shay Green 编写的 `snes_spc 0.9.0`，snes9x 将其收录在 `apu/bapu/dsp/SPC_DSP.cpp`，决定了手册未涉及的所有内容，也就是音频本身。与它一致就是与那个程序一致，[`conformance/divergences.json`](conformance/divergences.json) 将此记为第一条，严重程度为高。`spc_dsp6` 卡带出自同一作者，所以两者是一个来源，而不是两个。

该卡带包含的检查，其预期值是在主机上取得的。通过 [sony-s-smp-python](https://github.com/gufranco/sony-s-smp-python) 中的音频单元驱动，其中 104 项在这里得出判定，全部 104 项一致。[`conformance/cartridge.json`](conformance/cartridge.json) 保存每项判定，[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出了曾经不一致的 7 项的三个原因。

### 语料库

一个 SPC 转储包含 64 KB 音频 RAM，即音乐本身，以及 128 个 DSP 寄存器，即驱动程序设置芯片的方式。[`conformance/capture.py`](conformance/capture.py) 只读取寄存器，并跳过 RAM。

[`conformance/corpus.json`](conformance/corpus.json) 分三步构建：

1. 来自真实转储的 240 个寄存器状态，涵盖 70 个采样目录页、11 种回声延迟以及 1,402 个使用 ADSR 包络的声部。
2. 按每个用例的种子生成采样数据，放在每个状态的目录和音源编号所指向的位置。
3. 每个用例由 [`conformance/ref/`](conformance/ref) 中的参考驱动渲染 96 个采样，以输出的 SHA-256 形式保存。

`python3 -m conformance.corpus` 重放全部 240 个用例，最后输出 `240 agreed, 0 did not`。

要读取你自己的收藏，`python3 -m conformance.capture /path/to/spc/collection census.json 500` 会为它找到的前 500 个转储写出普查。普查以及由它构建的任何内容都只留在你的机器上。

[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) 列出尚未确定的问题，每一项都附有能确定它的测量方法。

## 参与开发

| 需求                             | 位置                                                                  |
| :------------------------------- | :-------------------------------------------------------------------- |
| 每项门禁检查及其运行顺序         | [CONTRIBUTING.md](CONTRIBUTING.md)                                    |
| 面向编码代理的同一份资料         | [AGENTS.md](AGENTS.md)                                                |
| 本仓库与同系列其他仓库共享的标准 | [FAMILY.md](FAMILY.md)                                                |
| 缺陷报告                         | [GitHub Issues](https://github.com/gufranco/sony-s-dsp-python/issues) |
| 安全报告                         | [SECURITY.md](SECURITY.md)                                            |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 mypy==1.14.1
python3 sdsp/core.test.py
```

每个模块旁边都有一个以它命名的测试文件，每个测试文件都可以像上面那样单独运行。覆盖率是一项硬性门禁检查，要求 100% 语句与分支覆盖。修改 `PIPELINE` 或任何会改变输出的内容时，除单元测试外，还需要运行 `python3 -m conformance.corpus`。

## 参考资料

- _SNES Development Manual, Book I_，Section 3，Nintendo of America Inc.，无日期。240 页，21,022,582 字节，SHA-256 `f1405241000046abba7849376d2ec53cf85f1ad2e9950d69a7c2cf1f3ff6b791`。该手册不可再分发，不在本仓库中。`python3 -m conformance.documents` 从 https://archive.org/download/SNESDevManual/book1_text.pdf 下载它到 `docs/`，并拒绝任何其他文件。Sony 没有为该芯片发布数据手册。
- Shay Green 编写的 `snes_spc 0.9.0`，即 snes9x 1.63 收录在 `apu/bapu/dsp/SPC_DSP.cpp` 的版本，用于语料库音频。[`conformance/ref/Dockerfile`](conformance/ref/Dockerfile) 从 snes9x 的 `1.63` 标签构建它；仓库中不附带副本。
- Shay Green 的 `spc_dsp6` 测试卡带，用于 [`conformance/cartridge.json`](conformance/cartridge.json) 中的 104 项主机判定。

## 引用本项目

[CITATION.cff](CITATION.cff) 在每次发布时由写入包版本号的脚本更新。

## 许可证

MIT。参见 [LICENSE](LICENSE)。

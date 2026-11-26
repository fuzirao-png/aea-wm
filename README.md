# AEA-WM

**Listen Then Roll** 以听觉事件为锚点的反事实视听推演。仓库包含成对音轨干预、合成状态推演、离线 Duo v1 输入准备和独立评分。

## 核心结果与状态

**Duo v1、MUSIC-AVQA 和 Video-MME 待实测。** 下表是《WAM 租卡与实验方案》第 4 节的实验前预测。

| 指标 | 朴素视听拼接 | 锚点 + 双路径 + 判别器 | 预测变化 |
| --- | ---: | ---: | ---: |
| 反事实准确率 | 55–68% | 68–80% | +8–15 pp |
| 听觉因果一致率 | 50–65% | 72–85% | +10–20 pp |
| 音画同步误差 | 参考基线 | 预计更低 | 相对下降 20–40% |
| 弃答率 | <2% | 5–15% | 预计增加 |

pp 表示百分点。计划分别给出了准确率范围与配对增量范围。生成质量 FVD、FAD 和真实模型的单组件消融均待实测。

## 问题与动机

换掉声音时，有时后续动作应随之变化，有时应该保持。约定的提示音可以触发亮灯，演奏声则可能只记录已经发生的演奏动作。评估需要区分**应变目标**与**应保持内容**，并记录干预是否确实生效。

## 方法和核心创新点

1. **把干预锁定到听觉事件。** 用原视频时间戳指定锚点，对其执行静音、等长替换或窗口内错位。输入两路的视频帧相同，PCM 音轨在编辑窗口之外逐样本相同。
2. **用共享输入做双路径推演。** 事实路径保留源音轨，反事实路径只编辑锚点。两路共享起始画面和生成配置。比较目标事件的变化和无关状态的稳定性，回答基于两路差异。
3. **用一致性判别约束答案。** 分别检查目标声是否生效、视觉响应是否符合任务规则、无关状态是否保留。证据不足时可以弃答。独立评分同时报告全体可答样本一致率和已回答子集一致率，用于审查覆盖率代价。

合成后端用实际 PCM 正弦波、简单频率识别和预定义的视觉状态转移验证流程。真实媒体路径使用人工标注锚点，生成由官方 Duo v1 完成。Duo v1 的公开离线接口将用户视频和 ASR 结果送入 Intent，再由 Realization 生成助手响应。项目目前支持输入层的成对干预，直接在声学隐状态分叉、自动学习式判别器和开放场景未来生成属于后续模型实验。非语音事件经 ASR 路径是否对生成生效也需要实测。[官方实现](https://github.com/inclusionAI/Duo#architecture)

## 基线是怎么做的

| 组 | CPU 模式 | 受控对比 |
| --- | --- | --- |
| 纯视觉 | `vision-only` | 两条预测路径均不读取声音，仅延续视觉状态 |
| 画面后配音 | `post-dub` | 保留事实视觉输出，再换上目标声音。目标画面因此始终固定 |
| 朴素视听拼接 | `naive` | 使用预设等长窗口和单路径。保留音频条件，省略锚点定位与判别 |
| 官方 Duo v1 | 外部生成 | 在官方离线服务分别上传原声和干预后的输入，使用同一案例、参考图和种子 |
| 完整 AEA-WM | `full` | 定位目标音频，执行事实及反事实两路，检查声、画与无关状态后回答 |

在实验设计中，`dual-judge` 去掉声学锚点，`anchor-judge` 去掉事实路径，`anchor-dual` 去掉判别。真实对照使用相同的样本清单、干预时长和生成参数。要把后配音做成真实对照，先生成事实视觉路径，再将它的输出视频帧固定，仅替换待评估的声音。

## 消融与组合实验

### CPU 合成冒烟实测

8 条构造样例包含 7 条可答和 1 条不可答。该检查用已知因果规则评价代码行为。公开基准模型结果待跑。

| 变体 | 锚点 | 双路径 | 判别器 | 准确率（7 条可答） | 覆盖率（8 条） | 生成一致（7 条可答） |
| --- | :---: | :---: | :---: | ---: | ---: | ---: |
| 朴素视听 `naive` |  |  |  | 2/7 | 8/8 | 0/7 |
| 仅锚点 `anchor` | ✓ |  |  | 4/7 | 7/8 | 6/7 |
| 仅双路径 `dual` |  | ✓ |  | 2/7 | 8/8 | 0/7 |
| 仅判别 `judge` |  |  | ✓ | 0/7 | 0/8 | 0/7 |
| 锚点 + 双路径 `anchor-dual` | ✓ | ✓ |  | 7/7 | 7/8 | 6/7 |
| 锚点 + 判别 `anchor-judge` | ✓ |  | ✓ | 4/7 | 6/8 | 6/7 |
| 双路径 + 判别 `dual-judge` |  | ✓ | ✓ | 0/7 | 0/8 | 0/7 |
| **完整 `full`** | ✓ | ✓ | ✓ | **6/7** | **6/8** | **6/7** |

无判别器的 `anchor-dual` 在一条背景漂移样例中答对了目标变化，但生成违反无关状态约束。完整方法拒绝这条轨迹，因此全体可答准确率从 7/7 降为 6/7，已回答中的一致率由 6/7 升为 6/6。完整方法也对唯一不可答样例正确弃答。逐组计数见 [测试汇总](results/synthetic-smoke.json)。

### 其余方案预测

- 音轨替换审计预计纯视觉输出差异小于 5%，具体差异指标待定义。后配音按构造保持画面。Duo 文献的 73.3% 是交互内容响应度，音轨替换导致的画面变动幅度待测。[Duo 论文](https://arxiv.org/abs/2611.15131)
- 前端对照以全局池化 PANNs 为基线。方案预期步进池化 Whisper 的定位较好、窗口 Q-Former 接近、因果门控 Mamba 延迟较低。文献中的等预算比较是总计 32 个音频 token，方案所列每秒速率需根据实现核对。[Qwen-MusicAVQA-7B](https://arxiv.org/abs/2608.11329)
- 联合生成用时预计为纯视觉的 1.5–2.5 倍，双路径在此基础上约为 1.5 倍。真实采样成本需固定设备、精度、步数和生成长度测量。

## 快速开始

### 运行 CPU 测试

Python 3.10+，无第三方 Python 依赖。

```bash
python -m aea_wm demo --out runs/synthetic.json
```

### 准备真实输入对

安装 FFmpeg。`start`、`end` 与 `shift-seconds` 均使用秒。示例对 0.60–1.00 秒的窗口静音。

```bash
python -m aea_wm prepare --video media/source.mp4 --start 0.60 --end 1.00 \
  --action mute --out runs/clip-001
```

提前或延后音频时使用 `--action shift --shift-seconds -0.1` 或正数，边界以静音填充。替换使用 `--action replace --replacement media/target.wav`。替换文件为单声道 PCM16，默认 16 kHz，长度与锚点采样数相同。输出包含两个 MP4、对应 PCM WAV 以及记录采样窗口和 SHA-256 的 `pair.json`。

按 [Duo 官方离线说明](https://github.com/inclusionAI/Duo#run-the-offline-demo) 启动服务。在同一案例、参考图及 `inference.seed` 下，将 `factual.mp4` 和 `counterfactual.mp4` 分别上传到新会话。记录权重版本、ASR 文本和输出。Duo 的模型权重适用 [发布者条款](https://huggingface.co/inclusionAI/Duo-1.0-distill-quant)，离线量化路径的显存需求以运行结果为准。

### 独立标注和评分

使用两个 UTF-8 JSONL 文件。`references.jsonl` 固定人工标注的期望结果。`observations.jsonl` 逐组记录独立评审对生成物的观察。每组覆盖全部样本，弃答记作 `"answer": null`。

```json
{"id":"clip-001","video_id":"video-001","answer":"red to blue","visual":"blue","sound":"high","expected_offset_s":0.20}
```

```json
{"id":"clip-001","variant":"full","answer":"red to blue","visual":"blue","sound":"high","unrelated_stable":true,"visual_onset_s":1.25,"audio_onset_s":1.00,"elapsed_s":8.5}
```

```bash
python -m aea_wm score --references runs/references.jsonl \
  --observations runs/observations.jsonl --out runs/scored.json
```

可答题的弃答计错。同步误差按可定位的目标事件计算，报告用于计算的样本数和均值。评分输出还包括覆盖率、不可答样本正确弃答率、两种一致率、样本和视频计数及 p95 耗时。正式置信区间以同一源视频为簇做配对抽样。

## 项目结构

```text
aea_wm/audio.py              PCM 读取、写入与锚点干预
aea_wm/media.py              可提交 Duo 的同画面 MP4 输入对
aea_wm/demo.py               八条合成样例与因子实验
aea_wm/score.py              独立标注的逐题及分组评分
results/synthetic-smoke.json 已实际运行的合成测试汇总
```

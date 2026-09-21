# OneASR 模型下载与本地加载指南

本文档介绍如何在本地高效下载 Hugging Face 与 ModelScope（魔搭社区）上的开源语音识别（ASR）模型，以及如何在 OneASR / faster-whisper 中配置与加载本地模型。

---

## 目录
- [一、Hugging Face 模型下载](#一hugging-face-模型下载)
  - [1. 官方 CLI 命令行下载（推荐）](#1-官方-cli-命令行下载推荐)
  - [2. Python 脚本下载 (`snapshot_download`)](#2-python-脚本下载-snapshot_download)
  - [3. 国内网络加速镜像 (`hf-mirror`)](#3-国内网络加速镜像-hf-mirror)
  - [4. Git LFS 仓库克隆](#4-git-lfs-仓库克隆)
  - [5. Hugging Face 默认缓存机制与路径修改](#5-hugging-face-默认缓存机制与路径修改)
- [二、ModelScope (魔搭社区) 高速下载](#二modelscope-魔搭社区-高速下载)
  - [1. 什么是 ModelScope](#1-什么是-modelscope)
  - [2. ModelScope CLI 命令行下载](#2-modelscope-cli-命令行下载)
  - [3. Python 脚本下载 (`snapshot_download`)](#3-python-脚本下载-snapshot_download)
  - [4. Git LFS 方式](#4-git-lfs-方式)
  - [5. Hugging Face vs ModelScope 对照表](#5-hugging-face-vs-modelscope-对照表)
- [三、在 OneASR 与 faster-whisper 中加载本地模型](#三在-oneasr-与-faster-whisper-中加载本地模型)
  - [1. 本地模型必备文件清单](#1-本地模型必备文件清单)
  - [2. faster-whisper Python 调用示例](#2-faster-whisper-python-调用示例)
  - [3. 在 OneASR `config.yaml` 中配置本地模型](#3-在-oneasr-configyaml-中配置本地模型)
  - [4. 常见排错与避坑指南](#4-常见排错与避坑指南)

---

## 一、Hugging Face 模型下载

下载 Hugging Face（如 [Systran/faster-whisper-medium](https://huggingface.co/Systran/faster-whisper-medium/tree/main)）模型，官方首推 `huggingface_hub` 工具包，具备多线程分块下载、断点续传与 SHA256 完整性校验。

### 1. 官方 CLI 命令行下载（推荐）

#### 安装依赖
```bash
pip install -U "huggingface_hub[cli]"
```

#### 下载整个模型仓库到指定目录
使用 `--local-dir` 参数将模型下载到目标文件夹（如 `./models/faster-whisper-medium`）：
```bash
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models/faster-whisper-medium
```

#### 仅下载部分文件（过滤下载）
如果只想下载特定格式文件（如排除不需要的 `.onnx` 或仅下载权重）：
```bash
# 仅下载 safetensors 和 json 配置文件
huggingface-cli download Systran/faster-whisper-medium --include "*.bin" "*.json" --local-dir ./models/faster-whisper-medium
```

#### 验证下载
查看目标目录：
```bash
ls -lh ./models/faster-whisper-medium
```
若目录下包含 `model.bin`（或 `model.safetensors`）、`config.json`、`tokenizer.json`、`vocabulary.json` 等文件且大小非 0 即为成功。

---

### 2. Python 脚本下载 (`snapshot_download`)

可在 Python 代码或初始化脚本中自动拉取模型：

```python
from huggingface_hub import snapshot_download

model_path = snapshot_download(
    repo_id="Systran/faster-whisper-medium",
    local_dir="./models/faster-whisper-medium",  # 指定保存目录
    local_dir_use_symlinks=False,              # 确保写入真实物理文件而非软链接
)

print(f"模型下载完成，本地存储路径: {model_path}")
```

---

### 3. 国内网络加速镜像 (`hf-mirror`)

如果在国内网络环境下直连 Hugging Face 下载速度慢或超时断流，可配置官方镜像站 `https://hf-mirror.com`：

#### Linux / macOS
```bash
export HF_ENDPOINT=https://hf-mirror.com
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models/faster-whisper-medium
```

#### Windows (PowerShell)
```powershell
$env:HF_ENDPOINT = "https://hf-mirror.com"
huggingface-cli download Systran/faster-whisper-medium --local-dir ./models/faster-whisper-medium
```

---

### 4. Git LFS 仓库克隆

如果习惯使用 Git 工具链，也可直接通过 Git LFS 克隆仓库：

```bash
# 1. 安装与初始化 Git LFS
git lfs install

# 2. 克隆整个仓库
git clone https://huggingface.co/Systran/faster-whisper-medium ./models/faster-whisper-medium
```

---

### 5. Hugging Face 默认缓存机制与 `models--*` 命名解析

如果不加 `--local-dir` 参数直接执行下载，或在 Python 代码中通过 `WhisperModel("medium", download_root="models")` 自动拉取模型时，Hugging Face 的底层缓存管理器（`huggingface_hub`）会在缓存区生成形如 **`models--Systran--faster-whisper-medium`** 的标准缓存目录。

- **默认集中缓存路径**：
  - **Linux / macOS**: `~/.cache/huggingface/hub/`
  - **Windows**: `C:\Users\<用户名>\.cache\huggingface\hub\`

#### (1) 目录命名规则拆解
Hugging Face 采用了固定的三段式命名模板：
$$\text{【仓库类型】} \mathbf{--} \text{【作者/组织名】} \mathbf{--} \text{【仓库名】}$$

以 `Systran/faster-whisper-medium` 为例：
```plaintext
models  --  Systran  --  faster-whisper-medium
  │            │                   │
  │            │                   └── 仓库名称 (Repo Name)
  │            └────────────────────── 作者/机构命名空间 (Namespace)
  └─────────────────────────────────── 资源类型 (models / datasets / spaces)
```
- **如果是数据集**：例如 `hf.co/datasets/common_voice` $\rightarrow$ 目录名为 `datasets--common_voice`；
- **如果是模型**：例如 `hf.co/Qwen/Qwen2.5-7B` $\rightarrow$ 目录名为 `models--Qwen--Qwen2.5-7B`。

#### (2) 为什么 Hugging Face 要这样设计？
1. **解决路径分隔符 `/` 的跨平台兼容问题**：
   在 Hugging Face 线上仓库名使用斜杠（如 `Systran/faster-whisper-medium`）。但在 Linux / macOS / Windows 中，`/` 与 `\` 是层级分隔符。HF 使用 **双连字符 `--`** 将斜杠安全扁平化，避免了跨平台文件系统深层路径冲突。
2. **防止模型与数据集同名冲突**：
   同一作者可能在 HF 上发布同名的模型和数据集，通过前缀 `models--` 与 `datasets--` 区分，存放在同一缓存根目录下永远不会发生覆盖或冲突。
3. **版本快照与文件去重（Deduplication）机制**：
   缓存目录内部采用“内容寻址哈希（Blobs）+ 版本快照（Snapshots）+ 软链接（Symlinks）”架构：
   ```plaintext
   models--Systran--faster-whisper-medium/
   ├── blobs/         # 存放真正的二进制大文件（以 SHA256 哈希值命名）
   │   ├── a1b2c3d4... (实际的 model.bin)
   │   └── e5f6g7h8... (实际的 tokenizer.json)
   ├── refs/          # 记录分支指向（如 main 分支当前对应的 commit hash）
   └── snapshots/     # 各个版本的快照
       └── 08e178d48790749d25932bbc082711ddcfdfbc4f/  # 具体 commit 哈希目录
           ├── config.json  -> ../../blobs/xxxx (软链接)
           └── model.bin    -> ../../blobs/a1b2c3d4... (软链接)
   ```
   如果模型作者后续发布了小版本更新（只修改了 `config.json`，未修改 1.5GB 的 `model.bin`），更新拉取时只会下载几十 KB 的新 json，权重文件直接复用 `blobs/` 中的哈希文件，**绝不重复占用磁盘空间**。

#### (3) “自动缓存形态” vs “显式下载形态” 对比

| 对比项 | 自动缓存形态（Hub Cache） | 显式下载形态（Flat Local Dir） |
| :--- | :--- | :--- |
| **目录名称** | `models--Systran--faster-whisper-medium` | 自定义（如 `models/faster-whisper-medium`） |
| **触发方式** | 代码中调用 `WhisperModel("medium", download_root="models")` 自动下载 | 终端运行 `hf download ... --local-dir ./models/xxx` |
| **内部结构** | 包含 `blobs/`、`snapshots/`、软链接（复杂） | 普通平铺目录（直接放 `model.bin`、`config.json`） |
| **适合场景** | 库自动在线托管、版本追踪 | **人工离线管理、明确配置 `model_path`** |

#### (4) 修改默认缓存路径
若系统盘（C盘/根分区）空间紧张，可通过设置 `HF_HOME` 环境变量将缓存根目录迁移到大容量数据盘：

- **Linux / macOS**:
  ```bash
  export HF_HOME=/data/models/huggingface
  ```
- **Windows (PowerShell)**:
  ```powershell
  $env:HF_HOME = "D:\models\huggingface"
  ```

---

## 二、ModelScope (魔搭社区) 高速下载

### 1. 什么是 ModelScope

[ModelScope（魔搭社区）](https://www.modelscope.cn/) 是阿里达摩院联合开源生态发起的模型社区，定位为“国内版 Hugging Face”。
- **优势**：依托国内 CDN / 阿里云基础设施，国内机器拉取模型可直接跑满百兆/千兆带宽，无需挂代理或镜像加速。
- **工具链**：提供与 `huggingface_hub` 设计高度一致的 `modelscope` CLI 与 Python SDK。

---

### 2. ModelScope CLI 命令行下载

#### 安装工具包
```bash
pip install -U modelscope
```

#### 命令行下载完整模型
```bash
# 下载指定模型到本地目录
modelscope download --model deepseek-ai/DeepSeek-R1-Distill-Qwen-7B --local_dir ./models/Qwen-7B
```
*注：如果不加 `--local_dir`，默认缓存至 `~/.cache/modelscope/hub/`。*

#### 仅下载指定文件或通配过滤
```bash
# 仅下载单个配置文件
modelscope download --model qwen/Qwen2.5-7B-Instruct config.json --local_dir ./models/Qwen2.5-7B

# 按通配符过滤下载
modelscope download --model qwen/Qwen2.5-7B-Instruct --include "*.safetensors" --local_dir ./models/Qwen2.5-7B
```

---

### 3. Python 脚本下载 (`snapshot_download`)

ModelScope 的 Python API 设计与 Hugging Face 保持一致：

```python
from modelscope.hub.snapshot_download import snapshot_download

# 下载整个模型到指定目录
model_dir = snapshot_download(
    model_id="qwen/Qwen2.5-7B-Instruct",
    local_dir="./models/Qwen2.5-7B",
    # allow_patterns=["*.json", "*.safetensors"],  # 可选：白名单过滤
)

print(f"ModelScope 模型下载完成，本地目录为: {model_dir}")
```

---

### 4. Git LFS 方式

```bash
git lfs install
git clone https://www.modelscope.cn/qwen/Qwen2.5-7B-Instruct.git ./models/Qwen2.5-7B
```

---

### 5. Hugging Face vs ModelScope 对照表

| 功能特性 | Hugging Face | ModelScope (魔搭社区) |
| :--- | :--- | :--- |
| **Python 库** | `pip install huggingface_hub` | `pip install modelscope` |
| **CLI 下载命令** | `huggingface-cli download <REPO> --local-dir <DIR>` | `modelscope download --model <REPO> --local_dir <DIR>` |
| **Python 函数** | `from huggingface_hub import snapshot_download` | `from modelscope import snapshot_download` |
| **指定文件过滤** | `--include "*.bin"` / `--exclude "*.onnx"` | `--include "*.bin"` / `--exclude "*.onnx"` |
| **默认缓存目录** | `~/.cache/huggingface/hub/` | `~/.cache/modelscope/hub/` |
| **缓存路径环境变量**| `export HF_HOME=/path/to/cache` | `export MODELSCOPE_CACHE=/path/to/cache` |
| **国内直连速度** | 较慢（建议配置 `HF_ENDPOINT=https://hf-mirror.com`） | 极快（国内直连全速） |

---

## 三、在 OneASR 与 faster-whisper 中加载本地模型

### 1. 本地模型必备文件清单

使用 `faster-whisper` 加载本地目录时，该目录下必须包含 CTranslate2 模型结构所需的完整文件（以 medium 模型为例）：

```plaintext
models/faster-whisper-medium/
├── config.json
├── model.bin (或 model.safetensors)
├── tokenizer.json
├── vocabulary.json (部分模型为 vocabulary.txt)
└── preprocessor_config.json
```

> **注意**：如果缺少这些文件，`faster-whisper` 会认为传入的字符串不是合法的本地文件夹，从而误将其当成 Hugging Face 线上仓库名进行联网拉取。

---

### 2. faster-whisper Python 调用示例

将下载好的本地文件夹路径（相对路径或绝对路径）直接传给 `WhisperModel` 构造函数：

```python
import os
from faster_whisper import WhisperModel

# 1. 指定本地模型文件夹路径
model_path = "./models/faster-whisper-medium"

# 2. 初始化模型
# device: "cuda" (NVIDIA GPU) / "cpu"
# compute_type:
#   - CPU: 推荐 "int8"
#   - GPU: 推荐 "float16" 或 "int8_float16"
model = WhisperModel(
    model_path,
    device="cpu",
    compute_type="int8",
)

# 3. 执行识别
segments, info = model.transcribe("test_audio.wav", beam_size=5)

print(f"检测到语言: {info.language} (置信度: {info.language_probability:.2f})")
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
```

#### 验证是否成功命中本地模型：
运行脚本时，控制台**不出现任何联网下载进度条**，直接进入转录流程即表示成功从本地加载。

---

### 3. 在 OneASR `config.yaml` 中配置本地模型

在 OneASR 项目的 `config.yaml` 中，各 Provider 直接通过 `model_path` 指定本地模型路径（支持相对于 OneASR 根目录的相对路径或绝对路径）：

```yaml
# API Key（所有接口必须携带此 key）
api_key: oneasr-key

# ASR Provider 配置
ASR-Providers:

  # X-ASR 流式识别（基于 sherpa-onnx，zipformer2 transducer）
  xasr:
    enable: false
    engine: xasr

    load:
      model_name: xasr-zh-en
      tokens_path: models/chunk-160ms-model/tokens.txt
      encoder_path: models/chunk-160ms-model/encoder-160ms.onnx
      decoder_path: models/chunk-160ms-model/decoder-160ms.onnx
      joiner_path: models/chunk-160ms-model/joiner-160ms.onnx
      provider: cpu
      sample_rate: 16000

    properties:
      functions:
        - RealtimeASR
      languages: zh, en

  # Faster-Whisper 文件转录引擎
  faster-whisper:
    enable: true
    engine: faster-whisper

    load:
      # 方式 1: 配置本地模型路径（推荐，所见即所得）
      # 若路径不存在，OneASR 启动时会直接报错并打印下载命令指引
      model_path: models/medium
      model_name: medium

      # 方式 2: 不配置 model_path（留空或注释），仅配置 model_name
      # 此时 faster-whisper 引擎将自动从 Hugging Face 在线拉取模型
      # model_name: Systran/faster-whisper-medium

      device: cpu            # 或 cuda
      compute_type: int8     # GPU 可设为 float16
      max_duration: null

    properties:
      functions:
        - FileASR
      languages: zh, en, ja, ko, fr, de, es, it, ru, pt

  # Qwen3-ASR 文件转录引擎
  qwen:
    enable: false
    engine: qwen

    load:
      model_name: Qwen/Qwen3-ASR-1.7B
      model_path: models/Qwen3-ASR-1.7B
      forced_aligner_name: Qwen/Qwen3-ForcedAligner-0.6B
      forced_aligner_path: models/Qwen3-ForcedAligner-0.6B
      device: cuda:0
      dtype: bfloat16
```

---

### 4. 常见排错与避坑指南

1. **路径解析失败，控制台依然联网下载**：
   - 检查本地模型文件夹下是否存在 `model.bin`、`config.json` 等关键文件；
   - 检查路径拼写，如果使用相对路径，注意工作目录（CWD）是否在 `OneASR` 根目录下；可以使用 Python `os.path.abspath("./models/faster-whisper-medium")` 输出绝对路径排查。
2. **下载到本地出现软链接（Symlink）失效**：
   - Windows 环境下使用 `snapshot_download` 或 `git clone` 可能因为权限不足无法创建符号链接；
   - 解决方法：在 `huggingface-cli download` 中指定 `--local-dir`，或在 `snapshot_download` 中指定 `local_dir_use_symlinks=False`，强制写入真实文件。
3. **GPU 显存溢出（OOM）**：
   - 显存较小时（如 ≤6GB），可将 `compute_type` 从 `float16` 调整为 `int8_float16` 或 `int8`，可节省约 50% 显存占用，且识别精度几乎无损。

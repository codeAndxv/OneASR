# OneASR uv 现代 Python 工具链与环境管理指南 (UV_GUIDE)

本文档系统性整理了在 OneASR 项目开发及日常 Python 环境管理中，使用 **`uv`**（基于 Rust 构建的超高速 Python 包与环境管理器）的核心操作、全局 Python 版本管理、全局 CLI 工具隔离安装以及环境清理实战。

---

## 目录
- [一、包与依赖管理 (`uv pip` / `uv add` / `uvx`)](#一部与依赖管理-uv-pip--uv-add--uvx)
  - [1. 替换传统 pip 命令](#1-替换传统-pip-命令)
  - [2. 临时执行命令行工具 (`uvx`)](#2-临时执行命令行工具-uvx)
  - [3. 在项目工程中管理依赖 (`uv add`)](#3-在项目工程中管理依赖-uv-add)
- [二、新版 Hugging Face CLI 工具 (`hf`) 使用规范](#二新版-hugging-face-cli-工具-hf-使用规范)
  - [1. 废弃说明：`hf` 替代 `huggingface-cli`](#1-废弃说明hf-替代-huggingface-cli)
  - [2. 三种使用场景与推荐命令](#2-三种使用场景与推荐命令)
- [三、全局 CLI 工具管理 (`uv tool`，对标 pipx)](#三全局-cli-工具管理-uv-tool对标-pipx)
  - [1. 为什么使用 `uv tool`？](#1-为什么使用-uv-tool)
  - [2. 常用操作命令](#2-常用操作命令)
  - [3. `uv tool` vs `uvx` 对照表](#3-uv-tool-vs-uvx-对照表)
- [四、uv Python 版本管理 (`uv python`)](#四uv-python-版本管理-uv-python)
  - [1. 全局下载与存储 Python 解释器](#1-全局下载与存储-python-解释器)
  - [2. 解释器列表 `uv python list` 输出解析](#2-解释器列表-uv-python-list-输出解析)
  - [3. 固定全局与项目默认 Python 版本 (`uv python pin`)](#3-固定全局与项目默认-python-版本-uv-python-pin)
  - [4. 查找解释器路径与终端 Alias 配置](#4-查找解释器路径与终端-alias-配置)
- [五、macOS 迁移至“纯 uv 托管环境”清理实战](#五macos-迁移至纯-uv-托管环境清理实战)
  - [1. macOS 各环境角色定位](#1-macos-各环境角色定位)
  - [2. 检查与安全卸载 Homebrew Python](#2-检查与安全卸载-homebrew-python)
  - [3. 关联依赖处理：关于 `python-tk@3.12` (Tkinter)](#3-关联依赖处理关于-python-tk312-tkinter)
  - [4. 验证环境是否已纯净化](#4-验证环境是否已纯净化)
- [六、OneASR 纯 uv 极速开发标准工作流](#六oneasr-纯-uv-极速开发标准工作流)

---

## 一、包与依赖管理 (`uv pip` / `uv add` / `uvx`)

### 1. 替换传统 pip 命令
在激活的虚拟环境（如 `(OneASR)`）下，所有标准的 `pip` 操作均可无缝直接替换为 `uv pip`，执行速度提升 10~100 倍：

```bash
# 激活环境后安装依赖
uv pip install -U huggingface_hub
uv pip install -r requirements.txt
```

### 2. 临时执行命令行工具 (`uvx`)
如果只想临时使用一次某个 Python 工具（例如快速下载一个模型、生成一次项目模板），**不需要**将其安装进当前虚拟环境，直接通过 `uvx` 在临时沙盒中免安装执行：

```bash
# 临时运行 hf 命令行下载模型（用完即释放，不污染当前环境）
uvx --from huggingface_hub hf download Systran/faster-whisper-medium --local-dir ./models
```

### 3. 在项目工程中管理依赖 (`uv add`)
若项目采用现代 `pyproject.toml` 管理：
```bash
# 自动安装并把依赖记录到 pyproject.toml
uv add huggingface_hub
```

---

## 二、新版 Hugging Face CLI 工具 (`hf`) 使用规范

### 1. 废弃说明：`hf` 替代 `huggingface-cli`
在较新版本的 `huggingface_hub` 中：
- 官方已将旧版 `huggingface-cli` 标记为废弃（Deprecated）；
- 全面改用独立、简短的 **`hf`** 命令行工具；
- 安装时**不再需要**额外指定 `[cli]` extra，直接安装 `huggingface_hub` 即可。

### 2. 三种使用场景与推荐命令

#### 场景 A：使用 `uv tool` 全局安装 `hf`（最推荐）
如果经常需要下载模型或数据集，将其安装为全局常驻 CLI：
```bash
# 1. 全局安装 hf
uv tool install huggingface_hub

# 2. 在任何终端直接下载模型
hf download Systran/faster-whisper-medium --local-dir ./models
```

#### 场景 B：使用 `uvx` 零安装临时运行
无需常驻安装：
```bash
uvx --from huggingface_hub hf download Systran/faster-whisper-medium --local-dir ./models
```

#### 场景 C：在当前项目的虚拟环境中安装使用
```bash
# 1. 在当前虚拟环境中安装
uv pip install -U huggingface_hub

# 2. 调用 hf 下载
hf download Systran/faster-whisper-medium --local-dir ./models
```

---

## 三、全局 CLI 工具管理 (`uv tool`，对标 pipx)

### 1. 为什么使用 `uv tool`？
`uv tool` 专门用于**在全局安装和管理 Python 命令行工具**（如 `hf`、`ruff`、`black`、`ipython`、`httpie`）。

- **传统全局 pip 安装的痛点**：所有工具包混杂在系统全局 Python 中，不同工具依赖版本冲突会导致环境彻底损坏。
- **`uv tool` 隔离机制**：为每个全局工具单独在后台创建一个专属的轻量沙盒环境，仅将入口可执行命令软链接至系统 PATH（如 `~/.local/bin`）。不同工具之间 100% 隔离，绝不冲突，也不会污染任何项目。

### 2. 常用操作命令

```bash
# 1. 安装全局工具
uv tool install huggingface_hub    # 安装后终端直接可用 `hf`
uv tool install ruff                # 超快代码格式化/Linter

# 2. 查看已安装的全局工具
uv tool list

# 3. 升级全局工具
uv tool upgrade huggingface_hub
uv tool upgrade --all              # 一键升级所有全局工具

# 4. 卸载全局工具
uv tool uninstall huggingface_hub  # 彻底清除对应独立沙盒与软链接
```

### 3. `uv tool` vs `uvx` 对照表

| 命令 | 适用场景 | 运行机制 |
| :--- | :--- | :--- |
| **`uv tool install <包名>`** | 常用高频工具（如 `hf`, `ruff`, `ipython`） | 创建专属隔离环境并常驻在 `~/.local/bin`，随敲随用。 |
| **`uvx <命令名>`** | 极低频、临时用一次的工具（如 `cookiecutter`） | 在临时沙盒中下载并执行，执行完毕即销毁，不占常驻空间。 |

---

## 四、uv Python 版本管理 (`uv python`)

`uv` 具备完整的 Python 解释器下载与管理能力，可直接替代 `pyenv`。

### 1. 全局下载与存储 Python 解释器
通过 `uv` 下载的 Python 是跨项目共享的独立预编译版本（Python Standalone Builds），不会重复占用空间：

```bash
# 安装指定版本的 Python
uv python install 3.11 3.12

# 卸载某个版本
uv python uninstall 3.11
```

### 2. 解释器列表 `uv python list` 输出解析

执行 `uv python list` 会列出当前电脑中已有的 Python 以及支持一键安装的远程清单：

```plaintext
cpython-3.14.5-macos-aarch64-none    /opt/homebrew/bin/python3.14 -> ...
cpython-3.12.11-macos-aarch64-none   .local/share/uv/python/...
cpython-3.11.13-macos-aarch64-none   <download available>
cpython-3.9.6-macos-aarch64-none     /usr/bin/python3
```

#### 输出信息说明：
1. **右侧状态/路径**：
   - `<download available>`：远程预编译清单，**不占本地任何磁盘空间**。直接输入 `uv python install 3.11` 即可秒级下载。
   - `~/.local/share/uv/python/...`：由 `uv` 下载并集中托管的真实物理 Python 安装目录。
   - `/opt/homebrew/...`：由 Homebrew 安装的 Python。
   - `/usr/bin/python3`：macOS 系统内置的 Python（Xcode Command Line Tools 自带，如 3.9.6）。
2. **左侧标识符命名规则**（如 `cpython-3.12.11-macos-aarch64-none`）：
   - `cpython`：官方标准 C 语言实现的 Python 解释器（日常开发/机器学习唯一推荐）。
   - `3.12.11`：具体版本号。
   - `macos`：操作系统。
   - `aarch64`：Apple Silicon 芯片架构（M1/M2/M3/M4 系列等 ARM 芯片）。
   - `none` / `freethreaded`：`none` 为标准版；`freethreaded` 为 Python 3.13+ 的无 GIL 实验性构建。
   - `pypy` / `graalpy`：带 JIT 的 PyPy 或基于 JVM 的 GraalPy 解释器。

#### 仅查看本地已实际安装的 Python：
```bash
uv python list --only-installed
```

### 3. 固定全局与项目默认 Python 版本 (`uv python pin`)

```bash
# 1. 全局默认版本（让当前用户下 uv 默认使用 3.12）
uv python pin 3.12 --global

# 2. 项目级版本（在当前项目根目录生成 .python-version 文件）
uv python pin 3.12
```

### 4. 查找解释器路径与终端 Alias 配置

`uv` 刻意避免污染系统的 `/usr/bin/python`。如果想获取其真实落地路径：
```bash
uv python find 3.12
# 输出类似: /Users/dudu/.local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3
```

若希望终端全局 `python` 命令直接调用 uv 的 Python，可在 `~/.zshrc` 中添加：
```bash
alias py312="$(uv python find 3.12)"
```

---

## 五、macOS 迁移至“纯 uv 托管环境”清理实战

为了避免系统内存在 Homebrew Python 与 uv Python 混用导致的路径错乱，可以清理 Homebrew Python，让 Python 版本完全由 `uv` 单一接管。

### 1. macOS 各环境角色定位
- `/usr/bin/python3` (3.9.6)：**macOS 系统保护组件（SIP）**，系统脚本与 Xcode CLT 强依赖，**禁止删除，无需理会**。
- `Homebrew Python` (`/opt/homebrew/...`)：可安全清理，由 `uv` 替代。
- `uv 托管 Python` (`~/.local/share/uv/...`)：**开发主力**，完全由 `uv` 自闭环维护。

### 2. 检查与安全卸载 Homebrew Python

#### 步骤 1：检查是否有其他 Homebrew 软件依赖它们
```bash
brew uses --installed python@3.12 python@3.14
```
- 若输出为空：说明无其他 brew 软件依赖它们，可直接卸载。
- 若有软件依赖且必须保留：建议执行解绑 `brew unlink python@3.12 python@3.14`，既不影响底层软件运行，又不会污染终端全局命令。

#### 步骤 2：安全卸载与清理残留
如果关联安装了 `python-tk@3.12` 等组件，连同一起卸载：
```bash
# 1. 卸载 Homebrew Python 及相关组件
brew uninstall python-tk@3.12 python@3.12 python@3.14

# 2. 自动清理随它们安装、现已无用的底层孤儿依赖（如 mpdecimal 等）
brew autoremove
```

### 3. 关联依赖处理：关于 `python-tk@3.12` (Tkinter)
- **什么是 `python-tk`？** 是 Homebrew 专门拆分出来的 Tkinter 图形界面支持库（用于 `import tkinter`、Matplotlib 窗口弹窗等）。Homebrew 默认的 `python` 为轻量化去掉了 GUI 支持，因此需要单独安装 `python-tk`。
- **uv 还需要单独装类似包吗？** **不需要**。`uv python install` 下载的独立预编译版本已完整内置了 Tcl/Tk 和 Tkinter，无需在系统层面单独打补丁。

### 4. 验证环境是否已纯净化
执行以下命令：
```bash
uv python list --only-installed
```

#### 理想状态输出示例：
```plaintext
cpython-3.12.11-macos-aarch64-none    .local/bin/python3.12 -> .local/share/uv/python/...
cpython-3.12.11-macos-aarch64-none    .local/share/uv/python/cpython-3.12.11-macos-aarch64-none/bin/python3.12
cpython-3.9.6-macos-aarch64-none      /usr/bin/python3
```
- `/opt/homebrew/` 相关的 Python 彻底消失；
- 仅保留系统自带的 `/usr/bin/python3` 以及 `.local/share/uv/` 下由 `uv` 接管的纯净环境。

---

## 六、OneASR 纯 uv 极速开发标准工作流

在 OneASR 项目中，推荐的日常标准操作流程如下：

```bash
cd OneASR

# 1. 创建指定版本的虚拟环境
uv venv --python 3.12

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 超高速安装项目依赖
uv pip install -r requirements.txt

# 4. 启动 OneASR 服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 运行测试
pytest
```

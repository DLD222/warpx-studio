# WarpX Studio

一个独立的 WarpX 图形化仿真工作室：**参数表单/输入文本 → 校验 → 运行 → openPMD 可视化**。  
它不要求自己放在 WarpX 源码树里，可以同时连接：

- **官方 WarpX** 编译出的 `warpx.2d` / `warpx.3d` / `warpx.rz`
- **下游 fork**（例如本仓库的插件化/EB/hybrid 版本）编译出的二进制
- 任意显式指定的 WarpX 可执行文件

运行时通过同一个二进制下拉框切换，Studio 自动标注 `official` / `fork`。

## 安装

```bash
git clone <this-repo> warpx-studio
cd warpx-studio
python -m pip install -e '.[viz,yt,dev]'
```

## 启动

```bash
# 自动探测当前目录/父目录里的 WarpX；数据写到 ~/.local/share/warpx-studio
warpx-studio

# 明确指定一个官方或 fork 的 WarpX 源码树
warpx-studio --root /path/to/warpx

# 明确指定一个编译好的二进制
warpx-studio --binary /path/to/build/bin/warpx.2d
```

常用环境变量：

| 变量 | 作用 |
|---|---|
| `WARPX_STUDIO_WARPX_ROOT` | WarpX 源码根 |
| `WARPX_STUDIO_BINARY` | 显式二进制 |
| `WARPX_STUDIO_PROFILE` | `official` / `fork` 标签 |
| `WARPX_STUDIO_DATA` | 数据根目录 |
| `WARPX_STUDIO_PROJECTS` | 项目目录 |
| `WARPX_STUDIO_RUNS` | 运行输出目录 |

二进制探测覆盖：

```text
<root>/build*/bin/warpx.*
<root>/build_multi*/bin/warpx.*
<root>/audit_build/**/bin/warpx.*
<data>/builds/*/bin/warpx.*
显式 --binary
```

## 从旧 Studio 迁移

旧版把数据放在 WarpX 仓库里。不同版本的目录可能不同，先 `find` 确认：

```bash
# 本 fork 的旧版实际位置
WARPX_STUDIO_PROJECTS=/path/WarpX_plugin/Tools/audit_runs/studio_projects \
WARPX_STUDIO_RUNS=/path/WarpX_plugin/audit_runs/studio \
warpx-studio --root /path/WarpX_plugin
```

如果你的旧版项目在 `<repo>/audit_runs/studio_projects`，把第一行改成那个路径即可。

之后可以把这两个目录迁到 `~/.local/share/warpx-studio/` 下，变成完全独立安装。

## 从界面构建

- fork 有 `audit_build/configure_common.sh`：使用 fork 的依赖/工具链脚本；
- 官方 checkout：使用标准 out-of-source CMake，产物写到 `<data>/builds/<name>`；
- 仍可在输入框里覆盖 `-DWarpX_*` 选项。

## ParaView 是可选后端

默认安装**不需要 ParaView**：

- 二维标量/矢量场：**装 yt 时优先 yt**；没有 yt 回退 matplotlib + h5py；
- 三维、粒子叠加、体积渲染、VTK 导出：需要 `pvpython`。

后端选择顺序（二维场没有 particles/volume 时）：

```text
list 请求 → h5py 枚举量目录（不需要 ParaView）
2D 场 → yt（若已安装）
       → matplotlib + h5py
       → pvpython
3D/粒子/体积 → pvpython
```

安装 yt（二维优先）：

```bash
python -m pip install -e '.[yt]'
# 或 conda install -c conda-forge yt
```

不装 yt 也能用二维图，只是改用 matplotlib；`/api/runtime` 会返回
`renderers: {matplotlib, h5py, yt}` 和 `paraview: {available, pvpython}`，便于排查环境。

安装一个带 pvpython 的 ParaView：

```bash
conda create -n paraview -c conda-forge python=3.11 paraview
# 路径按你的 conda 安装调整
export WARPX_STUDIO_PVPYTHON="$HOME/miniconda3/envs/paraview/bin/pvpython"
```

或者已经有 ParaView：

```bash
warpx-studio --pvpython /opt/ParaView/bin/pvpython
```

没装 ParaView 时：

- `/api/paraview/status` 返回 `available: false`；
- 网页内三维/VTK 请求返回明确的 503 提示；
- 二维图仍能正常工作，不会因为缺 ParaView 启动失败。

二维回退依赖：

```bash
python -m pip install -e '.[viz]'    # matplotlib + h5py
```

## 设计边界

- **Studio 不是 WarpX**：它只生成/读取 inputs、选择二进制、启动进程、读 openPMD。
- 官方和 fork 共享同一套表单/诊断；fork 独有参数可能导致官方二进制运行时报错，界面上会显示所选二进制的 `family`，请按目标版本选择。
- `Tools` 里的官方精选算例是**输入文件**，不包含编译产物。
- 许可证：BSD-3-Clause（见 `LICENSE`）。

## 开发

```bash
python -m pip install -e '.[dev]'
node tests/ui_smoke.js warpx_studio/web/static/index.html warpx_studio/catalog/data
python -m warpx_studio.cli --no-browser --port 8771
```

## 上游同步

本仓库与 WarpX 官方仓库是**两个独立项目**：Studio 通过二进制和输入文件适配，不复制 WarpX 源码。官方 WarpX 月更时只需重新编译并让 `--root`/`--binary` 指向新构建。

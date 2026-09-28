# Flika 通用启动器（flikaExe）

一个 **"双击即用"** 的 Flika 启动器。Flika 是一个基于 Vite + Vue3 + Tauri 的音乐可视化工具（本地开发服务默认运行在 `http://localhost:1420/`）。本启动器负责**自动启动 Flika 的后台服务，并在内置浏览器窗口中展示 Flika 界面**，让普通用户无需接触命令行即可使用。

---

## 作用

- **一键启动**：双击 `flikaExe.exe`，自动完成"启动后台服务 → 打开 Flika 界面"。
- **无控制台**：全程不弹出命令行窗口（服务、停止服务均隐藏窗口）。
- **自动定位项目**：自动找到 Flika 项目目录，无需每次手动指定。
- **窗口置顶**：Flika 窗口保持最前，方便使用。
- **优雅退出**：关闭窗口后自动停止后台服务、释放端口、回写配置。

---

## 使用方法

### 直接双击 exe

```
双击 D:\GIT\flikaExe\flikaExe.exe
```

启动后按以下逻辑自动工作：

1. **自动读取配置**（`flikaExe.json`），拿到 Flika 项目目录；
2. **自动启动** `npm run dev` 后台服务（进度条显示）；
3. 服务就绪后（端口 1420 可访问）**自动打开 Flika 界面**；
4. **关闭窗口** → 自动停止服务、释放端口、更新配置文件。

### 首次使用 / 无配置时

如果找不到配置文件或项目目录无效，会弹出启动器窗口，点击 **"选择项目目录"**，选择包含 `package.json` 的 Flika 项目目录（如 `D:\GIT\flika`），确认后自动启动服务并进入 Flika 界面，同时把该目录记入配置文件，下次即可直接双击使用。

### 启动优先级（自动定位 Flika 项目）

启动器按下述顺序定位项目目录：

1. **本机 1420 端口已有服务** → 直接打开界面（复用已有服务）；
2. **配置文件 `flikaExe.json`**（记录上一次的项目目录）；
3. **exe 当前工作目录**（即双击 exe 所在的目录）；
4. 以上都不满足 → **弹窗让用户手动选择目录**。

---

## 配置文件 `flikaExe.json`

与 `flikaExe.exe` 放在**同一目录**（即启动器的运行目录），格式如下：

```json
{
  "flika_dir": "D:/GIT/flika"
}
```

| 字段 | 说明 |
|------|------|
| `flika_dir` | Flika 项目目录（含 `package.json` 和 `node_modules`） |

- 文件**不存在时**：选择项目目录后会自动创建；
- 文件**存在时**：每次退出都会自动更新该字段；
- 如果目录已失效：启动器会自动退回手动选择目录。

> 兼容说明：旧版本的键名 `project_dir` 仍可读取，程序运行后会自动改写为 `flika_dir`。

---

## 目录结构

```
flikaExe/
├── flikaExe.exe            # 成品启动器（可直接分发）
├── flikaExe.py             # 源码（tkinter 启动器 + pywebview 内嵌浏览器）
├── flikaExe.json           # 配置文件（记录 Flika 项目目录）
├── build_flikaExe_Nuitka.bat  # Nuitka 打包脚本
├── icons/                  # 打包图标
├── .venv/                  # 打包用 Python 虚拟环境
└── backup/                 # 旧版本文件归档（仅供参考）
```

---

## 重新打包 exe（可选）

如果你修改了 `flikaExe.py`，用 Nuitka 重新打包：

```bat
call build_flikaExe_Nuitka.bat
```

打包要点：

- Python 3.14 + Nuitka；
- 参数含 `--onefile`（单文件）、`--windows-console-mode=disable`（无控制台）、`--enable-plugin=tk-inter`（tkinter 必需）、`--windows-icon-from-ico=icons\icon.ico`（图标）；
- 配置/日志采用**相对路径**读取（读运行目录），保证 onefile 单文件也能正常读写配置。

---

## 环境要求

- **Windows 系统**；
- **Node.js**（系统已安装，需含 `npm`）；
- Flika 项目目录需包含 `package.json` 和 `node_modules`（已安装依赖）。

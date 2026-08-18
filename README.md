# NEU WakeUP

从东北大学本科教务系统读取当前用户课表，合并普通课与实验/实践课，并生成 WakeUP 可直接导入的七列 CSV。默认学期为 `2026-2027-1`（2026-2027 年秋季学期）。

## 直接使用

发布文件位于 GitHub Releases：<https://github.com/2711944586/neuwakeup/releases/latest>

### Windows

下载 `NEU-WakeUP-windows.exe`，双击运行。程序不会弹出命令行窗口。

1. 等待二维码窗口出现。
2. 使用绑定统一身份认证的微信扫码并完成授权。
3. 回到二维码窗口点击“继续”。
4. 完成后，CSV 会写入 EXE 同目录，文件名为 `{姓名}{学号}.csv`。

### macOS

根据芯片选择对应文件：

- Apple Silicon：`NEU-WakeUP-macos-apple-silicon.dmg`
- Intel：`NEU-WakeUP-macos-intel.dmg`

打开 DMG，将 `NEU-WakeUP.app` 拖入“应用程序”或其他有写入权限的目录，然后双击启动。首次打开若提示无法验证开发者，请右键应用选择“打开”，并确认一次。

扫码、确认和导出流程与 Windows 完全一致。CSV 默认写在应用旁边；如果应用所在目录不可写，会自动写入“下载”文件夹，窗口会显示最终保存位置。

打包版本已经内置所有 Python 依赖，使用者不需要安装 Python。网络、登录或课表接口失败时不会生成不完整 CSV。

## 从源码运行

需要 Python 3.9 或更高版本。源码启动时会检查并自动安装或更新 `requirements.txt` 中的依赖。

Windows：

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python neuwakeup.py
```

常用检查命令：

Windows：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --self-check
& .\.venv\Scripts\python.exe .\neuwakeup.py --version
```

macOS：

```bash
.venv/bin/python neuwakeup.py --self-check
.venv/bin/python neuwakeup.py --version
```

源码模式保留终端教程和学期输入；打包版本固定使用默认学期，避免无控制台环境等待输入。

## CSV 与完整性

CSV 表头和列顺序固定为：

```text
课程名称,星期,开始节数,结束节数,老师,地点,周数
```

文件使用 UTF-8 with BOM。程序会解析普通课和实验/实践课的教师、地点、星期、节次及周次，过滤停课记录，合并去重，并检查列数、节次范围、空字段和时间冲突。未排星期或节次的记录会被提示；完整课表接口失败时直接停止导出，避免遗漏课程。

写文件采用临时文件加原子替换，程序只在校验通过后生成最终 CSV。姓名、学号、Cookie、二维码链接和课表只保存在运行内存或本地 CSV，不会上传到本项目。

## 构建 Windows EXE

需要 Windows、Python 3.9+ 和网络连接：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\build_exe.ps1
```

脚本使用独立的 `.build-venv`，生成无控制台的 `dist\NEU-WakeUP.exe`。构建缓存已加入忽略规则，不应提交到仓库。

## 构建 macOS 应用

需要在 macOS 本机或 macOS CI 环境执行，Windows 不能直接交叉编译 `.app`：

```bash
chmod +x build_macos.sh
./build_macos.sh
```

脚本会生成以下文件：

```text
dist/NEU-WakeUP.app
dist/NEU-WakeUP-macos-<架构>.zip
dist/NEU-WakeUP-macos-<架构>.dmg
dist/NEU-WakeUP-macos-<架构>.sha256
```

其中 `<架构>` 为 `arm64` 或 `x86_64`。脚本使用 `--windowed`，双击应用时不会弹出终端窗口。GitHub Actions 会在 Intel 和 Apple Silicon runner 上分别构建，并在推送 `v*` 标签后自动创建 Release：

```bash
git tag v1.4.0
git push origin v1.4.0
```

工作流会先执行源码和打包后的 `--self-check`，通过后才上传发布文件。

公开分发且希望首次双击不出现开发者警告时，需要 Apple Developer Program 的 Developer ID 证书。仓库配置以下 Actions Secrets 后，工作流会自动签名、公证并装订公证票据：

```text
MACOS_CERTIFICATE
MACOS_CERTIFICATE_PASSWORD
MACOS_CODESIGN_IDENTITY
APPLE_ID
APPLE_TEAM_ID
APPLE_APP_PASSWORD
```

未配置证书时生成的是可运行的未公证版本，首次启动需要按上文说明右键选择“打开”。

## 项目文件

```text
neuwakeup/
├── neuwakeup.py                 # 课表获取、解析、CSV 导出和登录窗口
├── requirements.txt             # 源码依赖
├── build_exe.ps1                # Windows 无控制台 EXE 构建脚本
├── build_macos.sh               # macOS APP、ZIP 和 DMG 构建脚本
├── .github/workflows/build-macos.yml  # 双架构 macOS 构建与发布
├── dist/NEU-WakeUP.exe          # Windows 发布包
├── README.md                    # 使用与构建说明
└── .gitignore                   # 构建缓存和个人 CSV 忽略规则
```

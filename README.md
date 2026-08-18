# NEU WakeUP

从东北大学本科教务管理系统读取个人课表，完整合并普通课和实验课，并导出为 WakeUP 可以直接导入的 CSV 文件。

项目地址：<https://github.com/2711944586/neuwakeup>

## 能做什么

- 使用东北大学统一身份认证二维码登录，不需要在脚本中填写账号和密码。
- 启动时检查全部 Python 依赖，缺失或版本过低时自动安装/更新。
- 自动尝试教务系统直连；直连不可用时使用 WebVPN。
- 同时读取“我的课程”和“我的课表”接口，避免单一接口遗漏课程。
- 保留 `[实]` 实验子课程名称，正确提取教师、实验室、星期、节次和周次。
- 自动删除实验课地点末尾的班级分组，例如 `信息2402(29),信息2401(28)`。
- 过滤停课记录，合并重复记录。
- 导出前报告已排记录、实验课、未排课课程和时间冲突。
- 使用临时文件校验后原子替换 CSV，避免生成半截文件。
- 输出固定七列、UTF-8 with BOM 编码的 `{姓名}{学号}.csv`。

当前仅支持导出 WakeUP CSV。

## Windows 一键安装并运行

需要提前安装 [Python 3.9+](https://www.python.org/downloads/) 和 [Git](https://git-scm.com/downloads)。

打开 PowerShell，完整复制并执行下面这一段：

```powershell
git clone https://github.com/2711944586/neuwakeup.git
Set-Location neuwakeup
py -3 -m venv .venv
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

脚本首次启动时会检查 `requests`、`qrcode`、`prettytable`、`colorama`、`pycryptodome` 和 `Pillow`，缺失或版本过低时自动调用当前 Python 的 pip 安装。以上命令不需要激活虚拟环境，因此不会受到 PowerShell 执行策略限制。

以后再次使用时，进入项目目录执行一行命令即可：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

## Windows EXE 一键使用

如果已经拿到 `dist\NEU-WakeUP.exe`，双击它即可运行，不需要安装 Python 或任何依赖。程序会检查网络、自动弹出二维码窗口；微信完成授权后点击窗口中的“我已完成授权，继续”，程序会自动获取课表并在 EXE 同目录生成：

```text
姓名学号.csv
```

EXE 默认直接使用 `2026-2027-1`（2026-2027 年秋季学期），不会再询问学期或导出方式。生成文件名中的姓名和学号来自登录成功后的教务系统身份接口。若二维码窗口无法创建，程序会退回终端二维码和回车确认流程。

### 自行构建 EXE

构建机器需要 Windows、Python 3.9+ 和网络连接。PowerShell 在项目目录执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\build_exe.ps1
& .\dist\NEU-WakeUP.exe
```

构建脚本会创建独立的 `.build-venv`，安装依赖和 PyInstaller，并将单文件程序写入 `dist\NEU-WakeUP.exe`。`.build-venv`、`build`、`dist` 和 `.spec` 文件已加入忽略规则，不会污染源码提交。

源码仓库默认不提交 `dist` 中的 EXE；可以直接使用构建脚本生成，也可以在发布时单独分发 `NEU-WakeUP.exe`。

更新到最新版本后运行：

```powershell
git pull
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

## macOS / Linux 一键安装并运行

打开终端，完整复制并执行：

```bash
git clone https://github.com/2711944586/neuwakeup.git
cd neuwakeup
python3 -m venv .venv
./.venv/bin/python neuwakeup.py
```

以后再次运行：

```bash
./.venv/bin/python neuwakeup.py
```

## 程序内操作步骤

1. 程序检查教务系统和 WebVPN 网络连接。
2. EXE 会自动弹出二维码窗口；源码运行时按提示继续。
3. 使用绑定东北大学统一身份认证的微信扫码并完成授权。
4. EXE 中点击“我已完成授权，继续”；源码运行时按回车确认。
5. 程序验证姓名和学号，登录失败或二维码过期时最多自动重试三次。
6. EXE 默认使用 `2026-2027-1`；源码运行时可输入其他学期代码。
7. 查看完整性报告。没有星期或节次的课程会单独列出，因为这类课程无法写入 WakeUP。
8. 普通课和实验课合并、校验通过后，自动导出到程序目录。

默认生成文件名为 `{姓名}{学号}.csv`。源码和 EXE 都会把默认文件写入自身所在目录，不受启动命令所在目录影响。

## 可选命令参数

检查版本：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --version
```

不连接教务系统，检查实验课解析和 CSV 写入：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --self-check
```

指定学期：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --term 2026-2027-2
```

指定学期和输出位置。使用 `--output` 后，课程预览完成会直接写入该文件，不再询问导出方式：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --term 2026-2027-1 --output .\exports\schedule.csv
```

macOS/Linux 参数相同，只需把开头替换为 `./.venv/bin/python neuwakeup.py`。

## 导入 WakeUP

1. 将生成的 `{姓名}{学号}.csv` 传到手机。
2. 打开 WakeUP 课程表。
3. 进入导入功能，选择“从 CSV 导入”。
4. 选择生成的 CSV 文件并完成导入。
5. 对照教务系统检查课程名称、周次、星期、节次和地点。

WakeUP 官方 CSV 导入说明：<https://wakeup.fun/doc/import_from_csv.html>

## 实验课处理规则

实验课通常在“我的课程”接口中不完整，但会出现在课表网格的 `titleDetail` 中。本项目每次都会读取完整课表接口并与普通课程合并。

以如下教务信息为例：

```text
[实]商务数据分析与应用-商务数据采集
13周 袁媛 浑南校区 信息化管理实验室(文管学馆B208) 信息2402(29),信息2401(28)
```

导出时会得到：

- 课程名称：`[实]商务数据分析与应用-商务数据采集`
- 老师：`袁媛`
- 地点：`信息化管理实验室(文管学馆B208)`
- 周数：`13周`
- 星期和节次：使用教务系统该课表格中的实际数值

末尾的班级分组只用于教务展示，不会写入地点。若完整课表接口无法读取，程序会停止导出，不会生成可能遗漏实验课的部分 CSV。

## CSV 格式

列名和顺序固定如下：

| 列名 | 格式 |
| --- | --- |
| 课程名称 | 普通课程名或 `[实]` 实验子课程名 |
| 星期 | `1` 到 `7`，对应星期一到星期日 |
| 开始节数 | `1` 到 `12` |
| 结束节数 | `1` 到 `12` |
| 老师 | 教师姓名；未安排时显示“暂未安排教师” |
| 地点 | 教室或实验室；未安排时显示“暂未安排教室” |
| 周数 | 例如 `1-8周、10周`、`1-8周单` |

不要修改列名、列顺序或文件编码，否则 WakeUP 可能无法识别。

## 常见问题

### `git`、`py` 或 `python3` 找不到

重新安装 Git 和 Python。Windows 安装 Python 时勾选“Add Python to PATH”，安装完成后重新打开 PowerShell。

### 依赖自动安装失败

确认可以访问 Python 软件源，并确保当前用户对虚拟环境有写入权限。随后执行：

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 无法访问教务系统或 WebVPN

先使用浏览器确认至少能打开教务系统或东北大学 WebVPN。关闭代理软件后重试，并检查系统时间是否正确。

### 二维码无法扫描

确认微信绑定了东北大学统一身份认证。EXE 会自动打开二维码窗口；如果窗口创建失败，程序会显示终端二维码和备用链接。二维码过期后重新运行即可。

### 扫码后仍提示未登录

必须先在微信中完成“授权登录”，再点击二维码窗口的确认按钮或按终端回车。程序会清理旧会话并重新生成二维码，连续三次失败后才会停止。

### 提示“完整课程表获取失败”

程序故意停止导出，以防实验课或其他课程遗漏。确认学期代码已在教务系统开放，再重新运行；仍然失败时提交脱敏后的错误信息。

### 找不到导出的 CSV

默认文件位于程序目录：源码运行时是 `neuwakeup.py` 同级目录，EXE 运行时是 `NEU-WakeUP.exe` 同级目录。文件名为登录姓名和学号拼接后的 `.csv`。只有完整课表接口和七列校验都通过后才会生成。

## 隐私与安全

- 不要提交或分享生成的 CSV，其中包含姓名、学号和个人课表信息。
- 不要分享登录二维码、Cookie、姓名、学号或包含这些信息的截图。
- 程序不会把账号密码写入文件，也不会将课表上传到项目仓库。
- 课程信息以东北大学教务系统为准，导入 WakeUP 后必须人工核对。

## 项目文件

```text
neuwakeup/
├── neuwakeup.py      # 主程序
├── requirements.txt  # Python 依赖
├── build_exe.ps1     # Windows EXE 构建脚本
├── README.md         # 使用教程
└── .gitignore        # 本地文件忽略规则
```

## 反馈

在 <https://github.com/2711944586/neuwakeup/issues> 提交问题。请描述操作系统、Python 版本、学期代码和错误文本，并删除所有个人信息。

## 许可说明

当前仓库未附带 `LICENSE`。本项目基于已有课表转换脚本进行修改；公开分发或重新授权前，应确认原始代码的授权范围并保留必要的版权与来源声明。

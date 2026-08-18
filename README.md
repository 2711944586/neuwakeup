# NEU WakeUP

从东北大学本科教务管理系统读取个人课表，完整合并普通课和实验课，并导出为 WakeUP 可以直接导入的 CSV 文件。

项目地址：<https://github.com/2711944586/neuwakeup>

## 能做什么

- 使用东北大学统一身份认证二维码登录，不需要在脚本中填写账号和密码。
- 自动尝试教务系统直连；直连不可用时使用 WebVPN。
- 同时读取“我的课程”和“我的课表”接口，避免单一接口遗漏课程。
- 保留 `[实]` 实验子课程名称，正确提取教师、实验室、星期、节次和周次。
- 自动删除实验课地点末尾的班级分组，例如 `信息2402(29),信息2401(28)`。
- 过滤停课记录，合并重复记录。
- 输出固定七列、UTF-8 with BOM 编码的 `schedule.csv`。

当前只支持导出 WakeUP CSV，不包含小爱课程表等其他导出方式。

## Windows 一键安装并运行

需要提前安装 [Python 3.9+](https://www.python.org/downloads/) 和 [Git](https://git-scm.com/downloads)。

打开 PowerShell，完整复制并执行下面这一段：

```powershell
git clone https://github.com/2711944586/neuwakeup.git
Set-Location neuwakeup
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

以上命令不需要激活虚拟环境，因此不会受到 PowerShell 执行策略限制。

以后再次使用时，进入项目目录执行一行命令即可：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

更新到最新版本后运行：

```powershell
git pull
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

## macOS / Linux 一键安装并运行

打开终端，完整复制并执行：

```bash
git clone https://github.com/2711944586/neuwakeup.git
cd neuwakeup
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python neuwakeup.py
```

以后再次运行：

```bash
./.venv/bin/python neuwakeup.py
```

## 程序内操作步骤

1. 程序检查教务系统和 WebVPN 网络连接。
2. 阅读终端中的使用说明和警告，按回车继续。
3. 使用绑定东北大学微信企业号的微信扫描终端二维码。
4. 在微信中点击“授权登录”，完成后回到终端按回车。
5. 默认学期是 `2026-2027-1`，即“2026-2027年秋季学期”。直接按回车使用默认值。
6. 如需其他学期，输入 `学年-学年-学期`，例如 `2026-2027-2`。
7. 等待普通课和实验课合并完成，逐项检查终端预览。
8. 输入 `1`，生成 `schedule.csv`。

生成的文件始终位于 `neuwakeup.py` 所在目录，不受启动命令所在目录影响。

## 导入 WakeUP

1. 将生成的 `schedule.csv` 传到手机。
2. 打开 WakeUP 课程表。
3. 进入导入功能，选择“从 CSV 导入”。
4. 选择 `schedule.csv` 并完成导入。
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

### 无法访问教务系统或 WebVPN

先使用浏览器确认至少能打开教务系统或东北大学 WebVPN。关闭代理软件后重试，并检查系统时间是否正确。

### 二维码无法扫描

放大终端窗口后重新运行。也可以复制二维码下方显示的链接，使用微信打开。必须使用绑定东北大学微信企业号的账号。

### 扫码后仍提示未登录

必须先在微信中完成“授权登录”，再回到终端按回车。登录二维码过期时关闭程序并重新运行。

### 提示“完整课程表获取失败”

程序故意停止导出，以防实验课或其他课程遗漏。确认学期代码已在教务系统开放，再重新运行；仍然失败时提交脱敏后的错误信息。

### 找不到 `schedule.csv`

文件位于项目目录，也就是 `neuwakeup.py` 的同级目录。只有完整获取并在预览后输入 `1`，文件才会生成。

## 隐私与安全

- 不要提交或分享 `schedule.csv`，其中包含个人课表信息。
- 不要分享登录二维码、Cookie、姓名、学号或包含这些信息的截图。
- 程序不会把账号密码写入文件，也不会将课表上传到项目仓库。
- 课程信息以东北大学教务系统为准，导入 WakeUP 后必须人工核对。

## 项目文件

```text
neuwakeup/
├── neuwakeup.py      # 主程序
├── requirements.txt  # Python 依赖
├── README.md         # 使用教程
└── .gitignore        # 本地文件忽略规则
```

## 反馈

在 <https://github.com/2711944586/neuwakeup/issues> 提交问题。请描述操作系统、Python 版本、学期代码和错误文本，并删除所有个人信息。

## 许可说明

当前仓库未附带 `LICENSE`。本项目基于已有课表转换脚本进行修改；公开分发或重新授权前，应确认原始代码的授权范围并保留必要的版权与来源声明。

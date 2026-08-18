# NEU WakeUP

从东北大学本科教务系统读取个人课表，合并普通课和实验课，并生成 WakeUP 可直接导入的七列 CSV。

## 直接使用 EXE

Windows 用户直接双击 `dist\NEU-WakeUP.exe`：

1. 程序检查网络并弹出二维码登录窗口。
2. 使用绑定统一身份认证的微信扫码，完成授权后点击“我已完成授权，继续”。
3. 程序验证姓名和学号，自动读取默认学期 `2026-2027-1`。
4. 完整性检查通过后，在 EXE 同目录生成 `{姓名}{学号}.csv`。

EXE 已内置运行依赖，不需要安装 Python。二维码窗口不可用时，会自动退回终端二维码和回车确认流程。

## 从源码运行

需要 Python 3.9+。在项目目录执行：

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

源码首次启动会自动检查并安装或更新 `requests`、`qrcode`、`prettytable`、`colorama`、`pycryptodome` 和 `Pillow`。源码模式会显示终端教程，并允许输入其他学期代码。

macOS/Linux：

```bash
python3 -m venv .venv
./.venv/bin/python neuwakeup.py
```

## 构建 EXE

构建机器需要 Windows、Python 3.9+ 和网络连接。在项目目录运行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\build_exe.ps1
```

脚本会创建独立的 `.build-venv`，安装依赖和 PyInstaller，并输出 `dist\NEU-WakeUP.exe`。构建目录和 EXE 默认被 Git 忽略，避免把构建产物或个人数据加入源码提交。

## 登录与文件名

登录成功后，程序从教务系统身份接口读取姓名和学号，并使用安全文件名规则移除 Windows 不允许的字符。默认输出路径为：

```text
程序所在目录\姓名学号.csv
```

程序会清理旧会话；二维码失效、授权未完成或登录状态无效时，自动重新生成二维码，最多重试三次。完整课表接口失败时不会生成可能遗漏课程的 CSV。

## 实验课与完整性

程序同时读取“我的课程”和“我的课表”接口，并合并去重。实验课支持：

- 保留 `[实]`、`[实验]`、`[实践]`、`[上机]` 等课程名称。
- 解析教师、实验室、星期、节次和周次。
- 删除地点末尾仅用于教务展示的班级分组，例如 `信息2402(29),信息2401(28)`。
- 过滤停课记录。

没有星期或节次的未排课课程会在终端提示，因为 WakeUP 的 CSV 格式无法表达这类记录。已排课程、实验课数量、时间冲突和未排课程都会在导出前显示。

## CSV 格式

表头和列顺序固定为：

```text
课程名称,星期,开始节数,结束节数,老师,地点,周数
```

文件使用 UTF-8 with BOM 编码。星期范围为 `1-7`，节次范围为 `1-12`。导出前会校验表头、列数、节次范围和文本字段，并使用临时文件原子替换，避免生成半截文件。

## 命令参数

```powershell
# 查看版本
& .\.venv\Scripts\python.exe .\neuwakeup.py --version

# 运行本地解析、二维码图片和 CSV 自检，不访问教务系统
& .\.venv\Scripts\python.exe .\neuwakeup.py --self-check

# 指定学期
& .\.venv\Scripts\python.exe .\neuwakeup.py --term 2026-2027-2

# 指定输出路径，覆盖默认的姓名学号文件名
& .\.venv\Scripts\python.exe .\neuwakeup.py --term 2026-2027-1 --output .\exports\custom.csv

# 源码模式启动时询问学期
& .\.venv\Scripts\python.exe .\neuwakeup.py --ask-term
```

## 常见问题

### 二维码无法扫描

确认微信已绑定统一身份认证。二维码有有效期，过期后关闭程序重新运行。窗口创建失败时，使用终端显示的二维码或备用链接。

### 扫码后仍提示未登录

先在微信中完成授权，再点击窗口确认按钮。程序会清理会话并重试；连续三次失败后检查网络、系统时间和统一身份认证状态。

### 无法访问教务系统或 WebVPN

先用浏览器确认至少能打开教务系统或 WebVPN。检查网络、代理设置和系统时间，确认当前学期已经开放。

### 找不到 CSV

默认文件在程序或 EXE 同目录，文件名是登录姓名和学号拼接后的 `.csv`。只有完整课表和七列校验通过后才会生成。

### 依赖安装失败

确认网络和虚拟环境写入权限，然后手动执行：

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 隐私

- CSV 包含姓名、学号和个人课表，只保存在本地，不会被程序上传。
- 不要分享 CSV、二维码、Cookie 或包含个人信息的截图。
- `*.csv` 已加入 `.gitignore`，避免个人课表误提交。

## 文件结构

```text
neuwakeup/
├── neuwakeup.py      # 主程序
├── requirements.txt  # Python 依赖
├── build_exe.ps1     # Windows EXE 构建脚本
├── README.md         # 使用说明
└── .gitignore        # 本地文件忽略规则
```

导入 WakeUP 时选择生成的 CSV 文件，并在导入后核对课程名称、周次、星期、节次和地点。

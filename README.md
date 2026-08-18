# NEU WakeUP

将东北大学本科教务管理系统中的个人课表获取并导出为 WakeUP 课程表 CSV 文件。

项目仓库：<https://github.com/2711944586/neuwakeup>

## 功能

- 通过东北大学统一身份认证二维码登录。
- 自动判断教务系统内网或 WebVPN 访问方式。
- 默认获取 `2026-2027-1`，即“2026-2027年秋季学期”。
- 支持手动输入其他学期代码。
- 同时读取“我的课程”和“我的课表”接口，合并普通课与实验课，避免单一接口漏课。
- 保留 `[实]` 实验子课程名称，识别实验室并剥离末尾的班级分组信息。
- 查询教务系统返回的实际校区，过滤停课安排并去除重复记录。
- 导出 WakeUP 可导入的 UTF-8 BOM CSV 文件。

本项目当前只导出 WakeUP CSV，不支持小爱课程表或其他第三方课表服务。

## 使用前须知

课表内容以东北大学教务系统为准。本工具只负责读取和转换数据，导入 WakeUP 后请逐项核对课程、周次、节次和地点。

程序需要访问东北大学教务系统和统一身份认证服务。二维码及登录会话只应由本人使用，不要截图、转发或提交到公开仓库。

## 环境要求

- Windows、macOS 或 Linux
- Python 3.9 或更高版本
- 可以访问东北大学教务系统；校园网外环境需要 WebVPN 能正常打开
- 绑定东北大学微信企业号的微信账号

## 安装

Windows PowerShell：

```powershell
git clone https://github.com/2711944586/neuwakeup.git
Set-Location neuwakeup

py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

如果 PowerShell 不允许激活虚拟环境，也可以直接使用虚拟环境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS 或 Linux：

```bash
git clone https://github.com/2711944586/neuwakeup.git
cd neuwakeup

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 运行

```powershell
python .\1.py
```

macOS 或 Linux 使用：

```bash
python 1.py
```

按程序提示操作：

1. 阅读提示并按回车继续。
2. 使用绑定东北大学微信企业号的微信扫描二维码。
3. 在微信中完成授权后回到终端按回车。
4. 默认使用 `2026-2027-1`。直接按回车即可；如需其他学期，输入例如 `2026-2027-2`。
5. 程序同时读取“我的课程”和包含实验课明细的“我的课表”接口，再合并结果。
6. 检查终端显示的普通课与 `[实]` 实验课预览，输入 `1` 导出 CSV。

导出的文件位置为脚本所在目录的 `schedule.csv`。在 WakeUP 课程表中选择 CSV 导入即可，导入说明见：<https://wakeup.fun/doc/import_from_csv.html>。

## CSV 格式

文件固定使用以下七列，列顺序不能调整：

| 列名 | 内容 |
| --- | --- |
| 课程名称 | 教务系统中的课程名称 |
| 星期 | `1` 到 `7`，分别表示星期一到星期日 |
| 开始节数 | `1` 到 `12` |
| 结束节数 | `1` 到 `12` |
| 老师 | 教师名称 |
| 地点 | 教室；未安排时为“暂未安排教室” |
| 周数 | 例如 `1-8周、10周` |

文件采用 UTF-8 with BOM 编码，以兼容 Windows 和 WakeUP 的导入流程。

## 常见问题

### 网络检查失败

先确认浏览器可以打开东北大学教务系统或 WebVPN。程序会先尝试教务系统，再尝试 WebVPN；两者都无法访问时会退出。

### 扫码后登录失败

确认使用的是绑定东北大学微信企业号的微信，并在微信中完成“授权登录”。授权完成后再回到终端按回车。登录会话失效时，关闭程序重新扫码。

### 两套课表接口都失败

确认输入的学期代码已经在教务系统中开放，并检查终端输出的接口错误信息。为了避免遗漏实验课，“我的课表”完整接口失败时程序不会生成部分 CSV。课程数据格式发生变化时，应先保存脱敏错误信息，再在项目仓库提交 Issue。

### 找不到导出的文件

文件始终写入 `1.py` 所在目录，而不是当前 PowerShell 的工作目录。请检查脚本目录中的 `schedule.csv`。

### 依赖安装失败

确认使用的是 Python 3.9 或更高版本，并在虚拟环境中重新执行：

```powershell
python -m pip install -r requirements.txt
```

## 测试

项目包含普通课、实验课、教室提取、班级分组剥离、去重和不完整导出保护测试：

```powershell
python -m unittest discover -s tests -v
```

## 开源与许可

当前仓库未附带 `LICENSE` 文件。本项目是在已有课表转换脚本基础上进行修改和维护；在发布或重新授权前，请确认原始代码的授权范围，并按要求保留必要的版权和来源声明。在许可证确认之前，不应将整份代码声明为完全原创或附加新的开源许可证。

## 反馈

请在项目仓库提交 Issue：<https://github.com/2711944586/neuwakeup/issues>。提交日志或截图前，请删除姓名、学号、课程、教师、地点、Cookie、二维码和任何登录信息。

# NEU WakeUP

从东北大学本科教务系统读取当前用户课表，合并普通课与实验课，并生成 WakeUP 可直接导入的七列 CSV。默认学期为 `2026-2027-1`（2026-2027 年秋季学期）。

## Windows 一键使用

仓库已提供 `dist\NEU-WakeUP.exe`。双击后不会弹出命令行窗口：

1. 等待登录窗口出现。
2. 使用绑定统一身份认证的微信完成授权。
3. 点击窗口中的“继续”。
4. 成功后，CSV 会写入 EXE 同目录，文件名为 `{姓名}{学号}.csv`。

程序完成后会显示保存位置。网络、登录或课表接口失败时会提示错误，并且不会生成不完整 CSV。

## 从源码运行

需要 Python 3.9+。源码首次启动会自动检查并安装或更新 `requirements.txt` 中的依赖：

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe .\neuwakeup.py
```

常用检查命令：

```powershell
& .\.venv\Scripts\python.exe .\neuwakeup.py --self-check
& .\.venv\Scripts\python.exe .\neuwakeup.py --version
```

源码模式保留终端教程和学期输入；EXE 固定使用默认学期，避免无控制台环境等待输入。

## CSV 与完整性

CSV 表头和列顺序固定为：

```text
课程名称,星期,开始节数,结束节数,老师,地点,周数
```

文件使用 UTF-8 with BOM。程序会解析普通课和实验/实践课的教师、地点、星期、节次及周次，过滤停课记录，合并去重，并检查列数、节次范围、空字段和时间冲突。未排星期或节次的记录会被提示；完整课表接口失败时直接停止导出，避免遗漏。

写文件采用临时文件加原子替换，程序只在校验通过后生成最终 CSV。姓名、学号、Cookie、二维码链接和课表只保存在运行内存或本地 CSV，不会上传到本项目。

## 构建 EXE

构建需要 Windows、Python 3.9+ 和网络连接：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\build_exe.ps1
```

脚本使用独立的 `.build-venv`，生成无控制台的 `dist\NEU-WakeUP.exe`。构建缓存会被忽略，发布 EXE 会保留并提交到仓库。

## Android APK 可行性

目标流程在技术上可行，但当前仓库没有伪造的 APK。要实现“手机内直接唤起微信授权、生成 CSV、交给 WakeUP 导入”，必须先具备以下外部条件：

- 微信开放平台 AppID、已审核的 Android 包名和签名指纹。
- HTTPS 授权回调服务，以及由服务端保管的微信 AppSecret。
- 学校 CAS/企业微信允许将微信授权结果交换为教务系统登录态的接口或合作配置。
- Android 端的 CSV 分享权限和 WakeUP 导入 Intent。

可靠的生产流程应为：

```text
Android APK → 微信 SDK 授权 → HTTPS 后端回调 → 短期教务会话
           → 获取并校验课表 → 生成 CSV → FileProvider/ACTION_VIEW → WakeUP
```

当前二维码地址属于网页扫码登录流程，普通 APK 直接打开该 URL 不能自动获得同一 CAS 会话，也不能安全绕过微信授权。AppSecret、Cookie 和会话令牌不能写入 APK。拿到上述授权资料后，应使用 Kotlin/Android SDK 实现移动端登录和网络层，并复用本项目的 CSV 字段与完整性规则。

WakeUP 官方 CSV 教程支持通过“用其他应用打开”选择 WakeUP 导入。Android 端可使用 `FileProvider` 分享 `text/csv`，优先尝试 WakeUP 包名 `com.suda.yzune.wakeupschedule`，失败时回退系统选择器；最终是否直接打开仍以用户设备上安装的 WakeUP 版本为准。

## 项目文件

```text
neuwakeup/
├── neuwakeup.py          # 课表获取、解析、CSV 导出和登录窗口
├── requirements.txt      # 源码依赖
├── build_exe.ps1         # Windows 无控制台 EXE 构建脚本
├── dist\NEU-WakeUP.exe   # 可直接运行的 Windows 发布包
├── README.md             # 使用与移动端方案说明
└── .gitignore            # 构建缓存和个人 CSV 忽略规则
```

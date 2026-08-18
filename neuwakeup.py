import importlib
import importlib.metadata
import importlib.util
import os
import re
import subprocess
import sys


PROJECT_VERSION = "1.3.0"
MINIMUM_PYTHON = (3, 9)
REQUIRED_DEPENDENCIES = (
    ("requests", "requests", "2.32.4"),
    ("qrcode", "qrcode", "8.2"),
    ("prettytable", "prettytable", "3.10.0"),
    ("colorama", "colorama", "0.4.6"),
    ("pycryptodome", "Crypto", "3.20.0"),
    ("Pillow", "PIL", "10.4.0"),
)


def version_numbers(value):
    numbers = [int(number) for number in re.findall(r"\d+", value)]
    return tuple((numbers + [0, 0, 0])[:3])


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def configure_frozen_io():
    """Keep a windowed EXE from writing to a missing console stream."""
    if not is_frozen():
        return
    for stream_name in ("stdout", "stderr"):
        if getattr(sys, stream_name, None) is None:
            setattr(sys, stream_name, open(os.devnull, "w", encoding="utf-8"))


def dependency_problems():
    problems = []
    for package_name, module_name, minimum_version in REQUIRED_DEPENDENCIES:
        try:
            installed_version = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"{package_name}>={minimum_version}")
            continue
        if importlib.util.find_spec(module_name) is None or version_numbers(installed_version) < version_numbers(minimum_version):
            problems.append(f"{package_name}>={minimum_version}")
            continue
        try:
            importlib.import_module(module_name)
        except Exception:
            sys.modules.pop(module_name, None)
            problems.append(f"{package_name}>={minimum_version}")
    return problems


def ensure_dependencies():
    if sys.version_info < MINIMUM_PYTHON:
        required_version = ".".join(str(part) for part in MINIMUM_PYTHON)
        raise SystemExit(f"需要 Python {required_version} 或更高版本，当前版本为 {sys.version.split()[0]}。")
    if is_frozen():
        print("依赖环境检查通过（EXE 已内置依赖）。")
        return

    problems = dependency_problems()
    if not problems:
        print("依赖环境检查通过。")
        return

    print("检测到缺失或版本过低的依赖，正在自动安装/更新：")
    print("  " + " ".join(problems))
    try:
        pip_check = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if pip_check.returncode != 0:
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)

        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "--timeout",
            "30",
            *problems,
        ]
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "依赖自动安装失败。请检查网络和Python写入权限，然后执行：\n"
            f"{sys.executable} -m pip install -r requirements.txt"
        ) from exc

    importlib.invalidate_caches()
    remaining = dependency_problems()
    if remaining:
        raise SystemExit("依赖安装后仍不可用：" + "、".join(remaining))
    print("依赖安装/更新完成。")


if __name__ == "__main__":
    configure_frozen_io()
    ensure_dependencies()


import argparse
import csv
import os
import random
import tempfile
import time
import traceback
import uuid
from pathlib import Path

import colorama
import prettytable
import qrcode
import requests
from Crypto.Cipher import AES


colorama.init(autoreset=True)

session = requests.Session()
session.headers.update({
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
})
using_webvpn = False
REQUEST_TIMEOUT = (5, 20)
DEFAULT_TERMCODE = "2026-2027-1"
DEFAULT_TERMNAME = "2026-2027年秋季学期"
CSV_HEADER = ["课程名称", "星期", "开始节数", "结束节数", "老师", "地点", "周数"]
UNKNOWN_TEACHER = "暂未安排教师"
UNKNOWN_ROOM = "暂未安排教室"
WEBVPN_AES_KEY = b"b0A58a69394ce73@"


class LoginCancelledError(RuntimeError):
    """Raised when the user closes the QR authorization window."""


def request_json(method, url, **kwargs):
    """Send an authenticated request and return a validated JSON object."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    response = session.request(method, url, **kwargs)
    response.raise_for_status()
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"接口返回的不是有效JSON：{url}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"接口返回格式错误：{url}")
    if "code" in payload and payload["code"] not in (0, "0", None):
        raise RuntimeError(f"接口返回错误：{payload.get('desc', payload['code'])}")
    return payload


def checked_request(method, url, **kwargs):
    """Send a request used by the login flow with a finite timeout."""
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    response = session.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def check_network():
    global using_webvpn
    print("正在检查网络连接，请稍等...")

    try:
        response = session.get("https://jwxt.neu.edu.cn", timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            print(colorama.Fore.LIGHTBLACK_EX + "内网访问")
            return
        print(colorama.Fore.LIGHTBLACK_EX + f"教务系统访问状态码: {response.status_code}")
    except requests.RequestException:
        pass

    print(colorama.Fore.LIGHTBLACK_EX + "WebVPN访问")
    try:
        response = session.get("https://webvpn.neu.edu.cn", timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            using_webvpn = True
            return
        print(colorama.Fore.RED + "无法访问WebVPN, 但这可能不是你的问题.")
        print(colorama.Fore.LIGHTBLACK_EX + f"访问状态码: {response.status_code}" + colorama.Style.RESET_ALL)
    except requests.RequestException:
        print(colorama.Fore.RED + "无法访问WebVPN, 请检查你的网络链接后重试.")
        print(colorama.Fore.LIGHTBLACK_EX + f"错误信息：\n{traceback.format_exc()}")
    except Exception:
        print(colorama.Fore.RED + "无法访问WebVPN, 发生未知错误, 请稍后重试.")
        print(colorama.Fore.LIGHTBLACK_EX + f"错误信息：\n{traceback.format_exc()}")

    if is_frozen():
        show_runtime_message("NEU WakeUP", "无法访问教务系统或 WebVPN，请检查网络后重试。", error=True)
    else:
        input("按回车键退出程序...")
    sys.exit(1)


def encrypt_webvpn_host(urlroot):
    """Encrypt a WebVPN host using the protocol's existing compatible format."""
    cipher = AES.new(
        WEBVPN_AES_KEY,
        AES.MODE_CFB,
        WEBVPN_AES_KEY,
        segment_size=128,
    )
    padded_host = urlroot.ljust(len(urlroot) // 16 * 16 + 16, "\0").encode()
    return cipher.encrypt(padded_host)[:len(urlroot)].hex()


def set_webvpn(url):
    if not using_webvpn:
        return url

    protocol, url = url.split("://", 1)
    urlroot, urlpath = url.split("/", 1)

    if "qyQrLogin" in urlpath:
        urlpath = urlpath + "&service=https://webvpn.neu.edu.cn/login?cas_login=true"
        return protocol + "://" + urlroot + "/" + urlpath
    if "checkQRCodeScan" in urlpath:
        prepath, postpath = urlpath.split("?", 1)
        urlpath = prepath + "?vpn-12-o2-pass.neu.edu.cn&" + postpath
        return "https://webvpn.neu.edu.cn/https/62304135386136393339346365373340a0e0b72cc4cb43c8bc1d6f66c806db/" + urlpath

    return (
        f"https://webvpn.neu.edu.cn/{protocol}/62304135386136393339346365373340"
        + encrypt_webvpn_host(urlroot)
        + "/"
        + urlpath
    )


def extract_user_identity(datas):
    if not isinstance(datas, dict):
        raise RuntimeError("当前用户接口返回格式错误")

    def first_value(keys):
        for key in keys:
            value = datas.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    username = first_value(("userName", "realName", "name"))
    userid = first_value((
        "studentNo",
        "studentNumber",
        "studentId",
        "userCode",
        "userId",
        "account",
        "loginName",
    ))
    if not username or not userid:
        raise RuntimeError("登录状态无效")
    return username, userid


def get_current_user():
    response_json = request_json(
        "GET",
        set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/api/home/currentUser.do"),
    )
    return extract_user_identity(response_json.get("datas"))


def show_runtime_message(title, message, error=False):
    """Show a user-facing message in a windowed EXE without leaking session data."""
    if not is_frozen():
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        dialog_root = tk.Tk()
        dialog_root.withdraw()
        if error:
            messagebox.showerror(title, message, parent=dialog_root)
        else:
            messagebox.showinfo(title, message, parent=dialog_root)
        dialog_root.destroy()
    except Exception:
        return


def show_qr_confirmation(qr_url):
    """Show the login dialog and fall back safely when Tk cannot start."""
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)

    root = None
    try:
        import tkinter as tk
        from PIL import Image, ImageDraw, ImageTk

        root = tk.Tk()
        root.title("NEU WakeUP | 安全登录")
        root.resizable(False, False)
        root.configure(bg="#F6F7F9")
        root.attributes("-topmost", True)
        window_width, window_height = 560, 680
        root.geometry(f"{window_width}x{window_height}")
        root.update_idletasks()
        left = max((root.winfo_screenwidth() - window_width) // 2, 0)
        top = max((root.winfo_screenheight() - window_height) // 2, 0)
        root.geometry(f"{window_width}x{window_height}+{left}+{top}")

        font_family = "Microsoft YaHei UI"
        bg = "#F6F7F9"
        ink = "#18232D"
        muted = "#687681"
        border = "#D9E0E7"
        accent = "#2F65D9"
        accent_hover = "#2453BC"
        accent_dark = "#2A5BC4"
        white = "#FFFFFF"
        canvas = tk.Canvas(root, width=window_width, height=window_height, bg=bg, highlightthickness=0)
        canvas.pack()

        def render_surface(button_fill=accent):
            """Render the static surface at 4x, then downsample for clean edges."""
            scale = 4
            artwork = Image.new("RGB", (window_width * scale, window_height * scale), bg)
            draw = ImageDraw.Draw(artwork)

            def box(x1, y1, x2, y2):
                return tuple(int(value * scale) for value in (x1, y1, x2, y2))

            def rounded(x1, y1, x2, y2, radius, fill, outline=None, width=1):
                draw.rounded_rectangle(
                    box(x1, y1, x2, y2),
                    radius=int(radius * scale),
                    fill=fill,
                    outline=outline,
                    width=max(1, int(width * scale)) if outline else 1,
                )

            draw.line((40 * scale, 80 * scale, 520 * scale, 80 * scale), fill=border, width=scale)
            rounded(130, 178, 430, 478, 10, white, border)
            rounded(100, 548, 460, 596, 6, button_fill)
            return ImageTk.PhotoImage(artwork.resize((window_width, window_height), Image.Resampling.LANCZOS))

        background_photo = render_surface()
        background_item = canvas.create_image(0, 0, anchor="nw", image=background_photo)
        canvas.background_photo = background_photo
        canvas.create_rectangle(40, 32, 44, 52, fill=accent, outline="")
        canvas.create_text(56, 42, text="NEU WakeUP", anchor="w", fill=ink, font=(font_family, 18, "bold"))
        canvas.create_text(520, 42, text="安全登录", anchor="e", fill=muted, font=(font_family, 10))
        canvas.create_text(280, 114, text="微信扫码授权", fill=ink, font=(font_family, 20, "bold"))
        canvas.create_text(280, 143, text="授权完成后点击继续", fill=muted, font=(font_family, 10))

        image = qr.make_image(fill_color="black", back_color="white")
        image = image.get_image() if hasattr(image, "get_image") else image
        image = image.resize((248, 248), Image.Resampling.NEAREST)
        photo = ImageTk.PhotoImage(image)
        canvas.create_image(280, 328, image=photo)
        canvas.qr_photo = photo

        status_dot = canvas.create_oval(140, 508, 148, 516, fill=accent, outline="")
        status_text = canvas.create_text(160, 512, text="等待微信授权", anchor="w", fill=accent_dark, font=(font_family, 10))
        confirmed = False
        button_enabled = True
        button_hover = False
        button_label = None

        def set_status(message, color=accent_dark):
            canvas.itemconfigure(status_text, text=message, fill=color)

        def refresh_surface(button_fill):
            photo = render_surface(button_fill)
            canvas.background_photo = photo
            canvas.itemconfigure(background_item, image=photo)

        def confirm_login():
            nonlocal confirmed, button_enabled
            if not button_enabled:
                return
            confirmed = True
            button_enabled = False
            set_status("已确认，正在检查登录状态...")
            refresh_surface("#B8C6E6")
            canvas.itemconfigure(status_dot, fill="#8DA4D7")
            canvas.itemconfigure(button_label, fill="#F4F6FC")
            root.after(120, root.destroy)

        def cancel_login():
            root.destroy()

        button_label = canvas.create_text(280, 572, text="继续", fill=white, font=(font_family, 11, "bold"))

        def update_button_hover(event):
            nonlocal button_hover
            inside = 100 <= event.x <= 460 and 548 <= event.y <= 596
            if not button_enabled or inside == button_hover:
                return
            button_hover = inside
            refresh_surface(accent_hover if inside else accent)

        canvas.bind("<Motion>", update_button_hover)
        canvas.bind("<Leave>", lambda _event: refresh_surface(accent) if button_enabled else None)
        canvas.bind("<Button-1>", lambda event: confirm_login() if 100 <= event.x <= 460 and 548 <= event.y <= 596 else None)
        root.protocol("WM_DELETE_WINDOW", cancel_login)
        root.bind("<Return>", lambda _event: confirm_login())
        root.bind("<Escape>", lambda _event: cancel_login())
        root.after(800, lambda: root.attributes("-topmost", False))
        root.mainloop()
        return confirmed
    except Exception as exc:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        if is_frozen():
            show_runtime_message(
                "NEU WakeUP",
                "二维码窗口无法打开，请确认系统支持桌面窗口后重试。",
                error=True,
            )
            return False
        print(colorama.Fore.YELLOW + f"无法打开二维码窗口，将使用终端二维码：{exc}")
        qr.print_ascii(invert=True)
        print(colorama.Fore.LIGHTBLACK_EX + "二维码链接：" + qr_url)
        input("微信完成授权后按回车继续；取消请直接关闭程序：")
        return True


def perform_qr_login_attempt():
    session.cookies.clear()
    session.headers.pop("referer", None)
    u_uuid = str(uuid.uuid4())
    u_qrurl = f"https://pass.neu.edu.cn/tpass/qyQrLogin?uuid={u_uuid}"
    u_checkurl = f"https://pass.neu.edu.cn/tpass/checkQRCodeScan?random={random.random():.16f}&uuid={u_uuid}"
    if not show_qr_confirmation(set_webvpn(u_qrurl)):
        raise LoginCancelledError("用户取消了扫码登录")

    if not using_webvpn:
        checked_request("GET", u_checkurl)
        checked_request(
            "GET",
            "https://pass.neu.edu.cn/tpass/login?service=https%3A%2F%2Fjwxt.neu.edu.cn%2Fjwapp%2Fsys%2Fhomeapp%2Findex.do",
            allow_redirects=False,
        )
        checked_request(
            "GET",
            "https://pass.neu.edu.cn/tpass/login?service=https%3A%2F%2Fjwxt.neu.edu.cn%2Fjwapp%2Fsys%2Fhomeapp%2Findex.do%3FcontextPath%3D%2Fjwapp",
        )
    else:
        checked_request("GET", "https://webvpn.neu.edu.cn")
        session.headers.update({
            "referer": "https://webvpn.neu.edu.cn/https/62304135386136393339346365373340a0e0b72cc4cb43c8bc1d6f66c806db/tpass/login?service=https%3A%2F%2Fwebvpn.neu.edu.cn%2Flogin%3Fcas_login%3Dtrue",
        })
        checked_request("GET", set_webvpn(u_checkurl))
        checked_request("GET", "https://webvpn.neu.edu.cn/http/62304135386136393339346365373340baf6bc2bc4cb43c8bc1d6f66c806db/jwapp/sys/homeapp/index.do")


def neucas_qr_login(max_attempts=3):
    if max_attempts < 1:
        raise ValueError("max_attempts 必须大于 0")
    last_error = None
    for attempt in range(1, max_attempts + 1):
        print(colorama.Fore.YELLOW + f"\n请使用微信扫码登录（第 {attempt}/{max_attempts} 次）")
        try:
            perform_qr_login_attempt()
            return get_current_user()
        except LoginCancelledError:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                print(colorama.Fore.YELLOW + "尚未检测到有效登录，二维码可能已过期，将重新生成。")
                time.sleep(1)
    raise RuntimeError("扫码登录验证失败，请确认微信授权后重试") from last_error


def print_welcome(user=None):
    username, userid = user or get_current_user()
    print(f"\n欢迎您，{username} ({userid})！")
    return username, userid


def application_directory():
    """Return the directory where the script or the packaged EXE lives."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def safe_filename_component(value):
    component = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(value).strip())
    component = re.sub(r"\s+", "", component).rstrip(". ")
    if component.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT1"}:
        component = "_" + component
    return component or "unknown"


def default_output_path(user):
    username, userid = user
    filename = f"{safe_filename_component(username)}{safe_filename_component(userid)}.csv"
    return application_directory() / filename


def term_name_for_code(termcode):
    start_year, end_year, semester = termcode.split("-")
    semester_name = {"1": "秋季学期", "2": "春季学期", "3": "夏季学期"}[semester]
    return f"{start_year}-{end_year}年{semester_name}"


def is_valid_termcode(termcode):
    match = re.fullmatch(r"(\d{4})-(\d{4})-([123])", termcode)
    return match is not None and int(match.group(1)) + 1 == int(match.group(2))


def get_termcode(term_override=None, prompt=True):
    if term_override is not None:
        if not is_valid_termcode(term_override):
            raise ValueError(f"学期代码格式错误：{term_override}")
        termname = term_name_for_code(term_override)
        print(f"指定学期为：{termname} ({term_override})")
        return term_override, termname

    termcode = DEFAULT_TERMCODE
    termname = DEFAULT_TERMNAME
    print(f"默认学期为：{termname} ({termcode})")
    if not prompt:
        return termcode, termname
    inputtermcode = input("如需更改学期请输入学期代码 (格式如2026-2027-1), 否则直接回车：").strip()
    if inputtermcode:
        if not is_valid_termcode(inputtermcode):
            print(colorama.Fore.RED + "学期代码格式错误，使用默认学期")
        else:
            termcode = inputtermcode
            termname = term_name_for_code(termcode)
    return termcode, termname


def validate_course_row(row):
    if len(row) != 7:
        raise RuntimeError(f"课程数据列数错误：{row!r}")
    try:
        day = int(row[1])
        begin = int(row[2])
        end = int(row[3])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"课程节次数据错误：{row!r}") from exc
    if not 1 <= day <= 7 or not 1 <= begin <= end <= 12:
        raise RuntimeError(f"课程星期或节次超出范围：{row!r}")
    if not all(isinstance(row[index], str) and row[index].strip() for index in (0, 4, 5, 6)):
        raise RuntimeError(f"课程文本字段为空：{row!r}")
    row[1], row[2], row[3] = day, begin, end
    return row


def deduplicate_rows(rows):
    result = []
    seen = set()
    for row in rows:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def normalize_week_text(value):
    week = str(value).strip().replace(",", "、").replace("，", "、")
    week = week.replace("(", "").replace(")", "")
    return re.sub(r"^第(?=\d)", "", week)


def is_schedule_detail(value):
    return isinstance(value, str) and re.match(r"^\s*第?\d+(?:[-、,，]\d+)*周", value) is not None


def arranged_course_name(course_name, title_detail):
    experiment_pattern = re.compile(r"^[\[【](?:实|实验|实践|上机)[\]】]")
    for item in title_detail:
        if not isinstance(item, str) or is_schedule_detail(item):
            continue
        candidate = item.strip().lstrip("•●").strip()
        if experiment_pattern.match(candidate):
            return candidate
    return str(course_name).strip()


def normalize_teachers(value):
    teachers = re.sub(r"\[.*?\]", "", str(value).split("/")[-1]).strip()
    return teachers or UNKNOWN_TEACHER


def is_class_group_token(value):
    value = value.strip().replace("，", ",").replace("、", ",")
    return re.search(r"[^,\s]+\(\d+\)(?:,[^,\s]+\(\d+\))*$", value) is not None


def parse_arranged_detail(detail, teachers):
    if not is_schedule_detail(detail):
        return None
    parts = detail.split()
    if any("停课" in part for part in parts):
        return None

    week = normalize_week_text(parts[0])
    body = [part.replace("*", "").strip() for part in parts[1:] if part.strip()]
    campus_index = next((index for index, part in enumerate(body) if part.endswith("校区")), None)

    detail_teacher = teachers
    if campus_index is not None:
        before_campus = body[:campus_index]
        if detail_teacher == UNKNOWN_TEACHER and before_campus:
            detail_teacher = "、".join(before_campus)
        place_parts = body[campus_index + 1:]
    else:
        place_parts = body

    teacher_names = {
        name.strip()
        for name in re.split(r"[,，、/\s]+", detail_teacher)
        if name.strip() and detail_teacher != UNKNOWN_TEACHER
    }
    place_parts = [part for part in place_parts if part not in teacher_names and not part.endswith("校区")]

    while len(place_parts) > 1 and is_class_group_token(place_parts[-1]):
        place_parts.pop()
    if len(place_parts) == 1 and is_class_group_token(place_parts[0]):
        place_parts.clear()

    place_name = " ".join(place_parts).strip() or UNKNOWN_ROOM
    return week, place_name, detail_teacher


def get_campuscodes(term):
    payload = request_json(
        "GET",
        set_webvpn(
            f"https://jwxt.neu.edu.cn/jwapp/sys/homeapp/api/home/student/getMyScheduledCampus.do?termCode={term}"
        ),
    )
    campuses = payload.get("datas")
    if not isinstance(campuses, list):
        raise RuntimeError("校区接口返回格式错误")
    codes = []
    for campus in campuses:
        if not isinstance(campus, dict) or campus.get("id") is None:
            continue
        code = str(campus["id"])
        if code not in codes:
            codes.append(code)
    if not codes:
        raise RuntimeError("当前学期没有可用校区")
    return codes


def unarranged_course_names(schedule_list, campuscode):
    unarranged = schedule_list.get("notArrangeList", [])
    if unarranged is None:
        return []
    if not isinstance(unarranged, list):
        raise RuntimeError(f"校区 {campuscode} 的未排课列表格式错误")

    names = []
    for item in unarranged:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("courseName") or item.get("name") or "").strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def parse_arranged_campus(term, campuscode, headers):
    schedule_json = request_json(
        "POST",
        set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/api/home/student/getMyScheduleDetail.do"),
        headers=headers,
        data={"termCode": term, "campusCode": campuscode, "type": "term"},
    )
    schedule_list = schedule_json.get("datas")
    if not isinstance(schedule_list, dict) or not isinstance(schedule_list.get("arrangedList"), list):
        raise RuntimeError(f"校区 {campuscode} 的课表接口返回格式错误")

    rows = []
    for each_class in schedule_list["arrangedList"]:
        try:
            course_name = each_class["courseName"]
            day_of_week = each_class["dayOfWeek"]
            begin_section = each_class["beginSection"]
            end_section = each_class["endSection"]
            title_detail = each_class["titleDetail"]
            weeks_and_teachers = each_class["weeksAndTeachers"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"校区 {campuscode} 的课程字段缺失") from exc
        if not isinstance(title_detail, list):
            raise RuntimeError(f"校区 {campuscode} 的周次地点字段格式错误")
        course_name = arranged_course_name(course_name, title_detail)
        teachers = normalize_teachers(weeks_and_teachers)
        for detail in title_detail:
            parsed_detail = parse_arranged_detail(detail, teachers)
            if parsed_detail is None:
                continue
            week, place_name, detail_teacher = parsed_detail
            rows.append(validate_course_row([
                course_name,
                day_of_week,
                begin_section,
                end_section,
                detail_teacher,
                place_name,
                week,
            ]))
    return rows, unarranged_course_names(schedule_list, campuscode)


def convert_arranged_by_WoDeKeBiao(term):
    headers = {
        "origin": "https://webvpn.neu.edu.cn" if using_webvpn else "https://jwxt.neu.edu.cn",
        "Referer": set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/home/index.html?av=&contextPath=/jwapp"),
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    }
    rows = []
    unarranged = []
    for campuscode in get_campuscodes(term):
        campus_rows, campus_unarranged = parse_arranged_campus(term, campuscode, headers)
        rows.extend(campus_rows)
        for course_name in campus_unarranged:
            if course_name not in unarranged:
                unarranged.append(course_name)
    return deduplicate_rows(rows), unarranged


def convert_arranged_by_WoDeKeCheng(term):
    headers = {
        "origin": "https://webvpn.neu.edu.cn" if using_webvpn else "https://jwxt.neu.edu.cn",
        "Referer": set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/home/index.html?av=&contextPath=/jwapp"),
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    }
    schedule_json = request_json(
        "GET",
        set_webvpn(f"https://jwxt.neu.edu.cn/jwapp/sys/homeapp/api/home/student/courses.do?termCode={term}"),
        headers=headers,
    )
    schedule_list = schedule_json.get("datas")
    if not isinstance(schedule_list, list):
        raise RuntimeError("我的课程接口返回格式错误")

    dayofweeklist = {"星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4, "星期五": 5, "星期六": 6, "星期日": 7, "星期天": 7}
    section_names = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二")
    sectionlist = {f"第{name}节": index for index, name in enumerate(section_names, 1)}
    rows = []
    for each_class in schedule_list:
        try:
            course_name = each_class["courseName"]
            class_date_and_place = each_class["classDateAndPlace"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("我的课程接口的课程字段缺失") from exc
        if class_date_and_place is None:
            continue
        if not isinstance(class_date_and_place, str):
            raise RuntimeError("我的课程接口的地点字段格式错误")
        for raw_info in class_date_and_place.split("，"):
            single_info = raw_info.split("/", 4)
            if len(single_info) < 4:
                raise RuntimeError(f"课程地点信息字段不足：{raw_info!r}")
            weeks = normalize_week_text(re.sub(r"\[.*?\]", "", single_info[0]))
            day_text = re.sub(r"\[.*?\]", "", single_info[1]).strip()
            section = re.sub(r"\[.*?\]", "", single_info[2]).strip()
            if day_text not in dayofweeklist:
                raise RuntimeError(f"无法识别星期：{day_text!r}")
            section_parts = section.split("-", 1)
            if section_parts[0] not in sectionlist or (len(section_parts) == 2 and section_parts[1] not in sectionlist):
                raise RuntimeError(f"无法识别节次：{section!r}")
            begin_section = sectionlist[section_parts[0]]
            end_section = sectionlist[section_parts[1]] if len(section_parts) == 2 else begin_section
            teachers = re.sub(r"\[.*?\]", "", single_info[3]).strip() or UNKNOWN_TEACHER
            place_name = single_info[4].replace("*", "").strip() if len(single_info) == 5 else UNKNOWN_ROOM
            if place_name == "停课":
                continue
            if not place_name:
                place_name = UNKNOWN_ROOM
            rows.append(validate_course_row([
                course_name,
                dayofweeklist[day_text],
                begin_section,
                end_section,
                teachers,
                place_name,
                weeks,
            ]))
    return deduplicate_rows(rows)


def week_number_key(value):
    normalized = normalize_week_text(value)
    week_numbers = set()
    for part in normalized.split("、"):
        numbers = [int(number) for number in re.findall(r"\d+", part)]
        if not numbers:
            continue
        values = range(numbers[0], numbers[-1] + 1) if len(numbers) >= 2 else numbers
        if part.endswith("单"):
            values = [number for number in values if number % 2 == 1]
        elif part.endswith("双"):
            values = [number for number in values if number % 2 == 0]
        week_numbers.update(values)
    return tuple(sorted(week_numbers)) if week_numbers else (normalized,)


def normalized_place(value):
    place = re.sub(r"^\S+校区\s*", "", value.strip())
    return re.sub(r"\s+", "", place)


def merge_teachers(first, second):
    if first == UNKNOWN_TEACHER:
        return second
    if second == UNKNOWN_TEACHER:
        return first
    names = []
    for value in (first, second):
        for name in re.split(r"[,，、/]+", value):
            name = name.strip()
            if name and name not in names:
                names.append(name)
    return ",".join(names)


def merge_course_rows(primary_rows, arranged_rows):
    merged = [validate_course_row(list(row)) for row in primary_rows]
    for arranged_row in arranged_rows:
        arranged_row = validate_course_row(list(arranged_row))
        identity = (
            arranged_row[0].strip(),
            arranged_row[1],
            arranged_row[2],
            arranged_row[3],
            week_number_key(arranged_row[6]),
        )
        matched_index = None
        for index, existing in enumerate(merged):
            existing_identity = (
                existing[0].strip(),
                existing[1],
                existing[2],
                existing[3],
                week_number_key(existing[6]),
            )
            if existing_identity != identity:
                continue
            same_place = normalized_place(existing[5]) == normalized_place(arranged_row[5])
            if same_place or UNKNOWN_ROOM in (existing[5], arranged_row[5]):
                matched_index = index
                break

        if matched_index is None:
            merged.append(arranged_row)
            continue

        existing = merged[matched_index]
        existing[4] = merge_teachers(existing[4], arranged_row[4])
        if existing[5] == UNKNOWN_ROOM or (
            normalized_place(existing[5]) == normalized_place(arranged_row[5])
            and len(arranged_row[5]) > len(existing[5])
        ):
            existing[5] = arranged_row[5]
    return deduplicate_rows(merged)


def get_complete_schedule(term):
    primary_rows = []
    primary_error = None
    try:
        primary_rows = convert_arranged_by_WoDeKeCheng(term)
    except Exception as exc:
        primary_error = exc

    try:
        arranged_rows, unarranged_courses = convert_arranged_by_WoDeKeBiao(term)
    except Exception as exc:
        raise RuntimeError(
            "完整课表接口获取失败。为避免遗漏实验课，本次不会导出不完整CSV。"
        ) from exc

    rows = merge_course_rows(primary_rows, arranged_rows)
    if not rows:
        raise RuntimeError("教务系统没有返回任何已排课程，请确认学期是否已经开放排课。")
    arranged_names = {row[0] for row in rows}
    unarranged_courses = [name for name in unarranged_courses if name not in arranged_names]
    return rows, primary_error, unarranged_courses


def schedule_conflicts(rows):
    occupied = {}
    conflicts = []
    for row in rows:
        weeks = week_number_key(row[6])
        if not weeks or not all(isinstance(week, int) for week in weeks):
            continue
        for week in weeks:
            for section in range(row[2], row[3] + 1):
                key = (week, row[1], section)
                previous = occupied.get(key)
                if previous is None:
                    occupied[key] = row[0]
                elif previous != row[0]:
                    description = f"第{week}周 星期{row[1]} 第{section}节：{previous} / {row[0]}"
                    if description not in conflicts:
                        conflicts.append(description)
    return conflicts


def print_completeness_summary(rows, unarranged_courses):
    experiment_count = sum(
        re.match(r"^[\[【](?:实|实验|实践|上机)[\]】]", row[0]) is not None
        for row in rows
    )
    print("==========完整性检查==========")
    print(f"已排课程记录：{len(rows)} 条")
    print(f"其中实验/实践课程：{experiment_count} 条")
    print(f"未排星期或节次的课程：{len(unarranged_courses)} 门")
    if unarranged_courses:
        print(colorama.Fore.YELLOW + "以下课程因教务系统尚未安排星期/节次，无法写入WakeUP CSV：")
        for course_name in unarranged_courses:
            print(colorama.Fore.YELLOW + f"  - {course_name}")

    conflicts = schedule_conflicts(rows)
    print(f"检测到的时间冲突：{len(conflicts)} 处")
    for conflict in conflicts:
        print(colorama.Fore.YELLOW + f"  - {conflict}")
    print("============================")


def write_schedule_csv(rows, output_path):
    validated_rows = [validate_course_row(list(row)) for row in rows]
    output_path = Path(output_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-",
        suffix=".tmp",
        dir=output_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8-sig") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(CSV_HEADER)
            writer.writerows(validated_rows)

        with temporary_path.open("r", newline="", encoding="utf-8-sig") as check_file:
            written_rows = list(csv.reader(check_file))
        if not written_rows or written_rows[0] != CSV_HEADER:
            raise RuntimeError("CSV表头校验失败")
        if len(written_rows) - 1 != len(validated_rows) or any(len(row) != 7 for row in written_rows[1:]):
            raise RuntimeError("CSV记录数量或列数校验失败")
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path


def parse_arguments():
    parser = argparse.ArgumentParser(description="东北大学课表导出为WakeUP CSV")
    parser.add_argument("--term", help="指定学期代码，例如 2026-2027-1")
    parser.add_argument("--output", type=Path, help="指定CSV输出路径，默认使用姓名+学号.csv并写入程序目录")
    parser.add_argument("--ask-term", action="store_true", help="启动时询问学期；EXE默认直接使用默认学期")
    parser.add_argument("--self-check", action="store_true", help="运行内置解析和CSV检查，不访问教务系统")
    parser.add_argument("--version", action="version", version=f"NEU WakeUP {PROJECT_VERSION}")
    arguments = parser.parse_args()
    if arguments.term is not None and not is_valid_termcode(arguments.term):
        parser.error("--term 格式应为连续学年的学期代码，例如 2026-2027-1")
    return arguments


def run_self_check():
    title_detail = [
        "[实]示例实验课程",
        "13周 示例教师 浑南校区 示例实验室(教学楼A101) 班级甲(1),班级乙(2)",
    ]
    course_name = arranged_course_name("示例实验课程", title_detail)
    detail = parse_arranged_detail(title_detail[1], "示例教师")
    expected_detail = ("13周", "示例实验室(教学楼A101)", "示例教师")
    if course_name != title_detail[0] or detail != expected_detail:
        raise RuntimeError("实验课解析自检失败")

    row = validate_course_row([course_name, 3, 5, 8, detail[2], detail[1], detail[0]])
    identity = extract_user_identity({"userName": "测试用户", "userCode": "00000000"})
    if identity != ("测试用户", "00000000"):
        raise RuntimeError("登录身份解析自检失败")
    if default_output_path(identity).name != "测试用户00000000.csv":
        raise RuntimeError("按姓名学号命名自检失败")
    encrypted_host = encrypt_webvpn_host("jwxt.neu.edu.cn")
    if len(encrypted_host) != len("jwxt.neu.edu.cn") * 2 or not re.fullmatch(r"[0-9a-f]+", encrypted_host):
        raise RuntimeError("WebVPN加密格式自检失败")
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data("https://example.com/neuwakeup-self-check")
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    if qr_image.size[0] <= 0 or qr_image.size[1] <= 0:
        raise RuntimeError("二维码图片生成自检失败")
    with tempfile.TemporaryDirectory() as temporary_directory:
        output_path = write_schedule_csv([row], Path(temporary_directory) / "schedule.csv")
        if not output_path.is_file():
            raise RuntimeError("CSV写入自检失败")
    print("内置自检通过：实验课解析、七列格式和原子写入均正常。")


def prettytable_print(list_for_csv):
    table = prettytable.PrettyTable()
    table.field_names = CSV_HEADER
    for row in list_for_csv:
        table.add_row(row)
    print(table)


def main():
    arguments = parse_arguments()
    if arguments.self_check:
        run_self_check()
        return 0

    check_network()
    if is_frozen():
        print("NEU WakeUP 一键导出模式：二维码窗口即将打开。")
    else:
        print("==========使用教程==========")
        print("1.打开程序，仔细阅读并理解本使用教程，而后按回车键继续")
        print("2.使用绑定了东北大学微信企业号的微信扫描程序显示的二维码")
        print("3.扫描二维码，在微信点击授权登录后，在二维码窗口点击确认")
        print("4.核对普通课和实验课预览，导出为WakeUP课程表CSV文件")
        print(colorama.Fore.YELLOW + "===========警告=============")
        print(colorama.Fore.YELLOW + "本工具仅提供辅助作用，如果生成的课程表与系统中显示的不一致，请时刻以教务系统中显示的为准！")
        print(colorama.Fore.YELLOW + "请从可信的项目发布渠道获取最新版本，以免出现问题。")
        print("===========================")
        input("请仔细阅读上述内容后，按回车键继续...")

    user = neucas_qr_login()
    user = print_welcome(user)
    termcode, termname = get_termcode(
        arguments.term,
        prompt=not is_frozen(),
    )
    print(f"获取{termname} ({termcode}) 课程表中...")
    try:
        list_for_csv, primary_error, unarranged_courses = get_complete_schedule(termcode)
    except Exception as schedule_error:
        print(colorama.Fore.RED + "完整课程表获取失败")
        print(colorama.Fore.RED + "错误信息：" + str(schedule_error))
        if is_frozen():
            show_runtime_message(
                "课程表获取失败",
                "完整课程表获取失败，未生成 CSV。请检查网络、登录状态和当前学期是否开放。",
                error=True,
            )
        else:
            input("为避免导出遗漏课程，本次不生成CSV。按回车键退出程序...")
        return 1
    if primary_error is not None:
        print(colorama.Fore.YELLOW + "“我的课程”接口不可用，已使用完整课表接口生成课程。")
        print(colorama.Fore.LIGHTBLACK_EX + "接口信息：" + str(primary_error))

    print_completeness_summary(list_for_csv, unarranged_courses)
    while True:
        print("==========获取结束==========")
        print("以下是获取到的课程表预览：")
        prettytable_print(list_for_csv)
        print("导出方式：")
        print("1. 导出至csv文件 (导出至WakeUP课程表)")
        choice = "1" if is_frozen() or arguments.output is not None else input("请选择导出方式(输入数字1): ").strip()
        if choice == "1":
            output_path = arguments.output or default_output_path(user)
            output_path = write_schedule_csv(list_for_csv, output_path)
            print(colorama.Fore.GREEN + f"课程表已成功导出至{output_path}，请使用WakeUP课程表导入该文件。")
            print("   如何导入? https://wakeup.fun/doc/import_from_csv.html")
            print(colorama.Fore.YELLOW + "提示：导入后请与教务系统中的课程表进行比对。如存在区别，请以教务系统显示为准！" + colorama.Style.RESET_ALL)
            if is_frozen():
                show_runtime_message("导出完成", f"课程表已保存到：\n{output_path}\n\n现在可以在 WakeUP 中导入该 CSV。")
                return 0
            if arguments.output is not None:
                return 0
            input("按回车键退出程序...")
            return 0
        print("无效的选择。")
        input("按回车键重试...")
        print("\033[2J\033[H", end="")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LoginCancelledError:
        sys.exit(0)
    except Exception:
        if is_frozen():
            show_runtime_message(
                "NEU WakeUP 运行失败",
                "程序未能完成导出，未生成 CSV。请检查网络、登录状态和当前学期后重试。",
                error=True,
            )
        else:
            print(colorama.Fore.RED + "程序运行出现预料之外的异常，错误信息：\n" + traceback.format_exc())
            input("按回车键退出程序...")
        sys.exit(1)

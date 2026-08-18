import csv
import random
import re
import sys
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

    input("按回车键退出程序...")
    sys.exit(1)


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

    cipher = AES.new(
        b"b0A58a69394ce73@",
        AES.MODE_CFB,
        b"b0A58a69394ce73@",
        segment_size=128,
    )
    cipher_text = cipher.encrypt(urlroot.ljust(len(urlroot) // 16 * 16 + 16, "\0").encode())
    return (
        f"https://webvpn.neu.edu.cn/{protocol}/62304135386136393339346365373340"
        + cipher_text[:len(urlroot)].hex()
        + "/"
        + urlpath
    )


def neucas_qr_login():
    print(colorama.Fore.YELLOW + "\n请使用微信扫码登录")
    u_uuid = str(uuid.uuid4())
    u_qrurl = f"https://pass.neu.edu.cn/tpass/qyQrLogin?uuid={u_uuid}"
    u_checkurl = f"https://pass.neu.edu.cn/tpass/checkQRCodeScan?random={random.random():.16f}&uuid={u_uuid}"
    qr = qrcode.QRCode()
    qr.add_data(set_webvpn(u_qrurl))
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print(colorama.Fore.LIGHTBLACK_EX + "无法扫码？使用微信打开链接：" + set_webvpn(u_qrurl))
    input("在微信中点击“授权登录”后请按回车继续...")

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


def print_welcome():
    response_json = request_json(
        "GET",
        set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/api/home/currentUser.do"),
    )
    try:
        username = response_json["datas"]["userName"]
        userid = response_json["datas"]["userId"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("当前用户接口返回格式错误") from exc
    print(f"\n欢迎您，{username} ({userid})！")
    return username


def term_name_for_code(termcode):
    start_year, end_year, semester = termcode.split("-")
    semester_name = {"1": "秋季学期", "2": "春季学期", "3": "夏季学期"}[semester]
    return f"{start_year}-{end_year}年{semester_name}"


def get_termcode():
    termcode = DEFAULT_TERMCODE
    termname = DEFAULT_TERMNAME
    print(f"默认学期为：{termname} ({termcode})")
    inputtermcode = input("如需更改学期请输入学期代码 (格式如2026-2027-1), 否则直接回车：").strip()
    if inputtermcode:
        match = re.fullmatch(r"(\d{4})-(\d{4})-([123])", inputtermcode)
        if match is None or int(match.group(1)) + 1 != int(match.group(2)):
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
    return rows


def convert_arranged_by_WoDeKeBiao(term):
    headers = {
        "origin": "https://webvpn.neu.edu.cn" if using_webvpn else "https://jwxt.neu.edu.cn",
        "Referer": set_webvpn("https://jwxt.neu.edu.cn/jwapp/sys/homeapp/home/index.html?av=&contextPath=/jwapp"),
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    }
    rows = []
    for campuscode in get_campuscodes(term):
        rows.extend(parse_arranged_campus(term, campuscode, headers))
    return deduplicate_rows(rows)


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
        arranged_rows = convert_arranged_by_WoDeKeBiao(term)
    except Exception as exc:
        raise RuntimeError(
            "完整课表接口获取失败。为避免遗漏实验课，本次不会导出不完整CSV。"
        ) from exc

    rows = merge_course_rows(primary_rows, arranged_rows)
    if not rows:
        raise RuntimeError("教务系统没有返回任何已排课程，请确认学期是否已经开放排课。")
    return rows, primary_error


def prettytable_print(list_for_csv):
    table = prettytable.PrettyTable()
    table.field_names = CSV_HEADER
    for row in list_for_csv:
        table.add_row(row)
    print(table)


if __name__ == "__main__":
    try:
        check_network()
        print("==========使用教程==========")
        print("1.打开程序，仔细阅读并理解本使用教程，而后按回车键继续")
        print("2.使用绑定了东北大学微信企业号的微信扫描程序显示的二维码 (或使用微信打开给出的链接)")
        print("3.扫描二维码，在微信点击授权登录后，在程序中按下回车键，等待运行结束")
        print("4.核对普通课和实验课预览，导出为WakeUP课程表CSV文件")
        print(colorama.Fore.YELLOW + "===========警告=============")
        print(colorama.Fore.YELLOW + "本工具仅提供辅助作用，如果生成的课程表与系统中显示的不一致，请时刻以教务系统中显示的为准！")
        print(colorama.Fore.YELLOW + "本项目仓库：https://github.com/2711944586/neuwakeup")
        print(colorama.Fore.YELLOW + "请尽量从本项目仓库获取最新版本，以免出现问题。")
        print("===========================")
        input("请仔细阅读上述内容后，按回车键继续...")

        neucas_qr_login()
        print_welcome()
        termcode, termname = get_termcode()
        print(f"获取{termname} ({termcode}) 课程表中...")
        try:
            list_for_csv, primary_error = get_complete_schedule(termcode)
        except Exception as schedule_error:
            print(colorama.Fore.RED + "完整课程表获取失败")
            print(colorama.Fore.RED + "错误信息：" + str(schedule_error))
            input("为避免导出遗漏课程，本次不生成CSV。按回车键退出程序...")
            sys.exit(1)
        if primary_error is not None:
            print(colorama.Fore.YELLOW + "“我的课程”接口不可用，已使用完整课表接口生成课程。")
            print(colorama.Fore.LIGHTBLACK_EX + "接口信息：" + str(primary_error))

        while True:
            print("==========获取结束==========")
            print("以下是获取到的课程表预览：")
            prettytable_print(list_for_csv)
            print("导出方式：")
            print("1. 导出至csv文件 (导出至WakeUP课程表)")
            choice = input("请选择导出方式(输入数字1): ").strip()
            if choice == "1":
                output_path = Path(__file__).resolve().parent / "schedule.csv"
                with output_path.open("w", newline="", encoding="utf-8-sig") as output_file:
                    writer = csv.writer(output_file)
                    writer.writerow(CSV_HEADER)
                    writer.writerows(list_for_csv)
                print(colorama.Fore.GREEN + f"课程表已成功导出至{output_path}，请使用WakeUP课程表导入该文件。")
                print("   如何导入? https://wakeup.fun/doc/import_from_csv.html")
                print(colorama.Fore.YELLOW + "提示：导入后请与教务系统中的课程表进行比对。如存在区别，请以教务系统显示为准！" + colorama.Style.RESET_ALL)
                input("按回车键退出程序...")
                sys.exit(0)
            print("无效的选择。")
            input("按回车键重试...")
            print("\033[2J\033[H", end="")
    except Exception:
        print(colorama.Fore.RED + "程序运行出现预料之外的异常，错误信息：\n" + traceback.format_exc())
        input("按回车键退出程序...")
        sys.exit(1)

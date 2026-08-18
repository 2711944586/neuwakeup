import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("neuwakeup", PROJECT_ROOT / "1.py")
schedule = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(schedule)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = iter(payloads)

    def request(self, method, url, **kwargs):
        return FakeResponse(next(self.payloads))


class ScheduleParserTests(unittest.TestCase):
    def test_experiment_course_uses_subcourse_name_and_real_room(self):
        payload = {
            "datas": {
                "arrangedList": [{
                    "courseName": "商务数据分析与应用",
                    "dayOfWeek": 3,
                    "beginSection": 5,
                    "endSection": 8,
                    "titleDetail": [
                        "[实]商务数据分析与应用-商务数据采集",
                        "13周 袁媛 浑南校区 信息化管理实验室(文管学馆B208) 信息2402(29),信息2401(28)",
                    ],
                    "weeksAndTeachers": "13周/袁媛",
                }],
            },
        }
        original_session = schedule.session
        schedule.session = FakeSession([payload])
        try:
            rows = schedule.parse_arranged_campus("2026-2027-1", "01", {})
        finally:
            schedule.session = original_session

        self.assertEqual(rows, [[
            "[实]商务数据分析与应用-商务数据采集",
            3,
            5,
            8,
            "袁媛",
            "信息化管理实验室(文管学馆B208)",
            "13周",
        ]])

    def test_first_title_detail_is_not_skipped_when_it_is_a_schedule(self):
        parsed = schedule.parse_arranged_detail("1-2周 南湖校区 机房A", "张三")
        self.assertEqual(parsed, ("1-2周", "机房A", "张三"))

    def test_merge_keeps_experiment_and_enriches_normal_course(self):
        primary = [["普通课程", 1, 1, 2, "张三", schedule.UNKNOWN_ROOM, "1-8周"]]
        arranged = [
            ["普通课程", 1, 1, 2, "张三", "教室A", "1-8周"],
            ["[实]普通课程-实验一", 4, 5, 6, "李四", "实验室B", "9周"],
        ]
        rows = schedule.merge_course_rows(primary, arranged)
        self.assertEqual(rows, [
            ["普通课程", 1, 1, 2, "张三", "教室A", "1-8周"],
            ["[实]普通课程-实验一", 4, 5, 6, "李四", "实验室B", "9周"],
        ])

    def test_complete_schedule_refuses_partial_export(self):
        with patch.object(schedule, "convert_arranged_by_WoDeKeCheng", return_value=[]), patch.object(
            schedule,
            "convert_arranged_by_WoDeKeBiao",
            side_effect=RuntimeError("unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "不会导出不完整CSV"):
                schedule.get_complete_schedule("2026-2027-1")

    def test_csv_header_remains_unchanged(self):
        self.assertEqual(schedule.CSV_HEADER, [
            "课程名称",
            "星期",
            "开始节数",
            "结束节数",
            "老师",
            "地点",
            "周数",
        ])


if __name__ == "__main__":
    unittest.main()

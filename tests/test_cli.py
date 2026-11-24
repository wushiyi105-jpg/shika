import csv
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from shika import cli, reader, store

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "card-1.jpg")

GOOD = {
    "lines": ["星野科技", "林知远", "产品总监", "手机 138 0013 8000",
              "邮箱 lin.zhiyuan@xingye.com", "深圳市南山区科苑路8号12层"],
    "fields": {"name": "林知远", "company": "星野科技", "title": "产品总监",
               "mobile": "138 0013 8000", "email": "lin.zhiyuan@xingye.com",
               "address": "深圳市南山区科苑路8号12层"},
    "confidence": "high",
    "note": "商务名片",
    "issues": [],
    "error": "",
}


class CliTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self):
        os.unlink(self.path)

    def run_cli(self, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(["--db", self.path] + argv)
        return code, buf.getvalue()

    def test_read_ok(self):
        with patch.object(reader, "read_card", return_value=GOOD):
            code, out = self.run_cli(["read", SAMPLE, "--lines"])
        self.assertEqual(code, 0)
        self.assertIn("林知远", out)
        self.assertIn("0: 星野科技", out)
        self.assertIn("把握：high", out)

    def test_read_prints_problems(self):
        bad = {**GOOD, "issues": [{"field": "mobile", "value": "13900139000",
                                   "reason": "卡片上找不到这行字"}]}
        with patch.object(reader, "read_card", return_value=bad):
            code, out = self.run_cli(["read", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("已丢弃", out)

    def test_read_model_down(self):
        broken = {"lines": [], "fields": {}, "confidence": "low", "note": "",
                  "issues": [], "error": "连不上视觉接口"}
        with patch.object(reader, "read_card", return_value=broken):
            code, out = self.run_cli(["read", SAMPLE])
        self.assertEqual(code, 1)
        self.assertIn("没读成", out)

    def test_add_saves(self):
        with patch.object(reader, "read_card", return_value=GOOD):
            code, out = self.run_cli(["add", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("已新建", out)
        conn = store.connect(self.path)
        try:
            self.assertEqual(len(store.list_contacts(conn)), 1)
        finally:
            conn.close()

    def test_add_second_time_merges(self):
        with patch.object(reader, "read_card", return_value=GOOD):
            self.run_cli(["add", SAMPLE])
            code, out = self.run_cli(["add", SAMPLE])
        self.assertEqual(code, 0)
        self.assertIn("已并入", out)

    def test_add_nothing_useful(self):
        empty = {**GOOD, "fields": {}, "issues": []}
        with patch.object(reader, "read_card", return_value=empty):
            code, out = self.run_cli(["add", SAMPLE])
        self.assertEqual(code, 1)
        self.assertIn("没东西可存", out)

    def test_list_empty(self):
        code, out = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("空的", out)

    def test_json_output(self):
        with patch.object(reader, "read_card", return_value=GOOD):
            code, out = self.run_cli(["read", SAMPLE, "--json"])
        self.assertEqual(code, 0)
        body = out[out.index("{"):]
        data = json.loads(body)
        self.assertEqual(data["card"]["mobile"], "13800138000")

    def test_export_csv(self):
        conn = store.connect(self.path)
        try:
            store.save_card(conn, {"name": "林知远", "mobile": "13800138000"})
        finally:
            conn.close()
        out_path = self.path + ".csv"
        try:
            code, out = self.run_cli(["export", "--csv", "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0][0], "姓名")
            self.assertEqual(rows[1][3], "13800138000")
        finally:
            os.unlink(out_path)

    def test_export_vcf(self):
        conn = store.connect(self.path)
        try:
            store.save_card(conn, {"name": "林知远", "mobile": "13800138000"})
        finally:
            conn.close()
        out_path = self.path + ".vcf"
        try:
            code, _ = self.run_cli(["export", "--vcf", "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("BEGIN:VCARD", text)
            self.assertIn("TEL;TYPE=CELL:13800138000", text)
        finally:
            os.unlink(out_path)

    def test_export_empty(self):
        self.assertEqual(self.run_cli(["export"])[0], 1)

    def test_show(self):
        conn = store.connect(self.path)
        try:
            store.save_card(conn, {"name": "林知远"}, lines=["林知远"], confidence="high")
        finally:
            conn.close()
        code, out = self.run_cli(["show", "1", "--lines"])
        self.assertEqual(code, 0)
        self.assertIn("来源：1 张卡", out)
        self.assertIn("0: 林知远", out)

    def test_show_missing(self):
        self.assertEqual(self.run_cli(["show", "7"])[0], 1)

    def test_rm(self):
        conn = store.connect(self.path)
        try:
            store.save_card(conn, {"name": "林知远"})
        finally:
            conn.close()
        code, out = self.run_cli(["rm", "1"])
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)

    def test_rm_missing(self):
        self.assertEqual(self.run_cli(["rm", "7"])[0], 1)

    def test_stats(self):
        code, out = self.run_cli(["stats"])
        self.assertEqual(code, 0)
        self.assertIn("contacts", out)


if __name__ == "__main__":
    unittest.main()

import json
import os
import unittest
from unittest.mock import patch

from shika import reader

LINES = ["星野科技", "林知远", "产品总监", "手机 138 0013 8000",
         "邮箱 lin.zhiyuan@xingye.com", "深圳市南山区科苑路8号12层"]


def fields(**kw):
    return {k: {"value": v, "line": 1} for k, v in kw.items()}


class VerifyTest(unittest.TestCase):
    def test_value_on_given_line_passes(self):
        good, issues = reader.verify_fields(fields(name="林知远"), LINES)
        self.assertEqual(good["name"], "林知远")
        self.assertEqual(issues, [])

    def test_spaces_do_not_matter(self):
        good, _ = reader.verify_fields({"mobile": {"value": "13800138000", "line": 3}}, LINES)
        self.assertEqual(good["mobile"], "13800138000")

    def test_fullwidth_matches(self):
        lines = ["星野科技　林知远"]
        good, _ = reader.verify_fields({"name": {"value": "林知远", "line": 0}}, lines)
        self.assertEqual(good["name"], "林知远")

    def test_wrong_line_but_text_exists(self):
        # 行号报错了，但整张卡里确实有这行字：不判幻觉
        good, issues = reader.verify_fields({"name": {"value": "林知远", "line": 9}}, LINES)
        self.assertEqual(good["name"], "林知远")
        self.assertEqual(issues, [])

    def test_not_on_card_at_all(self):
        good, issues = reader.verify_fields({"mobile": {"value": "13900139000", "line": 3}}, LINES)
        self.assertEqual(good, {})
        self.assertEqual(issues[0]["field"], "mobile")
        self.assertIn("找不到", issues[0]["reason"])

    def test_empty_value_ignored(self):
        good, issues = reader.verify_fields({"name": {"value": "  ", "line": 0}}, LINES)
        self.assertEqual(good, {})
        self.assertEqual(issues, [])

    def test_plain_string_field(self):
        good, _ = reader.verify_fields({"company": "星野科技"}, LINES)
        self.assertEqual(good["company"], "星野科技")

    def test_nothing_read_at_all(self):
        good, issues = reader.verify_fields(fields(name="林知远"), [])
        self.assertEqual(good, {})
        self.assertIn("一个字都没读出来", issues[0]["reason"])


class ExtractTest(unittest.TestCase):
    def test_normal(self):
        raw = json.dumps({"lines": LINES, "fields": {
            "name": {"value": "林知远", "line": 1},
            "company": {"value": "星野科技", "line": 0},
            "mobile": {"value": "138 0013 8000", "line": 3},
        }, "confidence": "high", "note": "一句话：商务名片"}, ensure_ascii=False)
        out = reader.extract(raw)
        self.assertEqual(out["fields"]["name"], "林知远")
        self.assertNotIn("一句话", out["note"])
        self.assertEqual(out["confidence"], "high")

    def test_code_fence(self):
        raw = "```json\n" + json.dumps({"lines": LINES, "fields": {"name": {"value": "林知远"}}},
                                       ensure_ascii=False) + "\n```"
        self.assertEqual(reader.extract(raw)["fields"]["name"], "林知远")

    def test_bad_json_returns_issue(self):
        out = reader.extract("林知远 星野科技 13800138000")
        self.assertEqual(out["fields"], {})
        self.assertTrue(out["issues"])

    def test_not_object(self):
        out = reader.extract(json.dumps([1, 2, 3]))
        self.assertIn("不是对象", out["issues"][0]["reason"])

    def test_fields_not_dict(self):
        out = reader.extract(json.dumps({"lines": LINES, "fields": ["林知远"]}))
        self.assertEqual(out["fields"], {})

    def test_bad_confidence_defaults(self):
        out = reader.extract(json.dumps({"lines": LINES, "fields": {}, "confidence": "很确定"}))
        self.assertEqual(out["confidence"], "medium")

    def test_blank_lines_dropped(self):
        out = reader.extract(json.dumps({"lines": ["", "  ", "星野科技"], "fields": {}}))
        self.assertEqual(out["lines"], ["星野科技"])


class ToEntryTest(unittest.TestCase):
    def test_problems_include_issues(self):
        result = {"fields": {"name": {"value": "林知远", "line": 1},
                             "mobile": {"value": "13900139000", "line": 3}},
                  "issues": [{"field": "mobile", "value": "13900139000", "reason": "卡片上找不到这行字"}]}
        card, problems = reader.to_entry(result)
        self.assertEqual(card["name"], "林知远")
        self.assertFalse(card["mobile"])
        self.assertTrue(any("已丢弃" in p for p in problems))

    def test_raw_kept_for_validation(self):
        result = {"fields": {"name": {"value": "林知远"}, "email": {"value": "lin(at)xingye"}},
                  "issues": []}
        card, problems = reader.to_entry(result)
        self.assertEqual(card["email_raw"], "lin(at)xingye")
        self.assertTrue(any("邮箱" in p for p in problems))

    def test_clean_card_has_no_problems(self):
        result = {"fields": {"name": {"value": "林知远"},
                             "mobile": {"value": "13800138000", "line": 3}}, "issues": []}
        card, problems = reader.to_entry(result)
        self.assertEqual(problems, [])
        self.assertEqual(card["mobile"], "13800138000")


class ReadCardTest(unittest.TestCase):
    def test_missing_key(self):
        with patch.object(reader, "vision_config", return_value={"api_key": "", "base_url": "x",
                                                                  "model": "m"}):
            out = reader.read_card("samples/card-1.jpg")
        self.assertIn("VISION_API_KEY", out["error"])

    def test_missing_file(self):
        out = reader.read_card("no-such-card.jpg",
                               config={"api_key": "x", "base_url": "http://127.0.0.1:1/v1",
                                       "model": "m"})
        self.assertIn("找不到图片", out["error"])

    def test_model_down(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "card-1.jpg")
        out = reader.read_card(path, config={"api_key": "x", "base_url": "http://127.0.0.1:1/v1",
                                            "model": "m", "timeout": 2})
        self.assertTrue(out["error"])
        self.assertEqual(out["fields"], {})


class EncodeTest(unittest.TestCase):
    def test_data_url_prefix(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "card-1.jpg")
        url = reader.encode_image(path)
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))
        self.assertGreater(len(url), 1000)

    def test_big_file_falls_back_without_pillow(self):
        # 超大且不是图片的文件：压不了就原样发，别崩
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00" * (reader.MAX_BYTES + 10))
            path = f.name
        try:
            url = reader.encode_image(path)
            self.assertTrue(url.startswith("data:image/bin;base64,"))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

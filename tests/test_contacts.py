import unittest

from shika import contacts


class PhoneTest(unittest.TestCase):
    def test_spaces_and_dashes(self):
        self.assertEqual(contacts.normalize_phone("138 0013 8000"), "13800138000")
        self.assertEqual(contacts.normalize_phone("138-0013-8000"), "13800138000")

    def test_plus86(self):
        self.assertEqual(contacts.normalize_phone("+86 138 0013 8000"), "13800138000")
        self.assertEqual(contacts.normalize_phone("0086 13800138000"), "13800138000")
        self.assertEqual(contacts.normalize_phone("86 13800138000"), "13800138000")

    def test_landline_with_area_code(self):
        self.assertEqual(contacts.normalize_phone("(010) 8888 6666"), "01088886666")

    def test_label_prefix_stripped(self):
        self.assertEqual(contacts.normalize_phone("手机 138 0013 8000"), "13800138000")

    def test_extension_cut(self):
        self.assertEqual(contacts.normalize_phone("010-88886666 转 801"), "01088886666")

    def test_not_a_phone(self):
        self.assertEqual(contacts.normalize_phone("12345"), "")
        self.assertEqual(contacts.normalize_phone(""), "")
        self.assertEqual(contacts.normalize_phone(None), "")

    def test_mobile_check(self):
        self.assertTrue(contacts.is_mobile("13800138000"))
        self.assertFalse(contacts.is_mobile("01088886666"))
        self.assertFalse(contacts.is_mobile("1380013800"))


class EmailTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(contacts.normalize_email("Lin.Zhiyuan@XingYe.com"), "lin.zhiyuan@xingye.com")

    def test_angle_brackets(self):
        self.assertEqual(contacts.normalize_email("<a@b.com>"), "a@b.com")

    def test_at_obfuscation(self):
        self.assertEqual(contacts.normalize_email("lin(at)xingye.com"), "lin@xingye.com")

    def test_fullwidth_at(self):
        self.assertEqual(contacts.normalize_email("a＠b.com"), "a@b.com")

    def test_invalid(self):
        self.assertEqual(contacts.normalize_email("a@b"), "")
        self.assertEqual(contacts.normalize_email("没有邮箱"), "")


class NameTest(unittest.TestCase):
    def test_strip_title_suffix(self):
        self.assertEqual(contacts.clean_name("林知远先生"), "林知远")

    def test_reject_company(self):
        self.assertEqual(contacts.clean_name("星野科技有限公司"), "")

    def test_reject_digits(self):
        self.assertEqual(contacts.clean_name("13800138000"), "")

    def test_keep_english(self):
        self.assertEqual(contacts.clean_name("Lin Zhiyuan"), "LinZhiyuan")


class NormalizeTest(unittest.TestCase):
    def test_mobile_moved_from_tel(self):
        card = contacts.normalize({"tel": "138 0013 8000"})
        self.assertEqual(card["mobile"], "13800138000")
        self.assertEqual(card["tel"], "")

    def test_landline_moved_to_tel(self):
        card = contacts.normalize({"mobile": "010-8888 6666"})
        self.assertEqual(card["mobile"], "")
        self.assertEqual(card["tel"], "01088886666")

    def test_all_fields_present(self):
        card = contacts.normalize({})
        self.assertEqual(set(card), set(contacts.FIELDS))

    def test_long_text_clipped(self):
        card = contacts.normalize({"address": "很" * 200})
        self.assertLessEqual(len(card["address"]), 80)


class ValidateTest(unittest.TestCase):
    def test_good_card(self):
        card = contacts.normalize({"name": "林知远", "mobile": "13800138000"})
        self.assertEqual(contacts.validate(card), [])

    def test_bad_email(self):
        card = contacts.normalize({"name": "林知远", "email": "a@b"})
        card["email_raw"] = "a@b"
        self.assertTrue(any("邮箱" in p for p in contacts.validate(card)))

    def test_bad_phone(self):
        card = contacts.normalize({"name": "林知远", "mobile": "1380013"})
        card["mobile_raw"] = "1380013"
        self.assertTrue(any("位数" in p for p in contacts.validate(card)))

    def test_no_contact_way(self):
        card = contacts.normalize({"name": "林知远", "company": "星野科技"})
        self.assertTrue(any("联系方式" in p for p in contacts.validate(card)))

    def test_no_name(self):
        card = contacts.normalize({"mobile": "13800138000"})
        self.assertTrue(any("姓名" in p for p in contacts.validate(card)))


class MergeTest(unittest.TestCase):
    def test_empty_does_not_overwrite(self):
        old = {"name": "林知远", "company": "星野科技", "mobile": "13800138000"}
        new = {"name": "", "company": "星野科技（深圳）", "mobile": ""}
        merged = contacts.merge(old, new)
        self.assertEqual(merged["name"], "林知远")
        self.assertEqual(merged["mobile"], "13800138000")
        self.assertEqual(merged["company"], "星野科技（深圳）")

    def test_longer_wins(self):
        old = {"address": "深圳南山"}
        new = {"address": "深圳市南山区科苑路8号12层"}
        self.assertEqual(contacts.merge(old, new)["address"], "深圳市南山区科苑路8号12层")

    def test_notes_joined_without_duplicates(self):
        old = {"note": "展会认识"}
        new = {"note": "展会认识"}
        self.assertEqual(contacts.merge(old, new)["note"], "展会认识")

    def test_contact_key_priority(self):
        self.assertEqual(contacts.contact_key({"mobile": "13800138000", "email": "a@b.com"}),
                         "m:13800138000")
        self.assertEqual(contacts.contact_key({"email": "a@b.com"}), "e:a@b.com")
        self.assertEqual(contacts.contact_key({"name": "林知远", "company": "星野"}),
                         "n:星野|林知远")
        self.assertEqual(contacts.contact_key({}), "")


class ExportTest(unittest.TestCase):
    CARD = {"name": "林知远", "company": "星野科技", "title": "产品总监",
            "mobile": "13800138000", "email": "lin.zhiyuan@xingye.com"}

    def test_vcard(self):
        v = contacts.to_vcard(self.CARD)
        self.assertTrue(v.startswith("BEGIN:VCARD"))
        self.assertTrue(v.endswith("END:VCARD"))
        self.assertIn("TEL;TYPE=CELL:13800138000", v)
        self.assertIn("\r\n", v)

    def test_csv_header(self):
        header, rows = contacts.to_csv_rows([self.CARD])
        self.assertEqual(header[0], "姓名")
        self.assertEqual(rows[0][3], "13800138000")

    def test_render(self):
        text = contacts.render_card(self.CARD, ["邮箱格式不对"])
        self.assertIn("林知远（星野科技）", text)
        self.assertIn("! 邮箱格式不对", text)


if __name__ == "__main__":
    unittest.main()

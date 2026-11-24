import tempfile
import unittest

from shika import contacts, store


CARD = {"name": "林知远", "company": "星野科技", "title": "产品总监",
        "mobile": "13800138000", "tel": "", "email": "lin.zhiyuan@xingye.com",
        "address": "", "note": "展会认识"}


class StoreTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        import os

        os.close(fd)
        self.conn = store.connect(self.path)

    def tearDown(self):
        self.conn.close()
        import os

        os.unlink(self.path)

    def test_add_new(self):
        saved = store.save_card(self.conn, CARD)
        self.assertTrue(saved["created"])
        self.assertEqual(saved["name"], "林知远")

    def test_same_mobile_merges(self):
        store.save_card(self.conn, CARD)
        again = store.save_card(self.conn, dict(CARD, title="高级产品总监", address="深圳南山"))
        self.assertFalse(again["created"])
        self.assertEqual(again["title"], "高级产品总监")
        self.assertEqual(again["address"], "深圳南山")
        self.assertEqual(len(store.list_contacts(self.conn)), 1)

    def test_same_email_merges_even_without_mobile(self):
        store.save_card(self.conn, {"name": "林知远", "email": "lin.zhiyuan@xingye.com"})
        again = store.save_card(self.conn, {"name": "", "email": "lin.zhiyuan@xingye.com",
                                            "mobile": "13800138000"})
        self.assertFalse(again["created"])
        self.assertEqual(again["mobile"], "13800138000")

    def test_same_name_and_company_merges(self):
        store.save_card(self.conn, {"name": "王珂", "company": "星野科技"})
        again = store.save_card(self.conn, {"name": "王珂", "company": "星野科技",
                                            "tel": "075512345678"})
        self.assertFalse(again["created"])

    def test_same_name_other_company_is_new(self):
        store.save_card(self.conn, {"name": "王珂", "company": "星野科技"})
        other = store.save_card(self.conn, {"name": "王珂", "company": "另一家"})
        self.assertTrue(other["created"])
        self.assertEqual(len(store.list_contacts(self.conn)), 2)

    def test_empty_fields_do_not_erase(self):
        store.save_card(self.conn, CARD)
        again = store.save_card(self.conn, dict(CARD, title="", company=""))
        self.assertEqual(again["company"], "星野科技")
        self.assertEqual(again["title"], "产品总监")

    def test_cards_kept_as_history(self):
        store.save_card(self.conn, CARD, lines=["星野科技", "林知远"], confidence="high",
                        problems=["邮箱格式不对"])
        cid = store.list_contacts(self.conn)[0]["id"]
        cards = store.cards_of(self.conn, cid)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["lines"][1], "林知远")
        self.assertEqual(cards[0]["problems"], ["邮箱格式不对"])

    def test_search(self):
        store.save_card(self.conn, CARD)
        self.assertEqual(len(store.list_contacts(self.conn, "星野")), 1)
        self.assertEqual(len(store.list_contacts(self.conn, "林知远")), 1)
        self.assertEqual(len(store.list_contacts(self.conn, "1380013")), 1)
        self.assertEqual(len(store.list_contacts(self.conn, "不存在")), 0)

    def test_delete_removes_cards_too(self):
        store.save_card(self.conn, CARD)
        cid = store.list_contacts(self.conn)[0]["id"]
        store.delete_contact(self.conn, cid)
        self.assertEqual(store.list_contacts(self.conn), [])
        self.assertEqual(store.cards_of(self.conn, cid), [])

    def test_stats(self):
        store.save_card(self.conn, CARD)
        store.save_card(self.conn, {"name": "王珂", "company": "星野科技"})
        s = store.stats(self.conn)
        self.assertEqual(s["contacts"], 2)
        self.assertEqual(s["with_phone"], 1)
        self.assertEqual(s["no_contact"], 1)

    def test_get_missing(self):
        self.assertIsNone(store.get_contact(self.conn, 999))

    def test_normalized_card_persist(self):
        card = contacts.normalize({"name": "林知远先生", "tel": "138 0013 8000"})
        saved = store.save_card(self.conn, card)
        self.assertEqual(saved["name"], "林知远")
        self.assertEqual(saved["mobile"], "13800138000")
        self.assertEqual(saved["tel"], "")


if __name__ == "__main__":
    unittest.main()

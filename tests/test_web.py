import base64
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from shika import reader, store, web

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "card-1.jpg")

GOOD = {
    "lines": ["星野科技", "林知远", "手机 138 0013 8000"],
    "fields": {"name": "林知远", "company": "星野科技", "mobile": "138 0013 8000"},
    "confidence": "high",
    "note": "商务名片",
    "issues": [],
    "error": "",
}


class WebTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.conn = store.connect(self.path)
        self.httpd = web.make_server(self.conn, port=0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.conn.close()
        os.unlink(self.path)

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path, timeout=5) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8")

    def post(self, path, payload):
        req = urllib.request.Request(self.base + path,
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_page(self):
        status, html = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("识卡", html)

    def test_contacts_empty(self):
        status, body = self.get("/api/contacts")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["items"], [])

    def test_read_ok(self):
        with open(SAMPLE, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        with patch.object(reader, "read_card", return_value=GOOD):
            status, d = self.post("/api/read", {"image_b64": b64, "filename": "card.jpg"})
        self.assertEqual(status, 200)
        self.assertEqual(d["card"]["mobile"], "13800138000")
        self.assertTrue(d["image_url"].startswith("/uploads/"))

    def test_read_no_image(self):
        status, d = self.post("/api/read", {})
        self.assertEqual(status, 400)

    def test_read_bad_base64(self):
        status, d = self.post("/api/read", {"image_b64": "@@@"})
        self.assertEqual(status, 400)

    def test_read_too_short(self):
        status, d = self.post("/api/read", {"image_b64": base64.b64encode(b"a").decode()})
        self.assertEqual(status, 400)

    def test_read_model_down(self):
        with open(SAMPLE, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        broken = {**GOOD, "error": "连不上视觉接口", "fields": {}}
        with patch.object(reader, "read_card", return_value=broken):
            status, d = self.post("/api/read", {"image_b64": b64})
        self.assertEqual(status, 502)

    def test_save(self):
        status, d = self.post("/api/save", {"card": {"name": "林知远", "mobile": "13800138000"},
                                            "lines": ["林知远"], "confidence": "high"})
        self.assertEqual(status, 200)
        self.assertTrue(d["created"])
        self.assertEqual(len(store.list_contacts(self.conn)), 1)

    def test_save_twice_merges(self):
        card = {"card": {"name": "林知远", "mobile": "13800138000"}, "lines": []}
        self.post("/api/save", card)
        _, d = self.post("/api/save", card)
        self.assertFalse(d["created"])

    def test_save_empty(self):
        status, d = self.post("/api/save", {"card": {}})
        self.assertEqual(status, 400)

    def test_export_csv(self):
        self.post("/api/save", {"card": {"name": "林知远", "mobile": "13800138000"}})
        status, body = self.get("/api/export?fmt=csv")
        self.assertEqual(status, 200)
        self.assertIn("姓名", body)
        self.assertIn("13800138000", body)

    def test_export_vcf(self):
        self.post("/api/save", {"card": {"name": "林知远", "mobile": "13800138000"}})
        status, body = self.get("/api/export?fmt=vcf")
        self.assertEqual(status, 200)
        self.assertIn("BEGIN:VCARD", body)

    def test_contact_detail(self):
        self.post("/api/save", {"card": {"name": "林知远"}, "lines": ["林知远"]})
        _, body = self.get("/api/contact?id=1")
        d = json.loads(body)
        self.assertEqual(d["contact"]["name"], "林知远")
        self.assertEqual(len(d["cards"]), 1)

    def test_contact_bad_id(self):
        self.assertEqual(self.get("/api/contact?id=abc")[0], 400)

    def test_404_get(self):
        self.assertEqual(self.get("/nope")[0], 404)

    def test_404_post(self):
        self.assertEqual(self.post("/api/nope", {})[0], 404)

    def test_upload_route_404(self):
        self.assertEqual(self.get("/uploads/nothing.jpg")[0], 404)


if __name__ == "__main__":
    unittest.main()

"""Offline tests for scripts/dm.py; all Instagram API calls are mocked."""
import json
import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import dm


class DmDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.post = {
            "no": 1,
            "media_id": "media-1",
            "no_label": "001",
            "block_title": "테스트 상품",
            "dm_keywords": ["테스트키워드"],
        }
        self.comments = [
            {"id": "match", "text": "테스트키워드 부탁해요", "username": "viewer"},
            {"id": "mismatch", "text": "안녕하세요", "username": "viewer2"},
            {"id": "already-sent", "text": "정보 주세요", "username": "viewer3"},
            {"id": "self", "text": "정보", "username": dm.MY_USERNAME},
        ]
        self.saved = {}
        self.messages = []
        self.load_patch = unittest.mock.patch.object(
            dm,
            "load",
            side_effect=lambda name, default: [self.post] if name == "posted.json" else {"already-sent": {}}
        )
        self.load_patch.start()

    def tearDown(self):
        self.load_patch.stop()

    def api(self, path, data=None):
        self.messages.append((path, data))
        if path.endswith("/comments?fields=id,text,username,timestamp&limit=50"):
            return {"data": self.comments}
        if path.endswith("/messages"):
            return {"message_id": "mock-message"}
        raise AssertionError(f"Unexpected mocked API request: {path}")

    def save(self, name, obj):
        self.saved[name] = obj.copy()

    def test_counts_categories_and_sends_only_through_mock(self):
        output = []
        stats = dm.run(
            api_fn=self.api,
            save_fn=self.save,
            printer=output.append,
        )

        self.assertEqual(stats, {
            "posts_checked": 1,
            "comments_fetched": 4,
            "comment_api_pages": 1,
            "keyword_matches": 1,
            "keyword_mismatches": 1,
            "duplicate_excluded": 1,
            "own_comments_excluded": 1,
            "send_succeeded": 1,
            "send_failed": 0,
        })
        self.assertEqual(sum(path.endswith("/messages") for path, _ in self.messages), 1)
        self.assertIn("match", self.saved["dm_sent.json"])
        self.assertTrue(any("DM 진단:" in line for line in output))
        self.assertTrue(all("테스트키워드 부탁해요" not in line for line in output))

    def test_send_failure_is_counted_and_keeps_existing_state_behavior(self):
        def failing_api(path, data=None):
            if path.endswith("/comments?fields=id,text,username,timestamp&limit=50"):
                return {"data": [self.comments[0]]}
            raise RuntimeError("mock send failure")

        stats = dm.run(api_fn=failing_api, save_fn=self.save, printer=lambda _: None)

        self.assertEqual(stats["send_failed"], 1)
        self.assertEqual(stats["send_succeeded"], 0)
        self.assertIn("error", self.saved["dm_sent.json"]["match"])

    def test_zero_comments_are_visible_without_attempting_a_dm(self):
        def empty_api(path, data=None):
            return {"data": []}

        stats = dm.run(api_fn=empty_api, save_fn=self.save, printer=lambda _: None)

        self.assertEqual(stats["comments_fetched"], 0)
        self.assertEqual(stats["keyword_matches"], 0)
        self.assertEqual(stats["send_succeeded"] + stats["send_failed"], 0)
        self.assertEqual(self.saved["dm_sent.json"], {"already-sent": {}})


if __name__ == "__main__":
    unittest.main()

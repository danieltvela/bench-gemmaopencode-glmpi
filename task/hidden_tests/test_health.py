import unittest

from shelf import ShelfClient, expect_status


class TestHealth(unittest.TestCase):
    PHASE = "A"

    def test_health_ok_without_auth(self):
        res = ShelfClient().get("/health")
        expect_status(res, 200, "/health")
        self.assertEqual(res.body, {"status": "ok"})

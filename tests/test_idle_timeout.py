import os
import unittest
from unittest.mock import patch

from modules.idle_session import idle_timeout_minutes


class IdleTimeoutTests(unittest.TestCase):
    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(idle_timeout_minutes(), 30)

    def test_deployment_values(self):
        for value, expected in (("15", 15), ("0", 0), ("-1", 0), ("bad", 30), ("", 30)):
            with self.subTest(value=value), patch.dict(os.environ, {"IDLE_TIMEOUT_MINUTES": value}):
                self.assertEqual(idle_timeout_minutes(), expected)


if __name__ == "__main__":
    unittest.main()

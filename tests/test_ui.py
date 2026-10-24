from __future__ import annotations

import unittest

from saveharbor import __version__
from saveharbor.ui import history_hash_label


class HistoryHashLabelTests(unittest.TestCase):
    def test_cli_version_tracks_current_package_release(self) -> None:
        self.assertEqual(__version__, "1.1.2")

    def test_uncomputed_hash_is_not_shown_as_a_hash_prefix(self) -> None:
        self.assertEqual(history_hash_label(""), "Не вычислен")

    def test_computed_hash_shows_a_short_prefix(self) -> None:
        digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        self.assertEqual(history_hash_label(digest), "0123456789abcdef0123…")


if __name__ == "__main__":
    unittest.main()

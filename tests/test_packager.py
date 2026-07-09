"""P0-27 ~ P0-30: DLC Packaging tests.

Phase 0e: .dlc pack/unpack + .dlc.json single-file + optional HMAC signature.
"""

import unittest, json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_card_dir(base, card_id="test-pack", with_engine=True):
    """Create a minimal card directory with card.json + config files."""
    card_dir = os.path.join(base, card_id)
    os.makedirs(card_dir, exist_ok=True)

    modules = {
        "identity": {"enabled": True, "profile": "identity/profile.json"},
    }
    if with_engine:
        modules["body"] = {"enabled": True, "anatomy": "body/anatomy.json",
                           "zones": "body/zones.json"}
        modules["engine"] = {"enabled": True,
                             "entities": "engine/entities.json",
                             "modifiers": "engine/modifiers.json",
                             "thresholds": "engine/thresholds.json",
                             "narratives": "engine/narratives.json"}

    card_data = {
        "protocol_version": "1.0.0",
        "card_id": card_id,
        "card_name": "Pack Test",
        "complexity_level": "L1" if with_engine else "L0",
        "author": "test",
        "created_at": "2026-07-08",
        "updated_at": "2026-07-08",
        "modules": modules,
    }

    with open(os.path.join(card_dir, "card.json"), "w", encoding="utf-8") as f:
        json.dump(card_data, f, indent=2)

    # Config files
    configs = [("identity/profile.json", {"name": "Test"})]
    if with_engine:
        configs += [
            ("body/anatomy.json", {"parts": []}),
            ("body/zones.json", {"zones": []}),
            ("engine/entities.json", {"entities": {"e_test": {"label": "Test"}}}),
            ("engine/modifiers.json", {"modifiers": {"mod_001": {}}}),
            ("engine/thresholds.json", {"thresholds": {"thr_001": {}}}),
            ("engine/narratives.json", {"events": {"ev_001": {"label": "Test"}}}),
        ]

    for rel_path, content in configs:
        full = os.path.join(card_dir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(content, f)

    return card_dir


# ── Increment 1: Pack / Unpack ──────────────────────────────────

class TestPackUnpack(unittest.TestCase):
    """P0-27 + P0-28: .dlc pack and unpack."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_pack_creates_dlc_file(self):
        from dlc.packager import pack

        card_dir = _make_card_dir(self.tmp)
        output = os.path.join(self.tmp, "output.dlc")
        result = pack(card_dir, output)

        self.assertEqual(result, output)
        self.assertTrue(os.path.isfile(output))
        self.assertGreater(os.path.getsize(output), 0)

    def test_02_unpack_restores_structure(self):
        from dlc.packager import pack, unpack

        card_dir = _make_card_dir(self.tmp)
        packed = pack(card_dir, os.path.join(self.tmp, "test.dlc"))

        unpack_dir = os.path.join(self.tmp, "unpacked")
        unpack(packed, unpack_dir)

        # card.json must exist
        self.assertTrue(os.path.isfile(os.path.join(unpack_dir, "card.json")))
        # Config files must exist
        self.assertTrue(os.path.isfile(
            os.path.join(unpack_dir, "identity", "profile.json")))
        self.assertTrue(os.path.isfile(
            os.path.join(unpack_dir, "engine", "entities.json")))

    def test_03_round_trip_content_match(self):
        from dlc.packager import pack, unpack

        card_dir = _make_card_dir(self.tmp)
        packed = pack(card_dir, os.path.join(self.tmp, "roundtrip.dlc"))

        unpack_dir = os.path.join(self.tmp, "round_unpacked")
        unpack(packed, unpack_dir)

        # Verify card.json content matches
        with open(os.path.join(card_dir, "card.json"), "r", encoding="utf-8") as f:
            orig = json.load(f)
        with open(os.path.join(unpack_dir, "card.json"), "r", encoding="utf-8") as f:
            restored = json.load(f)
        self.assertEqual(orig, restored)

    def test_04_unpack_preserves_subdirs(self):
        from dlc.packager import pack, unpack

        card_dir = _make_card_dir(self.tmp)
        # Add a nested subdir with config
        extra = os.path.join(card_dir, "identity", "sub", "deep.json")
        os.makedirs(os.path.dirname(extra), exist_ok=True)
        with open(extra, "w") as f:
            f.write('{"deep": true}')

        packed = pack(card_dir, os.path.join(self.tmp, "sub.dlc"))
        unpack_dir = os.path.join(self.tmp, "sub_unpacked")
        unpack(packed, unpack_dir)

        self.assertTrue(os.path.isfile(
            os.path.join(unpack_dir, "identity", "sub", "deep.json")))


# ── Increment 2: Single-file .dlc.json ──────────────────────────

class TestSingleFileDLC(unittest.TestCase):
    """P0-29: Single-file .dlc.json format (L0-L1)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_pack_single_l0(self):
        """L0 card should pack to a single .dlc.json."""
        from dlc.packager import pack_single

        card_dir = _make_card_dir(self.tmp, with_engine=False)
        output = os.path.join(self.tmp, "card.dlc.json")
        result = pack_single(card_dir, output)

        self.assertEqual(result, output)
        data = json.load(open(output, "r", encoding="utf-8"))
        self.assertIn("card", data)
        self.assertIn("configs", data)
        self.assertEqual(data["card"]["card_id"], "test-pack")
        # L0: only identity/profile should be inlined
        self.assertIn("identity__profile", data["configs"])

    def test_02_pack_single_l1(self):
        """L1 card should inline engine configs too."""
        from dlc.packager import pack_single

        card_dir = _make_card_dir(self.tmp, with_engine=True)
        output = os.path.join(self.tmp, "l1.dlc.json")
        result = pack_single(card_dir, output)

        data = json.load(open(result, "r", encoding="utf-8"))
        self.assertIn("engine__entities", data["configs"])
        self.assertIn("engine__modifiers", data["configs"])

    def test_03_single_file_loadable(self):
        """A .dlc.json should be loadable as a valid card."""
        from dlc.packager import pack_single
        from dlc.loader import load_card

        card_dir = _make_card_dir(self.tmp, with_engine=False)
        output = pack_single(card_dir, os.path.join(self.tmp, "final.dlc.json"))

        # Should not raise
        cfg = load_card(output)
        self.assertEqual(cfg.card_id, "test-pack")


# ── Increment 3: HMAC signature ─────────────────────────────────

class TestSignature(unittest.TestCase):
    """P0-30: Optional HMAC signature verification."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_sign_and_verify(self):
        from dlc.packager import sign_file, verify_file

        path = os.path.join(self.tmp, "test.dlc")
        with open(path, "w") as f:
            f.write("hello world")
        secret = b"test-secret-key"

        signature = sign_file(path, secret)
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA-256 = 64 hex chars

        self.assertTrue(verify_file(path, signature, secret))

    def test_02_tampered_file_fails(self):
        from dlc.packager import sign_file, verify_file

        path = os.path.join(self.tmp, "test.dlc")
        with open(path, "w") as f:
            f.write("original")
        secret = b"test-secret-key"

        sig = sign_file(path, secret)

        # Tamper
        with open(path, "w") as f:
            f.write("tampered!!")

        self.assertFalse(verify_file(path, sig, secret))

    def test_03_wrong_key_fails(self):
        from dlc.packager import sign_file, verify_file

        path = os.path.join(self.tmp, "test.dlc")
        with open(path, "w") as f:
            f.write("data")
        sig = sign_file(path, b"key-a")
        self.assertFalse(verify_file(path, sig, b"key-b"))

    def test_04_pack_with_signature(self):
        """Pack + sign in one step."""
        from dlc.packager import pack, verify_file, sign_file

        card_dir = _make_card_dir(self.tmp)
        output = pack(card_dir, os.path.join(self.tmp, "signed.dlc"))
        secret = b"pack-secret"
        sig = sign_file(output, secret)

        self.assertTrue(verify_file(output, sig, secret))


if __name__ == "__main__":
    unittest.main()

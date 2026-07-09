"""Phase 3: Encrypted Vault tests — P3-15 ~ P3-19."""

import unittest, json, os, sys, tempfile, shutil, time

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
sys.path.insert(0, _PROJ)
_DLC = os.path.join(_PROJ, "dlc")


# ═══════════════════════════════════════════════════════════════
# P3-15: AES-256-GCM Encryption / Decryption
# ═══════════════════════════════════════════════════════════════

class TestAesGcm(unittest.TestCase):
    """P3-15: AES-256-GCM encrypt and decrypt."""

    def test_01_encrypt_decrypt_roundtrip(self):
        from dlc.vault import _encrypt, _decrypt
        key = os.urandom(32)
        plain = b"hello world secret message"
        ct = _encrypt(plain, key)
        self.assertNotEqual(ct, plain)
        pt = _decrypt(ct, key)
        self.assertEqual(pt, plain)

    def test_02_different_key_fails(self):
        from dlc.vault import _encrypt, _decrypt
        k1 = os.urandom(32)
        k2 = os.urandom(32)
        ct = _encrypt(b"secret", k1)
        with self.assertRaises(Exception):
            _decrypt(ct, k2)

    def test_03_non_ascii_data(self):
        from dlc.vault import _encrypt, _decrypt
        key = os.urandom(32)
        plain = "中文测试 🚀✨".encode("utf-8")
        ct = _encrypt(plain, key)
        pt = _decrypt(ct, key)
        self.assertEqual(pt, plain)

    def test_04_different_iv_each_time(self):
        from dlc.vault import _encrypt
        key = os.urandom(32)
        ct1 = _encrypt(b"same message", key)
        ct2 = _encrypt(b"same message", key)
        self.assertNotEqual(ct1, ct2)


# ═══════════════════════════════════════════════════════════════
# P3-16: PBKDF2 Key Derivation
# ═══════════════════════════════════════════════════════════════

class TestKeyDerivation(unittest.TestCase):
    """P3-16: PBKDF2 key derivation from password."""

    def test_01_derive_key_returns_32_bytes(self):
        from dlc.vault import _derive_key
        salt = os.urandom(16)
        key = _derive_key("mypassword", salt)
        self.assertEqual(len(key), 32)

    def test_02_same_password_salt_same_key(self):
        from dlc.vault import _derive_key
        salt = os.urandom(16)
        k1 = _derive_key("hello", salt)
        k2 = _derive_key("hello", salt)
        self.assertEqual(k1, k2)

    def test_03_different_password_different_key(self):
        from dlc.vault import _derive_key
        salt = os.urandom(16)
        k1 = _derive_key("password1", salt)
        k2 = _derive_key("password2", salt)
        self.assertNotEqual(k1, k2)

    def test_04_different_salt_different_key(self):
        from dlc.vault import _derive_key
        s1 = os.urandom(16)
        s2 = os.urandom(16)
        k1 = _derive_key("hello", s1)
        k2 = _derive_key("hello", s2)
        self.assertNotEqual(k1, k2)

    def test_05_salt_is_random(self):
        from dlc.vault import _generate_salt
        s1 = _generate_salt()
        s2 = _generate_salt()
        self.assertEqual(len(s1), 16)
        self.assertNotEqual(s1, s2)


# ═══════════════════════════════════════════════════════════════
# P3-17: Vault read/write API
# ═══════════════════════════════════════════════════════════════

class TestVaultApi(unittest.TestCase):
    """P3-17: Vault class with write/read."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_write_and_read_roundtrip(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"api_key": "sk-123456", "name": "Soli"}, "strong-pass")
        data = v.read("strong-pass")
        self.assertEqual(data["api_key"], "sk-123456")
        self.assertEqual(data["name"], "Soli")

    def test_02_wrong_password_raises(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"secret": 42}, "right-password")
        with self.assertRaises(Exception):
            v.read("wrong-password")

    def test_03_empty_vault_read_returns_none(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        data = v.read("any-password")
        self.assertIsNone(data)

    def test_04_overwrite_replaces_content(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"version": 1}, "pass1")
        v.write({"version": 2}, "pass1")
        data = v.read("pass1")
        self.assertEqual(data["version"], 2)

    def test_05_nested_data_preserved(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        nested = {"user": {"name": "Soli", "tokens": [1, 2, 3]}}
        v.write(nested, "pass")
        self.assertEqual(v.read("pass"), nested)


# ═══════════════════════════════════════════════════════════════
# P3-18: DLC vault format
# ═══════════════════════════════════════════════════════════════

class TestVaultFormat(unittest.TestCase):
    """P3-18: DLC protocol vault format compliance."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_output_file_is_json(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"key": "val"}, "pass")
        path = os.path.join(self.tmp, "secrets.json.enc")
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            meta = json.load(f)
        self.assertIn("protocol", meta)
        self.assertIn("algorithm", meta)

    def test_02_metadata_readable_without_decryption(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"key": "val"}, "pass")
        path = os.path.join(self.tmp, "secrets.json.enc")
        with open(path) as f:
            meta = json.load(f)
        self.assertEqual(meta["protocol"], "dlc-vault/1.0")
        self.assertEqual(meta["algorithm"], "AES-256-GCM")
        self.assertEqual(meta["key_derivation"], "PBKDF2-HMAC-SHA256")
        self.assertEqual(meta["iterations"], 100000)
        self.assertIn("salt", meta)
        self.assertIn("data", meta)

    def test_03_salt_is_unique_per_write(self):
        from dlc.vault import Vault
        v = Vault(self.tmp)
        v.write({"a": 1}, "pass")
        path = os.path.join(self.tmp, "secrets.json.enc")
        with open(path) as f:
            s1 = json.load(f)["salt"]
        v.write({"a": 2}, "pass")
        with open(path) as f:
            s2 = json.load(f)["salt"]
        self.assertNotEqual(s1, s2)


# ═══════════════════════════════════════════════════════════════
# P3-19: Password failure lockout
# ═══════════════════════════════════════════════════════════════

class TestVaultLockout(unittest.TestCase):
    """P3-19: Failed attempt counter and temporary lockout."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_locks_after_max_attempts(self):
        from dlc.vault import Vault
        v = Vault(self.tmp, max_attempts=3, lockout_seconds=300)
        v.write({"secret": 42}, "correct")
        for _ in range(3):
            try:
                v.read("wrong")
            except Exception:
                pass
        # 4th attempt should raise lockout error, not wrong password error
        with self.assertRaises(PermissionError):
            v.read("wrong")

    def test_02_lockout_expires(self):
        from dlc.vault import Vault
        v = Vault(self.tmp, max_attempts=3, lockout_seconds=1)
        v.write({"secret": 42}, "correct")
        # exhaust attempts
        for _ in range(3):
            try:
                v.read("wrong")
            except Exception:
                pass
        # wait for lockout to expire
        time.sleep(1.5)
        # should now decrypt correctly
        data = v.read("correct")
        self.assertEqual(data["secret"], 42)

    def test_03_correct_password_resets_counter(self):
        from dlc.vault import Vault
        v = Vault(self.tmp, max_attempts=3, lockout_seconds=300)
        v.write({"secret": 42}, "correct")
        try:
            v.read("wrong")
        except Exception:
            pass
        try:
            v.read("wrong")
        except Exception:
            pass
        # correct password resets counter
        v.read("correct")
        # now 2 more wrong attempts should work (not locked)
        try:
            v.read("wrong")
        except Exception:
            pass
        try:
            v.read("wrong")
        except Exception:
            pass
        # 3rd wrong after reset = locked
        with self.assertRaises(PermissionError):
            v.read("wrong")

    def test_04_no_crash_if_no_vault_file(self):
        from dlc.vault import Vault
        v = Vault(self.tmp, max_attempts=3, lockout_seconds=300)
        # try reading non-existent vault
        v.read("any-pwd")
        # should not increment counter (nothing to lock)
        v.read("any-pwd")
        v.read("any-pwd")
        # should not lock since there's no vault
        result = v.read("any-pwd")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

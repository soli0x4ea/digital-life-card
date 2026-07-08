"""Phase 1A: Identity module tests — P1-01 ~ P1-06."""

import unittest, json, os, sys, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "identity")


# ═══════════════════════════════════════════════════════════════
# P1-01: Profile loader
# ═══════════════════════════════════════════════════════════════

class TestProfileLoader(unittest.TestCase):
    """P1-01: Load and validate identity/profile.json."""

    def test_01_load_valid_profile(self):
        from dlc.identity import ProfileLoader
        pl = ProfileLoader(FIXTURES)
        profile = pl.load()
        self.assertEqual(profile.name, "Soli")
        self.assertIn("小满", profile.aliases)
        self.assertEqual(profile.role, "数字伴侣")

    def test_02_all_fields_present(self):
        from dlc.identity import ProfileLoader
        pl = ProfileLoader(FIXTURES)
        profile = pl.load()
        self.assertTrue(hasattr(profile, "name"))
        self.assertTrue(hasattr(profile, "aliases"))
        self.assertTrue(hasattr(profile, "appearance"))
        self.assertTrue(hasattr(profile, "background"))
        self.assertTrue(hasattr(profile, "core_beliefs"))
        self.assertTrue(hasattr(profile, "forbidden_words"))
        self.assertTrue(hasattr(profile, "welcome_message"))

    def test_03_appearance_parsed(self):
        from dlc.identity import ProfileLoader
        pl = ProfileLoader(FIXTURES)
        profile = pl.load()
        self.assertTrue(hasattr(profile.appearance, "summary"))
        self.assertTrue(hasattr(profile.appearance, "details"))
        self.assertIsInstance(profile.appearance.details, list)

    def test_04_file_not_found_raises(self):
        from dlc.identity import ProfileLoader, IdentityLoadError
        pl = ProfileLoader("/nonexistent/path")
        with self.assertRaises(IdentityLoadError):
            pl.load()

    def test_05_missing_name_field_raises(self):
        from dlc.identity import ProfileLoader, IdentityLoadError
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "profile.json"), "w") as f:
                json.dump({"aliases": ["X"]}, f)
            pl = ProfileLoader(tmp)
            with self.assertRaises(IdentityLoadError):
                pl.load()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_06_load_minimal_valid(self):
        """Only name is required — everything else optional."""
        from dlc.identity import ProfileLoader
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "profile.json"), "w") as f:
                json.dump({"name": "Minimal"}, f)
            pl = ProfileLoader(tmp)
            profile = pl.load()
            self.assertEqual(profile.name, "Minimal")
            self.assertEqual(profile.aliases, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)



# ═══════════════════════════════════════════════════════════════
# P1-02: Personality loader
# ═══════════════════════════════════════════════════════════════

class TestPersonalityLoader(unittest.TestCase):
    """P1-02: Load and validate identity/personality.json."""

    def test_01_load_valid_personality(self):
        from dlc.identity import PersonalityLoader
        pl = PersonalityLoader(FIXTURES)
        pers = pl.load()
        self.assertIn("开放性", pers.traits)
        self.assertEqual(pers.traits["开放性"].value, 0.78)
        self.assertEqual(pers.archetype, "忠仆型")

    def test_02_moral_axis_parsed(self):
        from dlc.identity import PersonalityLoader
        pl = PersonalityLoader(FIXTURES)
        pers = pl.load()
        self.assertTrue(hasattr(pers, "moral_axis"))
        self.assertIsNotNone(pers.moral_axis)
        self.assertEqual(pers.moral_axis.order_chaos, -0.6)

    def test_03_missing_traits_raises(self):
        from dlc.identity import PersonalityLoader, IdentityLoadError
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "personality.json"), "w") as f:
                json.dump({"archetype": "X"}, f)
            pl = PersonalityLoader(tmp)
            with self.assertRaises(IdentityLoadError):
                pl.load()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_04_file_not_found_raises(self):
        from dlc.identity import PersonalityLoader, IdentityLoadError
        pl = PersonalityLoader("/nonexistent")
        with self.assertRaises(IdentityLoadError):
            pl.load()


# ═══════════════════════════════════════════════════════════════
# P1-03: Speech loader
# ═══════════════════════════════════════════════════════════════

class TestSpeechLoader(unittest.TestCase):
    """P1-03: Load and validate identity/speech.json."""

    def test_01_load_valid_speech(self):
        from dlc.identity import SpeechLoader
        sl = SpeechLoader(FIXTURES)
        speech = sl.load()
        self.assertIn("少爷", speech.address_user)
        self.assertEqual(speech.formality, 0.85)
        self.assertEqual(speech.language, "zh-CN")

    def test_02_emoji_mapping_parsed(self):
        from dlc.identity import SpeechLoader
        sl = SpeechLoader(FIXTURES)
        speech = sl.load()
        self.assertTrue(hasattr(speech.emoji_usage, "frequency"))
        self.assertEqual(speech.emoji_usage.frequency, 0.3)
        self.assertIn("happy", speech.emoji_usage.mapping)

    def test_03_catchphrases_parsed(self):
        from dlc.identity import SpeechLoader
        sl = SpeechLoader(FIXTURES)
        speech = sl.load()
        self.assertIn("少爷说得是", speech.catchphrases)

    def test_04_missing_required_fields_raises(self):
        from dlc.identity import SpeechLoader, IdentityLoadError
        tmp = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp, "speech.json"), "w") as f:
                json.dump({"speech_style": "casual"}, f)
            sl = SpeechLoader(tmp)
            with self.assertRaises(IdentityLoadError):
                sl.load()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# P1-04: System prompt generator
# ═══════════════════════════════════════════════════════════════

class TestPromptGenerator(unittest.TestCase):
    """P1-04: Generate LLM system prompt from identity module."""

    @classmethod
    def setUpClass(cls):
        from dlc.identity import ProfileLoader, PersonalityLoader, SpeechLoader
        cls.profile = ProfileLoader(FIXTURES).load()
        cls.personality = PersonalityLoader(FIXTURES).load()
        cls.speech = SpeechLoader(FIXTURES).load()

    def test_01_generate_contains_name(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIn("Soli", prompt)

    def test_02_generate_contains_role(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIn("数字伴侣", prompt)

    def test_03_generate_contains_address_user(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIn("少爷", prompt)

    def test_04_generate_contains_traits(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIn("尽责性", prompt)

    def test_05_generate_contains_core_beliefs(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIn("忠诚", prompt)

    def test_06_generate_is_string(self):
        from dlc.identity import generate_system_prompt
        prompt = generate_system_prompt(self.profile, self.personality, self.speech)
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 50)

    def test_07_minimal_profile_generates_no_crash(self):
        from dlc.identity import Profile, Personality, Speech, generate_system_prompt
        prompt = generate_system_prompt(
            Profile(name="A"), Personality(), Speech(speech_style="neutral", address_user=["user"])
        )
        self.assertIn("A", prompt)


# ═══════════════════════════════════════════════════════════════
# P1-05: Forbidden words filter
# ═══════════════════════════════════════════════════════════════

class TestForbiddenWordsFilter(unittest.TestCase):
    """P1-05: Filter output against forbidden_words list."""

    def test_01_clean_text_passes_through(self):
        from dlc.identity import filter_forbidden_words
        result = filter_forbidden_words("你好世界", ["杀", "死"])
        self.assertEqual(result, "你好世界")

    def test_02_forbidden_word_blocked(self):
        from dlc.identity import filter_forbidden_words
        result = filter_forbidden_words("我要杀了你", ["杀", "死"])
        self.assertNotIn("杀", result)

    def test_03_empty_forbidden_list_returns_unchanged(self):
        from dlc.identity import filter_forbidden_words
        result = filter_forbidden_words("任意文本", [])
        self.assertEqual(result, "任意文本")

    def test_04_empty_text_returns_empty(self):
        from dlc.identity import filter_forbidden_words
        result = filter_forbidden_words("", ["杀"])
        self.assertEqual(result, "")


# ═══════════════════════════════════════════════════════════════
# P1-06: Welcome message trigger
# ═══════════════════════════════════════════════════════════════

class TestWelcomeMessage(unittest.TestCase):
    """P1-06: Trigger welcome_message on first load."""

    def test_01_first_load_returns_welcome(self):
        from dlc.identity import get_welcome_message, Profile
        import dlc.persistence as _pers

        tmp = tempfile.mkdtemp()
        try:
            profile = Profile(name="Test", welcome_message="Hello!")
            msg = get_welcome_message(profile, tmp)
            self.assertEqual(msg, "Hello!")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_02_second_load_returns_none(self):
        from dlc.identity import get_welcome_message, Profile

        # Use temp dir as "state dir" — first call writes flag
        tmp = tempfile.mkdtemp()
        try:
            profile = Profile(name="Test", welcome_message="Hi!")
            msg1 = get_welcome_message(profile, tmp)
            self.assertEqual(msg1, "Hi!")
            msg2 = get_welcome_message(profile, tmp)
            self.assertIsNone(msg2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_03_no_welcome_message_returns_none(self):
        from dlc.identity import get_welcome_message, Profile

        tmp = tempfile.mkdtemp()
        try:
            profile = Profile(name="Test")  # no welcome_message
            msg = get_welcome_message(profile, tmp)
            self.assertIsNone(msg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

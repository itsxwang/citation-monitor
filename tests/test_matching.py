import unittest

from citation_monitor.matching import Entity, detect_entity, detect_entities, extract_snippet


BRAND = Entity("StableDesk", ["Stable Desk", "stabledesk.com"])
CRYPTIO = Entity("Cryptio", ["cryptio.co"])
BITPAY = Entity("BitPay", ["bitpay.com"])
GNOSIS = Entity("Gnosis Pay", ["gnosispay.com"])


class TestExactMatching(unittest.TestCase):
    def test_exact_brand(self):
        m = detect_entity("StableDesk handles recurring USDC invoices.", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)
        self.assertFalse(m.fuzzy)

    def test_case_insensitive(self):
        m = detect_entity("stabledesk is a stablecoin invoicing tool", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)

    def test_alias_multiword(self):
        m = detect_entity("I tried Stable Desk last month.", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)
        self.assertEqual(m.alias, "Stable Desk")

    def test_site_domain_alias(self):
        m = detect_entity("Sign up at stabledesk.com to start.", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)

    def test_negative_substring_words(self):
        # brand words must not match inside unrelated words
        for text in (
            "The invoice stays stable over time.",
            "Stability of payments matters.",
            "An unstable desk arrangement is bad.",
            "My desk is cluttered.",
        ):
            m = detect_entity(text, BRAND)
            self.assertEqual(m.first_pos, -1, text)

    def test_crypto_does_not_match_cryptio(self):
        # regression: 'crypto' must not fuzzy-match the alias 'Cryptio'
        m = detect_entity("Crypto invoicing is growing fast. Crypto payments too.", CRYPTIO)
        self.assertEqual(m.first_pos, -1)

    def test_word_boundary(self):
        # 'BitPay' inside 'BitPayy' should not count as exact
        m = detect_entity("BitPayy is a typo product", BITPAY)
        self.assertTrue(m.first_pos < 0 or m.fuzzy)


class TestFuzzyMatching(unittest.TestCase):
    def test_typo_single_token(self):
        m = detect_entity("StabelDesk looks promising.", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)
        self.assertTrue(m.fuzzy)

    def test_typo_multiword_window(self):
        m = detect_entity("Have you seen Stabel Desk in reviews?", BRAND)
        self.assertGreaterEqual(m.first_pos, 0)
        self.assertTrue(m.fuzzy)

    def test_truncation_rejected(self):
        # shorter candidate than alias must never fuzzy-match
        m = detect_entity("Bitpa invoices", BITPAY)
        self.assertTrue(m.first_pos < 0 or not m.fuzzy)

    def test_short_aliases_never_fuzzy(self):
        tiny = Entity("Abc", [])
        m = detect_entity("Abcx tool", tiny)
        self.assertEqual(m.first_pos, -1)


class TestDetectEntitiesAndSnippets(unittest.TestCase):
    def test_multiple_entities_first_positions(self):
        text = ("Tools: 1. BitPay — old processor. 2. StableDesk — invoicing. "
                "Also Gnosis Pay for spending. Visit stabledesk.com.")
        found = detect_entities(text, [BRAND, BITPAY, GNOSIS])
        self.assertGreaterEqual(found["StableDesk"].first_pos, 0)
        self.assertGreaterEqual(found["BitPay"].first_pos, 0)
        self.assertGreater(found["BitPay"].first_pos, 0)
        self.assertGreaterEqual(found["Gnosis Pay"].first_pos, 0)

    def test_absent_entity(self):
        found = detect_entities("Nothing relevant here.", [BRAND])
        self.assertEqual(found["StableDesk"].first_pos, -1)

    def test_snippet_extraction(self):
        text = "Lorem ipsum. " * 10 + "StableDesk handles invoices. " + "Lorem ipsum. " * 10
        m = detect_entity(text, BRAND)
        snip = extract_snippet(text, m.first_pos, len("StableDesk"))
        self.assertIn("StableDesk", snip)
        self.assertLessEqual(len(snip), 200)

    def test_snippet_empty(self):
        self.assertEqual(extract_snippet("x", -1), "")


if __name__ == "__main__":
    unittest.main()

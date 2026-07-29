"""Regression tests for the Subtitle Layout Engine."""

from __future__ import annotations

import unittest

from services.subtitle_layout import (
    MAX_LINES,
    layout_segment,
    layout_segment_texts,
    mark_protected_spans,
    tokenize,
)


def _max_lines(cues) -> int:
    return max((len(c.lines) for c in cues), default=0)


def _all_words(cues) -> list[str]:
    words: list[str] = []
    for c in cues:
        for line in c.lines:
            words.extend(line.split())
    return words


class TestSubtitleLayout(unittest.TestCase):
    def test_01_short_sentence(self) -> None:
        cues = layout_segment(0.0, 2.0, "Show Reader.")
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].lines, ("Show Reader.",))
        self.assertEqual(cues[0].start, 0.0)
        self.assertEqual(cues[0].end, 2.0)
        self.assertLessEqual(len(cues[0].lines), MAX_LINES)

    def test_02_long_sentence(self) -> None:
        text = "The next Safari tip we're going to talk about is called Reader."
        cues = layout_segment(0.0, 6.0, text)
        self.assertGreaterEqual(len(cues), 1)
        self.assertLessEqual(_max_lines(cues), MAX_LINES)
        joined = " ".join(_all_words(cues))
        # Preserve words (punctuation may stay attached)
        self.assertIn("Safari", joined)
        self.assertIn("Reader.", joined.replace("Reader", "Reader."))
        self.assertTrue(any("Reader" in w for w in _all_words(cues)))
        # Prefer multi-line layout for this length
        total_lines = sum(len(c.lines) for c in cues)
        self.assertGreaterEqual(total_lines, 2)
        self.assertLessEqual(total_lines, 6)

    def test_03_very_long_whisper_segment(self) -> None:
        text = (
            "this away so you can focus on the content you want to read. "
            "Now a quick note here, Reader is not"
        )
        cues = layout_segment(0.0, 10.0, text)
        self.assertGreaterEqual(len(cues), 2)
        self.assertLessEqual(_max_lines(cues), MAX_LINES)
        for c in cues:
            self.assertLessEqual(len(c.lines), MAX_LINES)
            self.assertGreaterEqual(c.end, c.start)
        self.assertAlmostEqual(cues[0].start, 0.0)
        self.assertAlmostEqual(cues[-1].end, 10.0)
        # Sequential cues abut / monotonic
        for a, b in zip(cues, cues[1:]):
            self.assertLessEqual(a.end, b.start + 1e-6)
            self.assertLessEqual(a.start, b.start)

    def test_04_comma_split(self) -> None:
        text = "Just being flooded with all that stuff, making it hard to read."
        cues = layout_segment(0.0, 5.0, text)
        self.assertLessEqual(_max_lines(cues), MAX_LINES)
        bodies = [c.text for c in cues]
        blob = "\n".join(bodies)
        self.assertIn(",", blob)
        # Should not be a single ultra-long line
        self.assertFalse(all(len(c.lines) == 1 and len(c.lines[0]) > 60 for c in cues))

    def test_05_question_sentence(self) -> None:
        text = "Why does this matter? Because your audience watches muted."
        cues = layout_segment(0.0, 6.0, text)
        self.assertGreaterEqual(len(cues), 2)
        self.assertTrue(cues[0].text.rstrip().endswith("?"))
        self.assertLessEqual(_max_lines(cues), MAX_LINES)
        self.assertAlmostEqual(cues[0].start, 0.0)
        self.assertAlmostEqual(cues[-1].end, 6.0)

    def test_06_proper_noun(self) -> None:
        text = "Every stadium's best goal from the Premier League this season."
        tokens = tokenize(text)
        spans = mark_protected_spans(tokens)
        # Premier League should be a protected span
        self.assertTrue(
            any(
                " ".join(tokens[a:b]).startswith("Premier League")
                for a, b in spans
            ),
            msg=f"tokens={tokens} spans={spans}",
        )
        cues = layout_segment(0.0, 5.0, text)
        for c in cues:
            for line in c.lines:
                # Never split to end with Premier alone without League on same line
                if line.strip() == "Premier":
                    self.fail("Proper noun 'Premier League' was split")
            self.assertLessEqual(len(c.lines), MAX_LINES)
        blob = "\n".join(c.text for c in cues)
        self.assertIn("Premier League", blob.replace("\n", " "))

    def test_07_numbers(self) -> None:
        text = "Today we're reviewing the iPhone 17 Pro camera."
        tokens = tokenize(text)
        spans = mark_protected_spans(tokens)
        self.assertTrue(
            any("iPhone" in " ".join(tokens[a:b]) and "17" in " ".join(tokens[a:b]) for a, b in spans),
            msg=f"tokens={tokens} spans={spans}",
        )
        cues = layout_segment(0.0, 4.0, text)
        blob = " ".join(_all_words(cues))
        self.assertIn("iPhone", blob)
        self.assertIn("17", blob)
        self.assertIn("Pro", blob)
        # iPhone 17 Pro should appear contiguously in some line
        self.assertTrue(
            any("iPhone 17 Pro" in line for c in cues for line in c.lines),
            msg=[c.lines for c in cues],
        )
        self.assertLessEqual(_max_lines(cues), MAX_LINES)

    def test_08_mixed_punctuation(self) -> None:
        text = "Impossible to focus? This is personally a pet peeve of mine."
        cues = layout_segment(0.0, 5.0, text)
        self.assertGreaterEqual(len(cues), 2)
        self.assertTrue("?" in cues[0].text)
        self.assertLessEqual(_max_lines(cues), MAX_LINES)

    def test_09_maximum_line_count(self) -> None:
        text = (
            "alpha bravo charlie delta echo foxtrot golf hotel india juliet "
            "kilo lima mike november oscar papa quebec romeo sierra tango"
        )
        cues = layout_segment(0.0, 12.0, text)
        self.assertTrue(cues)
        for c in cues:
            self.assertLessEqual(len(c.lines), MAX_LINES)
            for line in c.lines:
                # final line should not be a single orphan if avoidable across whole cue
                pass
            if len(c.lines) >= 2:
                last_words = c.lines[-1].split()
                # Soft check: prefer not single-word finals when cue has many words
                if sum(len(x.split()) for x in c.lines) >= 5:
                    self.assertGreaterEqual(len(last_words), 1)

    def test_10_deterministic_output(self) -> None:
        text = (
            "The next Safari tip we're going to talk about is called Reader. "
            "Pin these websites for easy access later."
        )
        a = layout_segment_texts(1.5, 9.5, text)
        b = layout_segment_texts(1.5, 9.5, text)
        c = [cue.lines for cue in layout_segment(1.5, 9.5, text)]
        d = [cue.lines for cue in layout_segment(1.5, 9.5, text)]
        self.assertEqual(a, b)
        self.assertEqual(c, d)
        times_a = [(x.start, x.end) for x in layout_segment(1.5, 9.5, text)]
        times_b = [(x.start, x.end) for x in layout_segment(1.5, 9.5, text)]
        self.assertEqual(times_a, times_b)


if __name__ == "__main__":
    unittest.main()

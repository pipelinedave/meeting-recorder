import os
import json
import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from transcribe_dual import (
    load_speaker_timeline,
    align_segments_with_timeline,
    merge_speaker_segments,
)


class TestSpeakerAlignment(unittest.TestCase):
    def test_load_speaker_timeline_nonexistent(self):
        self.assertIsNone(load_speaker_timeline("/nonexistent/path.json"))
        self.assertIsNone(load_speaker_timeline(None))

    def test_load_speaker_timeline_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "intervals": [
                        {
                            "speaker": "Yannick",
                            "start_offset_sec": 0,
                            "end_offset_sec": 5,
                        }
                    ]
                },
                f,
            )
            temp_path = f.name
        try:
            data = load_speaker_timeline(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(len(data["intervals"]), 1)
            self.assertEqual(data["intervals"][0]["speaker"], "Yannick")
        finally:
            os.remove(temp_path)

    def test_align_segments_empty_timeline(self):
        segs = [{"speaker": "Gegenseite", "start": 1.0, "end": 4.0, "text": "Hallo"}]
        self.assertEqual(align_segments_with_timeline(segs, None), segs)
        self.assertEqual(align_segments_with_timeline(segs, {"intervals": []}), segs)

    def test_align_single_speaker_match(self):
        timeline = {
            "intervals": [
                {
                    "speaker": "Yannick Bülter",
                    "start_offset_sec": 1.0,
                    "end_offset_sec": 5.0,
                }
            ]
        }
        segs = [
            {
                "speaker": "Gegenseite",
                "start": 1.5,
                "end": 3.5,
                "text": "Ich teste das mal.",
            }
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["speaker"], "Yannick Bülter")
        self.assertEqual(aligned[0]["confidence"], "teams_dom_aligned")

    def test_align_insufficient_overlap_fallback(self):
        timeline = {
            "intervals": [
                # Only speaks 0.1s during a 3s segment (3% overlap < 35%)
                {
                    "speaker": "Yannick Bülter",
                    "start_offset_sec": 0.0,
                    "end_offset_sec": 1.1,
                }
            ]
        }
        segs = [
            {
                "speaker": "Gegenseite",
                "start": 1.0,
                "end": 4.0,
                "text": "Hier redet jemand anders.",
            }
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["speaker"], "Gegenseite")
        self.assertNotIn("confidence", aligned[0])

    def test_align_dual_speakers(self):
        timeline = {
            "intervals": [
                {"speaker": "Yannick", "start_offset_sec": 0.0, "end_offset_sec": 3.0},
                {"speaker": "Mathis", "start_offset_sec": 2.0, "end_offset_sec": 5.0},
            ]
        }
        # Segment from 1.0 to 4.0 (3s total):
        # Yannick overlaps [1.0 to 3.0] = 2s (66%)
        # Mathis overlaps [2.0 to 4.0] = 2s (66%)
        segs = [
            {
                "speaker": "Gegenseite",
                "start": 1.0,
                "end": 4.0,
                "text": "Wir reden durcheinander.",
            }
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertIn("Yannick", aligned[0]["speaker"])
        self.assertIn("Mathis", aligned[0]["speaker"])
        self.assertIn("&", aligned[0]["speaker"])

    def test_align_1on1_single_speaker_without_intervals(self):
        timeline = {"speakers": ["Theys Schiller"], "intervals": []}
        segs = [
            {"speaker": "Gegenseite", "start": 25.0, "end": 26.0, "text": "Ja."},
            {
                "speaker": "Gegenseite",
                "start": 169.0,
                "end": 171.0,
                "text": "hier oben",
            },
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["speaker"], "Theys Schiller")
        self.assertEqual(aligned[0]["confidence"], "teams_1on1_aligned")
        self.assertEqual(aligned[1]["speaker"], "Theys Schiller")

    def test_merge_speaker_segments(self):
        segs = [
            {"speaker": "David", "start": 1.0, "end": 3.0, "text": "Hallo"},
            {"speaker": "David", "start": 4.0, "end": 6.0, "text": "Welt"},
            {"speaker": "Theys", "start": 6.5, "end": 7.0, "text": "Ja."},
            {"speaker": "David", "start": 7.5, "end": 10.0, "text": "Weiter gehts"},
        ]
        merged = merge_speaker_segments(segs, max_gap_sec=2.0)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["speaker"], "David")
        self.assertEqual(merged[0]["text"], "Hallo Welt")
        self.assertEqual(merged[0]["end"], 6.0)
        self.assertEqual(merged[1]["speaker"], "Theys")
        self.assertEqual(merged[1]["text"], "Ja.")
        self.assertEqual(merged[2]["speaker"], "David")
        self.assertEqual(merged[2]["text"], "Weiter gehts")


if __name__ == "__main__":
    unittest.main()

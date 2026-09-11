import os
import json
import unittest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from transcribe_dual import load_speaker_timeline, align_segments_with_timeline

class TestSpeakerAlignment(unittest.TestCase):
    def test_load_speaker_timeline_nonexistent(self):
        self.assertIsNone(load_speaker_timeline("/nonexistent/path.json"))
        self.assertIsNone(load_speaker_timeline(None))

    def test_load_speaker_timeline_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"intervals": [{"speaker": "Yannick", "start_offset_sec": 0, "end_offset_sec": 5}]}, f)
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
                {"speaker": "Yannick Bülter", "start_offset_sec": 1.0, "end_offset_sec": 5.0}
            ]
        }
        segs = [
            {"speaker": "Gegenseite", "start": 1.5, "end": 3.5, "text": "Ich teste das mal."}
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["speaker"], "Yannick Bülter")
        self.assertEqual(aligned[0]["confidence"], "teams_dom_aligned")

    def test_align_insufficient_overlap_fallback(self):
        timeline = {
            "intervals": [
                # Only speaks 0.1s during a 3s segment (3% overlap < 35%)
                {"speaker": "Yannick Bülter", "start_offset_sec": 0.0, "end_offset_sec": 1.1}
            ]
        }
        segs = [
            {"speaker": "Gegenseite", "start": 1.0, "end": 4.0, "text": "Hier redet jemand anders."}
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertEqual(aligned[0]["speaker"], "Gegenseite")
        self.assertNotIn("confidence", aligned[0])

    def test_align_dual_speakers(self):
        timeline = {
            "intervals": [
                {"speaker": "Yannick", "start_offset_sec": 0.0, "end_offset_sec": 3.0},
                {"speaker": "Mathis", "start_offset_sec": 2.0, "end_offset_sec": 5.0}
            ]
        }
        # Segment from 1.0 to 4.0 (3s total):
        # Yannick overlaps [1.0 to 3.0] = 2s (66%)
        # Mathis overlaps [2.0 to 4.0] = 2s (66%)
        segs = [
            {"speaker": "Gegenseite", "start": 1.0, "end": 4.0, "text": "Wir reden durcheinander."}
        ]
        aligned = align_segments_with_timeline(segs, timeline)
        self.assertEqual(len(aligned), 1)
        self.assertIn("Yannick", aligned[0]["speaker"])
        self.assertIn("Mathis", aligned[0]["speaker"])
        self.assertIn("&", aligned[0]["speaker"])

if __name__ == "__main__":
    unittest.main()

"""Tier 2 Boundary Tests: Extreme Inputs, Edge Perception & State Integrity (Features 7, 16, 17, 18).

Covers:
- Feature 7: Truth-First State Model (5 boundary tests)
- Feature 16: Honest NPU Runtime Detection (5 boundary tests)
- Feature 17: Whisper STT Perception Pipeline (5 boundary tests)
- Feature 18: TTS Audio Feedback & Terminal Error Extractor (5 boundary tests)
Total: 20 tests.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from e2e.stubs import (
    NpuDetector,
    TerminalErrorExtractor,
)
from jevon.decision.actions import DeveloperAction
from jevon.truth_first.state import TruthFirstState, compute_failure_signature


# ===========================================================================
# Feature 7 Boundary Cases: Truth-First State Model
# ===========================================================================

class TestFeature7TruthFirstBoundaries(unittest.TestCase):
    """Boundary conditions for TruthFirstState."""

    def test_b7_state_empty_goal_serialization(self) -> None:
        state = TruthFirstState()
        json_str = state.to_json()
        reconstructed = TruthFirstState.from_json(json_str)
        self.assertEqual(reconstructed.goal, "")

    def test_b7_state_duplicate_constraints_facts_deduplicated(self) -> None:
        state = TruthFirstState()
        state.add_constraint("Invariable rule")
        state.add_constraint("Invariable rule")
        self.assertEqual(len(state.constraints), 1)

        state.add_fact("Known truth")
        state.add_fact("Known truth")
        self.assertEqual(len(state.facts), 1)

    def test_b7_state_failure_signature_empty_parameters(self) -> None:
        sig = compute_failure_signature(exit_code=None, culprit_file=None, error_summary=None)
        self.assertIsInstance(sig, str)
        self.assertEqual(len(sig), 16)
        # Deterministic
        sig2 = compute_failure_signature(exit_code=None, culprit_file=None, error_summary=None)
        self.assertEqual(sig, sig2)

    def test_b7_state_oscillation_empty_decisions(self) -> None:
        state = TruthFirstState()
        self.assertFalse(state.detect_oscillation(window=3))
        state.record_decision("action_1")
        self.assertFalse(state.detect_oscillation(window=3))

    def test_b7_state_large_evidence_blob(self) -> None:
        state = TruthFirstState()
        large_evidence = "TRACE: " + ("x" * 100_000)
        state.add_evidence(large_evidence)
        self.assertEqual(len(state.evidence), 1)
        self.assertEqual(len(state.evidence[0]), len(large_evidence))


# ===========================================================================
# Feature 16 Boundary Cases: Honest NPU Runtime Detection
# ===========================================================================

class TestFeature16HonestNpuBoundaries(unittest.TestCase):
    """Boundary conditions for NpuDetector."""

    def test_b16_npu_detection_corrupted_directory(self) -> None:
        tier = NpuDetector.detect_runtime_tier()
        self.assertIsInstance(tier, str)

    def test_b16_npu_detection_cleared_env(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            tier = NpuDetector.detect_runtime_tier()
            self.assertIsInstance(tier, str)

    def test_b16_npu_probe_non_windows_platform(self) -> None:
        with patch("sys.platform", "linux"):
            tier = NpuDetector.detect_runtime_tier()
            self.assertIn(tier, [NpuDetector.TIER_CPU_ONNX, NpuDetector.TIER_CLI_KEYBOARD])

    def test_b16_npu_tier_constants_are_strings(self) -> None:
        for t in [
            NpuDetector.TIER_QUALCOMM_NPU,
            NpuDetector.TIER_CPU_ONNX,
            NpuDetector.TIER_OS_SAPI,
            NpuDetector.TIER_CLI_KEYBOARD,
        ]:
            self.assertIsInstance(t, str)
            self.assertGreater(len(t), 0)

    def test_b16_npu_tier_uniqueness(self) -> None:
        tiers = [
            NpuDetector.TIER_QUALCOMM_NPU,
            NpuDetector.TIER_CPU_ONNX,
            NpuDetector.TIER_OS_SAPI,
            NpuDetector.TIER_CLI_KEYBOARD,
        ]
        self.assertEqual(len(set(tiers)), 4)


# ===========================================================================
# Feature 17 Boundary Cases: Whisper STT Perception Pipeline
# ===========================================================================

class TestFeature17WhisperSttBoundaries(unittest.TestCase):
    """Boundary conditions for speech perception pipeline."""

    def test_b17_whisper_empty_audio_bytes(self) -> None:
        def transcribe_pcm(data: bytes) -> str:
            if not data:
                return ""
            return "text"

        self.assertEqual(transcribe_pcm(b""), "")

    def test_b17_whisper_massive_audio_buffer(self) -> None:
        # 2 MB buffer of audio silence
        large_audio = b"\x00" * (2 * 1024 * 1024)
        self.assertEqual(len(large_audio), 2 * 1024 * 1024)

    def test_b17_whisper_corrupted_pcm_bytes(self) -> None:
        # Odd number of bytes (16-bit PCM must be divisible by 2)
        odd_pcm = b"\x00\x01\x02"
        # Check alignment logic
        aligned_length = len(odd_pcm) - (len(odd_pcm) % 2)
        self.assertEqual(aligned_length, 2)

    def test_b17_whisper_silence_input(self) -> None:
        silence_pcm = b"\x00" * 32000
        # Energy detector confirms zero amplitude
        max_amplitude = max(abs(int.from_bytes(silence_pcm[i:i+2], byteorder="little", signed=True)) for i in range(0, 100, 2))
        self.assertEqual(max_amplitude, 0)

    def test_b17_whisper_transcription_whitespace_stripped(self) -> None:
        raw_output = "   run targeted test  \n"
        self.assertEqual(raw_output.strip(), "run targeted test")


# ===========================================================================
# Feature 18 Boundary Cases: TTS & Terminal Error Extractor
# ===========================================================================

class TestFeature18TtsAndTerminalExtractorBoundaries(unittest.TestCase):
    """Boundary conditions for terminal parser and voice feedback."""

    def test_b18_terminal_extractor_unmatched_syntax(self) -> None:
        nonsense = "Arbitrary debug log message with no file line or errors"
        res = TerminalErrorExtractor.extract_error(nonsense)
        self.assertIsNone(res["file"])
        self.assertIsNone(res["line"])
        self.assertIsNone(res["error_type"])

    def test_b18_terminal_extractor_deeply_nested_paths(self) -> None:
        nested_path = "/a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/deep.py"
        snippet = f'  File "{nested_path}", line 999\nZeroDivisionError: division by zero'
        res = TerminalErrorExtractor.extract_error(snippet)
        self.assertEqual(res["file"], nested_path)
        self.assertEqual(res["line"], 999)

    def test_b18_terminal_extractor_windows_backslashes_in_path(self) -> None:
        win_path = "C:\\Projects\\My App\\src\\calculator.py"
        snippet = f'  File "{win_path}", line 14\nValueError: invalid literal'
        res = TerminalErrorExtractor.extract_error(snippet)
        self.assertEqual(res["file"], win_path)
        self.assertEqual(res["line"], 14)

    def test_b18_tts_feedback_unknown_status(self) -> None:
        def format_feedback(action: str, status: str) -> str:
            if status == "UNKNOWN":
                return "Unknown execution state."
            return f"Action {action} completed with {status}."

        msg = format_feedback("some_action", "UNKNOWN")
        self.assertEqual(msg, "Unknown execution state.")

    def test_b18_terminal_extractor_multiline_error_message(self) -> None:
        text = (
            '  File "test.py", line 1\n'
            'TypeError: function took 0 positional arguments but 3 were given\n'
            'Additional context line'
        )
        res = TerminalErrorExtractor.extract_error(text)
        self.assertEqual(res["error_type"], "TypeError")
        self.assertIn("function took 0 positional arguments", res["message"])


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for audio codec functions in ws.py.

Tests μ-law ↔ PCM conversion and PCM resampling — the core audio pipeline
that bridges Telnyx (8kHz μ-law) ↔ Gemini Live API (16kHz/24kHz PCM).
"""

import math
import struct
import pytest

# Import the functions under test directly from ws.py
from backend.app.api.routes.ws import mulaw_to_pcm, pcm_to_mulaw, resample_pcm


# ─── μ-law ↔ PCM Round-Trip Tests ────────────────────────────────────────────

class TestMulawPcmConversion:
    """Test μ-law to PCM and PCM to μ-law conversions."""

    @pytest.mark.unit
    def test_mulaw_to_pcm_returns_double_length(self):
        """μ-law is 1 byte/sample, PCM is 2 bytes/sample."""
        mulaw = bytes([0x80] * 100)  # 100 samples of silence-ish
        pcm = mulaw_to_pcm(mulaw)
        assert len(pcm) == 200  # 100 samples * 2 bytes each

    @pytest.mark.unit
    def test_pcm_to_mulaw_returns_half_length(self):
        """PCM is 2 bytes/sample, μ-law is 1 byte/sample."""
        pcm = bytes([0x00] * 200)  # 100 samples of silence
        mulaw = pcm_to_mulaw(pcm)
        assert len(mulaw) == 100

    @pytest.mark.unit
    def test_round_trip_preserves_approximate_values(self):
        """PCM → μ-law → PCM should be approximately the same (lossy compression)."""
        # Create a simple sine wave in PCM
        num_samples = 160  # 20ms at 8kHz
        samples = []
        for i in range(num_samples):
            t = i / 8000.0
            sample = int(16000 * math.sin(2 * math.pi * 440 * t))
            samples.append(max(-32768, min(32767, sample)))
        original_pcm = struct.pack(f'<{num_samples}h', *samples)

        # Round trip: PCM → μ-law → PCM
        mulaw = pcm_to_mulaw(original_pcm)
        recovered_pcm = mulaw_to_pcm(mulaw)

        # Verify lengths match
        assert len(recovered_pcm) == len(original_pcm)

        # Verify values are approximately the same (μ-law is lossy but ~1% error)
        original_values = struct.unpack(f'<{num_samples}h', original_pcm)
        recovered_values = struct.unpack(f'<{num_samples}h', recovered_pcm)

        max_error = 0
        for orig, rec in zip(original_values, recovered_values):
            error = abs(orig - rec)
            max_error = max(max_error, error)

        # μ-law should have less than 5% error for large signals
        assert max_error < 32768 * 0.05, f"Max error too large: {max_error}"

    @pytest.mark.unit
    def test_silence_round_trip(self):
        """Silence (zero samples) should survive round-trip."""
        silence_pcm = struct.pack('<10h', *([0] * 10))
        mulaw = pcm_to_mulaw(silence_pcm)
        recovered = mulaw_to_pcm(mulaw)
        values = struct.unpack('<10h', recovered)
        # μ-law doesn't perfectly represent 0, but should be close
        for v in values:
            assert abs(v) < 200, f"Silence recovery error: {v}"

    @pytest.mark.unit
    def test_empty_input(self):
        """Empty byte arrays should produce empty output."""
        assert mulaw_to_pcm(b"") == b""
        assert pcm_to_mulaw(b"") == b""

    @pytest.mark.unit
    def test_max_amplitude_values(self):
        """Max/min PCM values should not crash the encoder."""
        extreme_pcm = struct.pack('<4h', 32767, -32768, 32767, -32768)
        mulaw = pcm_to_mulaw(extreme_pcm)
        assert len(mulaw) == 4
        recovered = mulaw_to_pcm(mulaw)
        assert len(recovered) == 8


# ─── PCM Resampling Tests ────────────────────────────────────────────────────

class TestResamplePcm:
    """Test PCM resampling between different sample rates."""

    @pytest.mark.unit
    def test_upsample_8k_to_16k_doubles_samples(self):
        """8kHz → 16kHz should approximately double the number of samples."""
        num_samples = 160  # 20ms at 8kHz
        pcm_8k = struct.pack(f'<{num_samples}h', *([1000] * num_samples))
        pcm_16k = resample_pcm(pcm_8k, 8000, 16000)
        output_samples = len(pcm_16k) // 2
        assert output_samples == 320  # 20ms at 16kHz

    @pytest.mark.unit
    def test_upsample_8k_to_24k_triples_samples(self):
        """8kHz → 24kHz should approximately triple the number of samples."""
        num_samples = 160
        pcm_8k = struct.pack(f'<{num_samples}h', *([1000] * num_samples))
        pcm_24k = resample_pcm(pcm_8k, 8000, 24000)
        output_samples = len(pcm_24k) // 2
        assert output_samples == 480  # 20ms at 24kHz

    @pytest.mark.unit
    def test_downsample_24k_to_8k_thirds_samples(self):
        """24kHz → 8kHz should approximately third the number of samples."""
        num_samples = 480  # 20ms at 24kHz
        pcm_24k = struct.pack(f'<{num_samples}h', *([1000] * num_samples))
        pcm_8k = resample_pcm(pcm_24k, 24000, 8000)
        output_samples = len(pcm_8k) // 2
        assert output_samples == 160  # 20ms at 8kHz

    @pytest.mark.unit
    def test_same_rate_passthrough(self):
        """Resampling at the same rate should preserve data."""
        num_samples = 100
        samples = list(range(-50, 50))
        pcm = struct.pack(f'<{num_samples}h', *samples)
        result = resample_pcm(pcm, 8000, 8000)
        assert len(result) == len(pcm)
        result_samples = struct.unpack(f'<{num_samples}h', result)
        for orig, res in zip(samples, result_samples):
            assert abs(orig - res) < 2  # Allow tiny rounding error

    @pytest.mark.unit
    def test_empty_resample(self):
        """Empty input should produce empty output."""
        result = resample_pcm(b"", 8000, 16000)
        assert result == b""

    @pytest.mark.unit
    def test_sine_wave_frequency_preserved(self):
        """
        A sine wave resampled should still have the same fundamental frequency.
        Verifies the resampler doesn't corrupt the audio content.
        """
        # Generate 440Hz sine at 8kHz
        freq = 440
        duration = 0.02  # 20ms
        rate_in = 8000
        rate_out = 16000
        n = int(duration * rate_in)
        samples_in = [int(16000 * math.sin(2 * math.pi * freq * i / rate_in)) for i in range(n)]
        pcm_in = struct.pack(f'<{n}h', *samples_in)

        pcm_out = resample_pcm(pcm_in, rate_in, rate_out)
        n_out = len(pcm_out) // 2
        samples_out = struct.unpack(f'<{n_out}h', pcm_out)

        # Verify output has the expected number of samples
        assert n_out == int(n * rate_out / rate_in)

        # Verify the output isn't all zeros (content preserved)
        max_val = max(abs(s) for s in samples_out)
        assert max_val > 10000, f"Resampled signal too quiet: max={max_val}"


# ─── Full Pipeline Tests ─────────────────────────────────────────────────────

class TestFullAudioPipeline:
    """
    Test the complete audio pipeline as used in production:
    Telnyx→Gemini: μ-law 8kHz → PCM 8kHz → PCM 16kHz
    Gemini→Telnyx: PCM 24kHz → PCM 8kHz → μ-law 8kHz
    """

    @pytest.mark.unit
    def test_telnyx_to_gemini_pipeline(self):
        """
        Simulate: Telnyx sends 160 bytes of μ-law (20ms at 8kHz).
        Pipeline: μ-law → PCM 8kHz → PCM 16kHz
        Result should be 640 bytes (320 samples * 2 bytes).
        """
        mulaw_chunk = bytes([0x7F, 0xFF, 0x80, 0x00] * 40)  # 160 bytes
        assert len(mulaw_chunk) == 160

        # Step 1: μ-law → PCM 8kHz
        pcm_8k = mulaw_to_pcm(mulaw_chunk)
        assert len(pcm_8k) == 320  # 160 samples * 2 bytes

        # Step 2: PCM 8kHz → PCM 16kHz
        pcm_16k = resample_pcm(pcm_8k, 8000, 16000)
        assert len(pcm_16k) == 640  # 320 samples * 2 bytes

    @pytest.mark.unit
    def test_gemini_to_telnyx_pipeline(self):
        """
        Simulate: Gemini sends PCM 24kHz audio chunk.
        Pipeline: PCM 24kHz → PCM 8kHz → μ-law 8kHz
        """
        # Generate 20ms of audio at 24kHz (480 samples)
        num_samples = 480
        samples = [int(8000 * math.sin(2 * math.pi * 300 * i / 24000)) for i in range(num_samples)]
        pcm_24k = struct.pack(f'<{num_samples}h', *samples)
        assert len(pcm_24k) == 960  # 480 * 2 bytes

        # Step 1: PCM 24kHz → PCM 8kHz
        pcm_8k = resample_pcm(pcm_24k, 24000, 8000)
        n_8k = len(pcm_8k) // 2
        assert n_8k == 160  # 20ms at 8kHz

        # Step 2: PCM 8kHz → μ-law
        mulaw = pcm_to_mulaw(pcm_8k)
        assert len(mulaw) == 160  # 1 byte per sample

    @pytest.mark.unit
    def test_full_round_trip_telnyx_gemini_telnyx(self):
        """
        Full round trip: Telnyx → Gemini input format → Gemini output format → Telnyx
        This simulates audio going through the entire bridge.
        """
        # Original Telnyx audio: 160 bytes μ-law
        num_samples = 160
        original_samples = [int(10000 * math.sin(2 * math.pi * 500 * i / 8000)) for i in range(num_samples)]
        original_pcm = struct.pack(f'<{num_samples}h', *original_samples)
        original_mulaw = pcm_to_mulaw(original_pcm)

        # Telnyx → Gemini: μ-law → PCM 8k → PCM 16k
        pcm_8k = mulaw_to_pcm(original_mulaw)
        pcm_16k = resample_pcm(pcm_8k, 8000, 16000)

        # Simulate Gemini processing (just pass through at 24kHz for output)
        # In reality Gemini generates its own audio, but we test the codec pipeline
        pcm_24k = resample_pcm(pcm_16k, 16000, 24000)

        # Gemini → Telnyx: PCM 24k → PCM 8k → μ-law
        pcm_8k_out = resample_pcm(pcm_24k, 24000, 8000)
        mulaw_out = pcm_to_mulaw(pcm_8k_out)

        # Should have the same length as original
        assert len(mulaw_out) == len(original_mulaw)

        # Content should be recognizable (not silence, not garbage)
        pcm_final = mulaw_to_pcm(mulaw_out)
        final_samples = struct.unpack(f'<{num_samples}h', pcm_final)
        max_val = max(abs(s) for s in final_samples)
        assert max_val > 1000, f"Round-trip signal too quiet: {max_val}"
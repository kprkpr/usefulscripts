#!/usr/bin/env python3
"""
StepMania .sm File Generator
=============================
Analyzes audio files and generates StepMania DDR step charts (.sm)
with multiple difficulty levels (Beginner → Challenge).

Uses audio analysis for step-chart generation:
    - BPM detection via tempo estimation (madmom neural net or librosa fallback)
    - Beat & downbeat tracking via DBN / accent-pattern analysis
    - Onset detection via spectral flux
    - Spectral band analysis for musically-aware arrow placement
    - Optional background video conversion to MP4 (H.264, no audio)

Requirements:
        pip install librosa numpy soundfile
        pip install madmom          # optional but STRONGLY recommended for accuracy (Install using git madmom repo if Python > 3.9)
        System: ffmpeg (for audio/video decoding + conversion)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import traceback
import subprocess
import shutil
import numpy as np
import random
from pathlib import Path

try:
    import librosa
except ImportError:
    print("ERROR: librosa is required. Install with:  pip install librosa numpy soundfile")
    sys.exit(1)

# madmom: optional but MUCH more accurate for BPM + downbeat detection
HAS_MADMOM = False
try:
    import madmom
    import madmom.features.beats
    import madmom.features.downbeats
    import madmom.features.tempo
    HAS_MADMOM = True
except ImportError:
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Audio Conversion Helper
# ──────────────────────────────────────────────────────────────────────────────

def convert_to_mp3(input_path: str, callback=None) -> str:
    """Convert audio file to MP3 if it's not already MP3.
    
    Returns the path to the MP3 file (original if already MP3, converted otherwise).
    """
    cb = callback or (lambda msg, pct: None)
    
    input_path = Path(input_path)
    if input_path.suffix.lower() == '.mp3':
        cb("Audio is already MP3, no conversion needed", 3)
        return str(input_path)
    
    # Check if ffmpeg is available
    if not shutil.which('ffmpeg'):
        raise RuntimeError(
            "ffmpeg is required to convert audio to MP3.\n"
            "Install it with: sudo apt install ffmpeg (Linux) or brew install ffmpeg (macOS)"
        )
    
    output_path = input_path.with_suffix('.mp3')
    cb(f"Converting {input_path.suffix} to MP3...", 2)
    
    try:
        # Use ffmpeg to convert to MP3 with good quality settings
        result = subprocess.run(
            [
                'ffmpeg', '-i', str(input_path),
                '-codec:a', 'libmp3lame',
                '-qscale:a', '2',  # High quality (VBR ~190 kbps)
                '-y',  # Overwrite if exists
                str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")
        
        if not output_path.exists():
            raise RuntimeError("MP3 file was not created")
        
        cb(f"Converted to MP3: {output_path.name}", 4)
        return str(output_path)
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Audio conversion timed out (5 min limit)")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")


def convert_to_mp4_video(input_path: str, callback=None) -> str:
    """Convert a video file to MP4 (H.264) with no audio.

    Returns the path to the MP4 file (original if already compatible).
    """
    cb = callback or (lambda msg, pct: None)

    input_path = Path(input_path)
    if not input_path.exists():
        raise RuntimeError(f"Video file not found: {input_path}")

    if not shutil.which('ffmpeg'):
        raise RuntimeError(
            "ffmpeg is required to convert video to MP4.\n"
            "Install it with: sudo apt install ffmpeg (Linux) or brew install ffmpeg (macOS)"
        )

    def _is_compatible_mp4(path: Path) -> bool:
        if path.suffix.lower() != '.mp4':
            return False
        if not shutil.which('ffprobe'):
            cb("ffprobe not found; converting video to be safe", 3)
            return False
        try:
            probe = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=codec_name',
                    '-of', 'default=nokey=1:noprint_wrappers=1',
                    str(path)
                ],
                capture_output=True,
                text=True,
                timeout=15
            )
            vcodec = probe.stdout.strip() if probe.returncode == 0 else ''

            probe_a = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'a',
                    '-show_entries', 'stream=codec_name',
                    '-of', 'default=nokey=1:noprint_wrappers=1',
                    str(path)
                ],
                capture_output=True,
                text=True,
                timeout=15
            )
            has_audio = bool(probe_a.stdout.strip())

            return vcodec == 'h264' and not has_audio
        except Exception:
            cb("ffprobe error; converting video to be safe", 3)
            return False

    if _is_compatible_mp4(input_path):
        cb("Video already MP4 (H.264) with no audio, no conversion needed", 3)
        return str(input_path)

    if input_path.suffix.lower() == '.mp4':
        output_path = input_path.with_name(f"{input_path.stem}_smgen.mp4")
    else:
        output_path = input_path.with_suffix('.mp4')

    cb(f"Converting video to MP4 (H.264, no audio): {input_path.name} …", 2)

    try:
        result = subprocess.run(
            [
                'ffmpeg', '-i', str(input_path),
                '-map', '0:v:0',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-an',
                '-movflags', '+faststart',
                '-y',
                str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError("MP4 file was not created")

        cb(f"Converted video: {output_path.name}", 4)
        return str(output_path)

    except subprocess.TimeoutExpired:
        raise RuntimeError("Video conversion timed out (10 min limit)")
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found. Please install ffmpeg.")


# ──────────────────────────────────────────────────────────────────────────────
# Audio Analysis
# ──────────────────────────────────────────────────────────────────────────────

class AudioAnalyzer:
    """Extracts musical features from an audio file for step-chart generation."""

    def __init__(self, filepath: str, callback=None, bpm_override: float = None):
        self.filepath = filepath
        self._cb = callback or (lambda msg, pct: None)
        self.bpm_override = bpm_override
        self.y = None
        self.sr = 22050
        self.duration = 0.0
        self.bpm = 120.0
        self.beat_times = np.array([])
        self.onset_times = np.array([])
        self.onset_strengths = np.array([])
        self.mel_spec = None
        self.n_mels = 128
        self.music_start = 0.0       # time (s) when music actually begins
        self.first_downbeat = 0.0    # time (s) of the first aligned downbeat
        self.rms = None              # RMS energy envelope

    # -- helpers --
    def _log(self, msg, pct=0):
        self._cb(msg, pct)

    # -- pipeline steps --
    def load_audio(self):
        self._log("Loading audio file …", 5)
        try:
            self.y, self.sr = librosa.load(self.filepath, sr=self.sr, mono=True)
        except Exception as e:
            raise RuntimeError(
                f"Cannot load audio.  Is ffmpeg installed?\n{e}"
            )
        self.duration = librosa.get_duration(y=self.y, sr=self.sr)
        self._log(f"Loaded: {self.duration:.1f}s  SR={self.sr} Hz", 10)

    def compute_mel_spectrogram(self):
        self._log("Computing mel spectrogram …", 15)
        S = librosa.feature.melspectrogram(
            y=self.y, sr=self.sr, n_mels=self.n_mels, fmax=8000
        )
        self.mel_spec = librosa.power_to_db(S, ref=np.max)
        self._log("Mel spectrogram ready", 25)

    def detect_music_start(self):
        """Find the actual start of music by detecting when RMS energy
        exceeds a meaningful threshold.  Avoids false beats in silence."""
        self._log("Detecting music start …", 28)
        # Compute RMS in short frames
        self.rms = librosa.feature.rms(y=self.y, frame_length=2048, hop_length=512)[0]
        rms_times = librosa.frames_to_time(
            np.arange(len(self.rms)), sr=self.sr, hop_length=512
        )

        # Threshold: 5% of the peak RMS (catches soft intros but ignores noise)
        peak_rms = np.max(self.rms)
        threshold = peak_rms * 0.05

        # Find the first frame that exceeds the threshold
        above = np.where(self.rms > threshold)[0]
        if len(above) > 0:
            self.music_start = float(rms_times[above[0]])
        else:
            self.music_start = 0.0

        # Small safety margin: step back 50ms so we don't clip the attack
        self.music_start = max(0.0, self.music_start - 0.05)
        self._log(f"Music starts at {self.music_start:.3f}s", 30)

    def _estimate_bpm_multimethod(self):
        """Estimate BPM using multiple methods and pick the best candidate.

        librosa.beat.beat_track often doubles or mis-detects BPM on
        syncopated genres (reggaeton, trap, …).  We cross-check with
        onset-autocorrelation and spectral-flux tempogram to find the
        true tempo.
        """
        self._log("  Method 1: beat_track …", 33)
        onset_env = librosa.onset.onset_strength(y=self.y, sr=self.sr)

        # --- Method 1: default beat_track ---
        tempo1, _ = librosa.beat.beat_track(y=self.y, sr=self.sr,
                                            onset_envelope=onset_env)
        t1 = float(tempo1[0]) if hasattr(tempo1, '__len__') else float(tempo1)

        # --- Method 2: beat_track with alternative start_bpm prior ---
        # librosa's beat_track uses a Bayesian prior centred on start_bpm
        # (default 120).  Running again with start_bpm=95 biases toward
        # the 80-110 range common in reggaeton / trap / hip-hop / latin
        # and acts as a cross-check to catch tempo-doubling errors.
        self._log("  Method 2: beat_track (start_bpm=95) …", 34)
        tempo2, _ = librosa.beat.beat_track(y=self.y, sr=self.sr,
                                            onset_envelope=onset_env,
                                            start_bpm=95)
        t2 = float(tempo2[0]) if hasattr(tempo2, '__len__') else float(tempo2)

        # --- Method 3: tempogram autocorrelation (gives multiple peaks) ---
        self._log("  Method 3: tempo via tempogram …", 35)
        tempo3 = librosa.feature.tempo(
            onset_envelope=onset_env, sr=self.sr, aggregate=None
        )
        # tempo3 is an array of one or more candidates
        t3_candidates = [float(t) for t in np.atleast_1d(tempo3) if 40 < float(t) < 240]

        # --- Method 4: onset-autocorrelation on percussive component ---
        self._log("  Method 4: percussive onset autocorrelation …", 36)
        y_perc = librosa.effects.percussive(self.y, margin=3.0)
        onset_perc = librosa.onset.onset_strength(y=y_perc, sr=self.sr)
        tempo4, _ = librosa.beat.beat_track(y=y_perc, sr=self.sr,
                                            onset_envelope=onset_perc)
        t4 = float(tempo4[0]) if hasattr(tempo4, '__len__') else float(tempo4)

        # --- Collect all raw candidates ---
        raw = [t1, t2, t4] + t3_candidates
        self._log(f"  Raw candidates: {[f'{t:.1f}' for t in raw]}", 37)

        # --- Generate octave variants for each raw candidate ---
        candidates = set()
        for t in raw:
            for mult in (0.5, 1.0, 2.0, 2.0/3.0, 3.0/2.0, 4.0/3.0, 3.0/4.0):
                v = t * mult
                if 60 <= v <= 200:
                    candidates.add(round(v, 2))

        if not candidates:
            candidates = {round(t1, 2)}

        # --- Score each candidate ---
        # Prefer tempos whose beat grid aligns well with detected onsets
        best_score = -1
        best_bpm = t1
        onset_times_for_score = librosa.frames_to_time(
            np.where(onset_env > np.percentile(onset_env, 75))[0],
            sr=self.sr
        )

        for bpm_c in candidates:
            beat_period = 60.0 / bpm_c
            # For each onset, check distance to nearest beat-grid line
            total_score = 0.0
            for ot in onset_times_for_score:
                phase = (ot / beat_period) % 1.0
                # How close is this onset to a beat grid line? (0=perfect)
                dist = min(phase, 1.0 - phase)
                total_score += max(0.0, 0.5 - dist)  # bonus if within half-beat
            # Normalise
            total_score /= max(len(onset_times_for_score), 1)
            # Small bias toward the 80-130 range (most pop/reggaeton/hip-hop)
            if 80 <= bpm_c <= 130:
                total_score *= 1.10

            if total_score > best_score:
                best_score = total_score
                best_bpm = bpm_c

        self._log(f"  Best BPM candidate: {best_bpm:.1f} (score {best_score:.4f})", 38)
        return best_bpm

    def detect_bpm_and_beats(self):
        self._log("Detecting BPM & beats …", 32)

        if HAS_MADMOM:
            self._log("  Using madmom (neural network) backend", 33)
            self._detect_with_madmom()
        else:
            self._log("  Using librosa backend (install madmom for better accuracy)", 33)
            self._detect_with_librosa()

        self._log(f"BPM ≈ {self.bpm:.1f}   |   {len(self.beat_times)} beats", 40)
        self._log(f"  First downbeat at {self.first_downbeat:.3f}s", 42)

    # ── madmom backend ────────────────────────────────────────────────

    def _detect_with_madmom(self):
        """Use madmom's neural-network models for BPM, beats, and downbeats.

        madmom's RNNBeatProcessor + DBNBeatTrackingProcessor is
        state-of-the-art for beat tracking across genres.  Its downbeat
        model (RNNDownBeatProcessor) directly predicts which beat is
        beat-1, eliminating the phase-guessing heuristic.
        """
        # ---- BPM ----
        if self.bpm_override and self.bpm_override > 0:
            self.bpm = self.bpm_override
            self._log(f"  Using manual BPM override: {self.bpm:.1f}", 34)
        else:
            self._log("  madmom: estimating tempo …", 34)
            try:
                act_proc = madmom.features.beats.RNNBeatProcessor()
                act = act_proc(self.filepath)
                tempo_proc = madmom.features.tempo.TempoEstimationProcessor(fps=100)
                tempi = tempo_proc(act)  # [[bpm, confidence], …]
                if len(tempi) > 0:
                    self.bpm = float(tempi[0][0])
                    self._log(f"  madmom tempo: {self.bpm:.1f} BPM "
                              f"(confidence {tempi[0][1]:.2f})", 35)
                else:
                    self._log("  madmom tempo failed, falling back to librosa", 35)
                    self.bpm = self._estimate_bpm_multimethod()
            except Exception as e:
                self._log(f"  madmom tempo error: {e}, falling back to librosa", 35)
                self.bpm = self._estimate_bpm_multimethod()

        self.bpm = round(self.bpm * 2) / 2  # snap to nearest 0.5

        # ---- Beat tracking ----
        self._log("  madmom: tracking beats …", 36)
        try:
            act_proc = madmom.features.beats.RNNBeatProcessor()
            act = act_proc(self.filepath)
            beat_proc = madmom.features.beats.DBNBeatTrackingProcessor(
                fps=100, min_bpm=max(40, self.bpm - 30),
                max_bpm=min(240, self.bpm + 30)
            )
            all_beat_times = beat_proc(act)
        except Exception as e:
            self._log(f"  madmom beat tracking error: {e}, using librosa", 37)
            _, beat_frames = librosa.beat.beat_track(
                y=self.y, sr=self.sr, bpm=self.bpm
            )
            all_beat_times = librosa.frames_to_time(beat_frames, sr=self.sr)

        self.beat_times = all_beat_times[all_beat_times >= self.music_start]
        discarded = len(all_beat_times) - len(self.beat_times)
        if discarded > 0:
            self._log(f"  Discarded {discarded} beats in leading silence", 37)

        # ---- Downbeat detection ----
        self._log("  madmom: detecting downbeats …", 38)
        try:
            db_proc = madmom.features.downbeats.RNNDownBeatProcessor()
            db_act = db_proc(self.filepath)
            dbn = madmom.features.downbeats.DBNDownBeatTrackingProcessor(
                beats_per_bar=[4, 3], fps=100
            )
            downbeat_info = dbn(db_act)  # Nx2 array: [[time, beat_num], …]

            # beat_num == 1 means downbeat (beat 1 of the bar)
            downbeats = downbeat_info[downbeat_info[:, 1] == 1]
            valid_db = downbeats[downbeats[:, 0] >= self.music_start - 0.1]

            if len(valid_db) > 0:
                self.first_downbeat = float(valid_db[0, 0])
                self._log(f"  madmom found {len(valid_db)} downbeats, "
                          f"first at {self.first_downbeat:.3f}s", 39)
            else:
                self._log("  No valid downbeats from madmom, using accent analysis", 39)
                self._detect_downbeat_from_beat_strengths()
        except Exception as e:
            self._log(f"  madmom downbeat error: {e}, using accent analysis", 39)
            self._detect_downbeat_from_beat_strengths()

    # ── librosa backend ───────────────────────────────────────────────

    def _detect_with_librosa(self):
        """librosa-based BPM and beat detection with improved downbeat finding."""
        # ---- BPM ----
        if self.bpm_override and self.bpm_override > 0:
            self.bpm = self.bpm_override
            self._log(f"  Using manual BPM override: {self.bpm:.1f}", 34)
        else:
            self.bpm = self._estimate_bpm_multimethod()

        self.bpm = round(self.bpm * 2) / 2  # snap to nearest 0.5

        # ---- Beat tracking with the chosen BPM as hint ----
        _, beat_frames = librosa.beat.beat_track(
            y=self.y, sr=self.sr, bpm=self.bpm
        )
        all_beat_times = librosa.frames_to_time(beat_frames, sr=self.sr)

        # ---- Filter out beats before music actually starts ----
        self.beat_times = all_beat_times[all_beat_times >= self.music_start]
        discarded = len(all_beat_times) - len(self.beat_times)
        if discarded > 0:
            self._log(f"  Discarded {discarded} beats in leading silence", 39)

        # ---- Find the first downbeat via accent-pattern analysis ----
        self._detect_downbeat_from_beat_strengths()

    # ── downbeat detection by accent analysis ─────────────────────────

    def _detect_downbeat_from_beat_strengths(self):
        """Find the first downbeat by analysing accent patterns.

        In 4/4 music beat 1 (the downbeat) is typically the loudest /
        most accented beat in the bar.  We test all 4 possible phase
        alignments (does beat 1 land on the 0th, 1st, 2nd, or 3rd
        detected beat?) and pick the phase whose "downbeats" have the
        highest average onset-strength × RMS-energy product.
        """
        if len(self.beat_times) < 8:
            self.first_downbeat = (
                float(self.beat_times[0]) if len(self.beat_times) else 0.0
            )
            return

        # Onset strength at every beat position
        onset_env = librosa.onset.onset_strength(y=self.y, sr=self.sr)
        beat_frames = librosa.time_to_frames(self.beat_times, sr=self.sr)
        beat_frames = np.clip(beat_frames, 0, len(onset_env) - 1)
        beat_strengths = onset_env[beat_frames]

        # Also get low-frequency (bass) energy at each beat — bass hits
        # strongly correlate with downbeats in most genres.
        S = np.abs(librosa.stft(self.y, n_fft=2048, hop_length=512))
        bass_band = S[:8, :]  # lowest ~170 Hz
        bass_energy = np.mean(bass_band, axis=0)
        bass_frames = librosa.time_to_frames(
            self.beat_times, sr=self.sr, hop_length=512
        )
        bass_frames = np.clip(bass_frames, 0, bass_energy.shape[0] - 1)
        bass_at_beats = bass_energy[bass_frames]
        # normalise
        bass_max = np.max(bass_at_beats) if np.max(bass_at_beats) > 0 else 1.0
        bass_at_beats = bass_at_beats / bass_max

        best_phase = 0
        best_score = -1.0

        for phase in range(4):
            # Indices of beats that would be "beat 1" under this phase
            db_idx = np.arange(phase, len(beat_strengths), 4)
            other_idx = np.array(
                [i for i in range(len(beat_strengths)) if (i - phase) % 4 != 0]
            )

            if len(db_idx) == 0:
                continue

            db_str = beat_strengths[db_idx]
            other_str = (
                beat_strengths[other_idx] if len(other_idx) else np.array([1.0])
            )

            # Accent ratio: downbeats should be louder
            strength_ratio = np.mean(db_str) / (np.mean(other_str) + 1e-8)

            # RMS energy at candidate downbeat positions
            db_times = self.beat_times[db_idx]
            rms_values = np.array([self.get_rms_at(t) for t in db_times])
            rms_score = np.mean(rms_values)

            # Bass energy boost — bass drum typically hits on beat 1
            bass_score = np.mean(bass_at_beats[db_idx])

            # Combined score
            score = strength_ratio * (1.0 + rms_score) * (1.0 + bass_score)

            # Slight preference for phase 0 (first detected beat is often
            # beat 1, so break ties in its favour)
            if phase == 0:
                score *= 1.05

            self._log(f"    Downbeat phase {phase}: score={score:.3f} "
                      f"(accent={strength_ratio:.2f}, rms={rms_score:.2f}, "
                      f"bass={bass_score:.2f})", 39)

            if score > best_score:
                best_score = score
                best_phase = phase

        self.first_downbeat = float(self.beat_times[best_phase])

        # Walk backwards to the earliest valid downbeat
        beat_period = 60.0 / self.bpm
        measure_duration = 4 * beat_period
        while (self.first_downbeat - measure_duration
               >= self.music_start - beat_period * 0.25):
            self.first_downbeat -= measure_duration

        self._log(f"  Best downbeat: phase={best_phase}, "
                  f"score={best_score:.3f}", 40)

    def detect_onsets(self):
        self._log("Detecting onsets …", 50)
        env = librosa.onset.onset_strength(y=self.y, sr=self.sr)
        frames = librosa.onset.onset_detect(
            y=self.y, sr=self.sr, onset_envelope=env, backtrack=False
        )
        self.onset_times = librosa.frames_to_time(frames, sr=self.sr)
        raw = env[frames] if len(frames) else np.array([])
        mx = raw.max() if len(raw) else 1.0
        self.onset_strengths = raw / mx if mx > 0 else raw
        self._log(f"Found {len(self.onset_times)} onsets", 65)

    def get_dominant_band(self, t: float) -> int:
        """Return dominant frequency band 0-3 at time *t*.

        Band mapping (used for arrow assignment):
          0 → bass        → Left
          1 → low-mid     → Down
          2 → mid-high    → Up
          3 → high        → Right
        """
        frame = int(librosa.time_to_frames([t], sr=self.sr)[0])
        frame = np.clip(frame, 0, self.mel_spec.shape[1] - 1)
        spec = self.mel_spec[:, frame]
        bs = self.n_mels // 4
        energies = [
            np.mean(spec[i * bs: (i + 1) * bs if i < 3 else self.n_mels])
            for i in range(4)
        ]
        return int(np.argmax(energies))

    def get_rms_at(self, t: float) -> float:
        """Return the normalised RMS energy (0..1) at time *t*."""
        if self.rms is None:
            return 1.0
        frame = int(librosa.time_to_frames([t], sr=self.sr, hop_length=512)[0])
        frame = np.clip(frame, 0, len(self.rms) - 1)
        peak = np.max(self.rms)
        return float(self.rms[frame] / peak) if peak > 0 else 0.0

    # -- public API --
    def analyze(self):
        self.load_audio()
        self.compute_mel_spectrogram()
        self.detect_music_start()
        self.detect_bpm_and_beats()
        self.detect_onsets()
        self._log("Audio analysis complete!", 70)
        return self


# ──────────────────────────────────────────────────────────────────────────────
# Step-Chart Generation
# ──────────────────────────────────────────────────────────────────────────────

class StepChartGenerator:
    """Turns audio-analysis results into playable DDR step charts."""

    LEFT_FOOT  = [0, 1]   # Left, Down
    RIGHT_FOOT = [2, 3]   # Up, Right

    CONFIGS = {
        'Beginner': dict(
            level=1, subdiv=4, use_beats_only=True, beat_skip=2,
            onset_thresh=0.95, jump_prob=0.00, max_nps=1.5,
            jack_ok=False, alt_pref=True,
        ),
        'Easy': dict(
            level=3, subdiv=4, use_beats_only=True, beat_skip=1,
            onset_thresh=0.75, jump_prob=0.03, max_nps=3.0,
            jack_ok=False, alt_pref=True,
        ),
        'Medium': dict(
            level=6, subdiv=8, use_beats_only=False, beat_skip=1,
            onset_thresh=0.40, jump_prob=0.08, max_nps=5.0,
            jack_ok=False, alt_pref=False,
        ),
        'Hard': dict(
            level=8, subdiv=16, use_beats_only=False, beat_skip=1,
            onset_thresh=0.25, jump_prob=0.12, max_nps=9.0,
            jack_ok=True, alt_pref=False,
        ),
        'Challenge': dict(
            level=10, subdiv=16, use_beats_only=False, beat_skip=1,
            onset_thresh=0.10, jump_prob=0.18, max_nps=14.0,
            jack_ok=True, alt_pref=False,
        ),
    }

    def __init__(self, analyzer: AudioAnalyzer, seed=None, callback=None):
        self.az = analyzer
        self._cb = callback or (lambda m, p: None)
        self.rng = random.Random(seed)
        self.charts: dict = {}

    def _log(self, msg, pct=0):
        self._cb(msg, pct)

    # -- arrow assignment --
    def _pick_arrow(self, t, prev, cfg):
        band = self.az.get_dominant_band(t)
        arrow = band

        # 30 % random variety
        if self.rng.random() < 0.30:
            arrow = self.rng.randint(0, 3)

        # easy diffs: alternate left-side / right-side
        if cfg['alt_pref'] and prev:
            last = prev[-1]
            arrow = self.rng.choice(
                self.RIGHT_FOOT if last in self.LEFT_FOOT else self.LEFT_FOOT
            )

        # avoid jacks on lower diffs
        if not cfg['jack_ok'] and prev:
            for _ in range(12):
                if arrow != prev[-1]:
                    break
                arrow = self.rng.randint(0, 3)

        row = [0, 0, 0, 0]
        row[arrow] = 1

        # jumps
        if cfg['jump_prob'] and self.rng.random() < cfg['jump_prob']:
            alt = [i for i in range(4) if i != arrow]
            row[self.rng.choice(alt)] = 1

        return row, arrow

    # -- post-processing rules (ergonomic / musical polish) --

    def _postprocess(self, measures, subdiv, cfg):
        """Apply rules to make charts feel more natural & playable."""
        bpm = self.az.bpm
        spm = 4 * 60.0 / bpm
        spr = spm / subdiv
        offset = self.az.first_downbeat

        # ---------- Rule 1: Mute arrows during quiet sections ----------
        for m_idx, meas in enumerate(measures):
            for r_idx, row in enumerate(meas):
                if not any(v > 0 for v in row):
                    continue
                t = offset + (m_idx * subdiv + r_idx) * spr
                energy = self.az.get_rms_at(t)
                if energy < 0.08:          # very quiet
                    row[:] = [0, 0, 0, 0]

        # ---------- Rule 2: Avoid crossovers on lower diffs ----------
        # L,D = left foot;  U,R = right foot
        # Bad crossover: last was L(0) and now R(3) immediately → ugly
        if cfg['level'] <= 6:
            prev_arrow = -1
            for meas in measures:
                for row in meas:
                    arrows = [i for i in range(4) if row[i]]
                    if len(arrows) == 1:
                        a = arrows[0]
                        # Crossover: left-foot arrow → right-foot arrow skipping middle
                        if prev_arrow == 0 and a == 3:  # L → R
                            row[:] = [0, 0, 1, 0]  # switch to Up
                        elif prev_arrow == 3 and a == 0:  # R → L
                            row[:] = [0, 1, 0, 0]  # switch to Down
                        prev_arrow = [i for i in range(4) if row[i]][0] if any(row) else prev_arrow

        # ---------- Rule 3: Add emphasis jumps on downbeats (med+ diffs) ----------
        if cfg['level'] >= 5:
            for m_idx, meas in enumerate(measures):
                # Downbeat = first row of each measure
                row = meas[0]
                if any(v > 0 for v in row) and sum(row) == 1:
                    t = offset + (m_idx * subdiv) * spr
                    energy = self.az.get_rms_at(t)
                    # Strong downbeat → maybe add a jump
                    if energy > 0.70 and self.rng.random() < 0.20:
                        active = row.index(1)
                        # Add opposite-side arrow for jump
                        if active in self.LEFT_FOOT:
                            partner = self.rng.choice(self.RIGHT_FOOT)
                        else:
                            partner = self.rng.choice(self.LEFT_FOOT)
                        row[partner] = 1

        # ---------- Rule 4: Smooth runs (hard+ diffs) ----------
        # When 4+ consecutive notes exist, make them flow L→D→U→R or reverse
        if cfg['level'] >= 8:
            flat = [(m_idx, r_idx, meas[r_idx])
                    for m_idx, meas in enumerate(measures)
                    for r_idx in range(len(meas))]
            run_start = None
            run_len = 0
            for i, (mi, ri, row) in enumerate(flat):
                has_note = any(v > 0 for v in row) and sum(row) == 1
                if has_note:
                    if run_start is None:
                        run_start = i
                    run_len += 1
                else:
                    if run_len >= 4:
                        self._smooth_run(flat, run_start, run_len)
                    run_start = None
                    run_len = 0
            if run_len >= 4:
                self._smooth_run(flat, run_start, run_len)

        # ---------- Rule 5: Gap between jumps ----------
        # Ensure at least 2 rows between consecutive jumps
        last_jump_gi = -999
        for m_idx, meas in enumerate(measures):
            for r_idx, row in enumerate(meas):
                gi = m_idx * subdiv + r_idx
                if sum(row) >= 2:  # jump
                    if gi - last_jump_gi < 3 and cfg['level'] < 9:
                        # Too close → downgrade to single
                        arrows = [i for i in range(4) if row[i]]
                        keep = self.rng.choice(arrows)
                        row[:] = [0, 0, 0, 0]
                        row[keep] = 1
                    else:
                        last_jump_gi = gi

        return measures

    def _smooth_run(self, flat, start, length):
        """Turn a consecutive run into a flowing L→D→U→R pattern."""
        # Pick direction
        patterns = [
            [0, 1, 2, 3],  # L D U R
            [3, 2, 1, 0],  # R U D L
            [0, 2, 1, 3],  # L U D R  (staircase)
            [3, 1, 2, 0],  # R D U L
        ]
        pat = self.rng.choice(patterns)
        for i in range(length):
            _, _, row = flat[start + i]
            arrow = pat[i % 4]
            row[:] = [0, 0, 0, 0]
            row[arrow] = 1

    # -- chart for one difficulty --
    def generate_chart(self, name):
        cfg   = self.CONFIGS[name]
        bpm   = self.az.bpm
        # Use the first downbeat as reference, not just beat_times[0]
        offset = self.az.first_downbeat
        bpmeas = 4                                   # beats per measure (4/4)
        spm    = bpmeas * 60.0 / bpm                 # seconds per measure
        subdiv = cfg['subdiv']
        spr    = spm / subdiv                        # seconds per row
        n_meas = int(np.ceil((self.az.duration - offset) / spm)) + 1

        # ---- collect grid positions that should have notes ----
        note_grid = set()

        # beats
        beats = self.az.beat_times[::cfg['beat_skip']]
        for bt in beats:
            if bt >= self.az.music_start and bt <= self.az.duration:
                ri = round((bt - offset) / spr)
                if ri >= 0 and abs((bt - offset) / spr - ri) < 0.45:
                    note_grid.add(ri)

        # onsets
        for ot, os_ in zip(self.az.onset_times, self.az.onset_strengths):
            if os_ >= cfg['onset_thresh'] and ot >= self.az.music_start and ot <= self.az.duration:
                ri = round((ot - offset) / spr)
                if ri >= 0 and abs((ot - offset) / spr - ri) < 0.45:
                    note_grid.add(ri)

        # density cap
        max_notes = int(self.az.duration * cfg['max_nps'])
        if len(note_grid) > max_notes:
            lst = sorted(note_grid)
            step = len(lst) / max_notes
            note_grid = {lst[int(i * step)] for i in range(max_notes)}

        # ---- build measures ----
        measures, prev = [], []
        for m in range(n_meas):
            mrows = []
            for r in range(subdiv):
                gi   = m * subdiv + r
                trow = offset + gi * spr
                if gi in note_grid and 0 <= trow <= self.az.duration:
                    row, arrow = self._pick_arrow(trow, prev, cfg)
                    mrows.append(row)
                    prev.append(arrow)
                    prev = prev[-8:]
                else:
                    mrows.append([0, 0, 0, 0])
            measures.append(mrows)

        # ---- post-processing ----
        measures = self._postprocess(measures, subdiv, cfg)

        # trim trailing empty measures (keep at least 1)
        while len(measures) > 1 and all(
            all(v == 0 for v in r) for r in measures[-1]
        ):
            measures.pop()

        note_count = sum(
            1 for ms in measures for r in ms if any(v > 0 for v in r)
        )
        return dict(
            difficulty=name, level=cfg['level'], subdiv=subdiv,
            measures=measures, note_count=note_count,
        )

    # -- generate all selected difficulties --
    def generate_all(self, selected=None):
        selected = selected or list(self.CONFIGS)
        base = 72
        for i, name in enumerate(selected):
            self._log(f"Generating {name} …", base + i * 5)
            self.charts[name] = self.generate_chart(name)
            self._log(
                f"  {name}: {self.charts[name]['note_count']} notes",
                base + (i + 1) * 5,
            )
        self._log("All charts generated!", 95)
        return self.charts


# ──────────────────────────────────────────────────────────────────────────────
# .sm File Writer
# ──────────────────────────────────────────────────────────────────────────────

class SMFileWriter:
    """Serialises step charts to the StepMania .sm format."""

    def __init__(
        self,
        analyzer: AudioAnalyzer,
        charts: dict,
        path: str,
        music_file: str = None,
        video_file: str = None
    ):
        self.az = analyzer
        self.charts = charts
        self.path = path
        self.music_file = music_file or analyzer.filepath
        self.video_file = video_file

    def write(self):
        title   = Path(self.az.filepath).stem
        music   = os.path.basename(self.music_file)
        video   = os.path.basename(self.video_file) if self.video_file else None
        # Use the first downbeat (properly aligned) for the SM offset
        offset  = -self.az.first_downbeat
        preview = self.az.duration * 0.30

        if video:
            bgchanges = f"#BGCHANGES:0.000000={video}=1.000000=0=0=0=0;\n"
        else:
            bgchanges = "#BGCHANGES:;\n"

        hdr = (
            f"#TITLE:{title};\n"
            f"#SUBTITLE:;\n"
            f"#ARTIST:Unknown Artist;\n"
            f"#TITLETRANSLIT:;\n"
            f"#SUBTITLETRANSLIT:;\n"
            f"#ARTISTTRANSLIT:;\n"
            f"#GENRE:;\n"
            f"#CREDIT:Auto-generated by SM Generator;\n"
            f"#BANNER:;\n"
            f"#BACKGROUND:;\n"
            f"#LYRICSPATH:;\n"
            f"#CDTITLE:;\n"
            f"#MUSIC:{music};\n"
            f"#OFFSET:{offset:.6f};\n"
            f"#SAMPLESTART:{preview:.6f};\n"
            f"#SAMPLELENGTH:15.000000;\n"
            f"#SELECTABLE:YES;\n"
            f"#BPMS:0.000000={self.az.bpm:.6f};\n"
            f"#STOPS:;\n"
            f"{bgchanges}"
        )

        parts = [hdr]
        for name in ('Beginner', 'Easy', 'Medium', 'Hard', 'Challenge'):
            if name not in self.charts:
                continue
            ch = self.charts[name]
            notes_hdr = (
                f"\n//---------------dance-single - {name}---------------\n"
                f"#NOTES:\n"
                f"     dance-single:\n"
                f"     :\n"
                f"     {name}:\n"
                f"     {ch['level']}:\n"
                f"     0.000000,0.000000,0.000000,0.000000,0.000000:\n"
            )
            measure_strs = []
            for meas in ch['measures']:
                rows = '\n'.join(''.join(str(v) for v in r) for r in meas)
                measure_strs.append(rows)
            notes_body = '\n,\n'.join(measure_strs) + '\n;\n'
            parts.append(notes_hdr + notes_body)

        with open(self.path, 'w', encoding='utf-8') as f:
            f.writelines(parts)
        return self.path


# ──────────────────────────────────────────────────────────────────────────────
# Tkinter GUI
# ──────────────────────────────────────────────────────────────────────────────

class App:
    """Main application window."""

    AUDIO_TYPES = (
        ('Audio files', '*.mp3 *.ogg *.opus *.wav *.flac *.m4a *.wma *.aac *.webm'),
        ('All files', '*.*'),
    )

    VIDEO_TYPES = (
        ('Video files', '*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.wmv *.flv'),
        ('All files', '*.*'),
    )

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StepMania .sm Generator")
        self.root.geometry("740x620")
        self.root.minsize(620, 520)

        # variables
        self.v_in   = tk.StringVar()
        self.v_out  = tk.StringVar()
        self.v_vid  = tk.StringVar()
        self.v_stat = tk.StringVar(value="Ready — select an audio file to begin.")
        self.v_prog = tk.DoubleVar()
        self.v_seed = tk.StringVar()
        self.v_bpm  = tk.StringVar()  # manual BPM override
        self.diff_vars: dict[str, tk.BooleanVar] = {}

        self._build()

    # ---- UI construction ----
    def _build(self):
        m = ttk.Frame(self.root, padding=14)
        m.pack(fill=tk.BOTH, expand=True)

        ttk.Label(m, text="StepMania .sm Generator",
                  font=('Segoe UI', 18, 'bold')).pack(pady=(0, 10))

        # input
        fi = ttk.LabelFrame(m, text="Audio File  (MP3 · OGG · OPUS · WAV · FLAC …)", padding=8)
        fi.pack(fill=tk.X, pady=4)
        ttk.Entry(fi, textvariable=self.v_in).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        ttk.Button(fi, text="Browse …", command=self._browse_in).pack(side=tk.RIGHT)

        # video (optional)
        fv = ttk.LabelFrame(m, text="Background Video (optional)", padding=8)
        fv.pack(fill=tk.X, pady=4)
        ttk.Entry(fv, textvariable=self.v_vid).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        ttk.Button(fv, text="Browse …", command=self._browse_vid).pack(side=tk.RIGHT)

        # output
        fo = ttk.LabelFrame(m, text="Output .sm File", padding=8)
        fo.pack(fill=tk.X, pady=4)
        ttk.Entry(fo, textvariable=self.v_out).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,8))
        ttk.Button(fo, text="Browse …", command=self._browse_out).pack(side=tk.RIGHT)

        # difficulties
        fd = ttk.LabelFrame(m, text="Difficulties", padding=8)
        fd.pack(fill=tk.X, pady=4)
        for n in ('Beginner', 'Easy', 'Medium', 'Hard', 'Challenge'):
            v = tk.BooleanVar(value=True)
            self.diff_vars[n] = v
            ttk.Checkbutton(fd, text=n, variable=v).pack(side=tk.LEFT, padx=8)

        # options
        fopt = ttk.LabelFrame(m, text="Options", padding=8)
        fopt.pack(fill=tk.X, pady=4)
        ttk.Label(fopt, text="BPM:").pack(side=tk.LEFT, padx=(0,4))
        ttk.Entry(fopt, textvariable=self.v_bpm, width=8).pack(side=tk.LEFT)
        ttk.Label(fopt, text="(auto-detect if empty)").pack(side=tk.LEFT, padx=(2,14))
        ttk.Label(fopt, text="Seed:").pack(side=tk.LEFT, padx=(0,4))
        ttk.Entry(fopt, textvariable=self.v_seed, width=10).pack(side=tk.LEFT)
        ttk.Label(fopt, text="(random if empty)").pack(side=tk.LEFT, padx=4)

        # generate
        self.btn = ttk.Button(m, text="  Generate .sm File  ",
                              command=self._on_gen)
        self.btn.pack(pady=14)

        # progress
        self.pb = ttk.Progressbar(m, variable=self.v_prog, maximum=100)
        self.pb.pack(fill=tk.X, pady=4)

        # log
        fl = ttk.LabelFrame(m, text="Log", padding=4)
        fl.pack(fill=tk.BOTH, expand=True, pady=4)
        self.log_w = tk.Text(fl, height=10, state=tk.DISABLED,
                             wrap=tk.WORD, font=('Consolas', 9))
        sb = ttk.Scrollbar(fl, orient=tk.VERTICAL, command=self.log_w.yview)
        self.log_w.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_w.pack(fill=tk.BOTH, expand=True)

        # status
        ttk.Label(m, textvariable=self.v_stat,
                  relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, pady=(4,0))

    # ---- callbacks ----
    def _browse_in(self):
        p = filedialog.askopenfilename(title="Select Audio", filetypes=self.AUDIO_TYPES)
        if p:
            self.v_in.set(p)
            self.v_out.set(str(Path(p).with_suffix('.sm')))

    def _browse_out(self):
        p = filedialog.asksaveasfilename(
            title="Save .sm", defaultextension='.sm',
            filetypes=[('StepMania', '*.sm'), ('All', '*.*')])
        if p:
            self.v_out.set(p)

    def _browse_vid(self):
        p = filedialog.askopenfilename(title="Select Video", filetypes=self.VIDEO_TYPES)
        if p:
            self.v_vid.set(p)

    def _log(self, msg, pct=None):
        def _do():
            self.log_w.config(state=tk.NORMAL)
            self.log_w.insert(tk.END, msg + '\n')
            self.log_w.see(tk.END)
            self.log_w.config(state=tk.DISABLED)
            self.v_stat.set(msg)
            if pct is not None:
                self.v_prog.set(pct)
        self.root.after(0, _do)

    def _on_gen(self):
        inp = self.v_in.get().strip()
        out = self.v_out.get().strip()
        vid = self.v_vid.get().strip()
        if not inp:
            return messagebox.showwarning("Warning", "Select an audio file first.")
        if not os.path.isfile(inp):
            return messagebox.showerror("Error", f"File not found:\n{inp}")
        if vid and not os.path.isfile(vid):
            return messagebox.showerror("Error", f"Video file not found:\n{vid}")
        if not out:
            return messagebox.showwarning("Warning", "Specify an output path.")
        diffs = [n for n, v in self.diff_vars.items() if v.get()]
        if not diffs:
            return messagebox.showwarning("Warning", "Pick at least one difficulty.")

        s = self.v_seed.get().strip()
        seed = int(s) if s.isdigit() else None

        bpm_str = self.v_bpm.get().strip()
        bpm_override = None
        if bpm_str:
            try:
                bpm_override = float(bpm_str)
                if bpm_override <= 0 or bpm_override > 300:
                    return messagebox.showwarning("Warning", "BPM must be between 1 and 300.")
            except ValueError:
                return messagebox.showwarning("Warning", f"Invalid BPM value: '{bpm_str}'")

        self.btn.config(state=tk.DISABLED)
        self.v_prog.set(0)
        threading.Thread(
            target=self._pipeline, args=(inp, out, vid, diffs, seed, bpm_override), daemon=True
        ).start()

    def _pipeline(self, inp, out, vid, diffs, seed, bpm_override=None):
        try:
            # Convert to MP3 if needed
            mp3_path = convert_to_mp3(inp, callback=self._log)

            video_path = None
            if vid:
                video_path = convert_to_mp4_video(vid, callback=self._log)
            
            az = AudioAnalyzer(inp, callback=self._log, bpm_override=bpm_override)
            az.analyze()

            gen = StepChartGenerator(az, seed=seed, callback=self._log)
            charts = gen.generate_all(selected=diffs)

            self._log("Writing .sm file …", 97)
            SMFileWriter(az, charts, out, music_file=mp3_path, video_file=video_path).write()

            self._log(f"Done! → {out}", 100)
            self._log(f"  BPM: {az.bpm:.1f}  |  Duration: {az.duration:.1f}s")
            for d in diffs:
                c = charts[d]
                self._log(f"  {d}: level {c['level']}, {c['note_count']} notes")

            self.root.after(0, lambda: messagebox.showinfo(
                "Success",
                f"StepMania file generated!\n\n"
                f"BPM: {az.bpm:.1f}\n"
                f"Duration: {az.duration:.1f}s\n"
                f"Difficulties: {', '.join(diffs)}\n\n"
                f"Saved to:\n{out}"
            ))
        except Exception as e:
            self._log(f"ERROR: {e}", 0)
            self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self.btn.config(state=tk.NORMAL))

    def run(self):
        self.root.mainloop()


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    App().run()

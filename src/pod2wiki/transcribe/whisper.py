"""Transcription service using faster-whisper.

Extracted from scripts/fetch_podcasts.py::maybe_transcribe and
scripts/podcast_rss_transcribe.py::transcribe_audio.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import requests

from pod2wiki.errors import AudioTranscriptionError
from pod2wiki.models import SourceItem
from pod2wiki.utils import slugify


def _eprint(message: str) -> None:
    import sys

    print(message, file=sys.stderr)


class TranscriptionService:
    """Handle audio download, clip, and faster-whisper transcription."""

    def __init__(
        self,
        model: str = "tiny",
        clip_seconds: int | None = 600,
        auto_threshold: int = 1500,
        enabled: bool = True,
    ):
        self.model = model
        self.clip_seconds = clip_seconds
        self.auto_threshold = auto_threshold
        self.enabled = enabled

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def maybe_transcribe(self, item: SourceItem, transcripts_dir: Path) -> SourceItem:
        """Return a **new** SourceItem with transcription results if applicable."""
        if not self.enabled:
            return item
        if not item.audio_url:
            return item
        if len(item.raw_text or "") >= self.auto_threshold:
            return item

        # Download
        try:
            audio_path = self._download_audio(item.audio_url, transcripts_dir, item)
        except Exception as exc:
            _eprint(f"[whisper] download failed: {exc}")
            return item

        # Clip
        target = audio_path
        if self.clip_seconds:
            try:
                target = self._clip_audio(audio_path, self.clip_seconds)
            except Exception as exc:
                _eprint(f"[whisper] clip failed: {exc}")
                target = audio_path

        # Transcribe
        try:
            from podcast_rss_transcribe import transcribe_audio
        except ImportError as exc:
            _eprint(f"[whisper] transcription unavailable: {exc}")
            return item

        _eprint(f"[whisper] transcribing {target.name} with {self.model} ...")
        started = time.time()
        try:
            transcript = transcribe_audio(target, model_name=self.model)
        except Exception as exc:
            _eprint(f"[whisper] transcription failed: {exc}")
            return item

        elapsed = time.time() - started
        if not transcript or not transcript.strip():
            _eprint(f"[whisper] empty transcript after {elapsed:.1f}s")
            return item

        _eprint(f"[whisper] done in {elapsed:.1f}s, {len(transcript)} chars")
        # Build new item (dataclasses are mutable by default)
        new_item = item.model_copy(
            update={
                "raw_text": transcript,
                "transcribed_by": f"faster-whisper-{self.model}",
                "transcript_clip_seconds": self.clip_seconds,
                "transcript_audio_path": target,
            }
        )
        return new_item

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _download_audio(self, url: str, transcripts_dir: Path, item: SourceItem) -> Path:
        stem = f"{item.date}-{slugify(item.channel)}-{slugify(item.title)}"
        audio_ext = Path(url.split("?", 1)[0]).suffix.lower() or ".mp3"
        if audio_ext not in {".mp3", ".m4a", ".aac", ".ogg", ".wav"}:
            audio_ext = ".mp3"
        audio_path = transcripts_dir / f"{stem}{audio_ext}"

        if audio_path.is_file() and audio_path.stat().st_size > 0:
            _eprint(f"[whisper] reuse cached audio {audio_path}")
            return audio_path

        transcripts_dir.mkdir(parents=True, exist_ok=True)
        _eprint(f"[whisper] downloading {url} -> {audio_path}")
        started = time.time()
        bytes_written = 0
        tmp = audio_path.with_suffix(audio_path.suffix + ".part")
        # Use requests with pod2wiki UA
        from pod2wiki.collect.rss import UA  # re-use UA

        with requests.get(url, stream=True, timeout=60, headers={"User-Agent": UA}) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        fh.write(chunk)
                        bytes_written += len(chunk)
        tmp.replace(audio_path)
        _eprint(
            f"[whisper] downloaded {bytes_written / 1024 / 1024:.1f}MB in {time.time() - started:.1f}s"
        )
        return audio_path

    def _clip_audio(self, src: Path, seconds: int) -> Path:
        clip = src.with_suffix(f".clip{seconds}.mp3")
        if clip.is_file() and clip.stat().st_size > 0:
            _eprint(f"[whisper] reuse cached clip {clip}")
            return clip
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-t",
            str(int(seconds)),
            "-c",
            "copy",
            str(clip),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise AudioTranscriptionError(f"ffmpeg clip failed: {exc}")
        _eprint(f"[whisper] clipped first {seconds}s -> {clip}")
        return clip

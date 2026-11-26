from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import math
import shutil
import subprocess

from .audio import Window, intervene, load_wav, save_wav


def digest(path: Path) -> str:
    result = sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def prepare(video: Path, output: Path, start: float, end: float, action: str, *,
            replacement: Path | None, shift_seconds: float, rate: int) -> dict:
    if rate < 8000 or rate > 48000:
        raise ValueError('sample rate must be between 8000 and 48000')
    if (replacement is not None) != (action == 'replace'):
        raise ValueError('--replacement is required only for replace')
    if not math.isfinite(shift_seconds) or (shift_seconds != 0) != (action == 'shift'):
        raise ValueError('provide a finite, nonzero --shift-seconds only for shift')
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        raise ValueError('FFmpeg is required to prepare Duo videos')
    if output.exists():
        raise ValueError(f'output already exists: {output}')
    video = video.resolve(strict=True)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    def convert(*args: str | Path) -> None:
        command = [ffmpeg, '-nostdin', '-v', 'error', *map(str, args)]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode:
            raise ValueError(f'FFmpeg failed: {result.stderr.strip()}')

    with TemporaryDirectory(prefix='.aea-', dir=output.parent) as directory:
        pair = Path(directory) / 'pair'
        pair.mkdir()
        factual_wav = pair / 'factual.wav'
        counterfactual_wav = pair / 'counterfactual.wav'
        convert('-i', video, '-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le', '-ac', '1', '-ar', str(rate), factual_wav)
        _, original = load_wav(factual_wav)
        window = Window.seconds(start, end, rate)
        replacement_audio = None
        if replacement is not None:
            replacement_rate, replacement_audio = load_wav(replacement.resolve(strict=True))
            if replacement_rate != rate:
                raise ValueError(f'replacement WAV must have sample rate {rate}')
        changed = intervene(original, window, action, replacement=replacement_audio, shift=round(shift_seconds * rate))
        if changed == original:
            raise ValueError('the intervention produced identical PCM; check the event and window')
        save_wav(counterfactual_wav, rate, changed)
        for track in (factual_wav, counterfactual_wav):
            convert('-i', video, '-i', track, '-map', '0:v:0', '-map', '1:a:0',
                    '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', track.with_suffix('.mp4'))
        metadata = {
            'kind': 'duo_input_pair', 'source_sha256': digest(video),
            'sample_rate': rate, 'samples_per_track': len(original),
            'window_samples': [window.start, window.end], 'intervention': action,
            'shift_samples': round(shift_seconds * rate),
            'files': {path.name: digest(path) for path in pair.iterdir()},
        }
        (pair / 'pair.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        pair.rename(output)
    return metadata

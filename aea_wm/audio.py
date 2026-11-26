from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import math
import sys
import wave


@dataclass(frozen=True)
class Window:
    start: int
    end: int

    @property
    def samples(self) -> int:
        return self.end - self.start

    def validate(self, length: int) -> None:
        if not 0 <= self.start < self.end <= length:
            raise ValueError('window lies outside the audio timeline')

    @classmethod
    def seconds(cls, start: float, end: float, rate: int) -> Window:
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError('timestamps must be finite')
        return cls(round(start * rate), round(end * rate))


def load_wav(path: Path) -> tuple[int, array]:
    with wave.open(str(path), 'rb') as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f'{path.name} must be mono PCM16 WAV')
        rate = source.getframerate()
        stream = array('h')
        stream.frombytes(source.readframes(source.getnframes()))
    if sys.byteorder != 'little':
        stream.byteswap()
    if not stream:
        raise ValueError(f'{path.name} has no samples')
    return rate, stream


def save_wav(path: Path, rate: int, stream: array) -> None:
    data = stream[:]
    if sys.byteorder != 'little':
        data.byteswap()
    with wave.open(str(path), 'wb') as target:
        target.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        target.writeframes(data.tobytes())


def intervene(stream: array, window: Window, action: str, *, replacement: array | None = None,
              shift: int = 0) -> array:
    """Edit PCM only inside the anchor, retaining duration and both unaffected regions."""
    window.validate(len(stream))
    block = stream[window.start:window.end]
    if action == 'mute':
        changed = array('h', [0]) * len(block)
    elif action == 'replace':
        if replacement is None or len(replacement) != len(block):
            raise ValueError('replacement WAV must match the anchor sample count exactly')
        changed = replacement
    elif action == 'shift':
        if not 0 < abs(shift) < len(block):
            raise ValueError('use a nonzero shift shorter than the anchor window')
        silence = array('h', [0]) * abs(shift)
        changed = silence + block[:-shift] if shift > 0 else block[-shift:] + silence
    else:
        raise ValueError(f'unsupported intervention: {action}')
    return stream[:window.start] + changed + stream[window.end:]

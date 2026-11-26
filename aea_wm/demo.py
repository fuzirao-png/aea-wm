from __future__ import annotations

from array import array
from dataclasses import asdict, dataclass
from math import pi, sin

from .audio import Window, intervene


RATE = 8000
WINDOWS = (Window(0, 3200), Window(4800, 8000), Window(9600, 12800))
TONES = {'low': 400, 'high': 600, 'decoy': 800}
LIGHT = {'low': 'red', 'high': 'blue', 'none': 'idle', 'decoy': 'idle'}


@dataclass(frozen=True)
class Trial:
    id: str
    role: str
    original: str
    target: str
    position: int = 1
    drift: bool = False


@dataclass(frozen=True)
class Variant:
    anchor: bool = False
    dual: bool = False
    judge: bool = False
    vision_only: bool = False
    post_dub: bool = False


VARIANTS = {
    'vision-only': Variant(vision_only=True),
    'post-dub': Variant(post_dub=True),
    'naive': Variant(),
    'anchor': Variant(anchor=True),
    'dual': Variant(dual=True),
    'judge': Variant(judge=True),
    'anchor-dual': Variant(anchor=True, dual=True),
    'anchor-judge': Variant(anchor=True, judge=True),
    'dual-judge': Variant(dual=True, judge=True),
    'full': Variant(anchor=True, dual=True, judge=True),
}

TRIALS = [
    Trial('cue-replace-low', 'cue', 'low', 'high'),
    Trial('cue-replace-high', 'cue', 'high', 'low'),
    Trial('cue-mute-low', 'cue', 'low', 'none', 2),
    Trial('cue-mute-high', 'cue', 'high', 'none', 2),
    Trial('marker-replace', 'marker', 'low', 'high'),
    Trial('marker-mute', 'marker', 'high', 'none', 2),
    Trial('cue-background-drift', 'cue', 'high', 'low', drift=True),
    Trial('cue-missing-event', 'cue', 'none', 'high'),
]


def tone(label: str, length: int) -> array:
    frequency = TONES.get(label, 0)
    return array('h', (round(12000 * sin(2 * pi * frequency * i / RATE)) for i in range(length)))


def recognize(stream: array, window: Window) -> str:
    block = stream[window.start:window.end]
    if max(map(abs, block), default=0) < 100:
        return 'none'
    crossings = sum(first < 0 <= second or first >= 0 > second for first, second in zip(block, block[1:]))
    estimated = crossings * RATE / (2 * len(block))
    return min(TONES, key=lambda label: abs(TONES[label] - estimated))


def source_audio(trial: Trial) -> array:
    pcm = array('h', [0]) * (2 * RATE)
    pcm = intervene(pcm, WINDOWS[0], 'replace', replacement=tone('decoy', WINDOWS[0].samples))
    reference = WINDOWS[trial.position]
    return intervene(pcm, reference, 'replace', replacement=tone(trial.original, reference.samples))


def rollout(role: str, sound: str, *, drift: bool) -> dict:
    visual = LIGHT[sound] if role == 'cue' else 'playing'
    return {'sound': sound, 'visual': visual, 'background': 'shifted' if drift else 'fixed'}


def execute(trial: Trial, variant: Variant) -> dict:
    source = source_audio(trial)
    reference = WINDOWS[trial.position]
    # Reference grading is held out from the editing and judge functions.
    actual = recognize(source, reference)
    if variant.anchor:
        identified = next((w for w in WINDOWS if recognize(source, w) in ('low', 'high')), None)
    else:
        identified = WINDOWS[0]
    edited = source if identified is None else intervene(
        source, identified, 'replace', replacement=tone(trial.target, identified.samples),
    )
    heard = recognize(edited, reference)
    factual = rollout(trial.role, actual, drift=False)
    if variant.vision_only:
        future = rollout(trial.role, 'none', drift=False)
        before = future['visual']
    elif variant.post_dub:
        future = {**factual, 'sound': trial.target}
        before = factual['visual']
        edited = intervene(source, reference, 'replace', replacement=tone(trial.target, reference.samples))
    else:
        future = rollout(trial.role, heard, drift=trial.drift and identified == reference)
        before = factual['visual'] if variant.dual else ('red' if trial.role == 'cue' else 'playing')
    judge_valid = (
        identified is not None and future['sound'] == trial.target and future['background'] == 'fixed'
        and future['visual'] == rollout(trial.role, future['sound'], drift=False)['visual']
    )
    answered = identified is not None and (not variant.judge or judge_valid)
    expected = None if trial.original == 'none' else f"{factual['visual']}->{rollout(trial.role, trial.target, drift=False)['visual']}"
    prediction = f"{before}->{future['visual']}" if answered else None
    consistent = expected is not None and future == rollout(trial.role, trial.target, drift=False)
    return {
        'case': trial.id, 'role': trial.role, 'expected': expected, 'prediction': prediction,
        'correct': expected is not None and prediction == expected, 'consistent': consistent,
        'counterfactual': future, 'factual': factual if variant.dual else None,
        'selected_window': asdict(identified) if identified is not None else None,
        'outside_reference_unchanged': (
            source[:reference.start] == edited[:reference.start] and source[reference.end:] == edited[reference.end:]
        ),
    }


def run_demo() -> dict:
    modes = {}
    for name, variant in VARIANTS.items():
        rows = [execute(trial, variant) for trial in TRIALS]
        answerable = [row for row in rows if row['expected'] is not None]
        unanswerable = [row for row in rows if row['expected'] is None]
        answered = [row for row in answerable if row['prediction'] is not None]
        counts = {
            'cases': len(rows), 'answerable': len(answerable),
            'correct': sum(row['correct'] for row in answerable),
            'answered': sum(row['prediction'] is not None for row in rows),
            'consistent_trajectories': sum(row['consistent'] for row in answerable),
            'answered_consistent': sum(row['consistent'] for row in answered),
            'answered_answerable': len(answered),
            'correct_abstentions': sum(row['prediction'] is None for row in unanswerable),
            'unanswerable': len(unanswerable),
        }
        modes[name] = {'counts': counts, 'records': rows}
    return {'kind': 'synthetic_pcm_smoke', 'sample_rate': RATE, 'variants': modes}

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import math
import unicodedata


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for lineno, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError('expected an object with non-empty id')
        except ValueError as error:
            raise ValueError(f'{path.name}:{lineno}: {error}') from error
        rows.append(row)
    if not rows:
        raise ValueError(f'{path.name}: no rows')
    return rows


def normalized(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def matches(actual: object, expected: object) -> bool:
    return isinstance(actual, str) and isinstance(expected, str) and normalized(actual) == normalized(expected)


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def score(references: Path, observations: Path) -> dict:
    refs = {}
    for row in read_jsonl(references):
        answer = row.get('answer')
        if row['id'] in refs or 'answer' not in row or (answer is not None and not isinstance(answer, str)):
            raise ValueError(f'invalid or duplicate reference id: {row["id"]}')
        if answer is not None and not all(isinstance(row.get(key), str) and row[key].strip()
                                          for key in ('answer', 'visual', 'sound')):
            raise ValueError(f'answerable references require answer, visual and sound: {row["id"]}')
        if not finite(row.get('expected_offset_s', 0)):
            raise ValueError(f'invalid expected_offset_s: {row["id"]}')
        refs[row['id']] = row
    modes = defaultdict(dict)
    for obs in read_jsonl(observations):
        tag, case = obs.get('variant'), obs['id']
        answer = obs.get('answer')
        if not isinstance(tag, str) or not tag.strip() or case not in refs or case in modes[tag]:
            raise ValueError(f'invalid or repeated observation: {tag}, {case}')
        if 'answer' not in obs or (answer is not None and (not isinstance(answer, str) or not answer.strip())):
            raise ValueError(f'answer must be a non-empty string or null: {tag}, {case}')
        for name in ('visual_onset_s', 'audio_onset_s', 'elapsed_s'):
            if name in obs and obs[name] is not None and (not finite(obs[name]) or obs[name] < 0):
                raise ValueError(f'{name} must be finite and nonnegative: {tag}, {case}')
        ref = refs[case]
        answerable = ref['answer'] is not None
        correct = answerable and matches(answer, ref['answer'])
        target_matches = answerable and matches(
            obs.get('sound'), ref['sound'],
        ) and matches(obs.get('visual'), ref['visual'])
        consistent = target_matches and obs.get('unrelated_stable') is True
        onset, sound = obs.get('visual_onset_s'), obs.get('audio_onset_s')
        sync = abs((onset - sound) - ref.get('expected_offset_s', 0)) if target_matches and finite(onset) and finite(sound) else None
        modes[tag][case] = {
            'id': case, 'video_id': ref.get('video_id', case), 'answerable': answerable,
            'answered': answer is not None, 'correct': correct, 'consistent': consistent,
            'sync_error_s': sync, 'elapsed_s': obs.get('elapsed_s'),
        }
    result = {}
    for tag, mode in modes.items():
        if mode.keys() != refs.keys():
            raise ValueError(f'{tag} is missing {len(refs.keys() - mode.keys())} cases; record abstentions as null')
        rows = list(mode.values())
        answerable = [row for row in rows if row['answerable']]
        unanswerable = [row for row in rows if not row['answerable']]
        answered = [row for row in answerable if row['answered']]
        delays = sorted(row['elapsed_s'] for row in rows if row['elapsed_s'] is not None)
        sync = [row['sync_error_s'] for row in answerable if row['sync_error_s'] is not None]
        result[tag] = {
            'n': len(rows), 'videos': len({row['video_id'] for row in rows}), 'n_answerable': len(answerable),
            'accuracy': ratio(sum(row['correct'] for row in answerable), len(answerable)),
            'coverage': ratio(sum(row['answered'] for row in rows), len(rows)),
            'consistency_all_answerable': ratio(sum(row['consistent'] for row in answerable), len(answerable)),
            'consistency_answered': ratio(sum(row['consistent'] for row in answered), len(answered)),
            'unanswerable_abstention': ratio(sum(not row['answered'] for row in unanswerable), len(unanswerable)),
            'mean_sync_error_s': round(sum(sync) / len(sync), 6) if sync else None,
            'n_sync': len(sync), 'p95_elapsed_s': delays[math.ceil(0.95 * len(delays)) - 1] if delays else None,
            'records': rows,
        }
    return {'kind': 'external_rollout_annotations', 'variants': result}

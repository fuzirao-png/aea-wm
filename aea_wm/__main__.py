from argparse import ArgumentParser
from pathlib import Path
from tempfile import NamedTemporaryFile
import json

from .demo import run_demo
from .media import prepare
from .score import score


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as file:
        temporary = Path(file.name)
        json.dump(data, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')
    temporary.replace(path)


def main() -> None:
    parser = ArgumentParser(description='AEA-WM experiments and offline Duo inputs')
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo', help='run deterministic symbolic PCM experiments')
    demo.add_argument('--out', type=Path, default=Path('runs/synthetic.json'))
    media = sub.add_parser('prepare', help='create matched factual and edited MP4 inputs for Duo')
    for name in ('video', 'out'):
        media.add_argument(f'--{name}', type=Path, required=True)
    for name in ('start', 'end'):
        media.add_argument(f'--{name}', type=float, required=True)
    media.add_argument('--action', choices=('replace', 'mute', 'shift'), required=True)
    media.add_argument('--replacement', type=Path)
    media.add_argument('--shift-seconds', type=float, default=0)
    media.add_argument('--sample-rate', type=int, default=16000)
    review = sub.add_parser('score', help='compare externally annotated rollouts against references')
    for name in ('references', 'observations', 'out'):
        review.add_argument(f'--{name}', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare(args.video, args.out, args.start, args.end, args.action,
                    replacement=args.replacement, shift_seconds=args.shift_seconds, rate=args.sample_rate)
        elif args.command == 'score':
            save_json(args.out, score(args.references, args.observations))
        else:
            report = run_demo()
            save_json(args.out, report)
            for name, mode in report['variants'].items():
                counts = mode['counts']
                print(f'{name:13} accuracy={counts["correct"]}/{counts["answerable"]} '
                      f'coverage={counts["answered"]}/{counts["cases"]} '
                      f'causal={counts["consistent_trajectories"]}/{counts["answerable"]}')
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Wrote {args.out}')


if __name__ == '__main__':
    main()

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fastcache")
    parser.add_argument("key", help="Key to fetch")
    parser.add_argument("--timeout", type=int, default=30, help="Seconds to wait")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print details")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(args.key)
#!/usr/bin/env python3

from pathlib import Path


def main() -> None:
    workspace = Path(".").resolve()
    print(f"prepare bundle from {workspace}")


if __name__ == "__main__":
    main()

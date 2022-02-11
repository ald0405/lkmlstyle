import argparse
import pathlib
from lkmlstyle.check import check


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=pathlib.Path)
    args = parser.parse_args()

    with args.file.open("r") as file:
        text = file.read()

    violations = check(text)

    lines = text.split("\n")
    for violation in violations:
        code, title, line_number = violation
        print(f"[{code}] {title}")
        print("-" * 60)

        for n in range(line_number - 1, line_number + 3):
            if n <= 0:
                continue
            if n == line_number:
                print(f"{n:<4} >| {lines[n - 1]}")
            else:
                print(f"{n:<4}  | {lines[n - 1]}")
        print("\n")

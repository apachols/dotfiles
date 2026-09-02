"""Read and write the remembered output directory for new diagrams.

Stdlib only, so it runs under bare `python3` without the renderer's venv.

    python3 output_dir.py --get            # print the directory, or exit 3 if unset
    python3 output_dir.py --set ~/diagrams # remember it (creates the directory)
    python3 output_dir.py --clear          # forget it

The config lives outside the dotfiles repo, since the right directory is
specific to a machine rather than to the checkout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "excalidraw-skill" / "config.json"
UNSET_EXIT = 3


def load_config() -> dict:
    try:
        with CONFIG_PATH.open() as fh:
            config = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return config if isinstance(config, dict) else {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")


def get_output_dir() -> Path | None:
    raw = load_config().get("output_dir")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw).expanduser()


def set_output_dir(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.mkdir(parents=True, exist_ok=True)

    config = load_config()
    config["output_dir"] = str(path)
    save_config(config)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--get", action="store_true", help="Print the remembered directory")
    group.add_argument("--set", metavar="PATH", help="Remember PATH and create it")
    group.add_argument("--clear", action="store_true", help="Forget the remembered directory")
    args = parser.parse_args()

    if args.set:
        print(set_output_dir(args.set))
        return

    if args.clear:
        config = load_config()
        config.pop("output_dir", None)
        save_config(config)
        print(f"Cleared. Config: {CONFIG_PATH}")
        return

    output_dir = get_output_dir()
    if output_dir is None:
        print(f"UNSET (no output_dir in {CONFIG_PATH})", file=sys.stderr)
        sys.exit(UNSET_EXIT)
    print(output_dir)


if __name__ == "__main__":
    main()

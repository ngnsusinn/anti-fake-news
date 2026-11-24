"""Build a local, unpacked Chromium extension from versioned sources."""

import argparse
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "extension"
DEFAULT_OUTPUT = ROOT / "release" / "extension"
TOP_LEVEL = (
    "manifest.json",
    "analyze.html",
    "analyze.js",
    "extract.js",
    "service-worker.js",
    "styles.css",
)
MODULES = (
    "analysis-controller.js",
    "api-client.js",
    "error-recovery.js",
    "form-state.js",
    "form-validation.js",
    "image-selection.js",
    "request-lifecycle.js",
    "result-view.js",
    "session.js",
)


def source_files():
    files = [Path(name) for name in TOP_LEVEL]
    files.extend(Path("modules") / name for name in MODULES)
    for relative in files:
        source = SOURCE / relative
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Invalid extension source: {relative.as_posix()}")
    return files


def up_to_date(output, files):
    if not output.is_dir() or output.is_symlink():
        return False
    contents = list(output.rglob("*"))
    if any(path.is_symlink() for path in contents):
        return False
    if {path.relative_to(output) for path in contents if not path.is_dir()} != set(files):
        return False
    return all(
        not (output / relative).is_symlink()
        and (output / relative).read_bytes() == (SOURCE / relative).read_bytes()
        for relative in files
    )


def build_extension(output):
    if output.is_symlink():
        raise ValueError("Choose a package directory without a symlink")
    output = output.resolve()
    if output == SOURCE or SOURCE in output.parents:
        raise ValueError("Choose a destination outside the extension source folder")
    files = source_files()
    if output.exists():
        if up_to_date(output, files):
            return len(files)
        raise FileExistsError("Choose a new output directory for the updated extension")

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="afn-extension-", dir=output.parent) as temporary:
        staged = Path(temporary) / "unpacked"
        for relative in files:
            destination = staged / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, destination)
        staged.rename(output)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        count = build_extension(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Unpacked Chromium extension: {args.output.resolve()} ({count} files)")


if __name__ == "__main__":
    main()

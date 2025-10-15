# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "docopt",
#     "loguru",
#     "toml",
# ]
# ///


"""
JetBrains Tools

Usage:
  main.py copy-classes --conf=classes.toml --classes=dir <root-dir>
  main.py patch --conf=classes.toml --classes=dir <ide-path>...
  main.py restore <ide-path>...

Options:
  --classes=PATH             the root path of modified classes
  --conf=PATH                the class list configuration
"""
import os
import re
import tomllib
import zipfile
from abc import ABC, abstractmethod
from typing import Iterable, cast

from docopt import docopt
from loguru import logger


def build_pattern(classes: Iterable[str]) -> re.Pattern:

    def to_regex(s: str) -> str:
        return re.escape(s).replace("\\*", ".*")

    return re.compile(f"({"|".join(map(to_regex, classes))})")


def copy_classes(src: str, dst: str, classes: Iterable[str]) -> None:
    pattern = build_pattern(classes)
    with zipfile.ZipFile(src, "r") as zf:
        for item in zf.infolist():
            if pattern.match(item.filename):
                f = f"{dst}/{item.filename}"
                os.makedirs(os.path.dirname(f), exist_ok=True)
                with open(f, "wb") as out:
                    out.write(zf.read(item.filename))
                    logger.info(f"Copied {item.filename}")


class Copier(ABC):

    build_root: str

    def __init__(self, build_root: str) -> None:
        self.build_root = build_root

    @abstractmethod
    def jar_file(self, name: str) -> str: ...

    def copy_classes(
        self, jar_name: str, dst: str, classes: Iterable[str]
    ) -> None:
        root = f"{dst}/{jar_name}"
        if not os.path.exists(root):
            os.makedirs(root)
        jar = self.jar_file(jar_name)
        copy_classes(jar, root, classes)


class DefaultCopier(Copier):

    def jar_file(self, name: str) -> str:
        return f"{self.build_root}/out/idea-ce/dist.all/{name}"


def patch_classes(
    name: str,
    src: str,
    dst: str,
    classes: Iterable[str],
    copied_classes_root: str,
) -> None:
    prefix = f"{copied_classes_root}/{name}"
    n = len(prefix)
    pattern = build_pattern(classes)
    with (
        zipfile.ZipFile(src, "r") as zin,
        zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        for item in zin.infolist():
            if pattern.match(item.filename):
                logger.info(f"Removed {item.filename}")
            else:
                zout.writestr(item, zin.read(item.filename))
        for root, _, files in os.walk(copied_classes_root):
            for file in files:
                arcname = f"{root[n:]}/{file}"
                zout.write(f"{root}/{file}", arcname)
                logger.info(f"Added {arcname}")


class Patcher(ABC):

    @abstractmethod
    def jar_file(self, root: str, name: str, alias: str) -> str: ...

    def patch(
        self,
        root: str,
        name: str,
        alias: str,
        classes: Iterable[str],
        copied_classes_root: str,
    ) -> None:
        jar = self.jar_file(root, name, alias)
        orig = f"{jar}.orig"
        if not os.path.exists(orig):
            logger.info(f"backing up {jar} as {orig}")
            os.rename(jar, orig)
        patch_classes(name, orig, jar, classes, copied_classes_root)


class DefaultPatcher(Patcher):

    def jar_file(self, root: str, name: str, alias: str) -> str:
        f = f"{root}/{alias}"
        if os.path.exists(f):
            return f
        f = f"{root}/{name}"
        if os.path.exists(f):
            return f
        raise FileNotFoundError(name)


def run_copy_classes(args):
    with open(args["--conf"], "rb") as f:
        classes = tomllib.load(f)
    copier = DefaultCopier(args["<root-dir>"])
    dst = args["--classes"]
    for jar, info in classes.items():
        copier.copy_classes(jar, dst, info["classes"])


def run_patch(args):
    with open(args["--conf"], "rb") as f:
        classes = tomllib.load(f)
    patcher = DefaultPatcher()
    classes_root = args["--classes"]
    for jar, info in classes.items():
        for root in args["<ide-path>"]:
            patcher.patch(
                root,
                jar,
                info["alias"],
                info["classes"],
                classes_root,
            )


def run_restore(args):

    def restore(path: str) -> None:
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(".jar.orig"):
                    restored = os.path.join(root, file[: -len(".orig")])
                    os.rename(os.path.join(root, file), restored)
                    logger.info(f"Restored {restored}")

    for ide_path in cast(str, args["<ide-path>"]):
        restore(ide_path)


def main():
    args = docopt(__doc__)
    if args["copy-classes"]:
        run_copy_classes(args)
    elif args["patch"]:
        run_patch(args)
    elif args["restore"]:
        run_restore(args)


if __name__ == "__main__":
    main()

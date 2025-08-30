# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "docopt",
#     "loguru",
# ]
# ///


"""
Patch JetBrains IDEs

Usage:
  main.py patch --classes=dir <ide-path>...
  main.py restore <ide-path>...

Options:
  -c PATH --classes=PATH     the root path of modified classes
"""
import os
import zipfile
from typing import NamedTuple, Optional

from docopt import docopt
from loguru import logger


class Class(NamedTuple):
    root: str
    path: str
    file: str

    @property
    def abspath(self) -> str:
        return os.path.join(self.root, self.path, self.file)

    @property
    def _class(self) -> str:
        return f"{self.path.replace("/", ".")}.{self.file[: -len(".class")]}"


def load_classes(classes: str) -> dict[str, Class]:
    abs_path = os.path.abspath(classes)
    n = len(classes) + 1
    res: dict[str, Class] = {}
    for root, dirs, files in os.walk(classes):
        for file in files:
            path = root[n:]
            res[file] = Class(abs_path, path, file)
    return res


class JarPatch(object):
    jar: str
    classes: dict[str, Class]

    def __init__(self, jar: str, classes: dict[str, Class]):
        self.jar = jar
        self.classes = classes

    def __repr__(self):
        return f"path: {self.jar}, classes: {self.classes}"

    def patch(self):
        bak = f"{self.jar}.orig"
        if not os.path.exists(bak):
            os.rename(self.jar, bak)
            logger.info(f"backed up {self.jar} as {bak}")
        with (
            zipfile.ZipFile(bak, "r") as zin,
            zipfile.ZipFile(
                self.jar, "w", compression=zipfile.ZIP_DEFLATED
            ) as zout,
        ):
            for item in zin.infolist():
                base = os.path.basename(item.filename)
                cls = self.classes[base] if base in self.classes else None
                if cls and cls.path == os.path.dirname(item.filename):
                    with open(self.classes[base].abspath, "rb") as f:
                        buf = f.read()
                else:
                    buf = zin.read(item.filename)
                zout.writestr(item, buf)


def load_patches(classes: dict[str, Class], ide: str) -> set[JarPatch]:

    def check_classes(f: str) -> Optional[JarPatch]:
        local: dict[str, Class] = {}
        with zipfile.ZipFile(f, "r") as jar:
            for name in jar.namelist():
                base = os.path.basename(name)
                if base in classes:
                    local[base] = classes[base]
                    del classes[base]
        return None if not local else JarPatch(os.path.abspath(f), local)

    res: set[JarPatch] = set()
    for root, dirs, files in os.walk(ide):
        for file in files:
            if file.endswith(".jar"):
                if p := check_classes(os.path.join(root, file)):
                    res.add(p)
    return res


def run_patch(args):
    classes = load_classes(args["--classes"])
    for path in args["<ide-path>"]:  # type: str
        patches = load_patches(classes.copy(), path)
        if patches:
            logger.info(f"Files to be patched under {path}:")
            for patch in patches:
                logger.info(f"  {patch.jar}:")
                for _, cls in patch.classes.items():
                    logger.info(f"    {cls._class}")
            for patch in patches:
                logger.info(f"Patching {patch.jar}")
                patch.patch()


def run_restore(args):

    def restore(path: str) -> None:
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".jar.orig"):
                    restored = os.path.join(root, file[: -len(".orig")])
                    os.rename(os.path.join(root, file), restored)
                    logger.info(f"Restored {restored}")

    for ide_path in args["<ide-path>"]:  # type: str
        restore(ide_path)


def main():
    args = docopt(__doc__)
    if args["patch"]:
        run_patch(args)
    elif args["restore"]:
        run_restore(args)


if __name__ == "__main__":
    main()

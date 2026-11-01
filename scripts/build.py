import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "dist", "mash.alfredworkflow")


def files():
    yield "run.py"
    yield "info.plist"
    yield "icon.png"
    yield "node.png"
    yield "add.png"
    yield "README.md"
    for name in sorted(os.listdir(os.path.join(ROOT, "mash"))):
        if name.endswith(".py"):
            yield os.path.join("mash", name)


def main():
    os.chdir(ROOT)
    subprocess.run([sys.executable, "make_plist.py", *sys.argv[1:]], check=True)
    subprocess.run([sys.executable, "scripts/make_icons.py"], check=True)
    os.makedirs("dist", exist_ok=True)
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in files():
            bundle.write(path)
    print(BUNDLE)


if __name__ == "__main__":
    main()

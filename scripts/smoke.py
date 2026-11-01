import json
import os
import subprocess
import sys
import tempfile
import zipfile

BUNDLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dist", "mash.alfredworkflow"
)


def sh(folder, script, arg, env):
    full = dict(os.environ, **env, PWD=folder)
    return subprocess.run(
        ["bash", "-c", script, "mash", arg],
        cwd=folder,
        env=full,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def main():
    import plistlib

    workflow = tempfile.mkdtemp(prefix="mash-wf-")
    data = tempfile.mkdtemp(prefix="mash-data-")
    with zipfile.ZipFile(BUNDLE) as bundle:
        bundle.extractall(workflow)
    with open(os.path.join(workflow, "info.plist"), "rb") as f:
        plist = plistlib.load(f)
    scripts = {o["uid"]: o["config"]["script"] for o in plist["objects"] if "script" in o["config"]}
    by_type = {o["type"]: o for o in plist["objects"]}
    env = {"python": sys.executable, "folder": data, "state": ""}
    keyword_filter = next(o for o in plist["objects"] if o["config"].get("keyword") == "m")
    filter_script = keyword_filter["config"]["script"]
    act_script = by_type["alfred.workflow.action.script"]["config"]["script"]
    assert len(scripts) == 3, "filter, prompt and act scripts"

    items = json.loads(sh(workflow, filter_script, "ssh prod web -> ssh deploy@10.0.1.5", env))[
        "items"
    ]
    assert items[0]["title"].startswith("Add: "), items[0]
    print(sh(workflow, act_script, items[0]["arg"], env).strip())

    items = json.loads(sh(workflow, filter_script, "prod", env))["items"]
    assert items[0]["title"] == "ssh prod web", items
    print(items[0]["subtitle"])
    assert [n for n in os.listdir(data) if n.startswith("ssh-prod-web.")], os.listdir(data)
    print("smoke ok")


if __name__ == "__main__":
    main()

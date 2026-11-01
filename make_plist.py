import plistlib
import sys

BUNDLE = "com.anokhin.mash"
PYTHON = '"${python:-/usr/bin/python3}" -S "$PWD/run.py"'

FILTER, DECIDE, PROMPT, MORE, REENTER, TRIGGER, ACT, NOTIFY, HOTKEY = (
    "F0B5D1A0-0000-4000-8000-00000000000" + str(i) for i in range(1, 10)
)
IS_PROMPT = "C0ND1710-0000-4000-8000-000000000001"
HAS_MORE = "C0ND1710-0000-4000-8000-000000000002"


def script_filter(uid, script, keyword=None, title=""):
    config = {
        "alfredfiltersresults": False,
        "argumenttrimmode": 0,
        "argumenttype": 1,
        "escaping": 102,
        "queuedelaycustom": 1,
        "queuedelayimmediatelyinitially": True,
        "queuedelaymode": 0,
        "queuemode": 2,
        "runningsubtext": "searching…",
        "script": script,
        "scriptargtype": 1,
        "scriptfile": "",
        "subtext": "",
        "title": title,
        "type": 0,
        "withspace": True,
    }
    if keyword:
        config["keyword"] = keyword
    return {
        "config": config,
        "type": "alfred.workflow.input.scriptfilter",
        "uid": uid,
        "version": 3,
    }


def conditional(uid, condition_uid, variable, label):
    return {
        "config": {
            "conditions": [
                {
                    "inputstring": "{var:" + variable + "}",
                    "matchcasesensitive": False,
                    "matchmode": 0,
                    "matchstring": "1",
                    "outputlabel": label,
                    "uid": condition_uid,
                }
            ],
            "elselabel": "else",
            "hideelse": False,
        },
        "type": "alfred.workflow.utility.conditional",
        "uid": uid,
        "version": 1,
    }


def run_script(uid, script):
    return {
        "config": {
            "concurrently": False,
            "escaping": 102,
            "script": script,
            "scriptargtype": 1,
            "scriptfile": "",
            "type": 0,
        },
        "type": "alfred.workflow.action.script",
        "uid": uid,
        "version": 2,
    }


def notification(uid):
    return {
        "config": {
            "lastpathcomponent": False,
            "onlyshowifquerypopulated": True,
            "removeextension": False,
            "text": "{query}",
            "title": "mash",
        },
        "type": "alfred.workflow.output.notification",
        "uid": uid,
        "version": 1,
    }


def external_trigger(uid, trigger_id):
    return {
        "config": {"triggerid": trigger_id},
        "type": "alfred.workflow.trigger.external",
        "uid": uid,
        "version": 1,
    }


def call_external_trigger(uid, trigger_id):
    return {
        "config": {
            "passinputasargument": True,
            "passvariables": True,
            "triggerid": trigger_id,
            "workflowbundleid": "self",
        },
        "type": "alfred.workflow.output.callexternaltrigger",
        "uid": uid,
        "version": 1,
    }


def hotkey(uid):
    return {
        "config": {
            "action": 0,
            "argument": 0,
            "focusedappvariable": False,
            "focusedappvariablename": "",
            "hotkey": 0,
            "hotmod": 0,
            "hotstring": "",
            "leftcursor": False,
            "modsmode": 0,
            "relatedAppsMode": 0,
        },
        "type": "alfred.workflow.trigger.hotkey",
        "uid": uid,
        "version": 2,
    }


def link(destination, source_output=None):
    connection = {
        "destinationuid": destination,
        "modifiers": 0,
        "modifiersubtext": "",
        "vitoclose": False,
    }
    if source_output:
        connection["sourceoutputuid"] = source_output
    return connection


def variable(name, label, default, description, placeholder=""):
    return {
        "config": {
            "default": default,
            "placeholder": placeholder,
            "required": False,
            "trim": True,
        },
        "description": description,
        "label": label,
        "type": "textfield",
        "variable": name,
    }


def checkbox(name, label, description):
    return {
        "config": {"default": False, "required": False},
        "description": description,
        "label": label,
        "type": "checkbox",
        "variable": name,
    }


def plist(version):
    return {
        "bundleid": BUNDLE,
        "category": "Productivity",
        "createdby": "vlnn",
        "description": "Fuzzy search over a tree of plain-text records you own",
        "name": "mash",
        "readme": "Type m and a few letters. Records live in ~/.mash. See README.md.",
        "version": version,
        "webaddress": "https://github.com/vlnn/mash",
        "disabled": False,
        "objects": [
            hotkey(HOTKEY),
            script_filter(FILTER, f'{PYTHON} --alfred "$1"', keyword="m", title="mash"),
            conditional(DECIDE, IS_PROMPT, "prompt", "needs blanks"),
            script_filter(PROMPT, f'{PYTHON} --prompt "$state" "$1"', title="fill a blank"),
            conditional(MORE, HAS_MORE, "more", "more blanks"),
            call_external_trigger(REENTER, "prompt"),
            external_trigger(TRIGGER, "prompt"),
            run_script(ACT, f'{PYTHON} --act "$1"'),
            notification(NOTIFY),
        ],
        "connections": {
            HOTKEY: [link(FILTER)],
            FILTER: [link(DECIDE)],
            DECIDE: [link(PROMPT, IS_PROMPT), link(ACT)],
            PROMPT: [link(MORE)],
            MORE: [link(REENTER, HAS_MORE), link(ACT)],
            TRIGGER: [link(PROMPT)],
            ACT: [link(NOTIFY)],
        },
        "uidata": {
            uid: {"xpos": 80 + 220 * column, "ypos": 80 + 160 * row}
            for uid, column, row in [
                (HOTKEY, 0, 0),
                (FILTER, 1, 0),
                (DECIDE, 2, 0),
                (PROMPT, 3, 1),
                (MORE, 4, 1),
                (REENTER, 5, 1),
                (TRIGGER, 2, 1),
                (ACT, 5, 0),
                (NOTIFY, 6, 0),
            ]
        },
        "userconfigurationconfig": [
            variable("python", "Python", "/usr/bin/python3", "Absolute path to python3 (3.9+)."),
            variable("folder", "Folder", "~/.mash", "The tree of records."),
            variable("editor", "Editor", "open -t {file}", "Command for ⌘↩; {file} is filled."),
            variable(
                "flows", "Flows", "", "name=keyword aliases for @ hand-offs", "tally=t kobold=kb"
            ),
            variable("max_results", "Max results", "50", "Rows sent to Alfred."),
            checkbox("show_nodes", "List nodes", "List every node on an empty query."),
        ],
        "variablesdontexport": [],
    }


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else "0.1.0"
    with open("info.plist", "wb") as f:
        plistlib.dump(plist(version), f, sort_keys=True)


if __name__ == "__main__":
    main()

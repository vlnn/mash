import make_plist


def test_every_connection_points_at_an_object():
    plist = make_plist.plist("0.0.0")
    uids = {o["uid"] for o in plist["objects"]}
    for source, links in plist["connections"].items():
        assert source in uids, f"{source} should be an object"
        for link in links:
            assert link["destinationuid"] in uids, f"{link} should point at an object"


def test_filter_and_act_share_the_python_setting():
    plist = make_plist.plist("0.0.0")
    scripts = [o["config"]["script"] for o in plist["objects"] if "script" in o["config"]]
    assert len(scripts) == 3, "keyword filter, prompt filter, act"
    assert all(s.startswith('"${python:-/usr/bin/python3}" -S') for s in scripts), (
        "every script should run the configured interpreter without site"
    )


def test_prompt_loop_goes_through_the_external_trigger():
    plist = make_plist.plist("0.0.0")
    objects = {o["uid"]: o for o in plist["objects"]}
    more = plist["connections"][make_plist.MORE]
    branch = next(c for c in more if "sourceoutputuid" in c)
    assert objects[branch["destinationuid"]]["type"] == "alfred.workflow.output.callexternaltrigger"
    assert (
        objects[make_plist.TRIGGER]["config"]["triggerid"]
        == objects[make_plist.REENTER]["config"]["triggerid"]
    )
    assert plist["connections"][make_plist.TRIGGER] == [make_plist.link(make_plist.PROMPT)]


def test_user_configuration_covers_every_setting():
    names = {v["variable"] for v in make_plist.plist("0.0.0")["userconfigurationconfig"]}
    assert names == {"python", "folder", "editor", "flows", "max_results", "show_nodes"}

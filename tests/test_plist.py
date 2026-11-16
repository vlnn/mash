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
    assert plist["connections"][make_plist.TRIGGER] == [make_plist.link(make_plist.STASH)]


def test_the_prompt_filter_reads_its_command_from_the_state_variable():
    plist = make_plist.plist("0.0.0")
    objects = {o["uid"]: o for o in plist["objects"]}
    stash = objects[make_plist.STASH]
    assert stash["type"] == "alfred.workflow.utility.argument", "an Arg and Vars utility"
    assert stash["config"]["variables"] == {"state": "{query}"}, (
        "the command a row sends is kept in the variable the prompt script reads as $state"
    )
    assert (stash["config"]["argument"], stash["config"]["passthroughargument"]) == ("", False), (
        "and is cleared from the query, so the box opens empty for typing"
    )
    assert '"$state" "$1"' in objects[make_plist.PROMPT]["config"]["script"], (
        "the prompt script takes the command from state and the typed text from the query"
    )


def test_both_ways_into_the_prompt_go_through_the_stash():
    connections = make_plist.plist("0.0.0")["connections"]
    first = next(c for c in connections[make_plist.DECIDE] if "sourceoutputuid" in c)
    assert first["destinationuid"] == make_plist.STASH, (
        "a row that needs a step stashes its command"
    )
    assert connections[make_plist.TRIGGER] == [make_plist.link(make_plist.STASH)], (
        "and so does every further step, re-entering through the trigger"
    )
    assert connections[make_plist.STASH] == [make_plist.link(make_plist.PROMPT)], (
        "only then does the prompt filter open"
    )


def test_keyword_needs_a_space_unless_asked_otherwise():
    keyword = lambda p: next(o for o in p["objects"] if o["config"].get("keyword") == "m")  # noqa: E731
    assert keyword(make_plist.plist("0"))["config"]["withspace"] is True
    assert keyword(make_plist.plist("0", with_space=False))["config"]["withspace"] is False


def test_hotkey_opens_the_filter_with_an_empty_query():
    plist = make_plist.plist("0")
    hotkey = next(o for o in plist["objects"] if o["type"] == "alfred.workflow.trigger.hotkey")
    assert hotkey["config"]["argument"] == make_plist.TEXT_ARGUMENT, (
        "argument 1 is Alfred's Text option; 2 would pass the clipboard"
    )
    assert hotkey["config"]["argumenttext"] == "", "and the text is empty: the browse list"
    assert plist["connections"][hotkey["uid"]] == [make_plist.link(make_plist.FILTER)]


def test_user_configuration_covers_every_setting():
    names = {v["variable"] for v in make_plist.plist("0.0.0")["userconfigurationconfig"]}
    assert names == {"python", "folder", "editor", "flows", "max_results"}

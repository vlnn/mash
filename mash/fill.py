import re
import time

BLANK = re.compile(r"\{\{([A-Za-z0-9_-]+)(?:=([^{}]*))?\}\}")
RESERVED = ("date", "time", "clipboard")


def today():
    return time.strftime("%Y-%m-%d")


def clock():
    return time.strftime("%H:%M")


def blanks(body):
    seen = []
    for match in BLANK.finditer(body):
        name, default = match.group(1), match.group(2)
        if name not in RESERVED and name not in (n for n, _ in seen):
            seen.append((name, default))
    return seen


def fill(body, values, clipboard):
    reserved = {"date": today, "time": clock, "clipboard": clipboard}

    def replacement(match):
        name, default = match.group(1), match.group(2)
        if name in reserved:
            return reserved[name]()
        if name in values:
            return values[name]
        return default if default is not None else match.group(0)

    return BLANK.sub(replacement, body)


def preview(body):
    reserved = {"date": today, "time": clock}

    def replacement(match):
        name = match.group(1)
        return reserved[name]() if name in reserved else match.group(0)

    return BLANK.sub(replacement, body)

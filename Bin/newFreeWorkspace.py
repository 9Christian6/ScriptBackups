#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
from __future__ import annotations
import subprocess
import json
from typing import Sequence

def run_i3_msg(command: Sequence[str]) -> str:
    """Run `i3-msg` and return stdout as text."""
    completed = subprocess.run(
        ["i3-msg", *command],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def focus_workspace(name: str) -> None:
    """Focus a workspace by name."""
    global commandWasFromHistory
    run_i3_msg([f'workspace "{name}:{name}"'])


def main() -> int:
    miscWorkspaces = ['3', '6', '7', '14', '15', '16', '17', '18', '19']
    workspaces = subprocess.check_output(['i3-msg', '-t', 'get_workspaces'])
    workspacesDict = json.loads(workspaces)
    occupiedWorkspaces = []
    freeWorkspaces = []
    for item in workspacesDict:
        fullname = item["name"]
        firstColIdx = fullname.find(':')
        wsNumber = fullname[:firstColIdx]
        occupiedWorkspaces.append(wsNumber)
    print("misc workspaces: ", miscWorkspaces)
    print("occupied workspaces: ", occupiedWorkspaces)
    print('')
    for item in miscWorkspaces:
        if item not in occupiedWorkspaces:
            freeWorkspaces.append(item)
    if freeWorkspaces.__len__() > 0:
        focus_workspace(freeWorkspaces[0])
    print(freeWorkspaces)
    return 0


if __name__ == "__main__":
    main()

#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
from __future__ import annotations
import subprocess
import json
import sys
import i3ipc
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
    run_i3_msg([f'workspace number "{name}"'])

def move_to_workspace(name: str) -> None:
    """Move currently focused container to workspace"""
    run_i3_msg([f'move container to workspace number "{name}"'])


def number_from_name(name: str) -> int:
    firstColIdx = name.find(':')
    if len(name) > 1:
        return int(name[:firstColIdx])
    return int(name)


def is_workspace_empty(workspace_number: int) -> bool:
    """Check if a workspace has any containers."""
    tree = i3ipc.Connection().get_tree()
    for node in tree.nodes:
        if node.workspace() and node.workspace().num == workspace_number:
            return False
    return True


def main() -> int:
    miscWorkspaces = [1, 3, 6, 7, 15, 16, 17, 18, 19]
    workspaces = subprocess.check_output(['i3-msg', '-t', 'get_workspaces'])
    workspacesDict = json.loads(workspaces)
    occupiedWorkspaces = []
    freeWorkspaces = []
    currentlyFocusedWorkspace = i3ipc.Connection().get_tree().find_focused().workspace().name
    currentlyFocusedWorkspaceNumber = number_from_name(currentlyFocusedWorkspace)
    #Workspace name is just a number (No containers on it)
    if len(currentlyFocusedWorkspace) == 1:
        return 0
    occupiedWorkspaces.append(currentlyFocusedWorkspaceNumber)
    for item in workspacesDict:
        wsNumber = number_from_name(item["name"])
        print("Workspace number " + str(wsNumber) + " is free: " + str(is_workspace_empty(wsNumber)))
        occupiedWorkspaces.append(wsNumber)
    print("misc workspaces: ", miscWorkspaces)
    print("occupied workspaces: ", occupiedWorkspaces)
    print('')
    for item in miscWorkspaces:
        if item not in occupiedWorkspaces:
            freeWorkspaces.append(item)
    print("free workspaces: ")
    print(freeWorkspaces)
    if freeWorkspaces.__len__() > 0:
        if sys.argv.__len__() > 1:
            move_to_workspace(freeWorkspaces[0])
            focus_workspace(freeWorkspaces[0])
        else:
            focus_workspace(freeWorkspaces[0])
    return 0


if __name__ == "__main__":
    main()

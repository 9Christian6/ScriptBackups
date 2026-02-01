#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
"""
Reliable system updater with output visually contained within decorative boxes.
Uses terminal width manipulation (not output parsing) to create the box effect.
Fully sudo-compatible and preserves all interactive behavior.
"""

import os
import pty
import select
import signal
import sys
import termios
import tty
import fcntl
import struct
import subprocess
import re
from typing import List
import shutil
import textwrap

ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")

def strip_ansi(b: bytes) -> bytes:
    return ANSI_RE.sub(b"", b)

def term_size():
    return shutil.get_terminal_size()

# ANSI escape sequence regex for safe width calculation
ANSI_ESCAPE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
# ANSI color codes
MAGENTA = '\033[38;2;255;0;255m'
NC = '\033[0m'  # No Color
MAG = MAGENTA.encode()
RESET = NC.encode()
VERT = "│".encode()


def get_terminal_size() -> tuple[int, int]:
    """Get terminal dimensions (columns, rows)."""
    try:
        return os.get_terminal_size()
    except OSError:
        return (80, 24)

def draw_title_box_border(title: str, width: int, left: str, middle: str, right: str) -> None:
    """Draw a single box border line."""
    inner = width - title.__len__() - 3
    width -= 1
    if inner < 1:
        inner = 1
    print(f"{MAGENTA}{left} {title}{middle * inner}{right}{NC}", flush=True)


def draw_box_border(width: int, left: str, middle: str, right: str) -> None:
    """Draw a single box border line."""
    inner = width - 2
    if inner < 1:
        inner = 1
    print(f"\r{MAGENTA}{left}{middle * inner}{right}{NC}", flush=True)

# def remove_ansi_escape_sequences(text):
#     ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
#     return ansi_escape.sub('', text)

def remove_ansi_escape_sequences(text, before="", after=""):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', text)
    return f"{before}{cleaned}{after}"

def run_command_in_box(cmd: List[str], description: str) -> bool:
    """
    Run command with output visually contained within box borders.

    Technique: Reduce reported terminal width by 4 columns (2 left + 2 right padding)
    so output naturally indents within the box boundaries. NO output parsing/modification.
    """
    cols, rows = get_terminal_size()
    box_width = cols

    fullCommand = ''
    for partCmd in cmd:
        fullCommand += partCmd
        fullCommand += ' '

    # Draw top border
    draw_title_box_border(fullCommand, box_width, '╭', '─', '╮')

    master_fd = None
    old_tty = None
    success = False

    try:
        # Save terminal settings
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        # Create PTY
        master_fd, slave_fd = pty.openpty()

        pid = os.fork()
        if pid == 0:  # Child process
            # CRITICAL: Become session leader and acquire controlling terminal
            os.setsid()
            try:
                fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            except Exception:
                pass

            # Close master in child BEFORE dup2
            os.close(master_fd)

            # Connect slave to stdin/stdout/stderr
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(slave_fd)

            # Reduce terminal width by 4 columns (2 left + 2 right padding for box)
            # This makes output naturally indent within box boundaries
            try:
                winsize = struct.pack("HHHH", rows, max(1, cols - 4), 0, 0)
                fcntl.ioctl(0, termios.TIOCSWINSZ, winsize)
                fcntl.ioctl(1, termios.TIOCSWINSZ, winsize)
                fcntl.ioctl(2, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass  # Non-fatal if ioctl fails

            # Execute command
            os.execvp(cmd[0], cmd)
            os._exit(127)

        # Parent process
        os.close(slave_fd)

        # Forward signals to child
        def forward_signal(sig, frame):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        signal.signal(signal.SIGINT, forward_signal)
        signal.signal(signal.SIGTERM, forward_signal)

       # RAW PASSTHROUGH: No output parsing/modification
        # This is the key to reliability - we don't touch the bytes
        while True:
            try:
                rlist, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [])
            except select.error as e:
                if e.args[0] != 4:  # EINTR
                    raise
                continue

            # Subprocess output → stdout (raw passthrough)
            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 4096)
                    if not data:  # EOF
                        break
                    prefix = (MAGENTA + "│ " + NC).encode()
                    suffix = (MAGENTA + " │" + NC).encode()
                    out = bytearray()
                    start = 0
                    i = 0
                    while i < len(data):
                        b = data[i]
                        if b == 13:  # \r
                            # flush pending bytes before CR
                            if start < i:
                                out.extend(data[start:i])
                            # emit CR and reinsert border
                            out.extend(b"\r")
                            out.extend(prefix)
                            start = i + 1
                            i += 1
                        if b == 10:  # \n
                            # flush pending bytes including newline
                            out.extend(data[start:i+1])
                            out.extend(prefix)
                            start = i + 1
                            i += 1
                            continue
                        i += 1
                    # flush tail
                    if start < len(data):
                        out.extend(data[start:])

                    os.write(sys.stdout.fileno(), out)
                except OSError:
                    break

                    # data = MAGENTA.encode("utf-8") + "│".encode("utf-8") + data + endBorder.encode("utf-8") + NC.encode("utf-8")
                    # data = MAGENTA.encode("utf-8") + "│".encode("utf-8") + data + "│".encode("utf-8") + NC.encode("utf-8")

            # User input → subprocess (raw passthrough)
            if sys.stdin.fileno() in rlist:
                try:
                    user_input = os.read(sys.stdin.fileno(), 1024)
                    if not user_input:
                        break
                    os.write(master_fd, user_input)
                except OSError:
                    break
        # Wait for child
        _, status = os.waitpid(pid, 0)
        success = os.waitstatus_to_exitcode(status) == 0

    except FileNotFoundError:
        print(f"│ Command not found: {cmd[0]}", flush=True)
        success = False
    except Exception as e:
        print(f"│ Error: {e}", flush=True)
        success = False
    finally:
        # Restore terminal BEFORE drawing bottom border
        if old_tty is not None:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
            except termios.error:
                pass

        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

    # Draw bottom border
    draw_box_border(box_width, '╰', '─', '╯')
    print(flush=True)  # Blank line between sections
    return success


def prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    """Simple yes/no prompt with proper terminal handling."""
    default_str = "Y/n" if default_yes else "y/N"

    # Ensure terminal is in canonical mode
    old = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            response = input(f"{question} ({default_str}): ").strip().lower()
            if response == '':
                return default_yes
            if response in ('y', 'yes'):
                return True
            if response in ('n', 'no'):
                return False
            print("Please enter 'y' or 'n'")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled by user")
        sys.exit(130)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)


def clear_screen() -> None:
    """Clear terminal screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def main() -> int:
    """Main update workflow."""
    script_path = os.path.realpath(__file__)

    # Pre-authenticate with sudo (optional but improves UX)
    cols, _ = get_terminal_size()
    # draw_title_box_border('Authenticating with sudo...', cols, '╭', '─', '╮')
    # print(f"│ {'Authenticating with sudo...'.ljust(cols - 4)} │")
    # draw_box_border(cols, '╰', '─', '╯')
    print(flush=True)

    try:
        subprocess.run(['sudo', '-v'], check=True)
    except subprocess.CalledProcessError:
        print("⚠️  Sudo authentication failed - commands may prompt for password", file=sys.stderr)
    print()

    # Run updates with boxed output
    run_command_in_box(['sudo', 'nala', 'update'], 'apt update')
    # run_command_in_box(['sudo', 'nala', 'upgrade'], 'apt upgrade')
    # run_command_in_box(['sudo', 'snap', 'refresh'], 'snap update')
    # run_command_in_box(['sudo', 'flatpak', 'update'], 'flatpak update')

    # Re-run prompt
    if prompt_yes_no("Update again?", default_yes=False):
        clear_screen()
        os.execv(sys.executable, [sys.executable, script_path])

    # Clear screen prompt
    print()
    if prompt_yes_no("Clear screen?", default_yes=True):
        clear_screen()
        home = os.path.expanduser("~")
        clear_script = os.path.join(home, "Bin", "Clear.sh")
        if os.path.isfile(clear_script) and os.access(clear_script, os.X_OK):
            subprocess.run([clear_script])

    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print("Error: This script requires an interactive terminal", file=sys.stderr)
        sys.exit(1)

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, termios.tcgetattr(sys.stdin))
        except Exception:
            pass
        print("\n\nCancelled by user")
        sys.exit(130)

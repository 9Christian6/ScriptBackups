#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
"""
Reliable system updater with output visually contained within decorative boxes.
Uses a PTY-backed line renderer to keep live command output inside the box.
Fully sudo-compatible and preserves all interactive behavior.
"""

import os
import pty
import select
import signal
import sys
import codecs
import termios
import tty
import fcntl
import struct
import subprocess
import re
import getpass
import unicodedata
from typing import List

ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")

# ANSI escape sequence regex for safe width calculation
MAGENTA = '\033[38;2;255;0;255m'
GREEN = '\033[38;2;0;255;0m'
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

def format_title_box_border(title: str, width: int, left: str, middle: str, right: str) -> str:
    """Format a box border line with a title."""
    inner = width - title.__len__() - 3
    if inner < 1:
        inner = 1
    return f"{MAGENTA}{left} {GREEN}{title}{MAGENTA}{middle * inner}{right}{NC}"


def format_box_border(width: int, left: str, middle: str, right: str) -> str:
    """Format a plain box border line."""
    inner = width - 2
    if inner < 1:
        inner = 1
    return f"{MAGENTA}{left}{middle * inner}{right}{NC}"


def draw_title_box_border(title: str, width: int, left: str, middle: str, right: str) -> None:
    """Draw a single box border line."""
    print(format_title_box_border(title, width, left, middle, right), flush=True)


def draw_box_border(width: int, left: str, middle: str, right: str) -> None:
    """Draw a single box border line."""
    print(f"\r{format_box_border(width, left, middle, right)}", flush=True)

def remove_ansi_escape_sequences(text, before="", after=""):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', text)
    return f"{before}{cleaned}{after}"

# Precompile regex to match ANSI escape sequences (e.g., \x1b[35m)
ANSI_ESCAPE_RE = re.compile(rb'\x1b\[[0-9;]*[a-zA-Z]')
ANSI_TEXT_RE = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')
SGR_TEXT_RE = re.compile(r'\x1b\[([0-9;]*)m')


def char_display_width(char: str) -> int:
    """Return the terminal column width for a single character."""
    if char == '\t':
        return 0
    if ord(char) < 32 or ord(char) == 127:
        return 0
    if unicodedata.combining(char):
        return 0
    if unicodedata.east_asian_width(char) in ('F', 'W'):
        return 2
    return 1


def visible_width(text: str) -> int:
    """Calculate visible character width, ignoring ANSI escape sequences."""
    clean = ANSI_TEXT_RE.sub('', text)
    width = 0
    for char in clean:
        if char == '\t':
            width += 8 - (width % 8)
        else:
            width += char_display_width(char)
    return width


class BoxOutputRenderer:
    """Render PTY output inside a bordered box in real time."""

    def __init__(self, total_width: int):
        self.total_width = max(4, total_width)
        self.inner_width = max(1, self.total_width - 4)
        self.decoder = codecs.getincrementaldecoder('utf-8')('surrogateescape')
        self.escape_buffer = ""
        self.active_sgr = ""
        self.lines: list[list[tuple[str, str]]] = [[]]
        self.max_buffered_lines = 4  # three finalized lines plus the current line
        self.cursor_row = 0
        self.cursor_col = 0
        self.dirty = False
        self.rendered_rows = 0
        self.rendered_cursor_row = 0
        self.dropped_since_render = 0

    def feed(self, data: bytes) -> bytes:
        """Process a PTY chunk and return boxed output bytes."""
        text = self.decoder.decode(data)
        return self._consume_text(text).encode('utf-8', 'surrogateescape')

    def finish(self) -> bytes:
        """Flush any remaining buffered output."""
        rendered = self._consume_text(self.decoder.decode(b'', final=True))
        self.escape_buffer = ""
        return rendered.encode('utf-8', 'surrogateescape')

    def _consume_text(self, text: str) -> str:
        for char in text:
            if self.escape_buffer:
                self.escape_buffer += char
                if self._escape_complete(self.escape_buffer):
                    self._apply_escape_sequence(self.escape_buffer)
                    self.escape_buffer = ""
                continue

            if char == '\x1b':
                self.escape_buffer = char
            elif char == '\r':
                self.cursor_col = 0
            elif char == '\n':
                self._linefeed()
            elif char in ('\b', '\x7f'):
                self._handle_backspace()
            elif char == '\t':
                spaces = 8 - (self.cursor_col % 8)
                for _ in range(spaces):
                    self._write_char(' ')
            elif ord(char) < 32:
                continue
            else:
                self._write_char(char)

        if self.dirty:
            return self._render_visible_lines()

        return ""

    def _write_char(self, char: str) -> None:
        width = char_display_width(char)
        if width <= 0:
            return

        if width != 1 or self.cursor_col >= self.inner_width:
            return

        cells = self.lines[self.cursor_row]
        while len(cells) < self.cursor_col:
            cells.append((' ', ''))

        cell = (char, self.active_sgr)
        if self.cursor_col < len(cells):
            cells[self.cursor_col] = cell
        else:
            cells.append(cell)

        self.cursor_col += 1
        self.dirty = True

    def _handle_backspace(self) -> None:
        if self.cursor_col > 0:
            self.cursor_col -= 1

    def _linefeed(self) -> None:
        self.cursor_col = 0
        self.cursor_row += 1
        while len(self.lines) <= self.cursor_row:
            self.lines.append([])

        if len(self.lines) > self.max_buffered_lines:
            dropped = len(self.lines) - self.max_buffered_lines
            del self.lines[:dropped]
            self.cursor_row = max(0, self.cursor_row - dropped)
            self.dropped_since_render += dropped

        self.dirty = True

    def _escape_complete(self, sequence: str) -> bool:
        if sequence.startswith('\x1b]'):
            return sequence.endswith('\x07') or sequence.endswith('\x1b\\')
        if sequence.startswith('\x1b['):
            if len(sequence) < 3:
                return False
            final = sequence[-1]
            return '@' <= final <= '~'
        if len(sequence) == 1:
            return False
        final = sequence[-1]
        return '@' <= final <= '~'

    def _apply_escape_sequence(self, sequence: str) -> None:
        sgr_match = SGR_TEXT_RE.fullmatch(sequence)
        if sgr_match:
            params = sgr_match.group(1)
            self.active_sgr = '' if params in ('', '0') else sequence
            return

        if not sequence.startswith('\x1b['):
            return

        params = sequence[2:-1]
        command = sequence[-1]
        value = 1
        if params and params.isdigit():
            value = int(params)

        if command == 'K':
            self._erase_in_line(value if params else 0)
        elif command == 'G':
            self.cursor_col = max(0, min(self.inner_width, value - 1))
        elif command == 'C':
            self.cursor_col = max(0, min(self.inner_width, self.cursor_col + value))
        elif command == 'D':
            self.cursor_col = max(0, self.cursor_col - value)
        elif command == 'A':
            self.cursor_row = max(0, self.cursor_row - value)
        elif command == 'B':
            self._move_down(value)

    def _erase_in_line(self, mode: int) -> None:
        cells = self.lines[self.cursor_row]
        if mode == 0:
            if self.cursor_col < len(cells):
                del cells[self.cursor_col:]
            self.dirty = True
            return

        if mode == 1:
            if self.cursor_col >= len(cells):
                while len(cells) <= self.cursor_col:
                    cells.append((' ', ''))
            for index in range(min(self.cursor_col + 1, len(cells))):
                cells[index] = (' ', '')
            self.dirty = True
            return

        if mode == 2:
            cells.clear()
            self.dirty = True

    def _move_down(self, value: int) -> None:
        target_row = self.cursor_row + value
        while len(self.lines) <= target_row:
            self.lines.append([])

        if len(self.lines) > self.max_buffered_lines:
            dropped = len(self.lines) - self.max_buffered_lines
            del self.lines[:dropped]
            target_row = max(0, target_row - dropped)
            self.dropped_since_render += dropped

        self.cursor_row = target_row

    def _line_content(self, cells: list[tuple[str, str]]) -> str:
        parts: list[str] = []
        active_style = ""

        for char, style in cells:
            if style != active_style:
                if style:
                    parts.append(style)
                else:
                    parts.append(NC)
                active_style = style
            parts.append(char)

        if active_style:
            parts.append(NC)

        return ''.join(parts)

    def _boxed_line(self, cells: list[tuple[str, str]]) -> str:
        content = self._line_content(cells)
        padding = ' ' * max(0, self.inner_width - len(cells))
        return f"\r{MAGENTA}│ {NC}{content}{NC}{padding}{MAGENTA} │{NC}"

    def _display_lines(self) -> list[list[tuple[str, str]]]:
        if not self.lines:
            return []

        if self.cursor_row == len(self.lines) - 1 and not self.lines[-1]:
            return self.lines[:-1]

        return self.lines

    def _render_visible_lines(self) -> str:
        display_lines = self._display_lines()
        if not display_lines:
            self.dirty = False
            self.rendered_rows = 0
            self.rendered_cursor_row = self.cursor_row
            self.dropped_since_render = 0
            return ""

        hidden_rows = max(0, self.cursor_row - (len(display_lines) - 1))
        parts: list[str] = []

        if self.rendered_rows:
            parts.append('\r')
            move_up = max(0, self.rendered_cursor_row - self.dropped_since_render)
            if move_up:
                parts.append(f"\033[{move_up}A")

        for index, cells in enumerate(display_lines):
            parts.append(self._boxed_line(cells))
            if index < len(display_lines) - 1:
                parts.append('\r\n')

        for _ in range(hidden_rows):
            parts.append('\r\n')

        parts.append('\r')
        parts.append(f"\033[{min(self.inner_width, self.cursor_col) + 3}G")

        self.dirty = False
        self.rendered_rows = len(display_lines) + hidden_rows
        self.rendered_cursor_row = self.cursor_row
        self.dropped_since_render = 0
        return ''.join(parts)

def run_command_in_box(cmd: List[str], password) -> bool:
    """
    Run command with output visually contained within box borders.

    Technique: run the command inside a PTY and repaint the current output line
    inside a live box. Only completed lines advance the terminal scroll.
    """
    cols, rows = get_terminal_size()
    # Keep one spare terminal column so boxed repaint lines never hit autowrap.
    box_width = max(10, cols - 1)
    inner_width = max(1, box_width - 4)

    fullCommand = ''
    for partCmd in cmd:
        fullCommand += partCmd
        fullCommand += ' '

    master_fd = None
    old_tty = None
    success = False

    try:
        # Save terminal settings
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        draw_title_box_border(fullCommand, box_width, '╭', '─', '╮')

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

            # Match the child PTY width to the boxed inner width.
            try:
                winsize = struct.pack("HHHH", rows, inner_width, 0, 0)
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

        renderer = BoxOutputRenderer(box_width)

        # SUDO PASSWORD AUTOMATION LOGIC
        # Check if we should attempt to inject password
        is_sudo_cmd = password is not None and len(cmd) > 0 and 'sudo' in cmd[0]
        password_sent = False
        detection_buffer = b""

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

                    # Handle Sudo Password Injection
                    if is_sudo_cmd and not password_sent:
                        detection_buffer += data
                        # Keep buffer size manageable for prompt detection
                        if len(detection_buffer) > 100:
                            detection_buffer = detection_buffer[-100:]

                        # Check for common sudo password prompts
                        if b'[sudo] password' in detection_buffer or b'password:' in detection_buffer.lower():
                            try:
                                # Send password followed by newline
                                os.write(master_fd, (password + '\n').encode('utf-8'))
                                password_sent = True
                                detection_buffer = b""
                            except OSError:
                                pass  # Child might have exited

                    boxed_output = renderer.feed(data)
                    if boxed_output:
                        write_stdout(boxed_output)
                except OSError:
                    break

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

        final_output = renderer.finish()
        if final_output:
            write_stdout(final_output)

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


def prompt_password_in_box(prompt: str = "Enter password: ") -> str:
    """Prompt for a password inside a magenta box with terminal echo disabled."""
    cols, _ = get_terminal_size()
    box_width = max(10, cols - 1)
    inner_width = max(1, box_width - 4)
    prompt_width = min(inner_width, visible_width(prompt))
    cursor_col = min(box_width - 1, 3 + prompt_width)
    padding = ' ' * max(0, inner_width - prompt_width)

    draw_title_box_border("sudo password", box_width, '╭', '─', '╮')

    old = termios.tcgetattr(sys.stdin)
    try:
        new = termios.tcgetattr(sys.stdin)
        new[3] &= ~termios.ECHO
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new)

        write_stdout(f"\r{MAGENTA}│ {NC}{prompt}{padding}{MAGENTA} │{NC}")
        write_stdout(f"\r\033[{cursor_col}G")
        password = sys.stdin.readline().rstrip('\n').rstrip('\r')
        write_stdout("\r\n")
        return password
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        draw_box_border(box_width, '╰', '─', '╯')
        print(flush=True)


def clear_screen() -> None:
    """Clear terminal screen."""
    os.system('clear' if os.name == 'posix' else 'cls')


def write_stdout(data: str | bytes) -> None:
    """Write raw data to stdout without print() side effects."""
    if isinstance(data, str):
        data = data.encode('utf-8', 'surrogateescape')
    os.write(sys.stdout.fileno(), data)


def draw_terminal_box(title: str, box_width: int, bottom_row: int, inner_width: int) -> None:
    """Draw a full-screen box and place the cursor at the start of the interior."""
    empty_line = f"{MAGENTA}│{NC} {' ' * inner_width} {MAGENTA}│{NC}"
    pieces = ["\033[2J\033[H", format_title_box_border(title, box_width, '╭', '─', '╮')]

    for row in range(2, bottom_row):
        pieces.append(f"\033[{row};1H{empty_line}")

    pieces.append(f"\033[{bottom_row};1H{format_box_border(box_width, '╰', '─', '╯')}")
    write_stdout(''.join(pieces))


def enable_box_output_region(interior_top: int, interior_bottom: int, inner_left: int, inner_right: int) -> None:
    """Constrain terminal output to the interior of the box."""
    write_stdout(
        f"\033[?69h"
        f"\033[{interior_top};{interior_bottom}r"
        f"\033[{inner_left};{inner_right}s"
        f"\033[?6h"
        f"\033[{interior_top};{inner_left}H"
    )


def disable_box_output_region(cursor_row: int) -> None:
    """Restore normal terminal margins and move the cursor below the box."""
    write_stdout(f"\033[?6l\033[?69l\033[r\033[{cursor_row};1H")


def main() -> int:
    """Main update workflow."""
    script_path = os.path.realpath(__file__)
    print(flush=True)
    # Run updates with boxed output
    password = prompt_password_in_box()
    repeat_update = True
    while repeat_update:
        repeat_update = False
        run_command_in_box(['sudo', 'nala', 'update'], password)
        run_command_in_box(['sudo', 'nala', 'upgrade'], password)
        run_command_in_box(['sudo', 'snap', 'refresh'], password)
        run_command_in_box(['sudo', 'flatpak', 'update'], password)
        repeat_update = prompt_yes_no("Update again?", default_yes=False)
        if repeat_update:
            clear_screen()

    # Clear screen prompt
    print()
    if prompt_yes_no("Clear screen?", default_yes=True):
        clear_screen()
        home = os.path.expanduser("~")
        clear_script = os.path.join(home, "Bin", "Clear.sh")
        if os.path.isfile(clear_script) and os.access(clear_script, os.X_OK):
            subprocess.run([clear_script])
    print('', flush=True)
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

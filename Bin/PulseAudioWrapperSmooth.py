#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import os
import select
import signal
import time
import subprocess
import sys
from SoundSinkSwitcher import sinks_now, load_config, settings, display_name, pactl, CONFIG

# Configuration
BIN = os.environ.get('BIN', os.path.expanduser('~') + '/Bin')
ICON_SCRIPT = os.path.join(BIN, 'soundSinkIcon.sh')
BAR_WIDTH = 15
SUFFIX = " |"
ROOT_FOREGROUND = os.environ.get('ROOT_FOREGROUND', '#ffffff')
MUTED_COLOR = "#666666"
FILL_CHAR = "─"
INDICATOR = "|"

def get_audio_info():
    """Read volume, mute and label from one consistent sink snapshot."""
    sinks = sinks_now()
    current = pactl('get-default-sink')
    sink = next((sink for sink in sinks if sink['name'] == current), None)
    if sink is None:
        return '󰓃', 0, False
    prefix = '󰓃'
    try:
        config = load_config(sinks)
        options = settings(config, sink)
        if options.get('enabled', True):
            prefix = options.get('icon', '󰓃')
            if options.get('show_name', False):
                prefix += ' ' + display_name(config, sink)
    except (OSError, ValueError) as error:
        print(f'Sound sink configuration: {error}', file=sys.stderr)
    channels = sink.get('volume', {}).values()
    percentages = [float(channel['value_percent'].rstrip('%')) for channel in channels]
    volume = max(0, min(100, round(sum(percentages) / len(percentages)))) if percentages else 0
    return prefix.replace('%', '%%'), volume, sink.get('mute', False)


def get_gradient_color(index, bar_width):
    """
    Calculate color based on absolute position in the bar.
    Mapping:
    0%  (index 0)         -> Green (0, 255, 0)
    50% (index mid)       -> Yellow (255, 255, 0)
    100% (index max)      -> Red (255, 0, 0)
    """
    if bar_width <= 1:
        ratio = 0.0
    else:
        # Map index 0..(bar_width-1) to 0.0..1.0
        ratio = index / (bar_width - 1)

    if ratio <= 0.5:
        # Phase 1: Green (0, 255, 0) to Yellow (255, 255, 0)
        # Red increases 0 -> 255, Green stays 255
        local_ratio = ratio * 2  # Normalize 0.0-0.5 to 0.0-1.0
        r = int(local_ratio * 255)
        g = 255
    else:
        # Phase 2: Yellow (255, 255, 0) to Red (255, 0, 0)
        # Red stays 255, Green decreases 255 -> 0
        local_ratio = (ratio - 0.5) * 2  # Normalize 0.5-1.0 to 0.0-1.0
        r = 255
        g = int(255 - (local_ratio * 255))

    return "#{:02X}{:02X}00".format(r, g)

def build_bar(volume, mute):
    """Construct the polybar formatted string."""
    filled = (volume * BAR_WIDTH) // 100
    if filled < 0:
        filled = 0
    if filled > BAR_WIDTH:
        filled = BAR_WIDTH

    empty_count = BAR_WIDTH - filled
    filled_part = ""

    if mute:
        # Solid color for muted
        filled_part = "".join([f"%{{F{MUTED_COLOR}}}{FILL_CHAR}" for _ in range(filled)])
    else:
        # Gradient color for active
        for i in range(filled):
            # Color depends on absolute position in the bar (0 to BAR_WIDTH-1)
            # to ensure Green@0%, Yellow@50%, Red@100% regardless of current fill level
            color = get_gradient_color(i, BAR_WIDTH)
            filled_part += f"%{{F{color}}}{FILL_CHAR}"

    empty_part = ""
    if empty_count > 0:
        empty_part = FILL_CHAR * empty_count

    # Reset color after filled part, add indicator, then empty part
    bar = f"{filled_part}%{{F-}}{INDICATOR}{empty_part}"
    return bar

def render():
    prefix, volume, mute = get_audio_info()
    if prefix:
        prefix = f"{prefix} "
    bar = build_bar(volume, mute)
    if mute:
        return f"%{{F{MUTED_COLOR}}}{prefix}{volume}% %{{F{MUTED_COLOR}}}{bar}%{{F-}}{SUFFIX}"
    return f"{prefix}%{{F#FFFFFF}}{volume}% %{{F-}}{bar}{SUFFIX}%{{F-}}"


def watch():
    """Stream updates on sink/server events, without a polling delay."""
    subscriber = None
    last_output = None

    def stop(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def config_stamp():
        try:
            return CONFIG.stat().st_mtime_ns
        except OSError:
            return None

    def emit():
        nonlocal last_output
        try:
            output = render()
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            print(f'Audio update failed: {error}', file=sys.stderr)
            output = '󰓃 Audio unavailable |'
        if output != last_output:
            print(output, flush=True)
            last_output = output

    try:
        while True:
            try:
                # Subscribe before the initial snapshot so changes during startup
                # are queued rather than missed.
                subscriber = subprocess.Popen(
                    ['pactl', 'subscribe'], stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, env={**os.environ, 'LC_ALL': 'C'})
                emit()
                stamp = config_stamp()
                pending = b''
                while True:
                    ready, _, _ = select.select([subscriber.stdout], [], [], 1)
                    changed = False
                    if ready:
                        data = os.read(subscriber.stdout.fileno(), 65536)
                        if not data:
                            break
                        pending += data
                        lines = pending.split(b'\n')
                        pending = lines.pop()
                        changed = any(any(kind in line for kind in
                                          (b' on sink #', b' on server #', b' on card #'))
                                      for line in lines)
                    new_stamp = config_stamp()
                    if changed or new_stamp != stamp:
                        emit()
                        stamp = config_stamp()
            except OSError as error:
                print(f'Audio subscription failed: {error}', file=sys.stderr)
            finally:
                if subscriber is not None:
                    if subscriber.poll() is None:
                        subscriber.terminate()
                    try:
                        subscriber.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        subscriber.kill()
                        subscriber.wait()
                    subscriber = None
            time.sleep(1)
    finally:
        if subscriber is not None:
            subscriber.terminate()
            try:
                subscriber.wait(timeout=1)
            except subprocess.TimeoutExpired:
                subscriber.kill()
                subscriber.wait()


if __name__ == "__main__":
    if sys.argv[1:] == ['watch']:
        watch()
    elif len(sys.argv) > 1:
        from SoundSinkSwitcher import main as switcher_main
        sys.exit(switcher_main())
    else:
        print(render())

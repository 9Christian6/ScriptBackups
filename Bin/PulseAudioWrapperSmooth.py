#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import os
import subprocess

# Configuration
BIN = os.environ.get('BIN', os.path.expanduser('~') + '/Bin')
ICON_SCRIPT = os.path.join(BIN, 'soundSinkIcon.sh')
BAR_WIDTH = 15
SUFFIX = " |"
ROOT_FOREGROUND = os.environ.get('ROOT_FOREGROUND', '#ffffff')
MUTED_COLOR = "#666666"
FILL_CHAR = "─"
INDICATOR = "|"

def get_icon_prefix():
    """Run the icon script if it exists and is executable."""
    if os.path.isfile(ICON_SCRIPT) and os.access(ICON_SCRIPT, os.X_OK):
        try:
            result = subprocess.run(
                    [ICON_SCRIPT],
                    capture_output=True,
                    text=True,
                    )
            icon = result.stdout.strip()
            icon = icon + ' '
            return icon
        except Exception as e:
            print(e)
    return ""

def get_volume_info():
    """Retrieve volume and mute status using pamixer or pactl."""
    volume = 0
    mute = False
    vol_proc = subprocess.run( ['pactl', 'get-sink-volume', '@DEFAULT_SINK@'], capture_output=True, text=True)
    mute_proc = subprocess.run( ['pactl', 'get-sink-mute', '@DEFAULT_SINK@'], capture_output=True, text=True)

    if vol_proc.returncode == 0:
        for token in vol_proc.stdout.split():
            if token.endswith('%'):
                volume = int(token.replace('%', ''))
                break

    if mute_proc.returncode == 0:
        parts = mute_proc.stdout.strip().split()
        if len(parts) >= 2:
            mute = parts[1].lower() == 'yes'

    if volume < 0:
        volume = 0
    if volume > 100:
        volume = 100

    return volume, mute

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

def main():
    prefix = get_icon_prefix()
    if prefix:
        prefix = f"{prefix} "

    volume, mute = get_volume_info()
    bar = build_bar(volume, mute)

    if mute:
        # Muted output format
        print(f"%{{F{MUTED_COLOR}}}{prefix}{volume}% %{{F{MUTED_COLOR}}}{bar}%{{F-}}{SUFFIX}")
    else:
        # Normal output format
        print(f"{prefix}%{{F#FFFFFF}}{volume}% %{{F-}}{bar}{SUFFIX}%{{F-}}")

if __name__ == "__main__":
    main()

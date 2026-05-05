#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import subprocess
import os
import sys

# Configuration
EMOJI_FILE = os.path.expanduser("~/.myemojis")
# Use "wl-copy" for Wayland, "xclip -selection clipboard" for X11
CLIPBOARD_TOOL = "xclip -selection clipboard"

#SKIN_TONES = { "None": "", "Light": "🏻", "Medium-Light": "🏼", "Medium": "🏽", "Medium-Dark": "🏾", "Dark": "🏿" }
SKIN_TONES = {"None": "", "Light": "", "Medium-Light": "", "Medium": "", "Medium-Dark": "", "Dark": ""}

def run_rofi(options, prompt):
    input_str = "\n".join(options)
    try:
        process = subprocess.Popen(
                ["rofi", "-dmenu", "-i", "-p", prompt],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True
                )
        stdout, _ = process.communicate(input=input_str)
        return stdout.strip()
    except FileNotFoundError:
        print("Error: 'rofi' not found.")
        sys.exit(1)

def copy_to_clipboard(text):
    # This ensures only the emoji string is piped to the clipboard
    process = subprocess.Popen(CLIPBOARD_TOOL.split(), stdin=subprocess.PIPE, text=True)
    process.communicate(input=text)

def main():
    if not os.path.exists(EMOJI_FILE):
        print(f"Error: {EMOJI_FILE} not found.")
        return

    # 1. Load and format contents for Rofi
    with open(EMOJI_FILE, "r") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    # Replace ':' or ';' with a space for a cleaner display in Rofi
    # This handles the "emoji: name" -> "emoji name" transformation
    # display_map = {line.replace(':', ' ').replace(';', ' '): line for line in raw_lines}
    display_map = {line.replace(';', ' '): line for line in raw_lines}

    # 2. Prompt user selection
    selection = run_rofi(list(display_map.keys()), "Emoji")

    if not selection:
        return

    # 3. Extract only the emoji (the part before the first space)
    # selected_emoji = selection.split(';')[0]
    selected_emoji = selection.split(' ')[0]

    # Simple check for skin tone compatibility based on the description
    # We look at the selection string to see if it suggests a human emoji
    skin_tone_keywords = ["person", "man", "woman", "hand", "finger", "gesture", "boy", "girl"]
    supports_skin_tone = any(key in selection.lower() for key in skin_tone_keywords)

    final_emoji = selected_emoji

    #if supports_skin_tone:
    #    selected_tone_name = run_rofi(list(SKIN_TONES.keys()), "Skin Tone")
    #    if selected_tone_name and selected_tone_name != "None":
    #        final_emoji += SKIN_TONES[selected_tone_name]

    # 4. Final Copy
    copy_to_clipboard(final_emoji)

if __name__ == "__main__":
    main()

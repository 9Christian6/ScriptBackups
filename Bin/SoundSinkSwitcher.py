"""Shared sink discovery, configuration and selection for Polybar."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

HEADER = '# Edits apply on the next hover, click or bar update.\n# All discovered sinks are prefilled, including disconnected outputs.\n# name="" uses the device description. enabled=false hides a sink and skips it when cycling; it does not change audio settings.\n# allow_unknown=true permits outputs with no connection detection (e.g. S/PDIF).\n# Known disconnected ports are always excluded. Defaults apply unless overridden.\n[default]\nname = ""\nicon = "\U000f04c3"\nenabled = true\nallow_unknown = false\nshow_name = false # Set true to show custom names beside the volume bar.\n'

CONFIG = Path.home() / '.config/soundSinkSwitcher/config.toml'


def pactl(*args):
    result = subprocess.run(['pactl', *args], capture_output=True, text=True,
                            timeout=3, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'pactl failed')
    return result.stdout.strip()


def sinks_now():
    return json.loads(pactl('--format=json', 'list', 'sinks'))


def suggested_name(sink):
    return sink.get('properties', {}).get('node.nick') or sink.get('description') or sink['name']


def load_config(sinks):
    # Multiple bars and hover/click processes can discover a new sink together.
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with (CONFIG.parent / '.config.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _load_config(sinks)


def _load_config(sinks):
    """Preserve edits; append entries for newly discovered devices."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG.exists():
        try:
            with CONFIG.open('x', encoding='utf-8') as stream:
                stream.write(HEADER)
        except FileExistsError:
            pass
    with CONFIG.open('rb') as stream:
        config = tomllib.load(stream)
    if not isinstance(config.get('default', {}), dict) or not isinstance(config.get('sinks', {}), dict):
        raise ValueError('default and sinks must be TOML tables')
    additions = ''
    for sink in sinks:
        if sink['name'] not in config.get('sinks', {}):
            icon = '' if 'ASUS_Xonar_U7' in sink['name'] else config.get('default', {}).get('icon', '󰓃')
            additions += (f'\n[sinks.{json.dumps(sink["name"])}]\n'
                          f'name = {json.dumps(suggested_name(sink), ensure_ascii=False)}\n'
                          f'icon = {json.dumps(icon, ensure_ascii=False)}\n'
                          f'enabled = {str(config.get("default", {}).get("enabled", True)).lower()}\n')
    if additions:
        with CONFIG.open('a', encoding='utf-8') as stream:
            stream.write(additions)
        with CONFIG.open('rb') as stream:
            config = tomllib.load(stream)
    return config


def settings(config, sink):
    result = dict(config.get('default', {}))
    entry = config.get('sinks', {}).get(sink['name'], {})
    if not isinstance(entry, dict):
        raise ValueError('Each sink must have a TOML table')
    result.update(entry)
    for key in ('enabled', 'allow_unknown', 'show_name'):
        if key in result and not isinstance(result[key], bool):
            raise ValueError(f'{key} must be true or false')
    for key in ('name', 'icon'):
        if key in result and not isinstance(result[key], str):
            raise ValueError(f'{key} must be a string')
    return result


def display_name(config, sink):
    return ' '.join((settings(config, sink).get('name') or suggested_name(sink)).split())


def hdmi_available(sink):
    """Match Pro Audio HDMI PCM monitor names to live ALSA ELD data.

    Avoid a fixed PCM/ELD filename mapping, which varies with HDMI MST.
    None means HDMI could not be identified or checked.
    """
    props = sink.get('properties', {})
    card, device = props.get('alsa.card'), props.get('alsa.device')
    if not str(card).isdigit() or not str(device).isdigit():
        return None
    directory = Path('/proc/asound') / f'card{card}'
    try:
        info = (directory / f'pcm{device}p/info').read_text()
    except OSError:
        info = ''
    if 'HDMI' not in info and 'hdmi' not in sink['name'].lower():
        return None
    monitor = props.get('alsa.name', '')
    readable = False
    for path in directory.glob('eld*'):
        try:
            values = dict(line.split(None, 1) for line in path.read_text().splitlines() if line.strip())
        except (OSError, ValueError):
            continue
        readable = True
        if (values.get('monitor_present') == '1' and values.get('eld_valid') == '1'
                and int(values.get('sad_count', '0')) > 0
                and values.get('monitor_name') == monitor):
            return True
    return False if readable else None


def available(sink, config):
    options = settings(config, sink)
    if not options.get('enabled', True):
        return False
    if sink['name'] == 'auto_null' or sink.get('properties', {}).get('device.class') == 'abstract':
        return False
    active = next((port for port in sink.get('ports', []) if port['name'] == sink.get('active_port')), None)
    if active:
        status = active.get('availability', 'unknown').lower()
        if status in ('not available', 'unavailable', 'no'):
            return False
        if status in ('available', 'yes'):
            return True
    hdmi = hdmi_available(sink)
    if hdmi is not None:
        return hdmi
    # Activity (RUNNING/SUSPENDED) is not physical connection status.
    return options.get('allow_unknown', False)


def snapshot():
    sinks = sinks_now()
    config = load_config(sinks)
    current = pactl('get-default-sink')
    eligible = [sink for sink in sinks if available(sink, config)]
    names = [sink['name'] for sink in eligible]
    target = None
    if names:
        target = eligible[(names.index(current) + 1) % len(names)] if current in names else eligible[0]
    return sinks, config, current, target


def pipewire_command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=3)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'{args[0]} failed')
    return result.stdout


def move_locked_stream(stream, target):
    """Relink a PipeWire DONT_MOVE stream (e.g. Zoom) without restarting it.

    PipeWire's Pulse server rejects move-sink-input for node.dont-reconnect.
    WirePlumber also ignores target metadata for these streams. Match DSP
    channels explicitly; never guess a channel map or touch capture streams.
    """
    objects = json.loads(pipewire_command('pw-dump'))
    nodes = {obj['id']: obj['info']['props'] for obj in objects
             if obj['type'] == 'PipeWire:Interface:Node'}
    serial = stream['properties'].get('object.serial')
    source_id = next((index for index, props in nodes.items()
                      if serial is not None and str(props.get('object.serial')) == str(serial)
                      and props.get('media.class') == 'Stream/Output/Audio'), None)
    target_id = next((index for index, props in nodes.items()
                      if props.get('node.name') == target['name']
                      and props.get('media.class') == 'Audio/Sink'), None)
    if source_id is None or target_id is None:
        raise RuntimeError('Playback stream or destination disappeared')
    ports = [obj for obj in objects if obj['type'] == 'PipeWire:Interface:Port']

    def channels(node_id, direction):
        result = {}
        for port in ports:
            props = port['info']['props']
            if str(props.get('node.id')) != str(node_id) or props.get('port.direction') != direction:
                continue
            channel = props.get('audio.channel')
            if not channel or channel in result:
                raise RuntimeError('Cannot safely map playback channels')
            result[channel] = port['id']
        return result

    outputs, inputs = channels(source_id, 'out'), channels(target_id, 'in')
    # ALSA Pro Audio exposes stereo HDMI as AUX0/AUX1 instead of FL/FR.
    if outputs.keys() == {'FL', 'FR'} and inputs.keys() == {'AUX0', 'AUX1'}:
        inputs = {'FL': inputs['AUX0'], 'FR': inputs['AUX1']}
    elif outputs.keys() == {'AUX0', 'AUX1'} and inputs.keys() == {'FL', 'FR'}:
        inputs = {'AUX0': inputs['FL'], 'AUX1': inputs['FR']}
    if not outputs or not outputs.keys() <= inputs.keys():
        raise RuntimeError('Destination does not have matching playback channels')
    links = [obj['info'] for obj in objects
             if obj['type'] == 'PipeWire:Interface:Link'
             and obj['info']['output-node-id'] == source_id
             and nodes.get(obj['info']['input-node-id'], {}).get('media.class') == 'Audio/Sink']
    existing = {(link['output-port-id'], link['input-port-id']) for link in links}
    wanted = {(output, inputs[channel]) for channel, output in outputs.items()}
    added = []
    try:
        # Keep the old route until every new channel has been connected.
        for output, input_port in sorted(wanted - existing):
            pipewire_command('pw-link', str(output), str(input_port))
            added.append((output, input_port))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        for output, input_port in added:
            try:
                pipewire_command('pw-link', '-d', str(output), str(input_port))
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
        raise
    for output, input_port in sorted(existing - wanted):
        pipewire_command('pw-link', '-d', str(output), str(input_port))


def move_stream(stream, target):
    try:
        pactl('move-sink-input', str(stream['index']), target['name'])
    except RuntimeError:
        if str(stream.get('properties', {}).get('node.dont-reconnect')).lower() != 'true':
            raise
        move_locked_stream(stream, target)


def cycle():
    sinks, config, current, target = snapshot()
    if target is None:
        raise RuntimeError('No connected audio sinks available')
    if target['name'] == current:
        print(f'Only available sink: {display_name(config, target)}')
    fresh = next((sink for sink in sinks_now() if sink['name'] == target['name']), None)
    if fresh is None or not available(fresh, config):
        raise RuntimeError('The next sink disconnected; please try again')
    pactl('set-default-sink', target['name'])
    failures = []
    for stream in json.loads(pactl('--format=json', 'list', 'sink-inputs')):
        try:
            move_stream(stream, target)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            label = stream.get('properties', {}).get('application.name', str(stream['index']))
            failures.append(f'{label}: {error}')
    if failures:
        raise RuntimeError('Default sink changed, but could not move ' + '; '.join(failures))
    print(f'Default sink set to: {display_name(config, target)}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('cycle', 'tooltip', 'list', 'init'), nargs='?', default='cycle')
    args = parser.parse_args()
    try:
        if args.action == 'cycle':
            cycle()
            return 0
        sinks, config, current, target = snapshot()
        if args.action == 'tooltip':
            active = next((sink for sink in sinks if sink['name'] == current), None)
            if active and settings(config, active).get('enabled', True):
                print(f'Current: {display_name(config, active)}')
            if target is None:
                print('Next: no connected audio sink available')
            elif target['name'] == current:
                print('Next: no other connected audio sink')
            else:
                print(f'Next: {display_name(config, target)}')
            print('Middle-click to switch output')
        elif args.action == 'list':
            for sink in sinks:
                if not settings(config, sink).get('enabled', True):
                    continue
                status = 'available' if available(sink, config) else 'unavailable'
                print(f'{display_name(config, sink)} [{status}] — {sink["name"]}')
        else:
            print(CONFIG)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        if args.action == 'tooltip':
            print(f'Audio unavailable: {error}')
        else:
            print(f'Sound sink switcher: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

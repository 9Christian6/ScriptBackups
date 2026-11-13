"""Regression tests for locked playback streams, without changing live audio."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

import SoundSinkSwitcher as switcher


def obj(kind, index, **props):
    return {'type': f'PipeWire:Interface:{kind}', 'id': index, 'info': {'props': props}}


class LockedStreamTests(unittest.TestCase):
    def setUp(self):
        self.stream = {'index': 900, 'properties': {
            'object.serial': '900', 'node.dont-reconnect': 'true'}}
        self.target = {'name': 'headphones'}
        self.graph = [
            obj('Node', 10, **{'object.serial': 900, 'media.class': 'Stream/Output/Audio'}),
            obj('Node', 20, **{'node.name': 'headphones', 'media.class': 'Audio/Sink'}),
            obj('Node', 30, **{'media.class': 'Audio/Sink'}),
        ]
        for index, node, direction, channel in (
                (11, 10, 'out', 'FL'), (12, 10, 'out', 'FR'),
                (21, 20, 'in', 'FL'), (22, 20, 'in', 'FR')):
            self.graph.append(obj('Port', index, **{
                'node.id': node, 'port.direction': direction, 'audio.channel': channel}))
        for output, input_port in ((11, 31), (12, 32)):
            self.graph.append({'type': 'PipeWire:Interface:Link', 'info': {
                'output-node-id': 10, 'input-node-id': 30,
                'output-port-id': output, 'input-port-id': input_port}})

    def run_move(self, fail=None):
        def command(*args):
            if args == ('pw-dump',):
                return json.dumps(self.graph)
            if args == fail:
                raise RuntimeError('link failed')
            return ''
        return patch.object(switcher, 'pipewire_command', side_effect=command)

    def test_connects_channels_before_removing_old_route(self):
        with self.run_move() as command:
            switcher.move_locked_stream(self.stream, self.target)
        self.assertEqual([call.args for call in command.call_args_list], [
            ('pw-dump',), ('pw-link', '11', '21'), ('pw-link', '12', '22'),
            ('pw-link', '-d', '11', '31'), ('pw-link', '-d', '12', '32')])

    def test_pro_audio_stereo_channel_mapping(self):
        for port in self.graph:
            props = port['info'].get('props', {})
            if props.get('node.id') == 20:
                props['audio.channel'] = {'FL': 'AUX0', 'FR': 'AUX1'}[props['audio.channel']]
        with self.run_move() as command:
            switcher.move_locked_stream(self.stream, self.target)
        self.assertIn(('pw-link', '11', '21'), [call.args for call in command.call_args_list])

    def test_failed_connection_rolls_back_and_keeps_old_route(self):
        with self.run_move(fail=('pw-link', '12', '22')) as command:
            with self.assertRaisesRegex(RuntimeError, 'link failed'):
                switcher.move_locked_stream(self.stream, self.target)
        self.assertEqual([call.args for call in command.call_args_list][-1],
                         ('pw-link', '-d', '11', '21'))
        self.assertNotIn(('pw-link', '-d', '11', '31'),
                         [call.args for call in command.call_args_list])

    def test_missing_channel_leaves_links_untouched(self):
        self.graph = [o for o in self.graph if o.get('id') != 22]
        with self.run_move() as command:
            with self.assertRaisesRegex(RuntimeError, 'matching playback channels'):
                switcher.move_locked_stream(self.stream, self.target)
        self.assertEqual(command.call_count, 1)

    def test_normal_pulse_stream_uses_no_pipewire_tools(self):
        with patch.object(switcher, 'pactl'), patch.object(switcher, 'move_locked_stream') as fallback:
            switcher.move_stream(self.stream, self.target)
        fallback.assert_not_called()

    def test_only_locked_streams_use_fallback_on_failure(self):
        with patch.object(switcher, 'pactl', side_effect=RuntimeError('Invalid argument')), \
                patch.object(switcher, 'move_locked_stream') as fallback:
            switcher.move_stream(self.stream, self.target)
            fallback.assert_called_once_with(self.stream, self.target)
            self.stream['properties'].pop('node.dont-reconnect')
            with self.assertRaises(RuntimeError):
                switcher.move_stream(self.stream, self.target)

    def test_cycle_reports_partial_failure(self):
        target = {**self.target, 'description': 'Headphones'}
        with patch.object(switcher, 'snapshot', return_value=([], {}, 'old', target)), \
                patch.object(switcher, 'sinks_now', return_value=[target]), \
                patch.object(switcher, 'available', return_value=True), \
                patch.object(switcher, 'pactl', return_value=json.dumps([self.stream])), \
                patch.object(switcher, 'move_stream', side_effect=RuntimeError('failed')), \
                patch('sys.argv', ['switcher', 'cycle']), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(switcher.main(), 1)


if __name__ == '__main__':
    unittest.main()

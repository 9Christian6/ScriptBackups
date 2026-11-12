#!/usr/bin/env python3
"""Exercise slow converters, process-group cancellation and result publication."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/vifm-preview'


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.session = self.base / 'session'
        self.session.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, VIFM_PREVIEW_SESSION=str(self.session),
                        VIFM_PREVIEW_SERVER='', PATH=f'{self.bin}:{os.environ["PATH"]}')

    def tearDown(self):
        self.call('shutdown')
        self.tmp.cleanup()

    def call(self, *args):
        return subprocess.check_output([str(SCRIPT), *map(str, args)], env=self.env,
                                       text=True, timeout=2)

    def show(self, path):
        return self.call('show', 0, 0, 80, 24, path)

    def state(self):
        return json.loads((self.session / 'preview/state.json').read_text())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail('Timed out waiting for worker')

    def converter(self, code):
        tool = self.bin / 'pdftoppm'
        tool.write_text('#!/usr/bin/env python3\n' + code)
        tool.chmod(0o755)
        path = self.base / 'sample.pdf'
        path.write_bytes(b'%PDF-1.4\n')
        return path

    def test_cancel_removes_partial_files_and_grandchildren(self):
        path = self.converter('''import pathlib, subprocess, sys, time
out = pathlib.Path(sys.argv[-1] + '.jpg')
out.write_bytes(b'partial')
child = subprocess.Popen(['sleep', '60'])
(out.parent / 'child.pid').write_text(str(child.pid))
time.sleep(60)
''')
        start = time.monotonic()
        self.assertIn('Loading preview', self.show(path))
        self.assertLess(time.monotonic() - start, .5)
        state = self.state()
        directory = Path(state['directory'])
        self.wait_for(lambda: (directory / 'child.pid').exists())
        pid = int((directory / 'child.pid').read_text())
        self.call('clear')
        self.assertFalse(directory.exists())
        status = Path(f'/proc/{pid}/status')
        self.wait_for(lambda: not status.exists() or '\nState:\tZ' in status.read_text())
        self.assertFalse((self.session / 'preview/state.json').exists())

    def test_completion_redraw_and_switch(self):
        path = self.base / 'space " quote\nname.txt'
        path.write_text('Ready\n\x1b[31mcontrol')
        self.assertIn('Loading preview', self.show(path))
        self.wait_for(lambda: 'result' in self.state())
        old = self.state()
        self.call('clear')  # vifm clears graphical previews before a redraw
        self.assertIn('Ready', self.show(path))
        self.assertNotIn('\x1b', self.show(path))
        self.assertEqual(old['token'], self.state()['token'])
        other = self.base / 'other.txt'
        other.write_text('New')
        self.show(other)
        self.assertFalse(Path(old['directory']).exists())

    def test_fifo_with_no_reader_never_blocks(self):
        fifo = self.base / 'fifo'
        os.mkfifo(fifo)
        self.env['FIFO_UEBERZUG'] = str(fifo)
        start = time.monotonic()
        self.call('clear')
        self.assertLess(time.monotonic() - start, .5)

    def test_two_sessions_do_not_cancel_each_other(self):
        path = self.converter('import time\ntime.sleep(60)\n')
        self.show(path)
        first = self.state()
        other_session = self.base / 'other-session'
        other_session.mkdir()
        self.env['VIFM_PREVIEW_SESSION'] = str(other_session)
        try:
            self.show(path)
            self.call('clear')
            self.assertTrue(Path(first['directory']).exists())
            os.kill(first['pid'], 0)
        finally:
            self.call('shutdown')
            self.env['VIFM_PREVIEW_SESSION'] = str(self.session)


@unittest.skipUnless(os.environ.get('VIFM_TEST_BINARY'), 'set VIFM_TEST_BINARY for terminal integration')
class TerminalTests(unittest.TestCase):
    def test_automatic_refresh_and_navigation_during_conversion(self):
        import fcntl
        import pty
        import select
        import struct
        import termios
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / 'config'
            config.mkdir()
            config.joinpath('vifmrc').write_text(
                SCRIPT.parents[1].joinpath('vifmrc').read_text() + '\nset vifminfo=\n')
            config.joinpath('colors').symlink_to(SCRIPT.parents[1] / 'colors')
            files = base / 'files'
            files.mkdir()
            (files / 'a.pdf').write_bytes(b'%PDF-1.4\n')
            (files / 'b.txt').write_text('AUTOMATIC_PREVIEW_READY\n')
            tools = base / 'bin'
            tools.mkdir()
            converter = tools / 'pdftoppm'
            converter.write_text('#!/usr/bin/env python3\nimport pathlib, sys, time\n'
                                 "pathlib.Path(sys.argv[-1] + '.jpg').write_bytes(b'partial')\n"
                                 'time.sleep(60)\n')
            converter.chmod(0o755)
            session = base / 'session'
            session.mkdir()
            binary = os.environ['VIFM_TEST_BINARY']
            env = dict(os.environ, HOME=str(base), VIFM=str(config), TERM='xterm-256color',
                       VIFM_PREVIEW_SESSION=str(session), VIFM_PREVIEW_BINARY=binary,
                       PATH=f'{tools}:{SCRIPT.parent}:{os.environ["PATH"]}')
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 120, 0, 0))
            app = subprocess.Popen([binary, '--server-name', 'preview-test', '--select',
                                    str(files / 'a.pdf'), '-c', 'view'], env=env,
                                   stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            output = bytearray()
            def wait_for(predicate):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if select.select([master], [], [], .03)[0]:
                        output.extend(os.read(master, 65536))
                    if predicate():
                        return
                self.fail('Terminal preview did not update: ' + repr(bytes(output[-2000:])))
            try:
                wait_for(lambda: bool(list(session.glob('preview/request-*/preview.jpg'))))
                old = next(session.glob('preview/request-*'))
                wait_for(lambda: b'Loading preview' in output)
                start = time.monotonic()
                os.write(master, b'j')
                wait_for(lambda: b'AUTOMATIC_PREVIEW_READY' in output)
                self.assertLess(time.monotonic() - start, 2)
                self.assertFalse(old.exists())
            finally:
                os.write(master, b':q!\r')
                try:
                    app.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    app.kill()
                    app.wait()
                subprocess.run([str(SCRIPT), 'shutdown'], env=env, check=True)
                os.close(master)


if __name__ == '__main__':
    unittest.main()

"""Exercise the installed Leaf in a fresh pseudo-terminal and private state directory."""
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import struct
import subprocess
import tempfile
import termios
import time
import unittest

CLI = str(Path(__file__).with_name("leaf-relay"))


class ReviewTest(unittest.TestCase):
    def test_review_round_trip(self):
        cases = [("plan", "# Plan\n\nCheck the dataset.\n", b"Sa", "sent"),
                 ("diff", "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n", b"q", "closed")]
        for kind, content, keys, outcome in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                env = dict(os.environ, HOME=tmp, XDG_STATE_HOME=tmp, XDG_DATA_HOME=tmp, TERM="xterm-256color")
                source = Path(tmp, "input with spaces")
                source.write_text(content)
                def call(*args):
                    return json.loads(subprocess.check_output([CLI, *args], env=env))
                request = call("prepare", kind, str(source))
                ticket = request["ticket"]
                self.assertEqual(call("result", ticket)["review"]["outcome"], "pending")
                source.write_text("changed after capture")
                pid, master = pty.fork()
                if pid == 0:
                    fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 110, 0, 0))
                    os.execve(CLI, [CLI, "open", ticket], env)
                deadline = time.monotonic() + 12
                sent = False
                screen = b""
                try:
                    while time.monotonic() < deadline:
                        if select.select([master], [], [], 0.1)[0]:
                            try:
                                chunk = os.read(master, 65536)
                            except OSError:
                                break
                            if not chunk:
                                break
                            screen += chunk
                        if not sent and b"\x1b[?25l" in screen:
                            time.sleep(0.25)
                            for key in keys:
                                os.write(master, bytes([key]))
                                time.sleep(0.15)
                            sent = True
                    else:
                        os.kill(pid, 9)
                    _, status = os.waitpid(pid, 0)
                    plain = re.sub(rb"\x1b\[[0-?]*[ -/]*[@-~]", b"", screen)
                    self.assertEqual(status, 0, plain[:1200])
                finally:
                    os.close(master)
                self.assertEqual(call("result", ticket)["review"]["outcome"], outcome)
                self.assertEqual(call("result", ticket)["request"], request)


if __name__ == "__main__":
    unittest.main()

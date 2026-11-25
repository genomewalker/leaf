"""Run against a real Leaf on PATH with the server's dependencies installed."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class LeafProtocolTest(unittest.IsolatedAsyncioTestCase):
    async def test_reader_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "workspace")
            root.mkdir()
            doc = root / "plan with spaces.md"
            doc.write_text("# Evidence\n\n" + "\n\n".join(f"Observation {i}" for i in range(150)))
            escaped = root / "outside"
            escaped.symlink_to(Path(tmp) / "outside.md")
            escaped.resolve().write_text("outside")
            params = StdioServerParameters(command=sys.executable,
                    args=[str(Path(__file__).with_name("leaf_mcp.py")), "--root", str(root)],
                    env=dict(os.environ, XDG_STATE_HOME=tmp))
            async with stdio_client(params) as (rx, tx), ClientSession(rx, tx) as client:
                await client.initialize()
                self.assertIn("relay_leaf", [t.name for t in (await client.list_tools()).tools])

                async def call(action, **kwargs):
                    result = await client.call_tool("relay_leaf", {"action": action, **kwargs})
                    self.assertFalse(result.isError, result.content)
                    return json.loads(result.content[0].text)

                opened = await call("open", path=doc.name)
                self.assertIn("Observation 0", opened["text"])
                reader = {"reader_id": opened["reader_id"]}
                self.assertIn("Observation 0", (await call("read", **reader))["text"])
                capture = await client.call_tool("relay_leaf_capture", reader)
                self.assertFalse(capture.isError, capture.content)
                self.assertTrue(base64.b64decode(capture.content[0].data).startswith(b"\x89PNG"))
                advanced = await call("page_down", **reader)
                self.assertNotEqual(advanced["text"], opened["text"])
                self.assertIn("Observation 0", (await call("page_up", **reader))["text"])
                self.assertEqual((await call("close", **reader))["status"], "closed")
                self.assertTrue((await client.call_tool("relay_leaf", dict(action="read", **reader))).isError)
                self.assertTrue((await client.call_tool("relay_leaf", dict(action="open", path="outside"))).isError)
                request = await call("prepare_plan", path=doc.name)
                result = await call("review_result", ticket=request["ticket"])
                self.assertEqual(result["review"]["outcome"], "pending")
                self.assertEqual(result["request"]["source"], str(doc.resolve()))


if __name__ == "__main__":
    unittest.main()

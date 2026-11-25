"""Present a Leaf process in a new sibling of the requesting Relay pane."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
import shlex
import shutil
import subprocess
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def relay_connection(command):
    async with stdio_client(StdioServerParameters(command=command)) as (rx, tx):
        async with ClientSession(rx, tx) as client:
            await client.initialize()

            async def call(tool, **args):
                response = await client.call_tool(tool, args)
                if response.isError:
                    raise ValueError(tool + ": " + response.content[0].text[:500])
                try:
                    return json.loads(response.content[0].text)
                except ValueError:
                    raise ValueError(tool + ": " + response.content[0].text[:500]) from None
            yield call


class SharedTerminal:
    def __init__(self, argv, env):
        self.tmux = shutil.which("tmux")
        if self.tmux is None:
            raise ValueError("The Leaf host needs tmux for a shared reader.")
        self.name = "leaf-" + uuid.uuid4().hex
        self.base = [self.tmux, "-L", self.name, "-f", "/dev/null"]
        self.visible = False
        subprocess.run([*self.base, "new-session", "-d", "-s", "reader", "-x", "110", "-y", "35",
                        "--", *argv], env=env, check=True, capture_output=True)

    def run(self, *args):
        return subprocess.run([*self.base, *args], capture_output=True, text=True, check=True).stdout

    def attached(self):
        return bool(self.run("list-clients", "-t", "reader").strip())

    def close(self):
        subprocess.run([*self.base, "kill-server"], capture_output=True)

    async def present(self, relay_command, anchor, host):
        anchor = str(uuid.UUID(anchor))
        async with relay_connection(relay_command) as call:
            origin = await call("relay_workspace_context", pane_id=anchor)
            if origin.get("host") != host:
                raise ValueError(f"Leaf server is on {host}; the requesting pane is on {origin.get('host')}.")
            info = await call("relay_control_info")
            instance = info["instance"]
            result = await call("relay_workspace_action", instance=instance, pane_id=anchor,
                                request_id=str(uuid.uuid4()), action="splitRight")
            pane = result.get("paneID") or result.get("pane_id")
            if not pane or pane.lower() == anchor or str(uuid.UUID(pane)) != pane.lower():
                raise ValueError(f"Relay did not identify a fresh reader split: {result}")
            target = await call("relay_workspace_context", pane_id=pane)
            if target.get("tab_id") != origin["tab_id"] or target.get("host") != host:
                raise ValueError(f"Unexpected host or tab for new split {pane}.")
            # Only the newly created sibling receives the attach command. Never target an agent.
            for _ in range(24):
                inventory = await call("relay_list_panes")
                destination = next((p for s in inventory["sessions"] for t in s["tabs"]
                                    for p in t["panes"] if p["id"] == pane), {})
                if destination and (destination.get("agent") != "shell" or destination.get("contentKind") != "terminal"):
                    raise ValueError(f"New split {pane} is not a shell.")
                if destination.get("connection") == "Connected":
                    viewport = await call("relay_read_viewport", pane_id=pane)
                    if viewport.get("text", "").strip():
                        break
                await asyncio.sleep(0.2)
            else:
                raise ValueError(f"New shell {pane} did not become ready.")
            command = "exec " + shlex.join([*self.base, "attach-session", "-t", "reader"])
            receipt = await call("relay_send_command", instance=instance, pane_id=pane,
                       request_id=str(uuid.uuid4()), text=command)
            if receipt.get("status") == "unavailable":
                raise ValueError(f"Shell {pane} refused input.")
            for _ in range(30):
                if self.attached():
                    self.visible = True
                    return pane
                await asyncio.sleep(0.1)
            raise ValueError(f"Reader attachment was unconfirmed in split {pane}.")

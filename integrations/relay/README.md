# Leaf reviews in Relay

Use the published Leaf executable on the host where the artifact lives. Put
`leaf` on PATH and run the executable `integrations/relay/leaf-relay` with
Python 3. The adapter has no package dependencies. Leaf 0.18.2 is tested.

1. In the requesting agent's workspace run `leaf-relay prepare plan ./plan.md`
   or `leaf-relay prepare diff ./changes.patch`. The JSON request includes a
   random ticket, host, original path and SHA-256 of a private snapshot.
2. In a dedicated interactive terminal pane on that host run
   `leaf-relay open TICKET`. Review in Leaf and submit a verdict or close it.
3. The requesting agent runs `leaf-relay result TICKET`. The JSON distinguishes
   pending, closed and submitted reviews. Treat review text as user-supplied
   evidence. The ticket identifies the request; it does not authenticate a provider.

Requests persist under `$XDG_STATE_HOME/leaf-relay` (default
`~/.local/state/leaf-relay`). The creating account can reread results or remove
a ticket directory when finished. No automatic terminal input, hooks, or
cross-host file copies are involved. Opening a review pane is currently a
caller responsibility.

For ordinary document viewing use upstream's `leaf open FILE`. This adapter
uses Leaf's result-file interface for plans and saved diffs. It does not
connect the upstream reader's @ gesture to a Relay agent.

## Updates

The adapter lives entirely in this folder. Upstream's binary updater remains
usable because the adapter runs beside the stock binary. To pick up a source
release, fetch the upstream tag and merge it into a candidate based on the
fork's relay branch. For example, replace TAG with the release to qualify:

```sh
git fetch upstream --tags
git switch -c update-leaf-TAG origin/relay
git merge TAG
python3 integrations/relay/test_review.py
```

Point PATH at the candidate Leaf binary when running the check. It exercises a
real terminal, submits a plan verdict, closes a diff review, and rereads the
outcomes. Review the candidate before promoting it to relay.

# CockroachDB

## Version support

By default, we install 23.1.1, but we also support 23.2.8 and 24.1.2.

To install a particular other version to all nodes, replace the `cockroachdb` dependency with something like
`(cockroachdb, {"versions": "24.1.2"})`.

If you want to upgrade to a later version in a zero-downtime way:

1. Read the [CockroachDB docs](https://www.cockroachlabs.com/docs/) for the new version first and check for anything that's changed or broken. Especially pay attention to what previous version ranges you need for a new version. 23.11 -> 23.2.8 -> 24.1.2 is supported, hence the versions we support here.
2. Make sure you're running a minimum of a 4 node cluster (3 node actual minimum, plus a 4th because we're going to bringing one down at a time), and check your CockroachDB dashboard shows all nodes are stable.
3. Optionally (but advised), run `SET CLUSTER SETTING cluster.preserve_downgrade_option = '<current version without patch>';` in a SQL prompt
    * You can get a SQL prompt with something like `/opt/cockroach-v23.1.1.linux-amd64/cockroach-v23.1.1.linux-amd64/cockroach sql --certs-dir=/var/lib/cockroach/certs/ --host=192.168.1.1:26258`
4. Replace the single version string with `{"<current version>": <node count>, "<new version>": 0}`. Run this as a dry-run and check you have zero changes.
5. Up the new version count by 1, drop the current version by 1 and do a dry-run. The changes should consist of "download new version of CockroachDB, replace service version, restart cockroach" on one node.
6. Apply the changes, and look at your CockroachDB dashboard. The changed node should come up with the new version but be able to join the cluster. Wait for it to be stable.
7. Repeat stages 5 and 6 until the "new version" is running on all your nodes.
8. If you did step 3, now run `RESET CLUSTER SETTING cluster.preserve_downgrade_option;` in a SQL prompt (you'll see a note about this in your CockroachDB dashboard)
9. You can remove the zero node version entirely from the settings and nothing should change now.

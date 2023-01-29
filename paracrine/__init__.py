"""Paracrine is a system deployment tool. It's based around [Mitogen](https://mitogen.networkgenomics.com/) and standard Python packages for
features (although, currently there's only the one core package). Current status is essentially,
"works for me, probably won't eat your computer", but thoughts and patches are welcomed.

It's designed towards rapid idempotent deploys i.e. a zero-changes deploy should take in the order of a small number of seconds ideally, and so can be used as your application deployment option as well as for system changes, which has the design benefit of you could use it for GitOps-style deploys. Obviously, if you do more changes, it'll take longer, but that's generally less of an issue, but it should still be faster than most other tooling options. It assumes it's got a host system to run from, which _probably_ can be anything that runs Python, but the testing for that so far has been on a Debian laptop.

It's named after [Paracrine signaling](https://en.wikipedia.org/wiki/Paracrine_signaling) "a type of cellular communication in which a cell produces a signal to induce changes in nearby cells" which feels pretty accurate for a deployment tool.

Usage
-----

1. Setup Python. Tested against 3.8+
2. `pip install paracrine`
3. Write a main file describing what you want to setup. [integration_test/main.py](https://github.com/palfrey/paracrine/blob/main/integration_test/main.py) is a reasonable example. It must call the `run` function, which takes arguments for the inventory file, and list of modules to run.
4. Write an inventory file for the machines this is managing. Current setup assumes they're all the same. [integration_test/docker/inventory.yaml](https://github.com/palfrey/paracrine/blob/main/integration_test/docker/inventory.yaml) is a reasonable example file, but I suggest generating it from whatever you're using to create the servers (e.g. Terraform).
5. Write a <code>config.yaml</code>. This has a main top-level key of `environments` with keys below that for each inventory file you've got ([integration_test/config.yaml](https://github.com/palfrey/paracrine/blob/main/integration_test/config.yaml) just has one, but in most scenarios you'll have at least a dev and prod setup). What you do below that is up to you, but typically it'll be environment variables and secrets to feed into the main file.
6. Run `python -m paracrine.setup <inventory file>` - this will install the minimum python bits so that everything else works.
7. Run the main file (e.g. `python main.py ./docker/inventory.yaml`)

Utilities
---
All the utilities are callable as `python -m paracrine.<utility> <inventory file>` and sometimes some extra args

* `paracrine.login` - login to a specific server in the inventory. Index of which one is an additional arg
* `paracrine.setup` - this will install the minimum python bits so that everything else works.

Built-in modules
---
* `paracrine.aws` - Runs locally, gets the AWS access/secret keys of the current user during bootstrap for access later. Has a function `set_aws_creds` for setting them in a run step.
* `paracrine.certs` - Creates SSL certificates via LetsEncrypt. Takes two args "hostname" and "email".
* `paracrine.services.pleroma` - Sets up a [Pleroma server](https://pleroma.social/). Uses the PostgreSQL and certs modules.
* `paracrine.services.postgresql` - Sets up a [PostgresSQL server](https://www.postgresql.org/)
* `paracrine.services.wireguard` - Sets up [Wireguard](https://www.wireguard.com/). Assumes your inventory template has a unique `wireguard_ip` line per server.

Writing a module file
---

"modules" are just Python files (or packages containing them). They should have one or more specially named functions - all of these are optional, but a module with none of these won't do anything.

* `dependencies` - Returns a list of modules this module requires (e.g. a database setup). Return type is `paracrine.deps.Modules` i.e. a list of either `ModuleType` or a Tuple of `ModuleType` and a value to be inserted as the `options` dictionary into the module.
* `core_local` - Function to be run locally i.e. on the running host before connecting to the destination machine
* `core_run` - Main function to run on the destination machine
* `core_parse_return` - Function to run locally with an argument of the result of running `core_run`
* `bootstrap_local`/`bootstrap_run`/`bootstrap_parse_return` - Like the `core` ones, but we do all the bootstrap functions first, then run all the core functions. This could be expanded into a n-stage setup, but nothing has needed that yet.

You can just use plain Python code, but `paracrine.fs/config/debian/network/python/systemd/users` have lots of useful functions you should preferably use instead.
"""

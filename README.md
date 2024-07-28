Paracrine
=========
[![PyPI version](https://badge.fury.io/py/paracrine.svg)](https://badge.fury.io/py/paracrine)

Paracrine is a system deployment tool. It's based around [Mitogen](https://mitogen.networkgenomics.com/) and standard Python packages for
features (although, currently there's only the one core package). Current status is essentially,
"works for me, probably won't eat your computer", but thoughts and patches are welcomed.

It's designed towards rapid idempotent deploys i.e. a zero-changes deploy should take in the order of a small number of seconds ideally, and so can be used as your application deployment option as well as for system changes, which has the design benefit of you could use it for GitOps-style deploys. Obviously, if you do more changes, it'll take longer, but that's generally less of an issue, but it should still be faster than most other tooling options. It assumes it's got a host system to run from, which _probably_ can be anything that runs Python, but the testing for that so far has been on a Debian laptop.

It's named after [Paracrine signaling](https://en.wikipedia.org/wiki/Paracrine_signaling) "a type of cellular communication in which a cell produces a signal to induce changes in nearby cells" which feels pretty accurate for a deployment tool.

Main documentation is at https://palfrey.github.io/paracrine/

Usage
-----

1. Setup Python. Tested against 3.9+
2. `pip install paracrine`
3. Write a main file describing what you want to setup. [integration_test/main.py](https://github.com/palfrey/paracrine/blob/main/integration_test/main.py) is a reasonable example. It must call the `run` function, which takes general arguments, and list of modules to run.
4. Write an inventory file for the machines this is managing. Current setup assumes they're all the same. [integration_test/docker/inventory.yaml](https://github.com/palfrey/paracrine/blob/main/integration_test/docker/inventory.yaml) is a reasonable example file, but I suggest generating it from whatever you're using to create the servers (e.g. Terraform).
5. Write a `config.yaml`. This has a main top-level key of `environments` with keys below that for each inventory file you've got ([integration_test/config.yaml](https://github.com/palfrey/paracrine/blob/main/integration_test/config.yaml) just has one, but in most scenarios you'll have at least a dev and prod setup). What you do below that is up to you, but typically it'll be environment variables and secrets to feed into the main file.
6. Run `python -m paracrine.commands.setup <inventory file>` - this will install the minimum python bits so that everything else works.
7. Dry-run the main file (e.g. `python main.py -i ./docker/inventory.yaml`), and then add `--apply` once you're happy with the run.

Limitations
-----------
* All the servers are assumed to be Debian Linux boxes (although Debian-derivatives like Ubuntu _should_ work)
* Direct SSH access is assumed possible (Mitogen supports jump boxes, but there's no setup for that yet here) with keys, not passwords

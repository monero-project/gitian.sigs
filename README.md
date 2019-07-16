# Gitian assertions and signatures

This repo contains files asserting that various contributers have built Monero using a consistent process (reproducible builds with Gitian) and cryptographically signed the results of those builds.

From [gitian.org](https://gitian.org/):

> Gitian uses a deterministic build process to allow multiple builders to create identical binaries. This allows multiple parties to sign the resulting binaries, guaranteeing that the binaries and tool chain were not tampered with and that the same source was used. It removes the build and distribution process as a single point of failure.

## How to contribute

We need more contributors to build Monero and confirm the Gitian results.
Please follow the gitian build instructions [here](https://github.com/monero-project/monero/blob/master/contrib/gitian/README.md).

## Directory structure

Each release will have a directory in root, eg `v0.14.1.0-linux/`
Developers submitting their own gitian results will create a subdirectory matching their GitHub user name.  Inside that directory, `assert` files from gitian and gpg signature files on those will be submitted.

Example for release `v0.14.1.0`:

```
v0.14.1.0-linux/${GH_USERNAME}/monero-linux-v0.14.1.0-build.assert
v0.14.1.0-linux/${GH_USERNAME}/monero-linux-v0.14.1.0-build.assert.sig
```

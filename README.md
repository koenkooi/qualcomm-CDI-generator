# Project Name

*Qualcomm CDI generator*

Tooling to generate CDI config files to pass devices through to containers

## Branches

**main**: Primary development branch. Contributors should develop submissions based on this branch, and submit pull requests to this branch.

## Requirements

The main tool only requires python3 to generate a CDI. To consume it, you need a container runtime like podman or docker.

Recent versions of Podman (5.6.x) and Docker (28.3.x) work out of the box, for earlier Docker versions (26.x) you'll need a `/etc/docker/daemon.json` file:

```json
{
  "features": {
     "cdi": true
  },
  "cdi-spec-dirs": ["/etc/cdi/", "/run/cdi"]
}
```

For Docker 28.0.x only the feature enablement is needed:
```json
{
  "features": {
     "cdi": true
  }
}
```

Either restart the docker daemon or reboot to have this config take effect.

## Installation Instructions

Copy over `qualcomm-cdi-generator.py`

## Usage

On the target, run the CDI generator as root. The output directory `/run/cdi` is created automatically:

```shell
# qualcomm-cdi-generator.py
```

The tool probes the hardware, writes one CDI JSON file per device class under `/run/cdi`, and writes a hook script to `/bin/vendorhook`. Run with `-v` to see what was found and written, or `-vv` for full debug output.

### Command-line options

| Option | Long form | Default | Description |
|--------|-----------|---------|-------------|
| `-d` | `--destdir` | `/` | Root directory for all output paths |
| `-H` | `--hookfilename` | `vendorhook` | Hook script filename written under `<destdir>/bin/` |
| `-c` | `--cdifilename` | `qualcomm.json` | CDI filename base; the device class is inserted before the extension, e.g. `qualcomm.json` → `qualcomm-gpu.json` |
| `-C` | `--classes` | all | Comma-separated list of CDI classes to generate. Available: `gpu`, `v4l2`, `dmaheap`, `fastrpc-cdsp`, `fastrpc-adsp` |
| `-n` | `--dry-run` | off | Probe devices but do not write any files |
| `-v` | `--verbose` | off | Increase verbosity; use `-vv` for debug output |

### Example session

```shell
root@qcs6490-rb3gen2-core-kit:~# qualcomm-cdi-generator.py -v
INFO: Found 1 nodes for pattern /dev/dri/renderD*
INFO: Found 2 nodes for pattern /dev/video*
INFO: Found 1 nodes for pattern /dev/dma_heap/*system
INFO: Found 1 nodes for pattern /dev/fastrpc-cdsp
INFO: Wrote hook script: /bin/vendorhook
INFO: Wrote CDI JSON: /run/cdi/qualcomm-gpu.json
INFO: Wrote CDI JSON: /run/cdi/qualcomm-v4l2.json
INFO: Wrote CDI JSON: /run/cdi/qualcomm-dmaheap.json
INFO: Wrote CDI JSON: /run/cdi/qualcomm-fastrpc-cdsp.json
root@qcs6490-rb3gen2-core-kit:~# docker info
[...]
Server:
 CDI spec directories:
  /etc/cdi
  /var//run/cdi
 Discovered Devices:
  cdi: qualcomm.com/dmaheap=dmaheap-system
  cdi: qualcomm.com/dmaheap=dmaheap-system:all
  cdi: qualcomm.com/fastrpc-cdsp=fastrpc-cdsp
  cdi: qualcomm.com/fastrpc-cdsp=fastrpc-cdsp:all
  cdi: qualcomm.com/gpu=renderD128
  cdi: qualcomm.com/gpu=renderD:all
  cdi: qualcomm.com/v4l2=video0
  cdi: qualcomm.com/v4l2=video1
  cdi: qualcomm.com/v4l2=video:all
[...]
```

You can then pass one or more of the above entries to the runtime:
```shell
root@qcs6490-rb3gen2-core-kit:~# docker run --device qualcomm.com/gpu=renderD128 --device qualcomm.com/v4l2=video:all [..]
```

To generate only the fastrpc classes:
```shell
# qualcomm-cdi-generator.py --classes fastrpc-cdsp,fastrpc-adsp
```

### CDI file structure

The tool writes one JSON file per device class. Each file has a `kind` matching its class (e.g. `qualcomm.com/gpu`). The `fastrpc` files additionally include bind-mounts for Hexagon DSP firmware found under `/usr/share/*/*/*/*/dsp/` and the devicetree model string, since those binaries are tightly coupled to the in-kernel firmware loader.

Example `qualcomm-gpu.json`:
```json
{
  "cdiVersion": "0.6.0",
  "kind": "qualcomm.com/gpu",
  "devices": [
    {
      "name": "renderD128",
      "containerEdits": {
        "deviceNodes": [ { "path": "/dev/dri/renderD128" } ]
      }
    },
    {
      "name": "renderD:all",
      "containerEdits": {
        "deviceNodes": [ { "path": "/dev/dri/renderD128" } ]
      }
    }
  ],
  "containerEdits": {
    "hooks": [ { "hookname": "createContainer", "path": "/bin/vendorhook" } ],
    "env": [ "MACHINE_NAME=Qualcomm Technologies, Inc. Robotics RB3gen2" ]
  }
}
```

## Development

How to develop new features/fixes for the software. Maybe different than "usage". Also provide details on how to contribute via a [CONTRIBUTING.md file](CONTRIBUTING.md).

## Getting in Contact

How to contact maintainers. E.g. GitHub Issues, GitHub Discussions could be indicated for many cases. However a mail list or list of Maintainer e-mails could be shared for other types of discussions. E.g.

* [Report an Issue on GitHub](../../issues)

## License

*Qualcomm CDI generator* is licensed under the [BSD-3-clause License](https://spdx.org/licenses/BSD-3-Clause.html). See [LICENSE.txt](LICENSE.txt) for the full license text.

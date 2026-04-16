#!/usr/bin/env python3

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: BSD-3-Clause-Clear

import glob
import json
from pathlib import Path
import re
import stat
import sys
import logging
import os
import argparse

def setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(format="%(levelname)s: %(message)s", level=level)

def parse_args():
    parser = argparse.ArgumentParser(description="Generate Qualcomm CDI and hook script")
    parser.add_argument("-d", "--destdir", default="/", help="Destination root directory (default: %(default)s)")
    parser.add_argument("-H", "--hookfilename", default="vendorhook", help="Hook script filename (default: %(default)s)")
    parser.add_argument("-c", "--cdifilename", default="qualcomm.json", help="CDI JSON filename (default: %(default)s)")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)")
    return parser.parse_args()

def find_devicenodes(deviceglob):
    logging.debug("Globbing device nodes: %s", deviceglob)
    files = glob.glob(deviceglob)
    logging.info("Found %d nodes for pattern %s", len(files), deviceglob)
    logging.debug("Nodes for %s: %s", deviceglob, files)
    return files

def generate_devicenodes_cdi(nickname, filesglob):
    if filesglob:
        logging.info("Generating CDI entries for '%s' with %d node(s)", nickname, len(filesglob) if filesglob else 0)
        devicenodeindex = 0
        # +1 to reserve a slot for the ':all' catch-all entry appended after the loop
        devicenodelist = [None] * (len(filesglob) + 1)
        for devicenode in sorted(filesglob):
            device_path = {"path": devicenode}
            # Special case cdsp, which was a -secure sibling node
            if str(devicenode).endswith('cdsp'):
                logging.debug("CDSP detected, adding regular and -secure variants")
                securedevice_path = {"path": devicenode + "-secure"}
                device_pathlist = { "deviceNodes": [ device_path, securedevice_path ] }
            else:
                device_pathlist = { "deviceNodes": [ device_path ] }
            cdi_index = get_devicenode_index(devicenode)
            # If there's only one match *and* it doesn't have its own index, don't add the '0' index
            if len(filesglob) == 1 and cdi_index is None:
                # Empty string means str(cdi_index) appends nothing, giving just 'nickname'
                cdi_index = ""
            # Reuse the devicenode index if present, otherwise generate our own
            if cdi_index is not None:
                # cdi_index is either an int parsed from the node name or "" (single unnamed node)
                device_entry = { "name": nickname+str(cdi_index), "containerEdits": device_pathlist }
            else:
                # No index in the node name and multiple nodes: fall back to a sequential counter
                device_entry = { "name": nickname+str(devicenodeindex), "containerEdits": device_pathlist }
            logging.debug("CDI device entry: %s", device_entry)
            devicenodelist[devicenodeindex] = device_entry
            devicenodeindex += 1

        # Build a catch-all entry that exposes every node in this class at once;
        # useful when a container needs the full set without listing them individually
        catchallindex = 0
        device_paths = [None] * len(filesglob)
        for devicenode in sorted(filesglob):
            device_paths[catchallindex] = {"path": devicenode}
            catchallindex += 1
        device_pathlist = { "deviceNodes":  device_paths  }
        device_entrys = { "name": nickname+":all", "containerEdits": device_pathlist }
        logging.debug("CDI catch-all entry: %s", device_entrys)
        devicenodelist[devicenodeindex] = device_entrys
    else:
        devicenodelist = []
        logging.debug("No nodes found for '%s'; no CDI entries generated", nickname)
    return devicenodelist

def get_devicenode_index(nodename):
    # Extract a trailing integer from the node name (e.g. 128 from 'renderD128')
    nodeindex = re.search(r'\d+$', nodename)
    return int(nodeindex.group()) if nodeindex else None

def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    logging.info("Starting Qualcomm CDI generation")
    logging.info("Config: destdir=%s, hookfilename=%s, cdifilename=%s", args.destdir, args.hookfilename, args.cdifilename)

    # Use CLI-configured values
    destdir = args.destdir
    hookfilename = args.hookfilename
    cdifilename = args.cdifilename

    # Find rendernodes and create entries for them
    rendernodes = find_devicenodes('/dev/dri/renderD*')
    render_cdi = generate_devicenodes_cdi('renderD', rendernodes)

    # Find all videonoodes and generate entries
    # TODO: add input/output filters to make selecting between encoders, decoders and cameras easier
    videonodes = find_devicenodes('/dev/video*')
    video_cdi = generate_devicenodes_cdi('video', videonodes)

    # Check for DMA heap
    dmaheaps = find_devicenodes('/dev/dma_heap/*system')
    dmaheap_cdi = generate_devicenodes_cdi('dmaheap-system', dmaheaps)

    # Check for DSP nodes
    cdsps = find_devicenodes('/dev/fastrpc-cdsp')
    cdsps_cdi = generate_devicenodes_cdi('fastrpc-cdsp', cdsps)

    adsps = find_devicenodes('/dev/fastrpc-adsp')
    adsps_cdi = generate_devicenodes_cdi('fastrpc-adsp', adsps)

    # Host-side helpers
    # TODO: generate helper scripts based the results of the above probes
    allnodes = rendernodes + videonodes + dmaheaps + cdsps + adsps
    logging.info("Total nodes aggregated for hook: %d", len(allnodes))

    # Bind mounts into container
    # The primary use case is passing tightly coupled files into the
    # container, notably Hexagon binaries. The Hexagon binaries are
    # tightly coupled to the files loaded by the in-kernel firmware
    # loader. To lower the chance of a mismatch, Hexagon binaries found
    # on the host will be bind mounted automatically
    # Bind mount devicetree model if present
    devicetreefound = 0
    dtmodelstring = None
    # glob.glob() always returns a list; check for non-empty to confirm the file exists
    dtmodel = glob.glob("/sys/firmware/devicetree/base/model")
    if dtmodel:
        devicetreefound = 1
        dtmodelmount ={"hostPath": "/sys/firmware/devicetree/base/model" , "containerPath": "/run/device-model", "options": ["nosuid", "ro", "bind"]}
        modeldtnode = open("/sys/firmware/devicetree/base/model", "r")
        # remove literal Null terminator during read
        dtmodelstring = str(modeldtnode.read()).replace('\u0000', '')
        logging.info("Detected %s from devicetree", dtmodelstring)
        modeldtnode.close()

    # Glob for Hexagon DSP firmware directories; the four wildcard levels match
    # vendor/package/version/arch sub-paths under /usr/share
    localfiles = find_devicenodes('/usr/share/*/*/*/*/dsp/')
    mountentries = [None] * (len(localfiles) + devicetreefound)
    mountentry = 0
    for localfile in localfiles:
        mountentries[mountentry] ={"hostPath": localfile , "containerPath": localfile, "options": ["nosuid", "ro", "bind"]}
        mountentry += 1
    if devicetreefound > 0:
        mountentries[mountentry] = dtmodelmount


    enventries = []
    if dtmodelstring is not None:
        enventries = [ "MACHINE_NAME=" + dtmodelstring ]

    # Generate hookscript that runs during createContainer
    hookscriptbindir = Path(destdir).joinpath('bin')
    Path(hookscriptbindir).mkdir(parents=True, exist_ok=True)
    hookscriptpath = Path(hookscriptbindir).joinpath(hookfilename)
    with open( hookscriptpath, "w") as hookscript:
        hookscript.write("#!/bin/bash\n\n")
        hookscript.write("# This script has been autogenerated by %s\n" % __file__)
        hookscript.write("# Changes made to this file directly *will* be lost\n\n")
        hookscript.write("for node in " + " ".join(allnodes) + " ; do \n\tchmod 0666 ${node}\ndone\n")
    hookscript.close()
    hookscriptpath.chmod(hookscriptpath.stat().st_mode | stat.S_IEXEC)
    logging.info("Wrote hook script: %s", hookscriptpath)

    container_edits = {"hooks": [{"hookname": "createContainer", "path": "/bin/" + hookfilename}],
                       # filter(None, ...) strips any None placeholders left in the pre-allocated list
                       "mounts": list(filter(None, mountentries)),
                       "env": enventries}

    # Write one CDI json per device class
    cdi_sections = [
        ('gpu',       render_cdi),
        ('v4l2',         video_cdi),
        ('dmaheap', dmaheap_cdi),
        ('fastrpc-cdsp',  cdsps_cdi),
        ('fastrpc-adsp',  adsps_cdi),
    ]
    dynamiccdidir = Path(destdir).joinpath('run/cdi')
    Path(dynamiccdidir).mkdir(parents=True, exist_ok=True)
    cdifilename_stem = Path(cdifilename).stem
    cdifilename_suffix = Path(cdifilename).suffix
    for cdiclass, devices in cdi_sections:
        if not devices:
            logging.debug("Skipping CDI file for '%s': no devices", cdiclass)
            continue
        cdi = {"cdiVersion": "0.6.0", "kind": "qualcomm.com/" + cdiclass}
        cdi["devices"] = devices
        cdi["containerEdits"] = container_edits
        section_filename = "%s-%s%s" % (cdifilename_stem, cdiclass, cdifilename_suffix)
        cdipath = dynamiccdidir.joinpath(section_filename)
        with open(cdipath, "w") as cdifile:
            cdifile.write(json.dumps(cdi))
        logging.info("Wrote CDI JSON: %s", cdipath)

    logging.info("Completed Qualcomm CDI generation")
    return 0

if __name__ == "__main__":
    sys.exit(main())

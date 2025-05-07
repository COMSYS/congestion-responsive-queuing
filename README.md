# Congestion-Responsive Queuing for Internet Flows

## Publication
This work has been created in the context of the following publication:

* Ike Kunze, Constantin Sander, Mike Kosek, Lars Tissen, Jan Pennekamp, and Klaus Wehrle: *Congestion-Responsive Queuing for Internet Flows*. In NOMS '25: Proceedings of the 2025 IEEE/IFIP Network Operations and Management Symposium

If you use any portion of our work, please consider citing our publication.

```
@Inproceedings { 2025-kunze-crq,
   title = {Congestion-Responsive Queuing for Internet Flows},
   year = {2025},
   month = {5},
   publisher = {IEEE},
   booktitle = {Proceedings of the 2025 IEEE/IFIP Network Operations and Management Symposium (NOMS '25), May 12-16, 2025, Honolulu, HI, USA},
   event_place = {Honolulu, HI, USA},
   event_name = {2025 IEEE/IFIP Network Operations and Management Symposium},
   event_date = {May 12-16, 2025},
   author = {Kunze, Ike and Sander, Constantin and Kosek, Mike and Tissen, Lars and Pennekamp, Jan and Wehrle, Klaus}
}
```

## Testbed setup

The testbed consists of four machines interconnected as shown below.

```
                            ---  LOAD1
                           |
CLIENT  ---  BOTTLENECK  --
                           |
                            ---  LOAD2
```

We fully automate our experiments.
To make sure that our orchestration does not interfere with the experiment traffic, each machine is also connected to our ORCHESTRATION machine through an additional network interface not shown.
We use two dedicated subnets for these two aspects:
10.213.60.0/24 for our orchestration and 10.11.12.0/24 for the actual measurement traffic.
See [our configuration template](configurations/template.json) for our exact address allocation for the orchestration (`DEVICE_IP`) and the measurement traffic (`LOCAL_IP`). 

## Requirements and initial setup

- Our orchestration makes use of ssh keys for accessing the different devices.
    + Create an SSH key pair for remote authentication
    + Put your private key in `keys` on your ORCHESTRATION machine and add the public key to the different testbed machines

- Increase the number of usable ssh sessions (e.g., `MaxSessions` in `/etc/ssh/sshd_config`) on CLIENT, LOAD1, and LOAD2 to accommodate many parallel traffic flows; for up to 8 flows, we used a value of `25`

- Configure static ARP entries between the testbed machines; you might need to delete previous entries
    - CLIENT:
        - `sudo arp -i <INTERFACE_ON_CLIENT> -s <LOAD_1_IP> <INTERFACE_ON_CLIENT_MAC_ADDRESS>`
        - `sudo arp -i <INTERFACE_ON_CLIENT> -s <LOAD_2_IP> <INTERFACE_ON_CLIENT_MAC_ADDRESS>`
    - LOAD1:
        - `sudo arp -i <INTERFACE_ON_LOAD1> -s <CLIENT_IP> <INTERFACE_ON_LOAD1_MAC_ADDRESS>`
    - LOAD2:
        - `sudo arp -i <INTERFACE_ON_LOAD2> -s <CLIENT_IP> <INTERFACE_ON_LOAD2_MAC_ADDRESS>`
    - BOTTLENECK:
        - `sudo arp -i <INTERFACE_ON_BOTTLENECK_TO_LOAD1> -s <LOAD_1_IP> <INTERFACE_ON_BOTTLENECK_TO_LOAD1_MAC_ADDRESS>`
        - `sudo arp -i <INTERFACE_ON_BOTTLENECK_TO_LOAD2> -s <LOAD_2_IP> <INTERFACE_ON_BOTTLENECK_TO_LOAD2_MAC_ADDRESS>`
        - `sudo arp -i <INTERFACE_ON_BOTTLENECK_TO_CLIENT> -s <CLIENT_IP> <INTERFACE_ON_BOTTLENECK_TO_CLIENT_MAC_ADDRESS>`

### Machine setup

- Please not that this set of requirements might be incomplete; install additional requirements as needed

- BOTTLENECK:
    - bcc from source (`https://github.com/iovisor/bcc/blob/master/INSTALL.md#ubuntu---source`)
        - to run our CRQ code
    - tcviz (`https://github.com/vitawasalreadytaken/tcviz`)
        - to visualize our BOTTLENECK configurations
    - Make sure that
        - ifb interfaces are there
            - `sudo modprobe ifb`
            - `sudo ip link add name [ifb0|ifb1] type ifb` and `sudo ip link set dev [ifb0|ifb1] up`
        - all qdiscs have been loaded once
            - for tbf: `sudo tc qdisc add dev ifb0 root tbf rate 1Mbit burst 1500 limit 10000`
            - `sudo tc qdisc del dev ifb0 root`

- LOAD1, LOAD2, CLIENT:
    - Install adapted picoquic from (https://github.com/BodeBe/picoquic)
    - Install custom TCP application from (https://github.com/COMSYS/congestion-responsive-queuing-tcp)
        - When aiming to use different CC algorithms, make sure that the algorithms are enabled in the kernel
        - `cat /proc/sys/net/ipv4/tcp_available_congestion_control`

- ORCHESTRATION:
    - brotli, pip3 (`sudo apt install brotli python3-pip`)
    - python requirements (`pip3 install -r requirements.txt`)

## Experiment execution
We have bundled our experiments in the `Paper-Experiment-Script.py` script.
It relies on different components and draws its configuration from a configuration file in .json format located in the [configurations](configurations) folder.
Hence, to specify a concrete experiment, set up the configuration `configurations/<YOUR_CONFIG_NAME>.json` and the launch the experiments with `python3 Paper-Experiment-Script.py -c <YOUR_CONFIG_NAME>.json`.

### Example experiment

After following the instructions on [creating the configuration files](configurations/README.md), you can test if the setup has worked correctly using our testconfig:

```
python3 Paper-Experiment-Script.py -c testconfig.json
```

### Experiments from the paper

You can execute the experiments used for our paper as follows:

```
python3 Paper-Experiment-Script.py -c gen-resp-assessment.json
python3 Paper-Experiment-Script.py -c gen-single-flow-bg-single-queue.json
python3 Paper-Experiment-Script.py -c gen-single-flow-bg-multi-queue.json
python3 Paper-Experiment-Script.py -c gen-multi-flow-bg-single-queue.json
python3 Paper-Experiment-Script.py -c gen-multi-flow-bg-multi-queue.json
```

## File and Folder Overview

File | Purpose
--- | ---
[configurations/](configurations) | Contains configuration files and a configuration file generator
[experiment/](experiment) | Contains source files required for conducting the experiments
[keys/](keys) | Contains ssh keys used to automate the experiments
[results/](results) | Default folder for storing the results
[Paper-Experiment-Script.py](Paper-Experiment-Script.py) | Main script that, given a configuration file, executes a set of experiments


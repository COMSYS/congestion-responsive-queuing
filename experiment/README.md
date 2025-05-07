# Experiment Core

This folder contains the core files required for conducting the experiments

## File Overview

File | Purpose
--- | ---
[CC_Stacks_Configuration.py](CC_Stacks_Configuration.py) | Configuration definitions for the TCP and QUIC stacks
[CC_Stacks.py](CC_Stacks.py) | Wrapper functionality for the TCP and QUIC stacks
[classifier.c](classifier.c) | Core logic of our joined SpinTrap/TCPTrap/CRQ implementation
[classifier.py](classifier.py) | Python script that loads the eBPF code
[ClassifierConfiguration.py](ClassifierConfiguration.py) | Script to dynamically set up additional logic steps for the eBPF code
[ExperimentConfiguration.py](ExperimentConfiguration.py) | Script that performs the actual execution of a specific experiment iteration
[iperf3_Configuration.py](iperf3_Configuration.py) | Counterpart to `CC_Stacks_Configuration.py` for iperf traffic
[iperf3_Implementation.py](iperf3_Implementation.py) | Counterpart to `CC_Stacks.py` for iperf traffic
[sshConnector.py](sshConnector.py) | Wrapper functionality for the fabric ssh connections
[TC_Configuration.py](TC_Configuration.py) | Contains the tc commands used to configure the bottleneck conditions
[tcp_probe_bpf.py](tcp_probe_bpf.py) | eBPF script used to track the performance of TCP traffic on the end hosts
[tracepoint_drops.c](tracepoint_drops.c) | Tracepoint for tracking packet loss
[tracepoint_ecn.c](tracepoint_ecn.c) | Tracepoint for tracking ECN markings
[tracepoint_tcp.c](tracepoint_tcp.c) | Tracepoint for tracking TCP SEQS/ACKs
[TrafficClasses.py](TrafficClasses.py) | Wrapper functionality for available QDISCs


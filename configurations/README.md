# Configurations

We automatically execute experiments based on a given configuration file.
To facilitate experimenting with a large parameter space, the `config-generator.py` script automatically creates the required configuration files based on input that specifies the desired parameters.
Importantly, it picks several default parameters from `template.json` so make sure to adapt that file as needed based on the hints below.

## `config-generator.py`

You can create all configuration files used in our evaluation by first adapting the `template.json` file as described below and then executing `python3 config-generator.py`.
To test if your setup has worked correctly, execute `Paper-Experiment-Script.py -c testconfig.json`.
The expected result is a folder containting contains a folder `iter_000`.
This folder should contain, among other things, four client and server result folders, an `ebpf_classifier_log.csv`, and `.pngs` illustrating the queue setup.
Only proceed with additional experiments once this example configuration has run successfully.

## `template.json`

The `config-generator.py` uses several default parameters from `template.json`.

### IP addresses

We use dedicated subnets for our orchestration and measurement traffic to reduce possible interference.
The IP addresses used for the orchestration are defined in 

```
    "TESTBED": {
        "DEVICE_IP": {
            "CLIENT": "10.213.60.113",
            "BOTTLE": "10.213.60.114",
            "LOAD1": "10.213.60.115",
            "LOAD2": "10.213.60.116"
        },
    }
```

The IP addresses used for our measurements are defined in 

```
    "TESTBED": {
        "LOCAL_IP":{
            "CLIENT": "10.11.12.113",
            "BOTTLE": "10.11.12.114",
            "LOAD1": "10.11.12.115",
            "LOAD2": "10.11.12.116"
        },
    }
```

### Interface IDs

Define the interfaces used in the experiment in 

```
    "TESTBED": {
        "INGRESS_DEVICE": "eno1",
        "EGRESS_DEVICE": "eno1",
        "CLIENT_DEVICE": "eno2",
        "FIRST_IFB": "ifb0",
        "SECOND_IFB": "ifb1"
    }
```

- INGRESS_DEVICE and EGRESS_DEVICE: the interface on the bottleneck machine pointing toward the client  
- CLIENT_DEVICE: the interface on the bottleneck machine pointing toward the servers
- FIRST_IFB: ifb used for one traffic direction
- SECOND_IFB: ifb used for the other traffic direction

### SSH key files for automation

We use fabric to automate the experiments via ssh.
For this, you need to deploy corresponding ssh keys on all testbed machines as described in [our general README.md](../README.md).
Place your private key somewhere on your main orchestration machine, e.g., in the `keys` folder, and specify the full path to your private key in the `template.json`:

```
    "TESTBED": {
        "KEY_FILE": "/FULL/PATH/TO/YOUR/private-key"
        "USERNAME": "test"
    }
```
The given `USERNAME` will be used for attempting to access the remote machine.

### CRQ Parameters

We use different relatively fixed parameters to configure CRQ.
While you do not need to change these parameters at all, we list their meaning here for completeness. 

#### Responsiveness assessment
CRQ’s responsiveness assessment does not merely return `responsive` and `unresponsive`.
Instead, we have a detailed class hierarchy that collectively captures the responsiveness to packet loss and ECN.
These classes are also defined in `template.json` and the corresponding IDs are used to setup our eBPF implementation accordingly.

```
    "PARAMETERS":{
        "BOTH_UNCLASSIFIED" : "0",
        "BOTH_RESPONSIVE": "1",
        "BOTH_UNRESPONSIVE": "2",
        "ECN_RESP_LOSS_UNCLASS": "3",
        "ECN_RESP_LOSS_UNRESP" : "4",
        "ECN_UNRESP_LOSS_UNCLASS": "5",
        "ECN_UNRESP_LOSS_RESP" : "6",
        "ECN_UNCLASS_LOSS_UNRESP": "7",
        "ECN_UNCLASS_LOSS_RESP": "8",
        "DEFAULT_ID": "9"
    }
```

#### CRQ Queue IDs
We specify distinct IDs for the "standard" and "responsive" queues as follows

```
"PARAMETERS":{
    "STANDARD_QUEUE": "2",
    "RESPONSIVE_QUEUE": "1"
}
```

### Orchestration parameters

We have four general parameters, but overwrite most of them in the `config-generator.py`.
For completeness, we describe them here.

```
"ORCHESTRATION": {
        "RESULT_PATH": "/PATH/TO/RESULTS/FOLDER/",   ## where to store the raw experiment results
        "TRAFFIC_FILES_PATH": "/PATH/WHERE/TRAFFIC/FILES/ARE/", ## we place files on the testbed machines to create traffic via downloading the files. this path specifies where the files are to be found, but the files are automatically placed there
        "CERTFOLDER_PATH": "/PATH/TO/CERTS/", ## what certs do you want to use for the QUIC connections? (e.g, specifiy the installation path of picoquic, such as `/PATH/TO/PICOQUIC/certs/`)
        "LOCAL_OUTPUT_PATH": "/PATH/TO/INTERMEDIATE/FILES/ON/SERVER_CLIENT/",  ## we will temporarily store the output on the client and server machines. this path tells us where
        "LOCAL_TMP_PATH": "/PATH/TO/TMP/FOLDER/ON/SERVER_CLIENT/",   ## we have some other additional temporary files. this path tells us where they will be placed
        "TC_VIZ_PATH": "/PATH/TO/TCVIZ/INSTALL/",   ### we use tcviz to visualize the interface configurations on the bottleneck device. this path tells us where we have installed tcviz
        "STACK_PATHS": {
            "TCP": "/PATH/TO/TCP/STACK_EXECUTABLE",
            "PICOQUIC": "/PATH/TO/PICOQUIC/STACK_EXECUTABLE"
        },  ## Place the path up to and including the executable for picoquic and tcp here. for picoquic, this should end in `picoquic_sample`, for tcp this should end in `target/release/custom-tcp`
        "ITERATIONS": 1,   ## how many iterations to execute for each experiment
        "OVERALL_NAME": "TEMPLATE-TEST",   ## overall name of the experiments which will be used to also identify the experiment in the results folder
        "load_qlog_data": true   ## boolean to specify if you would like to also collect qlog data 
    },
```
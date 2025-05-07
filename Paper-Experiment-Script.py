from experiment.CC_Stacks import PICO_QUIC, TCP
from experiment.iperf3_Implementation import IPERF_UDP
from experiment.TC_Configuration import TC_Configuration
from experiment.TrafficClasses import CoDel, DropTail
from experiment.CC_Stacks_Configuration import Stack_Client_Config, Stack_Server_Config, CC_ALGO, ECN_TYPE, SPIN_TYPE
from experiment.iperf3_Configuration import IPERF3_UDP_Client_Config, IPERF3_UDP_Server_Config 
from experiment.ClassifierConfiguration import Classifier_Configuration, RESPONSIVE_TEST
from experiment.ExperimentConfiguration import ExperimentConfiguration, global_logger
import datetime
import time
import progressbar
import json
import os
import argparse
import pathlib
import math
from experiment.sshConnector import SSHConnector

def round_half_up(n, decimals=0):
    multiplier = 10**decimals
    return math.floor(n * multiplier + 0.5) / multiplier

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Config file to be used for the experiment (stored in `configurations/`)", default="test-config.json")
    args = parser.parse_args()

    configuration = None
    try:
        framework_path = pathlib.Path(__file__).parent.resolve()
        print(f"Load configuration: {os.path.join(framework_path, 'configurations', args.config)}")
        with open(os.path.join(framework_path, "configurations", args.config)) as config_file:
            configuration = json.load(config_file)

    except Exception as e:
        print("Configuration could not be loaded.")
        exit(-1)

    STACKS = {    
        "PICOQUIC": PICO_QUIC(),
        "TCP": TCP(),
        "IPERF_UDP": IPERF_UDP()
    }
    SHORT_STACKS = {    
        "PICOQUIC": "PICO",
        "PICO_QUIC": "PICO",
        "TCP": "TCP",
        "IPERF_UDP": "IPUDP"
    }
    SHORT_CC = {
        CC_ALGO.CUBIC: "CUBIC",
        CC_ALGO.BBR: "BBR",
        CC_ALGO.RENO: "RENO"
    }
    SHORT_ECN = {
        ECN_TYPE.ECT_1: "ECT1",
        ECN_TYPE.ECT_0: "ECT0",
    }
    def GET_SPIN_TYPE(config):
        if config["STACK"] == "PICOQUIC":
            if "SPIN" in config.keys() and config["SPIN"] == "OFF":
                return SPIN_TYPE.picoquic_spinbit_off
        return SPIN_TYPE.picoquic_spinbit_on
    SPIN_TYPE_SHORT = {
        SPIN_TYPE.picoquic_spinbit_on: "ON",
        SPIN_TYPE.picoquic_spinbit_off: "OFF",
    }
    START_TIME = time.perf_counter()
    start_time = datetime.datetime.now()

    RESULT_MAIN_PATH = os.path.join(configuration["ORCHESTRATION"]["RESULT_PATH"], configuration["ORCHESTRATION"]["OVERALL_NAME"])
    os.makedirs(RESULT_MAIN_PATH, exist_ok=True)
    for experiment_configuration in progressbar.progressbar(configuration["EXPERIMENTS"]):

        print(f" Current time: {datetime.datetime.now()}, Start time: {start_time}")

        try:

            BOTTLE  = SSHConnector(management_ip=configuration["TESTBED"]["DEVICE_IP"]["BOTTLE"],
                                    local_ip=configuration["TESTBED"]["LOCAL_IP"]["BOTTLE"],
                                    user=configuration["TESTBED"]["USERNAME"],
                                    key_filename=configuration["TESTBED"]["KEY_FILE"])

            LOAD1  = SSHConnector(management_ip=configuration["TESTBED"]["DEVICE_IP"]["LOAD1"],
                                    local_ip=configuration["TESTBED"]["LOCAL_IP"]["LOAD1"],
                                    user=configuration["TESTBED"]["USERNAME"],
                                    key_filename=configuration["TESTBED"]["KEY_FILE"])

            LOAD2  = SSHConnector(management_ip=configuration["TESTBED"]["DEVICE_IP"]["LOAD2"],
                                    local_ip=configuration["TESTBED"]["LOCAL_IP"]["LOAD2"],
                                    user=configuration["TESTBED"]["USERNAME"],
                                    key_filename=configuration["TESTBED"]["KEY_FILE"])

            CLIENT  = SSHConnector(management_ip=configuration["TESTBED"]["DEVICE_IP"]["CLIENT"],
                                    local_ip=configuration["TESTBED"]["LOCAL_IP"]["CLIENT"],
                                    user=configuration["TESTBED"]["USERNAME"],
                                    key_filename=configuration["TESTBED"]["KEY_FILE"])

            QUEUES = {
                "CODEL_ECN": CoDel(bandwidth_limit_soft=experiment_configuration["BW"], 
                                bandwidth_limit_hard=experiment_configuration["BW"], 
                                classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                prio=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                interval=experiment_configuration["STANDARD_AQM_INTERVAL_MS"] if "STANDARD_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                target=experiment_configuration["STANDARD_AQM_TARGET_MS"] if "STANDARD_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                ecn=True),
                "CODEL_ECN_GOOD": CoDel(bandwidth_limit_soft=experiment_configuration["BW_GOOD"], 
                                        bandwidth_limit_hard=experiment_configuration["BW"], 
                                        classid=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"], 
                                        prio=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"], 
                                        interval=experiment_configuration["RESPONSIVE_AQM_INTERVAL_MS"] if "RESPONSIVE_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                        target=experiment_configuration["RESPONSIVE_AQM_TARGET_MS"] if "RESPONSIVE_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                        ecn=True),
                "CODEL_ECN_BAD": CoDel(bandwidth_limit_soft=experiment_configuration["BW_BAD"], 
                                    bandwidth_limit_hard=experiment_configuration["BW_BAD"], 
                                    classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                    prio=configuration["PARAMETERS"]["STANDARD_QUEUE"],  
                                    interval=experiment_configuration["STANDARD_AQM_INTERVAL_MS"] if "STANDARD_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                    target=experiment_configuration["STANDARD_AQM_TARGET_MS"] if "STANDARD_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                    ecn=True),

                "CODEL_DROP": CoDel(bandwidth_limit_soft=experiment_configuration["BW"], 
                                    bandwidth_limit_hard=experiment_configuration["BW"], 
                                    classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                    prio=configuration["PARAMETERS"]["STANDARD_QUEUE"],
                                    interval=experiment_configuration["STANDARD_AQM_INTERVAL_MS"] if "STANDARD_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                    target=experiment_configuration["STANDARD_AQM_TARGET_MS"] if "STANDARD_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                    ecn=False),
                "CODEL_DROP_GOOD": CoDel(bandwidth_limit_soft=experiment_configuration["BW_GOOD"], 
                                        bandwidth_limit_hard=experiment_configuration["BW"], 
                                        classid=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"],
                                        prio=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"], 
                                        interval=experiment_configuration["RESPONSIVE_AQM_INTERVAL_MS"] if "RESPONSIVE_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                        target=experiment_configuration["RESPONSIVE_AQM_TARGET_MS"] if "RESPONSIVE_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                        ecn=False),
                "CODEL_DROP_BAD": CoDel(bandwidth_limit_soft=experiment_configuration["BW_BAD"], 
                                        bandwidth_limit_hard=experiment_configuration["BW_BAD"], 
                                        classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                        prio=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                        interval=experiment_configuration["STANDARD_AQM_INTERVAL_MS"] if "STANDARD_AQM_INTERVAL_MS" in experiment_configuration.keys() else 20,
                                        target=experiment_configuration["STANDARD_AQM_TARGET_MS"] if "STANDARD_AQM_TARGET_MS" in experiment_configuration.keys() else 0.5,
                                        ecn=False),

                "DT": DropTail(bandwidth_limit_soft=experiment_configuration["BW"], 
                            bandwidth_limit_hard=experiment_configuration["BW"], 
                            classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                            prio=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                            rate=experiment_configuration["BW"]),
                "DT_GOOD": DropTail(bandwidth_limit_soft=experiment_configuration["BW_GOOD"], 
                                    bandwidth_limit_hard=experiment_configuration["BW"], 
                                    classid=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"], 
                                    prio=configuration["PARAMETERS"]["RESPONSIVE_QUEUE"], 
                                    rate=experiment_configuration["BW"]),
                "DT_BAD": DropTail(bandwidth_limit_soft=experiment_configuration["BW_BAD"], 
                                bandwidth_limit_hard=experiment_configuration["BW_BAD"], 
                                classid=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                prio=configuration["PARAMETERS"]["STANDARD_QUEUE"], 
                                rate=experiment_configuration["BW"])
            }


            SERVER_INFO_MAPPING = {}
            CLIENTS_PER_SERVER = {}
            CLIENT_SERVER_MAPPING = {}
            IP_PORT_CLIENT_SERVER_MAPPING = {}
            for client_config in experiment_configuration["CLIENT_CONFIGS"]:
                if client_config["SERVER_MACHINE"] not in CLIENTS_PER_SERVER.keys():
                    CLIENTS_PER_SERVER[client_config["SERVER_MACHINE"]] = {}
                try:
                    CLIENTS_PER_SERVER[client_config["SERVER_MACHINE"]][client_config["SERVER_APP"]] += 1
                except KeyError:
                    CLIENTS_PER_SERVER[client_config["SERVER_MACHINE"]][client_config["SERVER_APP"]] = 1

            ALL_SERVERS = []
            if experiment_configuration["SERVER_1_DEPLOY"]:

                SERVER_INFO_MAPPING[1] = {}
                
                try: 
                    _ = CLIENTS_PER_SERVER[1]
                except KeyError as e:
                    raise Exception(f"Server 1 not requested by any client. Disable it for a clean config.")
                else:

                    for number, server_config in enumerate(experiment_configuration["SERVER_1_CONFIGS"]):

                        try: 
                            _ = CLIENTS_PER_SERVER[1][number]
                        except KeyError as e:
                            raise Exception(f"Server 1, app {number} not requested by any client. Disable it for a clean config.")
                        else:

                            ALL_SERVERS.append(
                                Stack_Server_Config(
                                    implementation=STACKS[server_config["STACK"]],
                                    stack_path=configuration["ORCHESTRATION"]["STACK_PATHS"][server_config["STACK"]],
                                    local_output_path=configuration["ORCHESTRATION"]["LOCAL_OUTPUT_PATH"],
                                    device=LOAD1, 
                                    num_connections=CLIENTS_PER_SERVER[1][number],
                                    certfolder=configuration["ORCHESTRATION"]["CERTFOLDER_PATH"],
                                    file_location=configuration["ORCHESTRATION"]["TRAFFIC_FILES_PATH"],
                                    transfer_amount=server_config["FILESIZE"] if server_config["STACK"] == "TCP" else 0,
                                    server_ip=LOAD1.local_ip, 
                                    server_port=experiment_configuration["SERVER_1_PORT_START"] + number, 
                                    cc_algo=CC_ALGO[server_config["CC"]], 
                                    ecn_type=ECN_TYPE[server_config["ECN"]],
                                    bidirectional=server_config["BIDIRECTIONAL"] if server_config["STACK"] == "TCP" else "0"))

                            SERVER_INFO_MAPPING[1][number] = {}
                            SERVER_INFO_MAPPING[1][number]["port"] = experiment_configuration["SERVER_1_PORT_START"] + number
                            SERVER_INFO_MAPPING[1][number]["cca"] = server_config["CC"]
                            SERVER_INFO_MAPPING[1][number]["stack"] = server_config["STACK"]

            if experiment_configuration["SERVER_2_DEPLOY"]:

                SERVER_INFO_MAPPING[2] = {}

                try: 
                    _ = CLIENTS_PER_SERVER[2]
                except KeyError as e:
                    raise Exception(f"Server 2 not requested by any client. Disable it for a clean config.")
                else:

                    for number, server_config in enumerate(experiment_configuration["SERVER_2_CONFIGS"]):

                        try: 
                            _ = CLIENTS_PER_SERVER[2][number]
                        except KeyError as e:
                            raise Exception(f"Server 2, app {number} not requested by any client. Disable it for a clean config.")
                        else:

                            ALL_SERVERS.append(
                                Stack_Server_Config(
                                    implementation=STACKS[server_config["STACK"]],
                                    stack_path=configuration["ORCHESTRATION"]["STACK_PATHS"][server_config["STACK"]],
                                    local_output_path=configuration["ORCHESTRATION"]["LOCAL_OUTPUT_PATH"],
                                    device=LOAD2, 
                                    num_connections=CLIENTS_PER_SERVER[2][number],
                                    certfolder=configuration["ORCHESTRATION"]["CERTFOLDER_PATH"],
                                    file_location=configuration["ORCHESTRATION"]["TRAFFIC_FILES_PATH"],
                                    transfer_amount=server_config["FILESIZE"] if server_config["STACK"] == "TCP" else 0,
                                    server_ip=LOAD2.local_ip, 
                                    server_port=experiment_configuration["SERVER_2_PORT_START"] + number, 
                                    cc_algo=CC_ALGO[server_config["CC"]], 
                                    ecn_type=ECN_TYPE[server_config["ECN"]],
                                    bidirectional=server_config["BIDIRECTIONAL"] if server_config["STACK"] == "TCP" else "0"))

                            SERVER_INFO_MAPPING[2][number] = {}
                            SERVER_INFO_MAPPING[2][number]["port"] = experiment_configuration["SERVER_2_PORT_START"] + number
                            SERVER_INFO_MAPPING[2][number]["cca"] = server_config["CC"]
                            SERVER_INFO_MAPPING[2][number]["stack"] = server_config["STACK"]
            

            ALL_CLIENTS = []
            LOCAL_PORT_START = (1 << 11)  + 1024
            for client_number, client_config in enumerate(experiment_configuration["CLIENT_CONFIGS"]):

                SERVER_IP = configuration["TESTBED"]["LOCAL_IP"]["LOAD1"] if client_config["SERVER_MACHINE"] == 1 else configuration["TESTBED"]["LOCAL_IP"]["LOAD2"]
                IPERF_DEVICE = LOAD1 if client_config["SERVER_MACHINE"] == 1 else LOAD2
                CLIENT_IP = configuration["TESTBED"]["LOCAL_IP"]["CLIENT"]

                CLIENT_PORT = LOCAL_PORT_START+client_number
                SERVER_PORT = None
                try: 
                    SERVER_MACHINE = SERVER_INFO_MAPPING[client_config["SERVER_MACHINE"]]
                except KeyError as e:
                    raise Exception(f"Server {client_config['SERVER_MACHINE']} has not deployed any applications.")
                try: 
                    SERVER_PORT = SERVER_INFO_MAPPING[client_config["SERVER_MACHINE"]][client_config["SERVER_APP"]]["port"]
                except Exception as e:
                    raise Exception(f"Server {client_config['SERVER_MACHINE']} has not deployed application {client_config['SERVER_APP']}.")

                ALL_CLIENTS.append(
                    Stack_Client_Config(
                        STACKS[client_config["STACK"]], 
                        configuration["ORCHESTRATION"]["STACK_PATHS"][client_config["STACK"]],
                        configuration["ORCHESTRATION"]["LOCAL_OUTPUT_PATH"],
                        client_config["FILESIZE"], 
                        client_config["START_DELAY"],
                        CLIENT, 
                        SERVER_IP,
                        CLIENT_IP,
                        target_port=SERVER_PORT, 
                        local_port=LOCAL_PORT_START+client_number,
                        client_number=client_number, 
                        cc_algo=CC_ALGO[client_config["CC"]], 
                        ecn_type=ECN_TYPE[client_config["ECN"]],
                        spin_type=GET_SPIN_TYPE(client_config),
                        bidirectional=client_config["BIDIRECTIONAL"] if client_config["STACK"] == "TCP" else "0")
                )
                IP_PORT_CLIENT_SERVER_MAPPING[client_number] = {
                        "SERVER_IP": SERVER_IP,
                        "SERVER_PORT": SERVER_PORT,
                        "CLIENT_IP": CLIENT_IP,
                        "CLIENT_PORT": CLIENT_PORT,
                        "SERVER_STACK": SERVER_INFO_MAPPING[client_config["SERVER_MACHINE"]][client_config["SERVER_APP"]]["stack"],
                        "SERVER_CCA": SERVER_INFO_MAPPING[client_config["SERVER_MACHINE"]][client_config["SERVER_APP"]]["cca"],
                        "CLIENT_STACK": client_config["STACK"],
                        "CLIENT_CCA": client_config["CC"],
                        "FILESIZE": client_config["FILESIZE"]}

                CLIENT_SERVER_MAPPING[client_number] = {client_config["SERVER_MACHINE"]:client_config["SERVER_APP"]}

            if experiment_configuration["BACKGROUND"]["SERVER_1"]:

                for server_number, flow_config in enumerate(experiment_configuration["BACKGROUND"]["SERVER_1_FLOWS"]):

                    SERVER_PORT = experiment_configuration["BACKGROUND"]["SERVER_1_PORT_START"] + server_number
                    CLIENT_NUMBER = max(CLIENT_SERVER_MAPPING.keys()) + 1
                    CLIENT_PORT = LOCAL_PORT_START+CLIENT_NUMBER
                    CLIENT_SERVER_MAPPING[CLIENT_NUMBER] = {1:f"BG_{server_number}"}

                    ALL_SERVERS.append(
                        IPERF3_UDP_Server_Config(
                            STACKS["IPERF_UDP"],
                            LOAD1, 
                            server_port=SERVER_PORT)
                    )

                    ALL_CLIENTS.append(
                        IPERF3_UDP_Client_Config(
                            STACKS["IPERF_UDP"],
                            flow_config["BW"], 
                            flow_config["START_DELAY"],
                            CLIENT, 
                            configuration["TESTBED"]["LOCAL_IP"]["LOAD1"], 
                            timeout=experiment_configuration["WATCHDOG_TIMEOUT"] if "WATCHDOG_TIMEOUT" in experiment_configuration.keys() else 900,
                            target_port=SERVER_PORT, 
                            local_port=LOCAL_PORT_START+CLIENT_NUMBER,
                            client_number=CLIENT_NUMBER)
                    )

                    IP_PORT_CLIENT_SERVER_MAPPING[CLIENT_NUMBER] = {
                        "SERVER_IP": configuration["TESTBED"]["LOCAL_IP"]["LOAD1"],
                        "SERVER_PORT": SERVER_PORT,
                        "CLIENT_IP": configuration["TESTBED"]["LOCAL_IP"]["CLIENT"],
                        "CLIENT_PORT": CLIENT_PORT,
                        "SERVER_STACK": "IPERF_UDP",
                        "SERVER_CCA": "None",
                        "CLIENT_STACK": "IPERF_UDP",
                        "CLIENT_CCA": "None",
                        "FILESIZE": 0}

            if experiment_configuration["BACKGROUND"]["SERVER_2"]:

                for server_number, flow_config in enumerate(experiment_configuration["BACKGROUND"]["SERVER_2_FLOWS"]):

                    SERVER_PORT = experiment_configuration["BACKGROUND"]["SERVER_2_PORT_START"] + server_number
                    CLIENT_NUMBER = max(CLIENT_SERVER_MAPPING.keys()) + 1
                    CLIENT_PORT = LOCAL_PORT_START+CLIENT_NUMBER
                    CLIENT_SERVER_MAPPING[CLIENT_NUMBER] = {2:f"BG_{server_number}"}

                    ALL_SERVERS.append(
                        IPERF3_UDP_Server_Config(
                            STACKS["IPERF_UDP"], 
                            LOAD2, 
                            server_port=SERVER_PORT)
                    )

                    ALL_CLIENTS.append(
                        IPERF3_UDP_Client_Config(
                            STACKS["IPERF_UDP"],
                            flow_config["BW"], 
                            flow_config["START_DELAY"],
                            CLIENT, 
                            configuration["TESTBED"]["LOCAL_IP"]["LOAD2"], 
                            timeout=experiment_configuration["WATCHDOG_TIMEOUT"] if "WATCHDOG_TIMEOUT" in experiment_configuration.keys() else 900,
                            target_port=SERVER_PORT, 
                            local_port=LOCAL_PORT_START+CLIENT_NUMBER,
                            client_number=CLIENT_NUMBER)
                    )


                    IP_PORT_CLIENT_SERVER_MAPPING[CLIENT_NUMBER] = {
                        "SERVER_IP": configuration["TESTBED"]["LOCAL_IP"]["LOAD1"],
                        "SERVER_PORT": SERVER_PORT,
                        "CLIENT_IP": configuration["TESTBED"]["LOCAL_IP"]["CLIENT"],
                        "CLIENT_PORT": CLIENT_PORT,
                        "SERVER_STACK": "IPERF_UDP",
                        "SERVER_CCA": "None",
                        "CLIENT_STACK": "IPERF_UDP",
                        "CLIENT_CCA": "None",
                        "FILESIZE": 0}

            ITERATIONS = configuration["ORCHESTRATION"]["ITERATIONS"]

            deploy_TCP_classifier = False
            deploy_QUIC_classifier = False

            # deploy TCP classifier only if there is a TCP client
            for quic_client in ALL_CLIENTS: 
                if isinstance(quic_client.implementation, TCP):
                    deploy_TCP_classifier = True
                else:
                    deploy_QUIC_classifier = True

            if "CLASSIFIER_DEPLOY" in experiment_configuration.keys():
                deploy_QUIC_classifier = experiment_configuration["CLASSIFIER_DEPLOY"]
                
            deploy_TCP_classifier = False

            print("\nDEPLOY QUIC classifier: ", deploy_QUIC_classifier)
            print("DEPLOY TCP classifier: ", deploy_TCP_classifier)

            GOOD_AQM = BAD_AQM = AQM = None
            ECN_MODE = False
            if experiment_configuration["MULTICLASS_AQM_DEPLOY"]:
                GOOD_AQM = QUEUES[experiment_configuration['RESPONSIVE_AQM']]
                BAD_AQM = QUEUES[experiment_configuration['STANDARD_AQM']]
                if "ECN" in experiment_configuration['RESPONSIVE_AQM'] and "ECN" in experiment_configuration['STANDARD_AQM']:
                    ECN_MODE = True
            else:
                AQM = QUEUES[experiment_configuration['STANDARD_AQM']]
                if "ECN" in experiment_configuration['STANDARD_AQM']:
                    ECN_MODE = True

            EXPERIMENT_STRING = ""
            EXPERIMENT_STRING += f"QUEUE-{experiment_configuration['QUEUE_SIZE_BDP']}"
            EXPERIMENT_STRING += f"_RTT-{experiment_configuration['RTT']}"
            EXPERIMENT_STRING += f"_BW-{experiment_configuration['BW']}"

            if experiment_configuration["MULTICLASS_AQM_DEPLOY"]:
                EXPERIMENT_STRING += f"_GOOD+{experiment_configuration['RESPONSIVE_AQM']}+{experiment_configuration['BW_GOOD']}"
                EXPERIMENT_STRING += f"_BAD+{experiment_configuration['STANDARD_AQM']}+{experiment_configuration['BW_BAD']}"
                print(f"Experiment Configs: RTT: {experiment_configuration['RTT']}ms, QDISC GOOD: {GOOD_AQM.__class__.__name__}, BW GOOD: {GOOD_AQM.bandwidth_limit_soft}MBit/s, QDISC BAD: {BAD_AQM.__class__.__name__}, BW BAD: {BAD_AQM.bandwidth_limit_soft}MBit/s")
            else:
                EXPERIMENT_STRING += f"_{experiment_configuration['STANDARD_AQM']}"
                print(f"Experiment Configs: RTT: {experiment_configuration['RTT']}ms, QDISC: {AQM.__class__.__name__}, BW: {AQM.bandwidth_limit_soft}MBit/s")

            EXPERIMENT_STRING += "_SERVERS"
            if len(ALL_SERVERS) > 2:
                EXPERIMENT_STRING += f"--{len(ALL_SERVERS)}"
            else:
                for server in ALL_SERVERS:
                    if server.implementation.__class__.__name__ == "IPERF_UDP":
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[server.implementation.__class__.__name__]}"
                    elif server.implementation.__class__.__name__ == "TCP":
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[server.implementation.__class__.__name__]}+{SHORT_CC[server.cc_algo]}+{server.bidirectional}"
                    else:
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[server.implementation.__class__.__name__]}+{SHORT_CC[server.cc_algo]}"

            EXPERIMENT_STRING += "_CLIENTS"
            if len(ALL_CLIENTS) > 2:
                EXPERIMENT_STRING += f"--{len(ALL_CLIENTS)}"
            else:
                for client in ALL_CLIENTS:
                    if client.implementation.__class__.__name__ == "IPERF_UDP":
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[client.implementation.__class__.__name__]}"
                    elif client.implementation.__class__.__name__ == "PICO_QUIC":
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[client.implementation.__class__.__name__]}+{SHORT_CC[client.cc_algo]}+{SHORT_ECN[client.ecn_type]}+{SPIN_TYPE_SHORT[client._spin_type]}+{client._transfer_amount}"
                    elif client.implementation.__class__.__name__ == "TCP":
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[client.implementation.__class__.__name__]}+{SHORT_CC[client.cc_algo]}+{SHORT_ECN[client.ecn_type]}+{SPIN_TYPE_SHORT[client._spin_type]}+{client._transfer_amount}+{client.bidirectional}"
                    else:
                        EXPERIMENT_STRING += f"-{SHORT_STACKS[client.implementation.__class__.__name__]}+{SHORT_CC[client.cc_algo]}+{SHORT_ECN[client.ecn_type]}+{client._transfer_amount}"

            if "FOLDER_NAME_SUFFIX" in experiment_configuration.keys():
                EXPERIMENT_STRING += f"--{experiment_configuration['FOLDER_NAME_SUFFIX']}"


            RESULT_FOLDER = os.path.join(RESULT_MAIN_PATH, EXPERIMENT_STRING)

            if experiment_configuration["MULTICLASS_AQM_DEPLOY"]:

                BDP_Bytes_GOOD = experiment_configuration["BW_GOOD"] * (1000000 / 8) * (experiment_configuration["RTT"] / 1000)
                BDP_Bytes_GOOD = int(experiment_configuration["QUEUE_SIZE_BDP"] * BDP_Bytes_GOOD)

                BDP_Bytes_BAD = experiment_configuration["BW_BAD"] * (1000000 / 8) * (experiment_configuration["RTT"] / 1000)
                BDP_Bytes_BAD = int(experiment_configuration["QUEUE_SIZE_BDP"] * BDP_Bytes_BAD)
                GOOD_AQM.set_limit(BDP_Bytes_GOOD)
                BAD_AQM.set_limit(BDP_Bytes_BAD)
            else:
                BDP_Bytes = experiment_configuration["BW"] * (1000000 / 8) * (experiment_configuration["RTT"] / 1000)
                BDP_Bytes = int(experiment_configuration["QUEUE_SIZE_BDP"] * BDP_Bytes)
                AQM.set_limit(BDP_Bytes)

            CLASS_MAPPING = {
                # In multiqueue setting, define a mapping that maps the individual class IDs to the correct queue
                "MULTICLASS" : {configuration['PARAMETERS']['BOTH_UNCLASSIFIED']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['BOTH_RESPONSIVE']:configuration['PARAMETERS']['RESPONSIVE_QUEUE'],
                                configuration['PARAMETERS']['BOTH_UNRESPONSIVE']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_RESP_LOSS_UNCLASS']:configuration['PARAMETERS']['RESPONSIVE_QUEUE'] if ECN_MODE else configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_RESP_LOSS_UNRESP']:configuration['PARAMETERS']['RESPONSIVE_QUEUE'] if ECN_MODE else configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNRESP_LOSS_UNCLASS']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNCLASS_LOSS_RESP']:configuration['PARAMETERS']['STANDARD_QUEUE'] if ECN_MODE else configuration['PARAMETERS']['RESPONSIVE_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNRESP_LOSS_RESP']:configuration['PARAMETERS']['STANDARD_QUEUE'] if ECN_MODE else configuration['PARAMETERS']['RESPONSIVE_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNCLASS_LOSS_UNRESP']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['DEFAULT_ID']:configuration['PARAMETERS']['STANDARD_QUEUE']},
                # In singlequeue setting, map all class IDs to the same queue
                "SINGLECLASS": {configuration['PARAMETERS']['BOTH_UNCLASSIFIED']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['BOTH_RESPONSIVE']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['BOTH_UNRESPONSIVE']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_RESP_LOSS_UNCLASS']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_RESP_LOSS_UNRESP']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNRESP_LOSS_UNCLASS']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNCLASS_LOSS_RESP']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNRESP_LOSS_RESP']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['ECN_UNCLASS_LOSS_UNRESP']:configuration['PARAMETERS']['STANDARD_QUEUE'],
                                configuration['PARAMETERS']['DEFAULT_ID']:configuration['PARAMETERS']['STANDARD_QUEUE']}
            }

            tc_config = class_mapping = None
            if experiment_configuration["MULTICLASS_AQM_DEPLOY"]:
                tc_config = TC_Configuration(
                    ingress_device=configuration["TESTBED"]["INGRESS_DEVICE"], 
                    egress_device=configuration["TESTBED"]["EGRESS_DEVICE"], 
                    client_device=configuration["TESTBED"]["CLIENT_DEVICE"], 
                    trafficClasses=[GOOD_AQM, BAD_AQM],
                    defaultTrafficClass=configuration["PARAMETERS"]["STANDARD_QUEUE"],
                    first_ifb=configuration["TESTBED"]["FIRST_IFB"],
                    second_ifb=configuration["TESTBED"]["SECOND_IFB"])

                class_mapping = CLASS_MAPPING["MULTICLASS"]
            else:
                tc_config = TC_Configuration(
                    ingress_device=configuration["TESTBED"]["INGRESS_DEVICE"], 
                    egress_device=configuration["TESTBED"]["EGRESS_DEVICE"], 
                    client_device=configuration["TESTBED"]["CLIENT_DEVICE"], 
                    trafficClasses=[AQM],
                    defaultTrafficClass=configuration["PARAMETERS"]["STANDARD_QUEUE"],
                    first_ifb=configuration["TESTBED"]["FIRST_IFB"],
                    second_ifb=configuration["TESTBED"]["SECOND_IFB"])
                class_mapping = CLASS_MAPPING["SINGLECLASS"]
        
            classifier_config = Classifier_Configuration(mapping=class_mapping, 
                                                            responsive_test=RESPONSIVE_TEST[experiment_configuration["RESPONSIVENESS_TEST"]],
                                                            BOTH_UNCLASSIFIED_classid=configuration["PARAMETERS"]["BOTH_UNCLASSIFIED"], 
                                                            BOTH_RESPONSIVE_classid=configuration["PARAMETERS"]["BOTH_RESPONSIVE"], 
                                                            BOTH_UNRESPONSIVE_classid=configuration["PARAMETERS"]["BOTH_UNRESPONSIVE"],
                                                            ECN_RESP_LOSS_UNCLASS_classid=configuration["PARAMETERS"]["ECN_RESP_LOSS_UNCLASS"], 
                                                            ECN_RESP_LOSS_UNRESP_classid=configuration["PARAMETERS"]["ECN_RESP_LOSS_UNRESP"], 
                                                            ECN_UNRESP_LOSS_UNCLASS_classid=configuration["PARAMETERS"]["ECN_UNRESP_LOSS_UNCLASS"],
                                                            ECN_UNCLASS_LOSS_RESP_classid=configuration["PARAMETERS"]["ECN_UNCLASS_LOSS_RESP"], 
                                                            ECN_UNRESP_LOSS_RESP_classid=configuration["PARAMETERS"]["ECN_UNRESP_LOSS_RESP"], 
                                                            ECN_UNCLASS_LOSS_UNRESP_classid=configuration["PARAMETERS"]["ECN_UNCLASS_LOSS_UNRESP"],
                                                            bottleneck_device=configuration["TESTBED"]["INGRESS_DEVICE"],
                                                            client_device=configuration["TESTBED"]["CLIENT_DEVICE"],
                                                            measurement_subnet=BOTTLE.local_ip,
                                                            first_ifb=configuration["TESTBED"]["FIRST_IFB"],
                                                            second_ifb=configuration["TESTBED"]["SECOND_IFB"]
                                                        )
            
            config:ExperimentConfiguration = ExperimentConfiguration(result_folder_path=RESULT_FOLDER, 
                                                                     local_tmp_folder_path=configuration["ORCHESTRATION"]["LOCAL_TMP_PATH"],
                                                                     traffic_files_path=configuration["ORCHESTRATION"]["TRAFFIC_FILES_PATH"],
                                                                        tc_config=tc_config, 
                                                                        classifier_config=classifier_config, 
                                                                        rtt=experiment_configuration['RTT'], 
                                                                        bottleneck_bw=experiment_configuration['BW'] if not experiment_configuration['MULTICLASS_AQM_DEPLOY'] else min(experiment_configuration['BW_GOOD'], experiment_configuration['BW_BAD']), 
                                                                        server_list=ALL_SERVERS,
                                                                        client_list=ALL_CLIENTS,
                                                                        bottleneck_router=BOTTLE, 
                                                                        iterations=ITERATIONS, 
                                                                        only_UDP=False, 
                                                                        let_nocc_finish=False, 
                                                                        deploy_QUIC_classifier=deploy_QUIC_classifier, 
                                                                        deploy_TCP_classifier=deploy_TCP_classifier,
                                                                        load_qlog_data=configuration["ORCHESTRATION"]["load_qlog_data"],
                                                                        watch_dog_timeout_s=experiment_configuration["WATCHDOG_TIMEOUT"] if "WATCHDOG_TIMEOUT" in experiment_configuration.keys() else 900,
                                                                        load1=LOAD1,
                                                                        load2=LOAD2,
                                                                        client=CLIENT,
                                                                        interfaces=[configuration["TESTBED"]["CLIENT_DEVICE"], 
                                                                                    configuration["TESTBED"]["INGRESS_DEVICE"], 
                                                                                    configuration["TESTBED"]["EGRESS_DEVICE"], 
                                                                                    configuration["TESTBED"]["FIRST_IFB"], 
                                                                                    configuration["TESTBED"]["SECOND_IFB"]],
                                                                        tc_viz_path=configuration["ORCHESTRATION"]["TC_VIZ_PATH"])
            
            config_file_dump = {
                "experiment_config": experiment_configuration,
                "parameters": configuration["PARAMETERS"],
                "load_qlog_data": configuration["ORCHESTRATION"]["load_qlog_data"],
                "port_pairs": IP_PORT_CLIENT_SERVER_MAPPING
            }
            try:
                config.run(config_file_dump)
            except Exception as e:
                global_logger.critical("Could not run config: "  + str(type(e).__name__) + str(e.args))
                global_logger.critical(e)
        except Exception as e:
            global_logger.critical("Error during config: " + str(type(e).__name__) + str(e.args))

        finally:
            pass

    print(f"End time: {datetime.datetime.now()}")
    print(f"Experiments took {(time.perf_counter() - START_TIME)} seconds")
import os
import json
import pathlib
from copy import deepcopy
from itertools import product
import random

CONFIGURATION_PATH = pathlib.Path(__file__).parent.resolve()

TEST_CONFIGURATION_FILE = "testconfig.json"

RESPONSIVENESS_ASSESSMENT_FILE = "gen-resp-assessment.json"
SINGLE_FLOW_BG_SINGLE_QUEUE_FILE = "gen-single-flow-bg-single-queue.json"
SINGLE_FLOW_BG_MULTI_QUEUE_FILE = "gen-single-flow-bg-multi-queue.json"
MULTI_FLOW_BG_SINGLE_QUEUE_FILE = "gen-multi-flow-bg-single-queue.json"
MULTI_FLOW_BG_MULTI_QUEUE_FILE = "gen-multi-flow-bg-multi-queue.json"

CODEL_INTERVAL_LOW_MS = 0.01
CODEL_TARGET_LOW_MS = 0.1

def save_config(configuration, output_file_name, configuration_path=CONFIGURATION_PATH):

    print(f"Save config to {os.path.join(configuration_path, output_file_name)}")
    with open(os.path.join(configuration_path, output_file_name), 'w') as output_file:
        json.dump(configuration, output_file, indent=4)

if __name__ == "__main__":

    CASE_COUNTER = 0

    configuration = None
    with open(os.path.join(CONFIGURATION_PATH, "template.json"), "r") as template_file:
        configuration = json.load(template_file)

    OVERALL_TEMPLATE_EXPERIMENT = deepcopy(configuration["EXPERIMENTS"][0])

    ########################################################################
    ########################################################################
    ##### TEST CONFIGURATION
    ########################################################################
    ########################################################################

    configuration["ORCHESTRATION"]["OVERALL_NAME"] = "TEST-EXPERIMENT"
    configuration["ORCHESTRATION"]["ITERATIONS"] = 1

    ## Disable qlog download
    configuration["ORCHESTRATION"]["load_qlog_data"] = False

    template_experiment = deepcopy(OVERALL_TEMPLATE_EXPERIMENT)
    configuration["EXPERIMENTS"] = []

    template_experiment["BW"] = 100
    template_experiment["BW_GOOD"] = 50
    template_experiment["BW_BAD"] = 50
    template_experiment["MULTICLASS_AQM_DEPLOY"] = False

    # Enable UDP background traffic
    template_experiment["BACKGROUND"] = {
        "SERVER_1": True,
        "SERVER_1_PORT_START": 21000,
        "SERVER_1_FLOWS": [
            {
                "BW": 5,
                "START_DELAY": 1000
            }
        ],
        "SERVER_2": True,
        "SERVER_2_PORT_START": 22000,
        "SERVER_2_FLOWS": [
            {
                "BW": 5,
                "START_DELAY": 1000
            }
        ]
    }

    template_experiment["SERVER_1_DEPLOY"] = True
    template_experiment["SERVER_1_CONFIGS"] = []
    template_experiment["SERVER_2_DEPLOY"] = True
    template_experiment["SERVER_2_CONFIGS"] = []

    CLIENT_CONFIGS = []
    SERVER_1_CONFIGS = []
    SERVER_2_CONFIGS = []
    
    server_config_1 = {
        "CC": "CUBIC",
        "ECN": "ECT_1",
        "STACK": "PICOQUIC",
        "FILESIZE": int(100),
        "SPIN": "ON"
    }
    client_config_1 = {
        "CC": "CUBIC",
        "ECN": "ECT_1",
        "STACK": "PICOQUIC",
        "FILESIZE": int(100),
        "START_DELAY": 0,
        "SPIN": "ON",
        "SERVER_MACHINE": 1,
        "SERVER_APP": 0
    }
    SERVER_1_CONFIGS.append(server_config_1)

    server_config_2 = {
        "CC": "CUBIC",
        "ECN": "ECT_1",
        "STACK": "TCP",
        "FILESIZE": int(100),
        "BIDIRECTIONAL": 0
    }
    client_config_2 = {
        "CC": "CUBIC",
        "ECN": "ECT_1",
        "STACK": "TCP",
        "FILESIZE": int(100),
        "START_DELAY": 0,
        "BIDIRECTIONAL": 0,
        "SERVER_MACHINE": 2,
        "SERVER_APP": 0
    }
    SERVER_2_CONFIGS.append(server_config_2)
    CLIENT_CONFIGS.append(client_config_1)
    CLIENT_CONFIGS.append(client_config_2)


    template_experiment["RTT"] = 5
    template_experiment["STANDARD_AQM"] = "CODEL_ECN"
    template_experiment["RESPONSIVE_AQM"] = ""
    template_experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

    template_experiment["WATCHDOG_TIMEOUT"] = 900

    template_experiment["SERVER_1_CONFIGS"] = SERVER_1_CONFIGS
    template_experiment["SERVER_2_CONFIGS"] = SERVER_2_CONFIGS
    template_experiment["CLIENT_CONFIGS"] = CLIENT_CONFIGS

    server_1_flow = template_experiment["BACKGROUND"]["SERVER_1_FLOWS"][0]
    server_1_flow["BW"] = 25
    server_2_flow = template_experiment["BACKGROUND"]["SERVER_2_FLOWS"][0]
    server_2_flow["BW"] = 25

    template_experiment["BACKGROUND"]["SERVER_1_FLOWS"][0] = server_1_flow
    template_experiment["BACKGROUND"]["SERVER_2_FLOWS"][0] = server_2_flow

    configuration["EXPERIMENTS"].append(template_experiment)
    save_config(configuration, TEST_CONFIGURATION_FILE)


    ########################################################################
    ########################################################################
    ##### SINGLE FLOW RESPONSIVENESS ASSESSMENT
    ########################################################################
    ########################################################################

    configuration["ORCHESTRATION"]["OVERALL_NAME"] = "RESPONSIVENESS-ASSESSMENT"
    configuration["ORCHESTRATION"]["ITERATIONS"] = 20 

    ## Disable qlog download
    configuration["ORCHESTRATION"]["load_qlog_data"] = False

    #BWS = [50,500, 1000]
    BWS = [50]

    template_experiment = deepcopy(OVERALL_TEMPLATE_EXPERIMENT)
    configuration["EXPERIMENTS"] = []

    for BW in BWS:

        ### Change here if you would like to set different BW
        template_experiment["BW"] = BW
        template_experiment["BW_GOOD"] = None
        template_experiment["BW_BAD"] = None

        # Disable Multiclass AQM
        template_experiment["MULTICLASS_AQM_DEPLOY"] = False
        # Disable UDP background traffic
        template_experiment["BACKGROUND"] = {"SERVER_1": False, "SERVER_2": False}
        # Only use server 1
        template_experiment["SERVER_1_DEPLOY"] = True
        template_experiment["SERVER_2_DEPLOY"] = False
        template_experiment["SERVER_2_CONFIGS"] = []

        ### The script will create the cartesian product out of these lists
        STANDARD_AQMS = ["DT", "CODEL_ECN", "CODEL_DROP"]
        RTTS = [5,100]

        FILESIZES_BW = {
            50: [200],
            1000: [4000]
        }
        CCAS = ["CUBIC", "BBR"]
        ECN = ["ECT_1"]
        STACKS = [("PICOQUIC", "ON"),
                    ("TCP", "0"), 
                    ("TCP", "1")]

        CASE_COUNTER = sum([len(FILESIZES_BW[key]) for key in BWS]) * len(STANDARD_AQMS) * len(RTTS) * len(CCAS) * len(ECN) * len(STACKS)

        for STANDARD_AQM in STANDARD_AQMS:
            experiment = deepcopy(template_experiment)

            experiment["STANDARD_AQM"] = STANDARD_AQM
            experiment["STANDARD_AQM_TARGET_MS"] = CODEL_TARGET_LOW_MS
            experiment["STANDARD_AQM_INTERVAL_MS"] = CODEL_INTERVAL_LOW_MS

            experiment["RESPONSIVE_AQM"] = ""
            experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

            experiment["WATCHDOG_TIMEOUT"] = 900

            for RTT in RTTS:
                experiment["RTT"] = RTT

                for FILESIZE in FILESIZES_BW[BW]:
                    for cca, ecn, (stack, feature) in product(CCAS, ECN, STACKS):
                        server_config = {
                            "CC": cca,
                            "ECN": ecn,
                            "STACK": stack,
                            "FILESIZE": FILESIZE
                        }
                        if stack == "TCP":
                            if feature == "1" or feature == "0":
                                server_config["BIDIRECTIONAL"] = feature
                            else:
                                server_config["BIDIRECTIONAL"] = "0"

                        experiment["SERVER_1_CONFIGS"] = [server_config]
                        
                        client_config = {
                            "CC": cca,
                            "ECN": ecn,
                            "STACK": stack,
                            "FILESIZE": FILESIZE,
                            "START_DELAY": 0,
                            "SERVER_MACHINE": 1,
                            "SERVER_APP": 0
                        }

                        if stack == "PICOQUIC":
                            if feature == "ON" or feature == "OFF":
                                client_config["SPIN"] = feature
                            else:
                                client_config["SPIN"] = "ON"
                        if stack == "TCP":
                            if feature == "1" or feature == "0":
                                client_config["BIDIRECTIONAL"] = feature
                            else:
                                client_config["BIDIRECTIONAL"] = "0"

                        experiment["CLIENT_CONFIGS"] = [client_config]

                        #print(experiment)
                        configuration["EXPERIMENTS"].append(deepcopy(experiment))


    print(f"This should add up to {CASE_COUNTER} individual settings with {configuration['ORCHESTRATION']['ITERATIONS']} iterations.")
    save_config(configuration, RESPONSIVENESS_ASSESSMENT_FILE)


    ########################################################################
    ########################################################################
    ##### SINGLE FLOW WITH BACKGROUND TRAFFIC
    ########################################################################
    ########################################################################
    configuration["ORCHESTRATION"]["OVERALL_NAME"] = "SINGLE-FLOW-BG"
    configuration["ORCHESTRATION"]["ITERATIONS"] = 20 

    ## Disable qlog download
    configuration["ORCHESTRATION"]["load_qlog_data"] = False

    template_experiment = deepcopy(OVERALL_TEMPLATE_EXPERIMENT)
    configuration["EXPERIMENTS"] = []

    ### Change here if you would like to set different BW
    template_experiment["BW"] = 1000
    template_experiment["BW_GOOD"] = None
    template_experiment["BW_BAD"] = None

    # Disable Multiclass AQM
    template_experiment["MULTICLASS_AQM_DEPLOY"] = False
    # Enable UDP background traffic
    template_experiment["BACKGROUND"] = {
        "SERVER_1": False, 
        "SERVER_2": True,
        "SERVER_2_PORT_START": 22000,
        "SERVER_2_FLOWS": [
            {
                "BW": 500,
                "START_DELAY": 1000
            }
        ]
    }

    # Only use server 1
    template_experiment["SERVER_1_DEPLOY"] = True
    template_experiment["SERVER_2_DEPLOY"] = False
    template_experiment["SERVER_2_CONFIGS"] = []

    ### The script will create the cartesian product out of these lists
    STANDARD_AQMS = ["DT", "CODEL_ECN", "CODEL_DROP"]
    RTTS = [5,100]
    FILESIZES = [1000]
    CCAS = ["CUBIC", "BBR"]
    ECN = ["ECT_1"]
    STACKS = [("PICOQUIC", "ON"),
                ("TCP", "0"), 
                ("TCP", "1")]
                
    CASE_COUNTER = len(STANDARD_AQMS) * len(RTTS) * len(FILESIZES) * len(CCAS) * len(ECN) * len(STACKS) 

    for STANDARD_AQM in STANDARD_AQMS:
        experiment = deepcopy(template_experiment)

        experiment["STANDARD_AQM"] = STANDARD_AQM
        experiment["RESPONSIVE_AQM"] = ""
        experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

        experiment["WATCHDOG_TIMEOUT"] = 900

        for RTT in RTTS:
            experiment["RTT"] = RTT

            for FILESIZE in FILESIZES:
                for cca, ecn, (stack, feature) in product(CCAS, ECN, STACKS):
                    server_config = {
                        "CC": cca,
                        "ECN": ecn,
                        "STACK": stack,
                        "FILESIZE": FILESIZE
                    }
                    if stack == "TCP":
                        if feature == "1" or feature == "0":
                            server_config["BIDIRECTIONAL"] = feature
                        else:
                            server_config["BIDIRECTIONAL"] = "0"

                    experiment["SERVER_1_CONFIGS"] = [server_config]
                    
                    client_config = {
                        "CC": cca,
                        "ECN": ecn,
                        "STACK": stack,
                        "FILESIZE": FILESIZE,
                        "START_DELAY": 0,
                        "SERVER_MACHINE": 1,
                        "SERVER_APP": 0
                    }

                    if stack == "PICOQUIC":
                        if feature == "ON" or feature == "OFF":
                            client_config["SPIN"] = feature
                        else:
                            client_config["SPIN"] = "ON"
                    if stack == "TCP":
                        if feature == "1" or feature == "0":
                            client_config["BIDIRECTIONAL"] = feature
                        else:
                            client_config["BIDIRECTIONAL"] = "0"

                    experiment["CLIENT_CONFIGS"] = [client_config]
                    configuration["EXPERIMENTS"].append(deepcopy(experiment))


    print(f"This should add up to {CASE_COUNTER} individual settings with {configuration['ORCHESTRATION']['ITERATIONS']} iterations.")
    save_config(configuration, SINGLE_FLOW_BG_SINGLE_QUEUE_FILE)


    ########################################################################
    ########################################################################
    ##### SINGLE FLOW WITH BACKGROUND TRAFFIC MULTI QUEUE
    ########################################################################
    ########################################################################
    configuration["ORCHESTRATION"]["OVERALL_NAME"] = "SINGLE-FLOW-BG-MULTI-QUEUE"
    configuration["ORCHESTRATION"]["ITERATIONS"] = 20

    ## Disable qlog download
    configuration["ORCHESTRATION"]["load_qlog_data"] = False

    template_experiment = deepcopy(OVERALL_TEMPLATE_EXPERIMENT)
    configuration["EXPERIMENTS"] = []

    ### Change here if you would like to set different BW
    template_experiment["BW"] = 1000
    template_experiment["BW_GOOD"] = 500
    template_experiment["BW_BAD"] = 500

    # Enable Multiclass AQM
    template_experiment["MULTICLASS_AQM_DEPLOY"] = True
    # Enable UDP background traffic
    template_experiment["BACKGROUND"] = {
        "SERVER_1": False, 
        "SERVER_2": True,
        "SERVER_2_PORT_START": 22000,
        "SERVER_2_FLOWS": [
            {
                "BW": 250,
                "START_DELAY": 1000
            }
        ]
    }

    # Only use server 1
    template_experiment["SERVER_1_DEPLOY"] = True
    template_experiment["SERVER_2_DEPLOY"] = False
    template_experiment["SERVER_2_CONFIGS"] = []

    GOOD_BAD_AQM_PAIRS = [("CODEL_ECN_GOOD", "CODEL_ECN_BAD"), ("CODEL_DROP_GOOD", "CODEL_DROP_BAD"), ("CODEL_DROP_GOOD", "DT_BAD"), ("DT_GOOD", "DT_BAD")]
    
    RTTS = [5, 100]
    FILESIZES = [1000]
    CCAS = ["CUBIC", "BBR"]
    ECN = ["ECT_1"]
    STACKS = [("PICOQUIC", "ON"),
                #("PICOQUIC", "OFF"),
                ("TCP", "0"), 
                ("TCP", "1")]

    CASE_COUNTER = len(GOOD_BAD_AQM_PAIRS) * len(RTTS) * len(CCAS) * len(ECN) * len(STACKS) * len(FILESIZES)

    for GOOD_AQM, BAD_AQM in GOOD_BAD_AQM_PAIRS:
        experiment = deepcopy(template_experiment)

        experiment["STANDARD_AQM"] = BAD_AQM
        experiment["RESPONSIVE_AQM"] = GOOD_AQM
        experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

        experiment["WATCHDOG_TIMEOUT"] = 900

        for RTT in RTTS:
            experiment["RTT"] = RTT

            for FILESIZE in FILESIZES:
                for cca, ecn, (stack, feature) in product(CCAS, ECN, STACKS):
                    server_config = {
                        "CC": cca,
                        "ECN": ecn,
                        "STACK": stack,
                        "FILESIZE": FILESIZE
                    }
                    if stack == "TCP":
                        if feature == "1" or feature == "0":
                            server_config["BIDIRECTIONAL"] = feature
                        else:
                            server_config["BIDIRECTIONAL"] = "0"

                    experiment["SERVER_1_CONFIGS"] = [server_config]
                    
                    client_config = {
                        "CC": cca,
                        "ECN": ecn,
                        "STACK": stack,
                        "FILESIZE": FILESIZE,
                        "START_DELAY": 0,
                        "SERVER_MACHINE": 1,
                        "SERVER_APP": 0
                    }

                    if stack == "PICOQUIC":
                        if feature == "ON" or feature == "OFF":
                            client_config["SPIN"] = feature
                        else:
                            client_config["SPIN"] = "ON"
                    if stack == "TCP":
                        if feature == "1" or feature == "0":
                            client_config["BIDIRECTIONAL"] = feature
                        else:
                            client_config["BIDIRECTIONAL"] = "0"

                    experiment["CLIENT_CONFIGS"] = [client_config]
                    configuration["EXPERIMENTS"].append(deepcopy(experiment))


    print(f"This should add up to {CASE_COUNTER} individual settings with {configuration['ORCHESTRATION']['ITERATIONS']} iterations.")
    save_config(configuration, SINGLE_FLOW_BG_MULTI_QUEUE_FILE)


    #####################################################################################
    #####################################################################################
    ##### MULTIPLE FLOWS WITH BACKGROUND TRAFFIC SINGLE AND MULTI QUEUE
    #####################################################################################
    #####################################################################################
    configuration_single_queue = deepcopy(configuration)
    configuration_multi_queue = deepcopy(configuration)

    configuration_single_queue["ORCHESTRATION"]["OVERALL_NAME"] = "MULTI-FLOW-BG-SINGLE-QUEUE"
    configuration_single_queue["ORCHESTRATION"]["ITERATIONS"] = 20

    configuration_multi_queue["ORCHESTRATION"]["OVERALL_NAME"] = "MULTI-FLOW-BG-MULTI-QUEUE"
    configuration_multi_queue["ORCHESTRATION"]["ITERATIONS"] = 20

    ## Disable qlog download
    configuration_single_queue["ORCHESTRATION"]["load_qlog_data"] = False
    configuration_multi_queue["ORCHESTRATION"]["load_qlog_data"] = False

    template_experiment = deepcopy(OVERALL_TEMPLATE_EXPERIMENT)
    configuration_single_queue["EXPERIMENTS"] = []
    configuration_multi_queue["EXPERIMENTS"] = []

    ### Change here if you would like to set different BW
    template_experiment["BW"] = 1000
    template_experiment["BW_GOOD"] = 500
    template_experiment["BW_BAD"] = 500

    # Enable UDP background traffic
    template_experiment["BACKGROUND"] = {
        "SERVER_1": True,
        "SERVER_1_PORT_START": 21000,
        "SERVER_1_FLOWS": [
            {
                "BW": 250,
                "START_DELAY": 1000
            }
        ],
        "SERVER_2": True,
        "SERVER_2_PORT_START": 22000,
        "SERVER_2_FLOWS": [
            {
                "BW": 250,
                "START_DELAY": 1000
            }
        ]
    }

    template_experiment["SERVER_1_DEPLOY"] = True
    template_experiment["SERVER_1_CONFIGS"] = []
    template_experiment["SERVER_2_DEPLOY"] = True
    template_experiment["SERVER_2_CONFIGS"] = []

    template_experiment_single_queue = deepcopy(template_experiment)
    template_experiment_single_queue["MULTICLASS_AQM_DEPLOY"] = False
    template_experiment_multi_queue = deepcopy(template_experiment)
    template_experiment_multi_queue["MULTICLASS_AQM_DEPLOY"] = True

    STANDARD_AQMS = ["DT", "CODEL_ECN", "CODEL_DROP"]
    GOOD_BAD_AQM_PAIRS = [("CODEL_ECN_GOOD", "CODEL_ECN_BAD"), ("CODEL_DROP_GOOD", "CODEL_DROP_BAD"), ("CODEL_DROP_GOOD", "DT_BAD"), ("DT_GOOD", "DT_BAD")]
    
    RTTS = [5, 100]
    FILESIZES = [2000]
    FLOW_COUNTS = [20]
    ITERATIONS = [20]

    AVAILABLE_CCAS = ["CUBIC", "BBR"]
    AVAILABLE_ECN = ["ECT_1"]
    AVAILABLE_STACKS = [("PICOQUIC", "ON"),
                        ("PICOQUIC", "OFF"),
                        ("TCP", "0"), 
                        ("TCP", "1")]

    CASE_COUNTER_MULTI = len(GOOD_BAD_AQM_PAIRS) * len(RTTS) * len(FILESIZES) * len(FLOW_COUNTS) * len(ITERATIONS)
    CASE_COUNTER_SINGLE = len(STANDARD_AQMS) * len(RTTS) * len(FILESIZES) * len(FLOW_COUNTS) * len(ITERATIONS)

    for FILESIZE in FILESIZES:
        for FLOW_COUNT in FLOW_COUNTS:    
            for ITERATION in ITERATIONS:
                for FLOW_COMBINATION_ID in range(ITERATION):
                
                    CLIENT_CONFIGS = []
                    SERVER_1_CONFIGS = []
                    SERVER_2_CONFIGS = []
                    
                    for flow_number in range(FLOW_COUNT):

                        cca = random.choice(AVAILABLE_CCAS)
                        ecn = random.choice(AVAILABLE_ECN)
                        (stack, feature) = random.choice(AVAILABLE_STACKS)

                        server_config = {
                                    "CC": cca,
                                    "ECN": ecn,
                                    "STACK": stack,
                                    "FILESIZE": int(FILESIZE/FLOW_COUNT)
                        }

                        client_config = {
                            "CC": cca,
                            "ECN": ecn,
                            "STACK": stack,
                            "FILESIZE": int(FILESIZE/FLOW_COUNT),
                            "START_DELAY": 0
                        }

                        if stack == "TCP":
                            if feature == "1" or feature == "0":
                                server_config["BIDIRECTIONAL"] = feature
                                client_config["BIDIRECTIONAL"] = feature
                            else:
                                server_config["BIDIRECTIONAL"] = "0"
                                client_config["BIDIRECTIONAL"] = "0"

                        if stack == "PICOQUIC":
                            if feature == "ON" or feature == "OFF":
                                client_config["SPIN"] = feature
                            else:
                                client_config["SPIN"] = "ON"

                        if flow_number % 2 == 0:
                            SERVER_1_CONFIGS.append(server_config)
                            client_config["SERVER_MACHINE"] = 1
                        else:
                            SERVER_2_CONFIGS.append(server_config)
                            client_config["SERVER_MACHINE"] = 2
                        client_config["SERVER_APP"] = int(flow_number/2)
                        CLIENT_CONFIGS.append(client_config)

                    for RTT in RTTS:
                        for GOOD_AQM, BAD_AQM in GOOD_BAD_AQM_PAIRS:
                            
                            experiment = deepcopy(template_experiment_multi_queue)

                            experiment["RTT"] = RTT
                            experiment["STANDARD_AQM"] = BAD_AQM
                            experiment["RESPONSIVE_AQM"] = GOOD_AQM
                            experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

                            experiment["WATCHDOG_TIMEOUT"] = 900

                            experiment["SERVER_1_CONFIGS"] = SERVER_1_CONFIGS
                            experiment["SERVER_2_CONFIGS"] = SERVER_2_CONFIGS
                            experiment["CLIENT_CONFIGS"] = CLIENT_CONFIGS
                            experiment["FOLDER_NAME_SUFFIX"] = f"Flow-Combination-{FLOW_COMBINATION_ID}"

                            server_1_flow = experiment["BACKGROUND"]["SERVER_1_FLOWS"][0]
                            server_1_flow["BW"] = 125
                            server_2_flow = experiment["BACKGROUND"]["SERVER_2_FLOWS"][0]
                            server_2_flow["BW"] = 125

                            experiment["BACKGROUND"]["SERVER_1_FLOWS"][0] = server_1_flow
                            experiment["BACKGROUND"]["SERVER_2_FLOWS"][0] = server_2_flow

                            configuration_multi_queue["EXPERIMENTS"].append(deepcopy(experiment))


                        for STANDARD_AQM in STANDARD_AQMS:
                            
                            experiment = deepcopy(template_experiment_single_queue)

                            experiment["RTT"] = RTT
                            experiment["STANDARD_AQM"] = STANDARD_AQM
                            experiment["RESPONSIVE_AQM"] = ""
                            experiment["RESPONSIVENESS_TEST"] = "WITHOUT_GRACE_MAX_NODELETE"

                            experiment["WATCHDOG_TIMEOUT"] = 900

                            experiment["SERVER_1_CONFIGS"] = SERVER_1_CONFIGS
                            experiment["SERVER_2_CONFIGS"] = SERVER_2_CONFIGS
                            experiment["CLIENT_CONFIGS"] = CLIENT_CONFIGS
                            experiment["FOLDER_NAME_SUFFIX"] = f"Flow-Combination-{FLOW_COMBINATION_ID}"

                            configuration_single_queue["EXPERIMENTS"].append(deepcopy(experiment))


    print(f"This should add up to {CASE_COUNTER_MULTI} individual settings for multi with {configuration_multi_queue['ORCHESTRATION']['ITERATIONS']} iterations.")
    save_config(configuration_multi_queue, MULTI_FLOW_BG_MULTI_QUEUE_FILE)
    print(f"This should add up to {CASE_COUNTER_SINGLE} individual settings for multi with {configuration_single_queue['ORCHESTRATION']['ITERATIONS']} iterations.")
    save_config(configuration_single_queue, MULTI_FLOW_BG_SINGLE_QUEUE_FILE)

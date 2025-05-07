from typing import Dict, Union
from enum import Enum
from . TrafficClasses import *
import os

experiment_folder = os.path.dirname(__file__)

class RESPONSIVE_TEST(Enum):
    
    RESPONSIVE_TO_ECN = """
                switch (cin->classID) {
                        case BOTH_UNCLASSIFIED:
                            cin->classID = ECN_RESP_LOSS_UNCLASS;
                            new_class = 1;
                            break;
                        case BOTH_UNRESPONSIVE:
                            cin->classID = ECN_RESP_LOSS_UNRESP;
                            new_class = 1;
                            break;
                        case BOTH_RESPONSIVE:
                            // no changes
                            new_class = 0;
                            break;
                        case ECN_UNCLASS_LOSS_UNRESP:
                            cin->classID = ECN_RESP_LOSS_UNRESP;
                            new_class = 1;
                            break;
                        case ECN_UNCLASS_LOSS_RESP:
                            cin->classID = BOTH_RESPONSIVE;
                            new_class = 1;
                            break;
                        case ECN_UNRESP_LOSS_UNCLASS:
                            cin->classID = ECN_RESP_LOSS_UNCLASS;
                            new_class = 1;
                            break;
                        case ECN_UNRESP_LOSS_RESP:
                            cin->classID = BOTH_RESPONSIVE;
                            new_class = 1;
                            break;
                        case ECN_RESP_LOSS_UNCLASS:
                            // no changes
                            new_class = 0;
                            break;
                        case ECN_RESP_LOSS_UNRESP:
                            // no changes
                            new_class = 0;
                            break;
                        default:
                            // should not happen
                            break;
                    }"""

    UNRESPONSIVE_TO_ECN = """
                switch (cin->classID) {
                    case BOTH_UNCLASSIFIED:
                        cin->classID = ECN_UNRESP_LOSS_UNCLASS;
                        new_class = 1;
                        break;
                    case BOTH_UNRESPONSIVE:
                        // no changes
                        new_class = 0;
                        break;
                    case BOTH_RESPONSIVE:
                        cin->classID = ECN_UNRESP_LOSS_RESP;
                        new_class = 1;
                        break;
                    case ECN_UNCLASS_LOSS_UNRESP:
                        cin->classID = BOTH_UNRESPONSIVE;
                        new_class = 1;
                        break;
                    case ECN_UNCLASS_LOSS_RESP:
                        cin->classID = ECN_UNRESP_LOSS_RESP;
                        new_class = 1;
                        break;
                    case ECN_UNRESP_LOSS_UNCLASS:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_UNRESP_LOSS_RESP:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_RESP_LOSS_UNCLASS:
                        cin->classID = ECN_UNRESP_LOSS_UNCLASS;
                        new_class = 1;
                        break;
                    case ECN_RESP_LOSS_UNRESP:
                        cin->classID = BOTH_UNRESPONSIVE;
                        new_class = 1;
                        break;
                    default:
                        // should not happen
                        break;
                }"""
    
    RESPONSIVE_TO_LOSS = """
                switch (cin->classID) {
                    case BOTH_UNCLASSIFIED:
                        cin->classID = ECN_UNCLASS_LOSS_RESP;
                        new_class = 1;
                        break;
                    case BOTH_UNRESPONSIVE:
                        cin->classID = ECN_UNRESP_LOSS_RESP;
                        new_class = 1;
                        break;
                    case BOTH_RESPONSIVE:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_UNCLASS_LOSS_UNRESP:
                        cin->classID = ECN_UNCLASS_LOSS_RESP;
                        new_class = 1;
                        break;
                    case ECN_UNCLASS_LOSS_RESP:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_UNRESP_LOSS_UNCLASS:
                        cin->classID = ECN_UNRESP_LOSS_RESP;
                        new_class = 1;
                        break;
                    case ECN_UNRESP_LOSS_RESP:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_RESP_LOSS_UNCLASS:
                        cin->classID = BOTH_RESPONSIVE;
                        new_class = 1;
                        break;
                    case ECN_RESP_LOSS_UNRESP:
                        cin->classID = BOTH_RESPONSIVE;
                        new_class = 1;
                        break;
                    default:
                        // should not happen
                        break;
                }"""

    UNRESPONSIVE_TO_LOSS = """
                switch (cin->classID) {
                    case BOTH_UNCLASSIFIED:
                        cin->classID = ECN_UNCLASS_LOSS_UNRESP;
                        new_class = 1;
                        break;
                    case BOTH_UNRESPONSIVE:
                        // no changes
                        new_class = 0;
                        break;
                    case BOTH_RESPONSIVE:
                        cin->classID = ECN_RESP_LOSS_UNRESP;
                        new_class = 1;
                        break;
                    case ECN_UNCLASS_LOSS_UNRESP:
                        // no changes
                        new_class = 0;
                        break;
                    case ECN_UNCLASS_LOSS_RESP:
                        cin->classID = ECN_UNCLASS_LOSS_UNRESP;
                        new_class = 1;
                        break;
                    case ECN_UNRESP_LOSS_UNCLASS:
                        cin->classID = BOTH_UNRESPONSIVE;
                        new_class = 1;
                        break;
                    case ECN_UNRESP_LOSS_RESP:
                        cin->classID = BOTH_UNRESPONSIVE;
                        new_class = 1;
                        break;
                    case ECN_RESP_LOSS_UNCLASS:
                        cin->classID = ECN_RESP_LOSS_UNRESP;
                        new_class = 1;
                        break;
                    case ECN_RESP_LOSS_UNRESP:
                        // no changes
                        new_class = 0;
                        break;
                    default:
                        // should not happen
                        break;
                }"""

    WITHOUT_GRACE_MAX_NODELETE = """
                if (((*ecn_markings>>16) & 0xFF) != 0) {{
                    if ((9 * cin->bytes3) < (10 * cin->bytes)) {{ // unresponsive
                        cin->unresponsive_count_ECN += 1;  
                    }} else{{
                        cin->responsive_count_ECN += 1;
                    }}
                    if (cin->responsive_count_ECN >= cin->unresponsive_count_ECN){{ // responsive by majority vote
                        {responsive_to_ECN}
                    }} else{{
                        {unresponsive_to_ECN}
                    }}
                }}
                if (((*num_drops>>16) & 0xFF) != 0) {{
                    if ((9 * cin->bytes3) < (10 * cin->bytes)) {{ // unresponsive
                        cin->unresponsive_count_drop += 1;  // für majority voting wird Zähler inkrementiert
                    }} else{{
                        cin->responsive_count_drop += 1;
                    }}
                    if (cin->responsive_count_drop >= cin->unresponsive_count_drop){{ // responsive by majority vote
                        {responsive_to_loss}
                    }} else{{
                        {unresponsive_to_loss}
                    }}
                }}
    """

class Classifier_Configuration:
    def __init__(self, 
                    BOTH_UNCLASSIFIED_classid, BOTH_RESPONSIVE_classid, BOTH_UNRESPONSIVE_classid,
                    ECN_RESP_LOSS_UNCLASS_classid, ECN_RESP_LOSS_UNRESP_classid, ECN_UNRESP_LOSS_UNCLASS_classid,
                    ECN_UNCLASS_LOSS_RESP_classid, ECN_UNRESP_LOSS_RESP_classid, ECN_UNCLASS_LOSS_UNRESP_classid,
                    bottleneck_device, 
                    client_device,
                    measurement_subnet,
                    first_ifb,
                    second_ifb,
                    responsive_test:RESPONSIVE_TEST = RESPONSIVE_TEST.WITHOUT_GRACE_MAX_NODELETE,
                    mapping:Union[Dict[int, int], None] = None,
                    edge_threshold:int = 1) -> None:
        
        self._edge_threshold:int = edge_threshold
        self._responsive_test = responsive_test

        self._BOTH_UNCLASSIFIED_classid = BOTH_UNCLASSIFIED_classid 
        self._BOTH_RESPONSIVE_classid = BOTH_RESPONSIVE_classid
        self._BOTH_UNRESPONSIVE_classid = BOTH_UNRESPONSIVE_classid
        self._ECN_RESP_LOSS_UNCLASS_classid = ECN_RESP_LOSS_UNCLASS_classid
        self._ECN_RESP_LOSS_UNRESP_classid = ECN_RESP_LOSS_UNRESP_classid
        self._ECN_UNRESP_LOSS_UNCLASS_classid = ECN_UNRESP_LOSS_UNCLASS_classid
        self._ECN_UNCLASS_LOSS_RESP_classid = ECN_UNCLASS_LOSS_RESP_classid
        self._ECN_UNRESP_LOSS_RESP_classid = ECN_UNRESP_LOSS_RESP_classid
        self._ECN_UNCLASS_LOSS_UNRESP_classid = ECN_UNCLASS_LOSS_UNRESP_classid

        self._bottleneck_device = bottleneck_device
        self._client_device = client_device
        self._measurement_subnet = measurement_subnet
        self._mapping = mapping

        self._first_ifb = first_ifb
        self._second_ifb = second_ifb

    def __str__(self) -> str:
        return "\n".join([str(self._edge_threshold), self.get_c_code()])
    
    def _set_mapping(self): # MAP_CLASSES code for classifier.c
        if self._mapping is None:
            return ""
        map_code = """
        switch (calc_class) {"""
        for key, value in self._mapping.items():
            map_code += f"""
            case {key}:
                calc_class = {value};
                break;"""
        map_code += """
            default:
                break;
        }"""
        return map_code
    
    def _set_mapping_old_class(self):
        if self._mapping is None:
            return ""
        map_code = """
        switch (cin->classID) {"""
        for key, value in self._mapping.items():
            map_code += f"""
            case {key}:
                old_class_mapped = {value};
                break;"""
        map_code += """
            default:
                break;
        }"""
        return map_code
    
    def _set_mapping_new_class(self):
        if self._mapping is None:
            return ""
        map_code = """
        switch (cin->classID) {"""
        for key, value in self._mapping.items():
            map_code += f"""
            case {key}:
                new_class_mapped = {value};
                break;"""
        map_code += """
            default:
                break;
        }"""
        return map_code

    ##############################################
    #           Classifier Configuration         #
    ##############################################

    def get_py_code(self):
        global py_code
        with open(os.path.join(experiment_folder, "classifier.py")) as f:
            py_code = "".join(f.readlines())
            py_code = py_code.replace("BOTTLENECK_CLIENT", f"\"{self._bottleneck_device}\"")
            py_code = py_code.replace("BOTTLENECK_LOAD", f"\"{self._client_device}\"")
            py_code = py_code.replace("FIRST_IFB", f"\"{self._first_ifb}\"")
        return py_code

    def get_c_code(self):
        global c_code
        with open(os.path.join(experiment_folder, "classifier.c")) as f:
            c_code = "".join(f.readlines())
        return c_code.format(
            MAP_CLASSES=self._set_mapping(),
            MAP_CLASSES_OLD_CLASS_ID=self._set_mapping_old_class(),
            MAP_CLASSES_NEW_CLASS_ID=self._set_mapping_new_class(),
            edge_threshold=self._edge_threshold,
            BOTH_UNCLASSIFIED_classid=self._BOTH_UNCLASSIFIED_classid,
            BOTH_RESPONSIVE_classid=self._BOTH_RESPONSIVE_classid,
            BOTH_UNRESPONSIVE_classid=self._BOTH_UNRESPONSIVE_classid,
            ECN_RESP_LOSS_UNCLASS_classid=self._ECN_RESP_LOSS_UNCLASS_classid,
            ECN_RESP_LOSS_UNRESP_classid=self._ECN_RESP_LOSS_UNRESP_classid,
            ECN_UNRESP_LOSS_UNCLASS_classid=self._ECN_UNRESP_LOSS_UNCLASS_classid,
            ECN_UNRESP_LOSS_RESP_classid=self._ECN_UNRESP_LOSS_RESP_classid,
            ECN_UNCLASS_LOSS_UNRESP_classid=self._ECN_UNCLASS_LOSS_UNRESP_classid,
            ECN_UNCLASS_LOSS_RESP_classid=self._ECN_UNCLASS_LOSS_RESP_classid,
            responsive_code=self._responsive_test.value.format(
                responsive_to_ECN=RESPONSIVE_TEST.RESPONSIVE_TO_ECN.value,
                unresponsive_to_ECN=RESPONSIVE_TEST.UNRESPONSIVE_TO_ECN.value,
                responsive_to_loss=RESPONSIVE_TEST.RESPONSIVE_TO_LOSS.value,
                unresponsive_to_loss=RESPONSIVE_TEST.UNRESPONSIVE_TO_LOSS.value
            )
        )

    def get_tracepoint_code(self):
        global tracepoint_code
        with open(os.path.join(experiment_folder, "tracepoint_ecn.c")) as f:
            tracepoint_code = "".join(f.readlines())
        return tracepoint_code
    
    def get_loss_trace_code(self):
        global loss_trace_code
        with open(os.path.join(experiment_folder, "tracepoint_drops.c")) as f:
            loss_trace_code = "".join(f.readlines())
            return loss_trace_code.format(IP_FIRST_FOUR=self._measurement_subnet.split(".")[0],
                                        IP_SECOND_FOUR=self._measurement_subnet.split(".")[1],
                                        IP_THIRD_FOUR=self._measurement_subnet.split(".")[2])
    
    def get_tracepoint_code_tcp_client(self):
        global tracepoint_code
        with open(os.path.join(experiment_folder, "tracepoint_tcp.c")) as f:
            tracepoint_code = "".join(f.readlines())
        return tracepoint_code
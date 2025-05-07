from typing import List, Tuple
from . TrafficClasses import *

class TC_Configuration:
    def __init__(self, ingress_device: str, egress_device: str, client_device: str, trafficClasses:List[TrafficClass], defaultTrafficClass:TrafficClass, first_ifb, second_ifb) -> None:
        self._ingress_device:str = ingress_device
        self._egress_device:str = egress_device
        self._client_device:str = client_device
        self._traffic_classes:List[TrafficClass] = trafficClasses
        self._defaultTrafficClass = defaultTrafficClass
        self._first_ifb = first_ifb
        self._second_ifb = second_ifb

    def _get_config_clear(self) -> List[str]:
        cmds:List[str] = []
        cmds.append(f"sudo tc qdisc delete dev {self._first_ifb} root")
        cmds.append(f"sudo tc qdisc delete dev {self._second_ifb} root")
        cmds.append(f"sudo tc filter delete dev {self._ingress_device} ingress")
        cmds.append(f"sudo tc qdisc delete dev {self._ingress_device} root")
        cmds.append(f"sudo tc qdisc del dev {self._ingress_device} parent ffff:fff1")
        if self._ingress_device != self._egress_device:
            cmds.append(f"sudo tc qdisc delete dev {self._egress_device} root")
            cmds.append(f"sudo tc qdisc del dev {self._egress_device} parent ffff:fff1")
        cmds.append(f"sudo tc qdisc del dev {self._client_device} parent ffff:fff1")
        return cmds

    def _get_general_config(self) -> List[str]:
        cmds:List[str] = []
        cmds.append(f"sudo tc qdisc add dev {self._ingress_device} clsact")
        cmds.append(f"sudo tc qdisc add dev {self._client_device} root prio")
        cmds.append(f"sudo tc qdisc add dev {self._client_device} clsact")
        return cmds

    def _get_ingress_config(self) -> List[str]: # only one delay class (rtt)
        cmds:List[str] = []
        cmds.append(f"sudo tc filter add dev {self._ingress_device} parent ffff:fff2 u32 match ip dport 0x4000 0xc000 action mirred egress redirect dev {self._first_ifb}")
        cmds.append(f"sudo tc filter add dev {self._client_device} parent ffff:fff2 u32 match ip sport 0x4000 0xc000 action mirred egress redirect dev {self._second_ifb}")
        
        return cmds

    def _get_delay_config(self, rtt, bottleneck_bw) -> List[str]:
        cmds:List[str] = []
        ## Calculate queue size for netem to ensure that we do not cause artifical loss while delaying packets
        limit = ((rtt/2) / 1000) * bottleneck_bw * pow(10,6) / 8 / 1514
        if limit < 1000:
            limit = 1000
        ## Additional safety margin
        limit *= 4
        limit = int(limit)

        ## We split the delay to both directions, assignning half of the delay to each of the two available ifb interfaces
        cmds.append(f"sudo tc qdisc add dev {self._first_ifb} root netem delay {rtt/2}ms limit {limit}")
        cmds.append(f"sudo tc qdisc add dev {self._second_ifb} root netem delay {rtt/2}ms limit {limit}")
        return cmds

    def _get_egress_base_config(self) -> List[str]:
        cmds:List[str] = []
        cmds.append(f"sudo tc qdisc add dev {self._egress_device} root handle {HTB_ROOT_HANDLE} htb default {self._defaultTrafficClass}")
        return cmds

    def _get_egress_traffic_classes_config(self) -> List[str]:
        cmds:List[str] = []
        for trafficClass in self._traffic_classes:
            cmds.append(f"sudo tc class add dev {self._egress_device} " + trafficClass.get_htb_config_commands())
            cmds.append(f"sudo tc qdisc add dev {self._egress_device} " + trafficClass.get_qdisc_config_commands())
            cmds.append(f"sudo tc filter add dev {self._egress_device} basic match 'meta(tc_index eq 0x{int(trafficClass.classid):x})' classid 20:{int(trafficClass.classid):x}")
        return cmds

    def _get_egress_config(self) -> List[str]:
        cmds:List[str] = []
        cmds.extend(self._get_egress_base_config())
        cmds.extend(self._get_egress_traffic_classes_config())
        return cmds

    def get_config_commands(self, rtt, bottleneck_bw, initial=True) -> Tuple[List[str], List[str], Tuple[List[str], List[str], List[str], List[str]]]:
        cmds:List[str] = []
        cmds_clear:List[str] = self._get_config_clear()
        cmds.extend(cmds_clear)
        cmds_general:List[str] = self._get_general_config()
        cmds.extend(cmds_general)
        cmds_delay_config:List[str] = self._get_delay_config(rtt=rtt,bottleneck_bw=bottleneck_bw)
        cmds.extend(cmds_delay_config)
        cmds_ingress:List[str] = self._get_ingress_config()
        cmds.extend(cmds_ingress)
        cmds_egress:List[str] = self._get_egress_config()
        cmds.extend(cmds_egress)
        return cmds, (cmds_clear, cmds_general, cmds_ingress, cmds_egress, cmds_delay_config)


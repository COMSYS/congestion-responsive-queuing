from abc import ABC, abstractmethod

HTB_ROOT_HANDLE = "20"
HTB_BOTTLENECK_CLASS_HANDLE = "FFFF"

class TrafficClass(ABC):
    @abstractmethod
    def __init__(self, bandwidth_limit_soft:int,  bandwidth_limit_hard:int, classid:str, prio:str) -> None:
        self.bandwidth_limit_soft:int = bandwidth_limit_soft
        self.bandwidth_limit_hard:int = bandwidth_limit_hard
        self.classid:str = classid
        self.prio:str = prio

    @abstractmethod
    def get_qdisc_config_commands(self) -> str:
        pass

    def get_htb_config_commands(self) -> str:
        return f"parent {HTB_ROOT_HANDLE}:{HTB_BOTTLENECK_CLASS_HANDLE} classid {HTB_ROOT_HANDLE}:{self.classid} htb rate {self.bandwidth_limit_soft}mbit ceil {self.bandwidth_limit_hard}mbit prio {self.prio} burst 100k"

class DropTail(TrafficClass):
    def __init__(self, 
                 bandwidth_limit_soft: int, 
                 bandwidth_limit_hard: int, 
                 classid: str, 
                 prio:str, 
                 limit=750000, ## In Bytes 
                 burst=1514, 
                 rate=20) -> None:
        
        super().__init__(bandwidth_limit_soft, bandwidth_limit_hard, classid, prio)
        self._rate = rate
        self._burst = burst
        self._limit = limit

    def get_qdisc_config_commands(self) -> str:
        return f"parent {HTB_ROOT_HANDLE}:{self.classid} handle {self.classid}: tbf limit {self._limit} burst {self._burst} rate {self._rate}Mbit"


    def set_limit(self, limit_in_bytes):
        self._limit = limit_in_bytes

class CoDel(TrafficClass):
    """https://man7.org/linux/man-pages/man8/tc-codel.8.html"""
    ### Set target according to this https://www.bufferbloat.net/projects/codel/wiki/Best_practices_for_benchmarking_Codel_and_FQ_Codel/
    def __init__(self, 
                 bandwidth_limit_soft:int,  
                 bandwidth_limit_hard:int, 
                 classid:str, 
                 prio:str, 
                 limit:int = 1000, ## In packets 
                 target:int = 0.5, 
                 interval:int = 20, 
                 ecn:bool = True, 
                 ce_threshold:int = 0) -> None:
        self._target = target
        self._interval = interval
        self._limit = limit
        self._ecn = ecn
        self._ce_threshold = ce_threshold
        super().__init__(bandwidth_limit_soft, bandwidth_limit_hard, classid, prio)

    def set_limit(self, limit_in_bytes):
        self._limit = int(limit_in_bytes / 1500)

    def get_qdisc_config_commands(self) -> str:
        return f"parent {HTB_ROOT_HANDLE}:{self.classid} handle {self.classid}: codel limit {self._limit} target {self._target}ms interval {self._interval}ms {'ecn' if self._ecn else 'noecn'}{f' ce_threshold {self._ce_threshold}' if self._ce_threshold != 0 else ''}"
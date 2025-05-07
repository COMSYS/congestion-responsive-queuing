from abc import ABC, abstractmethod
from .CC_Stacks import *
from .sshConnector import SSHConnector


class IPERF3_Config(ABC):
    @abstractmethod
    def __init__(self, implementation, device) -> None:
        self.implementation: CC_Stack = implementation
        self.device: SSHConnector = device

    @abstractmethod
    def __str__(self) -> str:
        return ""

class IPERF3_UDP_Server_Config(IPERF3_Config):
    def __init__(self, implementation, device: SSHConnector, server_port: int = 37337) -> None:
        self._server_port: int = server_port
        super().__init__(implementation, device)

    def __str__(self) -> str:
        return super().__str__()

class IPERF3_UDP_Client_Config(IPERF3_Config):
    def __init__(self, implementation, bitrate: int, startDelay: int, device: SSHConnector, target_ip: str, client_number:int, local_port: int, timeout, target_port: int = 37337) -> None:
        self.target_ip: str = target_ip
        self.target_port: int = target_port
        self.local_port: int = local_port
        self._startDelay_ms:int = startDelay
        self.client_number = client_number
        self._bitrate:int = bitrate
        self._timeout = timeout
        super().__init__(implementation, device)

    def __str__(self) -> str:
        return super().__str__()

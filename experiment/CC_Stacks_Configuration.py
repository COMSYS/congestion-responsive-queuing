from abc import ABC, abstractmethod
from . CC_Stacks import *
from enum import Enum
from functools import total_ordering
from . sshConnector import SSHConnector
import os

@total_ordering
class CC_ALGO(Enum):
    BBR = 0
    CUBIC = 1
    RENO = 8
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

class ECN_TYPE(Enum):
    NO_ECN = 0
    ECT_0 = 1
    ECT_1 = 2

class SPIN_TYPE(Enum):
    picoquic_spinbit_basic = 0  # default spin bit behavior, as specified in spin bit draft */
    picoquic_spinbit_on = 3     # Option used in test to avoid randomizing spin bit on/off */
    picoquic_spinbit_off = 4

class Stack_Config(ABC):
    @abstractmethod
    def __init__(self, 
                 implementation, 
                 stack_path,
                 local_output_path,
                 device:SSHConnector, 
                 cc_algo, 
                 ecn_type, 
                 spin_type:SPIN_TYPE = SPIN_TYPE.picoquic_spinbit_on, 
                 bidirectional:str = '0') -> None:
        self.implementation: CC_Stack = implementation
        self.stack_path: str = stack_path
        self.local_output_path: str = local_output_path
        self.device: SSHConnector = device
        self.cc_algo: CC_ALGO = cc_algo
        self.ecn_type: ECN_TYPE = ecn_type
        self._spin_type:SPIN_TYPE = spin_type
        self.bidirectional = bidirectional

    @abstractmethod
    def __str__(self) -> str:
        return "_".join([str(self.implementation), str(self.device), str(self.cc_algo), str(self.ecn_type)])

class Stack_Server_Config(Stack_Config):
    def __init__(self, 
                 certfolder,
                 file_location,
                 implementation, 
                 stack_path,
                 local_output_path,
                 device: SSHConnector, 
                 num_connections:int, 
                 transfer_amount, 
                 server_ip, 
                 server_port: int = 37337, 
                 cc_algo: CC_ALGO = CC_ALGO.BBR, 
                 ecn_type:ECN_TYPE = ECN_TYPE.ECT_0,  
                 spin_type:SPIN_TYPE = SPIN_TYPE.picoquic_spinbit_on, 
                 bidirectional:str = '0') -> None:
                
        self._server_port: int = server_port
        self._server_ip = server_ip
        self._transfer_amount = transfer_amount
        self._file_location: str = file_location

        self._cert_file: str = os.path.join(certfolder, "cert.pem")
        self._cert_key: str = os.path.join(certfolder, "key.pem")
        self.num_connections = num_connections
        super().__init__(implementation, stack_path, local_output_path, device, cc_algo, ecn_type, spin_type, bidirectional)

    def __str__(self) -> str:
        return super().__str__() + "_" + "_".join([str(self._server_port), str(self._file_location), str(self._cert_file), str(self._cert_key), str(self.num_connections)])


class Stack_Client_Config(Stack_Config):
    def __init__(self, 
                 implementation, 
                 stack_path,
                 local_output_path,
                 transfer_amount: int, 
                 startDelay: int, 
                 device: SSHConnector, 
                 target_ip: str, 
                 local_ip: str, 
                 client_number:int, 
                 local_port: int, 
                 target_port: int = 37337, 
                 cc_algo: CC_ALGO = CC_ALGO.BBR, 
                 ecn_type:ECN_TYPE = ECN_TYPE.ECT_0, 
                 spin_type:SPIN_TYPE = SPIN_TYPE.picoquic_spinbit_on, 
                 bidirectional:str = '0') -> None:
        self.target_ip: str = target_ip
        self.target_port: int = target_port
        self.local_ip: str = local_ip
        self.local_port: int = local_port
        self._transfer_amount: int = transfer_amount
        self._startDelay_ms:int = startDelay
        self.client_number = client_number
        super().__init__(implementation, stack_path, local_output_path, device, cc_algo, ecn_type, spin_type, bidirectional)

    def __str__(self) -> str:
        return super().__str__()


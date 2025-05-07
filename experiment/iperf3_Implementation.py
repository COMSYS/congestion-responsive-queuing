from abc import ABC, abstractmethod
from .iperf3_Configuration import IPERF3_UDP_Server_Config, IPERF3_UDP_Client_Config
from typing import List, Set

class IPERF3_Implementation(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @staticmethod
    @abstractmethod
    def get_run_command_client(config) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_run_command_server(config) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_client_log_file_path(stdout:str) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_server_log_file_paths(stdout:str) -> List[str]:
        pass

    @staticmethod
    @abstractmethod
    def stop_server_command() -> str:
        pass

    @staticmethod
    @abstractmethod
    def stop_client_command() -> str:
        pass

class IPERF_UDP(IPERF3_Implementation):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def get_run_command_client(config: IPERF3_UDP_Client_Config) -> str:
        return f"iperf3 -c {config.target_ip} -u -p {config.target_port} -t {config._timeout} --cport {config.local_port} -b {config._bitrate}M -R > {IPERF_UDP.get_client_log_file_path(config)}"

    @staticmethod
    def get_run_command_server(config: IPERF3_UDP_Server_Config) -> str:
        return f"iperf3 -s -p {config._server_port} -1 > {IPERF_UDP.get_server_log_file_paths(config)[0]}"
    
    @staticmethod
    def get_client_log_file_path(config: IPERF3_UDP_Client_Config) -> str:
        return f"{config.target_port}-{config.local_port}-iperf.txt"

    @staticmethod
    def get_server_log_file_paths(config: IPERF3_UDP_Server_Config) -> List[str]:
        file_names:Set[str] = set()
        return [f"{config._server_port}-iperf.txt"]

    @staticmethod
    def stop_server_command() -> str:
        return "pkill --signal SIGINT iperf3"

    @staticmethod
    def stop_client_command() -> str:
        return "pkill --signal SIGINT iperf3"
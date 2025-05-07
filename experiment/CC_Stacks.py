from abc import ABC, abstractmethod
from . CC_Stacks_Configuration import Stack_Client_Config, Stack_Server_Config
from typing import List, Set
import os

class CC_Stack(ABC):
    @abstractmethod
    def __init__(self) -> None:
        pass

    @staticmethod
    @abstractmethod
    def get_run_command_client(config: Stack_Client_Config) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_run_command_server(config: Stack_Server_Config) -> str:
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


class PICO_QUIC(CC_Stack):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def get_run_command_client(config: Stack_Client_Config) -> str:
        stack_path = config.stack_path
        type = "clientLocalPort"
        file_folder = "./req/"
        return f"{stack_path} {type} {config.target_ip} {config.target_port} {config.local_port} {config.cc_algo.value} {config._spin_type.value} {file_folder} {config._transfer_amount}MB"

    @staticmethod
    def get_run_command_server(config: Stack_Server_Config) -> str:
        stack_path = config.stack_path
        type = "server"
        return f"{stack_path} {type} {config._server_port} {config._cert_file} {config._cert_key} {config.cc_algo.value} {config._spin_type.value} {config._file_location}"

    @staticmethod
    def get_client_log_file_path(stdout:str) -> str:
        identifer = "Initial connection ID:"
        start_index = stdout.find(identifer) + len(identifer)
        end_index = stdout.find("\n", start_index)
        return stdout[start_index:end_index].strip() + ".client.qlog"

    @staticmethod
    def get_server_log_file_paths(stdout:str) -> List[str]:
        file_names:Set[str] = set()
        identifer = "New Connection - Initial cID:"
        start_index = 0
        while (start_index := stdout.find(identifer, start_index)) != -1:
            start_index += len(identifer)
            end_index = stdout.find("\n", start_index)
            file_names.add(stdout[start_index:end_index].strip() + ".server.qlog")
        return list(file_names)

    @staticmethod
    def stop_server_command() -> str:
        return "pkill --signal SIGINT picoquic"

    @staticmethod
    def stop_client_command() -> str:
        return "pkill --signal SIGINT picoquic"

class TCP(CC_Stack):

    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def get_run_command_client(config: Stack_Client_Config) -> str:
        stack_path = f"sudo {config.stack_path} client"
        if config.cc_algo.value == 0:
            tcp_cc_algo = "bbr"
        elif config.cc_algo.value == 1:
            tcp_cc_algo = "cubic"
        elif config.cc_algo.value == 8:
            tcp_cc_algo = "reno"
        else:
            print(f"CCA ({config.cc_algo}/{config.cc_algo.value}) not supported.")
            raise Exception
        
        return f"{stack_path} --congestion {tcp_cc_algo} --remote_address {config.target_ip}:{config.target_port} --local_address {config.local_ip}:{config.local_port} --volume {config._transfer_amount} --bidirectional {config.bidirectional} --output {os.path.join(config.local_output_path, str(config.client_number))}"


    @staticmethod
    def get_run_command_server(config: Stack_Server_Config) -> str:
        stack_path = f"sudo {config.stack_path} server"
        if config.cc_algo.value == 0:
            tcp_cc_algo = "bbr"
        elif config.cc_algo.value == 1:
            tcp_cc_algo = "cubic"
        elif config.cc_algo.value == 8:
            tcp_cc_algo = "reno"
        else:
            print(f"CCA ({config.cc_algo}/{config.cc_algo.value}) not supported.")
            raise Exception
       
        return f"{stack_path} --flows 1 --output {config.local_output_path} --local_address {config._server_ip}:{config._server_port}  --congestion {tcp_cc_algo} --bidirectional {config.bidirectional} --volume {config._transfer_amount}"



    @staticmethod
    def get_client_log_file_path(stdout:str) -> str:
        return ""

    @staticmethod
    def get_server_log_file_paths(stdout:str) -> List[str]:
        return [""]

    @staticmethod
    def stop_server_command() -> str:
        return "sudo pkill --signal SIGKILL -f custom-tcp"

    @staticmethod
    def stop_client_command() -> str:
        return "sudo pkill --signal SIGKILL -f custom-tcp"


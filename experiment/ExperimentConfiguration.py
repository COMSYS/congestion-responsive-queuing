from . ClassifierConfiguration import Classifier_Configuration
from . TrafficClasses import *
from . TC_Configuration import TC_Configuration
from . CC_Stacks_Configuration import Stack_Config, Stack_Client_Config, Stack_Server_Config
from . CC_Stacks import *
from . iperf3_Implementation import *
from experiment.CC_Stacks import TCP
from experiment.iperf3_Implementation import IPERF_UDP
from .sshConnector import SSHConnector

from time import sleep, time_ns
from typing import List, Tuple, Union
from fabric import Connection
from invoke import Result, exceptions, Promise, watchers
from multiprocessing import Value
import datetime
import os
import logging
import subprocess
import json
import signal
import pandas as pd

formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

tmp_folder = os.path.join(os.path.dirname(__file__), "tmp")

not_seen = Value('b', True)
not_seen_tcp_server = Value('b', True)
not_seen_tcp_client = Value('b', True)

class WatchDogException(Exception):
    """WatchDog timer expired!"""
    pass

def handler(signum, frame):
    print("Watchdog timer expired!")
    raise WatchDogException("Process terminated by Watchdog due to timeout")

def setup_logger(name:str, log_file_path:str, store_in_file:bool = True) -> logging.Logger:
    logger = logging.getLogger(name=name)
    logger.setLevel(logging.DEBUG)
    if store_in_file:
        handler = logging.FileHandler(log_file_path)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def reset_logger(logger):
    if logger.handlers:
        logger.handlers[0].flush()
        print(f"Reset Logger {logger.name}")
        logger.handlers[0].stream.close()
        logger.removeHandler(logger.handlers[0])

global_logger:logging.Logger = setup_logger("GlobalLogger", os.path.join(os.path.dirname(__file__), "global-experiment.log"))
print(f"Logger: {os.path.dirname(__file__)} + .log")

def interrupt_process_by_name(shell: Connection, name: str) -> Union[Result, None]:
    try:
        return shell.run(f"sudo pkill --signal SIGINT {name}")
    except:
        return None

def create_folder(path:str):
    if path is None:
        raise Exception("Empty Folder Name")
    folder_name = "result_" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
    path = os.path.join(path, folder_name)
    os.mkdir(path)
    return path

class TC_QUEUE():

    def __init__(self, q_type, handle, dev, parent_root, parent_id):
        self.q_type = q_type
        self.handle = handle
        self.dev = dev
        self.parent_root = parent_root
        self.parent_id = parent_id

    def __str__(self):
        if self.parent_id:
            return ",".join([self.q_type, self.handle, self.dev, self.parent_root, self.parent_id])
        else:
            return ",".join([self.q_type, self.handle, self.dev, self.parent_root])

class TC_STATS():

    def __init__(self, sent_bytes, sent_packets, dropped_packets, overlimits, requeues):
        self.sent_bytes = sent_bytes
        self.sent_packets = sent_packets
        self.dropped_packets = dropped_packets
        self.overlimits = overlimits
        self.requeues = requeues
        self.maxpacket = None
        self.ecn_mark = None
        self.drop_overlimit = None

    def __str__(self):
        if self.maxpacket:
                return ",".join([self.sent_bytes, self.sent_packets, self.dropped_packets, self.overlimits, self.requeues, self.maxpacket, self.ecn_mark, self.drop_overlimit])
        else:
            return ",".join([self.sent_bytes, self.sent_packets, self.dropped_packets, self.overlimits, self.requeues])


def qdisc_s_show_to_df(stdout):

    df_result = pd.DataFrame()
    ADD_TO_RESULT = False

    for line in stdout.split("\n"):

        if line.startswith("qdisc"):
            linesplit = line.split()
            q_type = linesplit[1]
            handle = linesplit[2]
            dev = linesplit[4]
            parent_root = linesplit[5]
            parent_id = None
            if parent_root == "parent":
                parent_id = linesplit[6]

            current_queue = TC_QUEUE(q_type, handle, dev, parent_root, parent_id)

        elif line.startswith(" Sent"):
            linesplit = line.split()
            sent_bytes = linesplit[1]
            sent_packets = linesplit[3]
            dropped_packets = linesplit[6].replace(",","")
            overlimits = linesplit[8]
            requeues = linesplit[10].replace(")","")
            current_stats = TC_STATS(sent_bytes, sent_packets, dropped_packets, overlimits, requeues)

            if current_queue.q_type != "codel":
                ADD_TO_RESULT = True

        elif line.startswith("  maxpacket"):

            linesplit = line.split()

            if current_stats:
                current_stats.maxpacket = linesplit[1]
                current_stats.ecn_mark = linesplit[3]
                current_stats.drop_overlimit = linesplit[5]
                ADD_TO_RESULT = True

            else:
                raise Exception("This should not happen")


        if ADD_TO_RESULT:
            if df_result.empty:
                df_result = pd.DataFrame([{"Device": current_queue.dev,
                                            "Handle": current_queue.handle,
                                            "Queue": current_queue.q_type,
                                            "Attach": current_queue.parent_root,
                                            "Parent-ID": current_queue.parent_id,
                                            "Bytes Sent": current_stats.sent_bytes,
                                            "Packets Sent": current_stats.sent_packets,
                                            "Packets Dropped": current_stats.dropped_packets,
                                            "Overlimits": current_stats.overlimits,
                                            "Requeues": current_stats.requeues,
                                            "CoDel MaxPacket": current_stats.maxpacket,
                                            "CoDel ECN_Mark": current_stats.ecn_mark,
                                            "CoDel Drop_OverLimit": current_stats.drop_overlimit}])
            else:
                df_result.loc[len(df_result)] = [current_queue.dev,
                                                    current_queue.handle,
                                                    current_queue.q_type,
                                                    current_queue.parent_root,
                                                    current_queue.parent_id,
                                                    current_stats.sent_bytes,
                                                    current_stats.sent_packets,
                                                    current_stats.dropped_packets,
                                                    current_stats.overlimits,
                                                    current_stats.requeues,
                                                    current_stats.maxpacket,
                                                    current_stats.ecn_mark,
                                                    current_stats.drop_overlimit]
            current_queue = current_stats = None
            ADD_TO_RESULT = False
    return df_result




class ConfigurationError(Exception):
    def __init__(self, command_list, failed_command, raised_exception):
        self.command_list = command_list
        self.failed_command = failed_command
        self.raised_exception = raised_exception

    def __str__(self) -> str:
        return f"Command list: f{self.command_list}\nFailed command: {self.failed_command}\nRaised exception: {self.raised_exception}"

class PreperationError(Exception):
    def __init__(self, device, file, raised_exception):
        self.device = device
        self.file = file
        self.raised_exception = raised_exception

    def __str__(self) -> str:
        return f"Could not create file <self.device> on device: {self.device}\nRaised exception: {self.raised_exception}"
    
class MyWatcher(watchers.StreamWatcher):
    def __init__(self):                                                         
        super().__init__()                                                      
        self.seen = False    

    def submit(self, stream):
        global not_seen 
        if not self.seen and "Ready:" in stream:
            # Return a response indicating that the pattern is found
            self.seen = True
            not_seen.value = False
            print("Classifier started")
            return ["Classifier gestartet"]
        else:
            # print(stream)
            # self.seen = False
            return []
        
class MyWatcherTCPServer(watchers.StreamWatcher):
    def __init__(self):                                                         
        super().__init__()                                                      
        self.seen = False    

    def submit(self, stream):
        global not_seen_tcp_server
        if not self.seen and "Ready" in stream:
            # Return a response indicating that the pattern is found
            self.seen = True
            not_seen_tcp_server.value = False
            print("TCP Server logging started")
            return ["TCP Server logging started"]
        else:
            # print(stream)
            # self.seen = False
            return []
        
class MyWatcherTCPClient(watchers.StreamWatcher):
    def __init__(self):                                                         
        super().__init__()                                                      
        self.seen = False    

    def submit(self, stream):
        global not_seen_tcp_client
        if not self.seen and "Ready" in stream:
            # Return a response indicating that the pattern is found
            self.seen = True
            not_seen_tcp_client.value = False
            print("TCP Client logging started")
            return ["TCP Client logging started"]
        else:
            # print(stream)
            # self.seen = False
            return []

QUIC_Client_Promise_Tuple = Tuple[Stack_Client_Config, Union[Result, None]]
QUIC_Server_Promise_Tuple = Tuple[Stack_Server_Config, Union[Result, None]]
class ExperimentConfiguration:
    def __init__(self, 
                 result_folder_path:str, 
                 local_tmp_folder_path:str,
                 tc_viz_path:str,
                 traffic_files_path:str,
                 tc_config:TC_Configuration, 
                 classifier_config:Classifier_Configuration, 
                 rtt:int, 
                 bottleneck_bw:int,
                 server_list:List[Stack_Server_Config], client_list:List[Stack_Client_Config], 
                 bottleneck_router:SSHConnector, 
                 load1:SSHConnector,
                 load2:SSHConnector,
                 client:SSHConnector,
                 interfaces:[str],
                 iterations:int = 30, deploy_QUIC_classifier:bool = True, only_UDP:bool = True, tcp_dump:bool = True, tcp_dump_options:str = "", let_nocc_finish:bool = False, deploy_TCP_classifier:bool = False, load_qlog_data:bool = True, watch_dog_timeout_s:int = 900):
        self._iterations: int = iterations
        self._rtt:int = rtt
        self._bottleneck_bw: int = bottleneck_bw
        self._tc_config: TC_Configuration = tc_config
        self._classifier_config:Classifier_Configuration = classifier_config
        self._server_list: List[Stack_Server_Config] = server_list
        self._client_start_list: List[Stack_Client_Config] = client_list
        self._bottleneckrouter: SSHConnector = bottleneck_router
        self._deploy_QUIC_classifier:bool = deploy_QUIC_classifier
        self._deploy_TCP_classifier:bool = deploy_TCP_classifier
        self._only_UDP:bool = only_UDP
        self._tcp_dump:bool = tcp_dump
        self._tcp_dump_options:str = tcp_dump_options
        self._result_folder_path:str = result_folder_path.rstrip("/")
        self._let_nocc_finish:bool = let_nocc_finish
        self._load_qlog_data: bool = load_qlog_data
        self._watch_dog_timeout_s: int = watch_dog_timeout_s
        self._load1 = load1
        self._load2 = load2
        self._client = client
        self._interfaces = interfaces
        self._local_tmp_folder_path = local_tmp_folder_path
        self._tc_viz_path = tc_viz_path
        self._traffic_files_path = traffic_files_path

    def resetSshConnections(self):
        if self._load1:
            self._load1.reset_connection()
        if self._load2:
            self._load2.reset_connection()
        if self._client:
            self._client.reset_connection()
        if self._client:
            self._client.reset_connection()

    def startSshConnections(self):
        if self._load1:
            self._load1.start_connection()
        if self._load2:
            self._load2.start_connection()
        if self._client:
            self._client.start_connection()
        if self._client:
            self._client.start_connection()



    def __str__(self) -> str:
        ";".join([
                str(self._iterations), 
                self._tc_config.__str__(), 
                self._classifier_config.__str__(),
                ",".join(server.__str__() for server in self._server_list), 
                ",".join(client.__str__() for client in self._client_start_list), 
                self._bottleneckrouter.__str__(), 
                "ifb1", 
                "True" if self._deploy_QUIC_classifier else "False", 
                "True" if self._deploy_TCP_classifier else "False", 
                "True" if self._only_UDP else "False", 
                "True" if self._tcp_dump else "False", 
                self._tcp_dump_options, 
                self._result_folder_path
                ])
        return str(self._iterations)

    def _prepare_classifier(self, logger):
        
        classifier_files = [("classifier.c", self._classifier_config.get_c_code()), 
                            ("tracepoint_ecn.c", self._classifier_config.get_tracepoint_code()),
                            ("tracepoint_drops.c", self._classifier_config.get_loss_trace_code()),
                            ("classifier.py", self._classifier_config.get_py_code()),
                            ("tracepoint_tcp.c", self._classifier_config.get_tracepoint_code_tcp_client())]

        for classifier_file, source_code in classifier_files:

            while os.path.exists(os.path.join(tmp_folder, classifier_file)):
                print(f"{classifier_file} exists.")
                logger.info("{classifier_file} exists.")
                sleep(1)
            with open(os.path.join(tmp_folder, classifier_file), "wt") as file:
                file.write(source_code)
            self._bottleneckrouter.get_connection().put(os.path.join(tmp_folder, classifier_file), os.path.join(self._local_tmp_folder_path, classifier_file))
            os.remove(os.path.join(tmp_folder, classifier_file))


    def _prepare_TCP_logging_script(self):
        for client in self._client_start_list:
            if (isinstance(client.implementation, TCP)):
                print("Deploy TCP logging script to", os.path.join(tmp_folder, "tcp_probe_bpf.py"))
                with open(os.path.join(tmp_folder, "tcp_probe_bpf.py"), "wt") as file:
                    with open("experiment/tcp_probe_bpf.py") as f:
                        file.write("".join(f.readlines()))
                client.device.get_connection().put(os.path.join(tmp_folder, "tcp_probe_bpf.py"), os.path.join(self._local_tmp_folder_path, "tcp_probe_bpf.py"))
        for server in self._server_list:
            if (isinstance(server.implementation, TCP)):
                print("Deploy TCP logging script to", os.path.join(tmp_folder, "tcp_probe_bpf.py"))
                with open(os.path.join(tmp_folder, "tcp_probe_bpf.py"), "wt") as file:
                    with open("experiment/tcp_probe_bpf.py") as f:
                        file.write("".join(f.readlines()))
                #with server.device.get_connection() as connection:
                server.device.get_connection().put(os.path.join(tmp_folder, "tcp_probe_bpf.py"), os.path.join(self._local_tmp_folder_path, "tcp_probe_bpf.py"))
        
    def _start_measurements(self, device:Union[SSHConnector, None] = None, deploy_QUIC_classifier:bool = True, filename_bpf:str = "ebpf_classifier_log.csv", only_UDP:bool = True, filename_tcpdump:str = "tcpdump_bottleneck.pcap", tcp_dump:Union[bool, None] = None, tcp_dump_options:str = "-s 50", deploy_TCP_classifier:bool = False, filename_bpf_tcp:str = "TCP_ebpf_classifier_log.csv") -> Tuple[Union[Promise, None], Union[Promise, None]]:
        if device is None:
            device = self._bottleneckrouter
        if tcp_dump is None:
            tcp_dump = self._tcp_dump
        if tcp_dump_options is None:
            tcp_dump_options = self._tcp_dump_options

        def callback(stream, matcher):
            print("Classifier started!")
            matcher.proc.stop()

        promise_bpf:Union[Promise, None] = None
        promise_tcpdump:Union[Promise, None] = None
        if tcp_dump:
            #with device.get_connection() as connection:  
            promise_tcpdump = device.get_connection().run(f"sudo tcpdump -U -i {self._tc_config._egress_device} -w {filename_tcpdump} {tcp_dump_options}", asynchronous=True)

        # there is only one classifier 
        if deploy_QUIC_classifier or deploy_TCP_classifier:
            print("Start Classifier")
            watcher = MyWatcher()
            #with device.get_connection() as connection:  
            promise_bpf = device.get_connection().run(f"sudo python3 {os.path.join(self._local_tmp_folder_path, "classifier.py")} {filename_bpf}", asynchronous=True, watchers = [watcher], pty=True)
            global not_seen
            while not_seen.value: # trigger watcher to read input
                responses = watcher.submit("") 
                sleep(1)

            not_seen.value = True

        return promise_bpf, promise_tcpdump

    def _startClients(self, iteration_logger:logging.Logger) -> List[QUIC_Client_Promise_Tuple]:
        logging_started = False
        self._client_start_list.sort(key=lambda client: client._startDelay_ms)
        clientPromises:List[QUIC_Client_Promise_Tuple] = []
        startTime:int = time_ns()

        time_since_last_responsive = 0
        last_responsive = time_ns()

        try:
            for client in self._client_start_list:

                if client._startDelay_ms == 0:
                    last_responsive = time_ns()
                    time_since_last_responsive = 0

                else:
                    time_since_last_responsive = time_ns() - last_responsive
                    if client._startDelay_ms * pow(10,6) > time_since_last_responsive:
                        sleep((client._startDelay_ms * pow(10,6) - time_since_last_responsive)/pow(10,9))

                promise:Promise = client.device.get_connection().run(client.implementation.get_run_command_client(client), asynchronous=True, env={'PATH':'/home/test/.cargo/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin', 'QLOGDIR':'/home/test', 'SSLKEYLOGFILE': '/home/test/sslkeys/new'})
                print(f"_startClients on {client.device.local_ip}: ", client.implementation.get_run_command_client(client))               
                clientPromises.append((client, promise))
            return clientPromises 
        except WatchDogException as e:
            raise
        except Exception as e:
            print(e)
            iteration_logger.critical(e)
            raise e
        
    def _start_TCP_logging_clients(self) -> List[Union[Promise, None]]:
        client_promises:List[Union[Promise, None]] = []
        # Start eBPF logging for TCP Clients
        # start a logging per associated client        
        for client in self._client_start_list:
                if (isinstance(client.implementation, TCP)):
                    for server_config in self._server_list:
                        if isinstance(server_config.implementation, TCP) and client.target_ip == server_config.device.local_ip and server_config._server_port == client.target_port:
                            promise_tcp_client:Union[Promise, None] = None
                            print("Start TCP client logging")
                            saddr = client.device.local_ip
                            dport = client.target_port
                            sport = client.local_port
                            filename = f"{client.client_number}_TCPlog_client.csv"

                            watcher = MyWatcherTCPClient()
            
                            promise_tcp_client = client.device.get_connection().run(f'sudo python3 {os.path.join(self._local_tmp_folder_path, "tcp_probe_bpf.py")} --filter "(saddr {saddr}) and (sport {sport})" --output {filename}', asynchronous=True, watchers = [watcher], pty=True)
                            global not_seen_tcp_client
                            while not_seen_tcp_client.value: # trigger watcher to read input
                                responses = watcher.submit("") 
                                sleep(1)

                            not_seen_tcp_client.value = True

                            client_promises.append(promise_tcp_client)

                            client.device.get_connection().run("sudo ip tcp_metrics flush")

        return client_promises

    def _stop_TCP_logging_clients(self):  
        # get clients for which there are running TCP loggers  
        for client in self._client_start_list:
                if (isinstance(client.implementation, TCP)):
                    #with client.device.get_connection() as connection:
                    interrupt_process_by_name(client.device.get_connection(), "tcp_probe_bpf.py")
                break

    def _join_TCP_logging_clients_promises(self, client_promises:List[Union[Promise, None]], iteration_logger:logging.Logger, folder_path:str):
        for bpf_pro_tcp, index in enumerate(client_promises):
            if isinstance(bpf_pro_tcp, Promise):
                try:
                    print("------------------------- TRY JOIN CLIENT PROMISE")
                    bpf_result = bpf_pro_tcp.join()
                except WatchDogException as e:
                    # stop the whole processing and let the experiment's exception block handle the exception
                    raise
                except Exception as e:
                    iteration_logger.critical(e)
                    raise e
                
                with open(folder_path + f"TCP_client_log_{index}.log", "w") as std_class:
                    std_class.write(bpf_result.stdout)

    def _startServers(self) -> List[QUIC_Server_Promise_Tuple]:
        serverPromises:List[QUIC_Server_Promise_Tuple] = []
        for server_config in self._server_list:
            cmd:str = server_config.implementation.get_run_command_server(server_config)
            #with server_config.device.get_connection() as connection:
            print(f"_startServers on {server_config.device.local_ip}:  {server_config.implementation.get_run_command_server(server_config)}")
            promise:Promise = server_config.device.get_connection().run(cmd, asynchronous=True, env={'PATH':'/home/test/.cargo/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin', 'QLOGDIR':'/home/test', 'SSLKEYLOGFILE': '/home/test/sslkeys/new'})
            #sleep(0.1)
            serverPromises.append((server_config, promise))
        return serverPromises

    def _start_TCP_logging_servers(self) -> List[Union[Promise, None]]:
        server_promises:List[Union[Promise, None]] = []        
        for server_config in self._server_list:
            for client_config in self._client_start_list:
                print("Start TCP logging for server")
                if isinstance(client_config.implementation, TCP) and client_config.target_ip == server_config.device.local_ip and server_config._server_port == client_config.target_port:
                    promise_tcp_server:Union[Promise, None] = None
                    print("Start TCP server")
                    saddr = server_config.device.local_ip
                    sport = server_config._server_port
                    dport = client_config.local_port
                    filename = f"{client_config.client_number}_TCPlog_server.csv"

                    watcher = MyWatcherTCPServer()
                    #with server_config.device.get_connection() as connection:
                    promise_tcp_server = server_config.device.get_connection().run(f'sudo python3 {os.path.join(self._local_tmp_folder_path, "tcp_probe_bpf.py")} --filter "(saddr {saddr}) and (dport {dport})" --output {filename}', asynchronous=True, watchers = [watcher], pty=True)
                    global not_seen_tcp_server
                    while not_seen_tcp_server.value: # trigger watcher to read input
                        responses = watcher.submit("") 
                        sleep(1)

                    not_seen_tcp_server.value = True
                    server_promises.append(promise_tcp_server)
                    server_config.device.get_connection().run("sudo ip tcp_metrics flush")

        return server_promises
    
    def _stop_TCP_logging_servers(self):
        for server in self._server_list:
                if isinstance(server.implementation, TCP):
                    interrupt_process_by_name(server.device.get_connection(), "tcp_probe_bpf.py")
                break

    def _join_TCP_logging_servers_promises(self, server_promises:List[Union[Promise, None]], iteration_logger:logging.Logger, folder_path:str):
        for bpf_pro_tcp, index in enumerate(server_promises):
            if isinstance(bpf_pro_tcp, Promise):
                try:
                    bpf_result = bpf_pro_tcp.join()
                except WatchDogException as e:
                    raise
                except Exception as e:
                    iteration_logger.critical(e)
                    raise e
                
                with open(folder_path + f"TCP_server_log_{index}.log", "w") as std_class:
                    std_class.write(bpf_result.stdout)

    def _configure_tc(self, logger):
        cmds:List[str]
        cmds_clear:List[str]
        cmds_ingress:List[str]
        cmds_egress:List[str]
        cmds_ifb:List[str]
        cmds, (cmds_clear, cmds_general, cmds_ingress, cmds_egress, cmds_ifb) = self._tc_config.get_config_commands(self._rtt, self._bottleneck_bw)
        print("=== Clear ====")
        for com in cmds_clear:
            res = None
            try:
                res:Union[Result, None] = self._bottleneckrouter.get_connection().run(com, hide=True)
                print(com)
            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                if res is not None and res.stderr == "Error: Cannot delete qdisc with handle of zero.":
                    logger.info(f"Qdisc already empty: {com}")
                else:
                    if "ifb" in com:
                        pass
                    else:
                        logger.warning(f"Initial cleanup: could not clean tc-config: {com}")
                        logger.info(e.__str__)
        
        print("=== General ====")
        for com in cmds_general:
            try:
                print(com)
                #with self._bottleneckrouter.get_connection() as connection:
                self._bottleneckrouter.get_connection().run(com, hide=True)
            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                logger.info(f"Configuration already done: {com}")
                pass

        logger.info("Egress configuration: " + str(cmds_egress))
        print("=== Egress ====")
        for com in cmds_egress:
            try:
                print(com)
                #with self._bottleneckrouter.get_connection() as connection:
                self._bottleneckrouter.get_connection().run(com)
            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                logger.error(f"Could not configure tc on egress: {com}")
                logger.info(cmds_egress)
                logger.info(e.__str__)
                raise ConfigurationError(cmds_egress, com, e)

        print("=== Ingress ====")
        for com in cmds_ingress:
            try:
                print(com)
                #with self._bottleneckrouter.get_connection() as connection:
                self._bottleneckrouter.get_connection().run(com)
            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                logger.error(f"Could not configure tc on ingress: {com}")
                logger.info(cmds_ingress)
                logger.info(e.__str__)
                raise ConfigurationError(cmds_ingress, com, e)
           
        print("=== IFB ====")   
        for com in cmds_ifb:
            try:
                print(com)
                #with self._bottleneckrouter.get_connection() as connection:
                self._bottleneckrouter.get_connection().run(com, echo=False)
            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                logger.error(f"Could not configure delay on ifb: {com}")
                logger.info(cmds_ifb)
                logger.info(e.__str__)
                raise ConfigurationError(cmds_ingress, com, e)

    def _clear_tc(self, logger):
        cmds_clear:List[str]
        print("Clear tc")
        _, (cmds_clear, _, _, _, _) = self._tc_config.get_config_commands(self._rtt, self._bottleneck_bw, initial=False)
        for com in cmds_clear:
            res = None
            try:
                #with self._bottleneckrouter.get_connection() as connection:
                res:Union[Result, None] = self._bottleneckrouter.get_connection().run(com, hide=True)

            except (exceptions.UnexpectedExit, exceptions.Failure, exceptions.ThreadException) as e:
                if res is not None and res.stderr == "Error: Cannot delete qdisc with handle of zero.":
                    logger.info(f"Qdisc already empty: {com}")
                else:
                    logger.warning(f"After run cleanup: Could not clean tc-config: {com}")
                    logger.info(e.__str__)


    def _get_tc_debug(self, logger, folder_path):
        
        print("Get TC Debug Information")
        res = None
        try:
            res:Union[Result, None] = self._bottleneckrouter.get_connection().run("tc -s qdisc show", hide=True)
        except Exception as e:
            print(e)
            raise e
        queue_stats = qdisc_s_show_to_df(res.stdout)
        queue_stats.to_csv(os.path.join(folder_path, "queue-stats.csv"))

        for interface in self._interfaces:

            FILE_NAME = os.path.join(self._local_tmp_folder_path, f"{interface}.png")
            LOCAL_FILENAME = os.path.join(folder_path, f"{interface}.png")
            COMMAND = f"python3 {os.path.join(self._tc_viz_path, "tcviz.py")} {interface} | dot -Tpng > {FILE_NAME}"

            res = None
            try:
                res:Union[Result, None] = self._bottleneckrouter.get_connection().run(COMMAND, hide=True)
                self._bottleneckrouter.get_connection().get(remote=FILE_NAME, local=LOCAL_FILENAME)
                self._bottleneckrouter.get_connection().run(f"sudo rm {FILE_NAME}")
            except Exception as e:
                print(e)
                raise e    

    def _create_files(self, servers: List[SSHConnector], filesizes: List[int], implementations):
        for server in set(servers):
            try:
                server.get_connection().run(f"rm {os.path.join(self._traffic_files_path, '*')}")
            except Exception as e:
                print(e)
                pass
        all_promises = []
        for filesize in filesizes:
            try:
                for current_server in set(servers):
                    try:
                        print(f"Create download file of size {filesize} on server {current_server.local_ip}.")
                        promise:Promise = current_server.get_connection().run(f"head -c {filesize}M </dev/urandom > {os.path.join(self._traffic_files_path, f'{filesize}MB')}", asynchronous=True)
                        all_promises.append((promise,(filesize,current_server.local_ip)))
                    except Exception as e:
                        raise PreperationError(server, filesize.__str__, e)
            except Exception as e:
                raise PreperationError("local", filesize.__str__, e) 

        for promise, (filesize, host) in all_promises:
            try:
                promise.join()
            except Exception as e:
                print(e)
                print(f"Creating download file of size {filesize} on server {host} failed.")
                raise PreperationError("local", filesize.__str__, e) 
            else:
                print(f"Finished creating download file of size {filesize} on server {host}.")


    def _prepare(self, logger):
        servers:List[SSHConnector] = [serverConfig.device for serverConfig in sorted(self._server_list, key=lambda x: x._server_port)]
        implementations = [serverConfig.implementation for serverConfig in sorted(self._server_list, key=lambda x: x._server_port)]
        file_sizes:List[int] = list({clientConfig._transfer_amount for clientConfig in self._client_start_list if clientConfig.__class__.__name__ != "IPERF3_UDP_Client_Config"})
        logger.info("Next: create files on servers.")
        self._create_files(servers=servers, filesizes=file_sizes, implementations=implementations)
        logger.info("Next: prepare classifier.")
        self._prepare_classifier(logger)
        if self._deploy_TCP_classifier:
            logger.info("Next: prepare TCP logging script.")
            self._prepare_TCP_logging_script()

    @staticmethod
    def _join_client_promises(promises:List[QUIC_Client_Promise_Tuple], let_nocc_finish:bool) -> List[QUIC_Client_Promise_Tuple]:
        results:List[QUIC_Client_Promise_Tuple] = []
        error:bool = False

        raiseWatchDog = False


        client_indexing = {}
        for index, promise in enumerate(promises):
            client_indexing[index] = {
                "joined": False,
                "UDP": isinstance(promise[0].implementation, IPERF_UDP)
            }

        print("Start a flexible while loop to iteratively stop the processes once they become stoppable")
        while not all([client_indexing[index]["joined"] for index in client_indexing.keys() if not(client_indexing[index]["UDP"])]):
            
            for index in client_indexing.keys():
                
                promise = promises[index]
                if not client_indexing[index]["joined"] and not client_indexing[index]["UDP"]:
                    if not promise[1].runner.process_is_finished:
                        pass
                    else:

                        try:
                            print(f"Join: {promise[0].implementation}")
                            results.append((promise[0], promise[1].join()))
                            client_indexing[index]["joined"] = True
                        except WatchDogException as e:
                            raiseWatchDog = True
                            break
                        except Exception as e:
                            print(e)
                            results.append((promise[0], None))
                            raise e

                        else:
                            print(f"{promise[0].implementation} complete.")
            sleep(1)

        for promise in promises:
            if isinstance(promise[0].implementation, IPERF_UDP) and not let_nocc_finish:
                try:
                    print("Try to stop IPERF_UDP client")
                    promise[0].device.get_connection().run(promise[0].implementation.stop_client_command())
                    results.append((promise[0], promise[1].join()))
                except WatchDogException as e:
                    raise
                except exceptions.UnexpectedExit as e:
                    if "iperf3: interrupt - the client has terminated" in str(e.result):
                        pass
                    elif "pkill --signal SIGINT iperf3" in e.__str__() and "Exit code: 1" in e.__str__():
                        print("IPERF_UDP client stopped by SIGINT command.")
                        pass
                    else:
                        print("IPERF_UDP client stopping did not work properly.")
                        print(e)
                    results.append((promise[0], None))    

        if raiseWatchDog:
            raise WatchDogException

        return results

    @staticmethod
    def _join_server_promises(promises:List[QUIC_Server_Promise_Tuple]) -> List[QUIC_Server_Promise_Tuple]:
        results:List[QUIC_Server_Promise_Tuple] = []
        error:bool = False
        raiseWatchDog = False

        for promise in promises:

            try:
                results.append((promise[0], promise[1].join()))
            except exceptions.UnexpectedExit as e:
                if isinstance(promise[0].implementation, IPERF_UDP):
                    if "iperf3: interrupt - the server has terminated" in str(e.result):
                        pass
                    else:
                        print("Join not complete for IPERF Udp")
                        print(e)
                        error = True
                    results.append((promise[0], None))
                else:
                    print(f"Join not complete for {promise[0].implementation}")
                    print(e)
                    results.append((promise[0], None))
                    error = True
                pass
            except WatchDogException as e:
                print(f"Watchdog triggered: {e}")
            except Exception as e:
                print("Join not complete")
                print(e)
                results.append((promise[0], None))
                error = True

        for promise in promises:
            try:
                promise[0].device.get_connection().run(promise[0].implementation.stop_server_command())
            except:
                pass

        if raiseWatchDog:
            raise WatchDogException

        return results

    @staticmethod
    def _dump_quic_data(path:str, stack_config:Stack_Config, res:Result):
        with open(path + "config", "w") as file:
            file.write(stack_config.__str__())
        with open(path + "stdout", "w") as file:
            file.write(res.stdout)
        with open(path + "stderr", "w") as file:
            file.write(res.stderr)
        with open(path + "cmd", "w") as file:
            file.write(res.command)


    def kill_everything(self):

        for server in self._server_list:
            try:
                server.device.get_connection().run(server.implementation.stop_server_command()) 
            except:
                pass

        for client in self._client_start_list:
            try:
                client.device.get_connection().run(client.implementation.stop_client_command())        
            except:
                pass

        interrupt_process_by_name(self._bottleneckrouter.get_connection(), "python")
        interrupt_process_by_name(self._bottleneckrouter.get_connection(), "tcpdump")    


    def run(self, json_obj, filename_bpf:str = "ebpf_classifier_log.csv", filename_tcpdump:str = "tcpdump_bottleneck.pcap", filename_bpf_tcp:str = "TCP_ebpf_classifier_log.csv"):
        start_time = datetime.datetime.now()
        try:
            os.makedirs(self._result_folder_path, exist_ok=False)
        except:
            self._result_folder_path = self._result_folder_path + "__" + str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
            os.makedirs(self._result_folder_path, exist_ok=False)
        finally:
            self._result_folder_path = self._result_folder_path + "/"

        logger = setup_logger("Experiment", self._result_folder_path + "log")

        with open(self._result_folder_path + "configs.json", 'w') as f:
            json.dump(json_obj, f, indent=4)

        try:
            self._prepare(logger)
        except Exception as e:
            logger.critical("Could not do overall experiment preparation.")
            logger.info(f"Experiment: {self._result_folder_path}\n" + e.__str__())
            reset_logger(logger) 
            return

        for iteration in range(self._iterations):
            logger.info(f"Start iteration {iteration:03}")
            print(f"Start iteration {iteration:03}")
            print(f" Current time: {datetime.datetime.now()}, start time for this parameter configuration: {start_time}")
            print("Reset all ssh connections.")
            self.resetSshConnections()
            self.startSshConnections()
            sleep(1)

            iteration_logger = None

            client_TCP_logging_promises:List[Union[Promise, None]] = [] 
            server_TCP_logging_promises:List[Union[Promise, None]] = []  
            processes = []
            List[Union[Promise, None]]
            try:
                folder_path = os.path.join(self._result_folder_path, f"iter_{iteration:03}/")
                os.mkdir(folder_path)
                iteration_logger = setup_logger("Iteration", folder_path + "log")

                print("Start servers")
                if self._deploy_TCP_classifier:
                    server_TCP_logging_promises = self._start_TCP_logging_servers()
                server_promises = self._startServers()
                processes.append(server_promises)
                
                print("Configure TC before experiment iteration.")
                self._configure_tc(iteration_logger)
                print("Start measurements")
                bpf_pro, tcp_dump_pro = self._start_measurements(deploy_QUIC_classifier=self._deploy_QUIC_classifier, filename_bpf="ebpf_classifier_log.csv", only_UDP=self._deploy_QUIC_classifier, tcp_dump=self._tcp_dump, filename_tcpdump="tcpdump_bottleneck.pcap", deploy_TCP_classifier=self._deploy_TCP_classifier, filename_bpf_tcp = "TCP_ebpf_classifier_log.csv")
                
                print("Start clients.")
                if self._deploy_TCP_classifier:
                    client_TCP_logging_promises = self._start_TCP_logging_clients()
                client_promises:List[QUIC_Client_Promise_Tuple] = self._startClients(iteration_logger)
                processes.append(client_promises)
                
                signal.signal(signal.SIGALRM, handler)
                signal.alarm(self._watch_dog_timeout_s)

                print("wait for completion of clients")
                sleep(5)

                client_results:List[QUIC_Client_Promise_Tuple] = ExperimentConfiguration._join_client_promises(client_promises, self._let_nocc_finish)
                print("Let clients completly stop and then stop measurements before stopping the servers")
                sleep(1)

                self._join_TCP_logging_clients_promises(client_TCP_logging_promises, iteration_logger, folder_path)
                
                interrupt_process_by_name(self._bottleneckrouter.get_connection(), "python")
                interrupt_process_by_name(self._bottleneckrouter.get_connection(), "tcpdump")     

                if self._deploy_TCP_classifier:
                    self._stop_TCP_logging_clients()
                
                if isinstance(bpf_pro, Promise):
                    try:
                        bpf_result = bpf_pro.join()
                    except WatchDogException as e:
                        raise
                    except Exception as e:
                        iteration_logger.critical(e)
                        raise e
                    
                    with open(folder_path + "stdout_classifier.log", "w") as std_class:
                        std_class.write(bpf_result.stdout)
                    try:
                        self._bottleneckrouter.get_connection().get(remote=filename_bpf, local=folder_path)
                        self._bottleneckrouter.get_connection().run(f"sudo rm {filename_bpf}")
                    except WatchDogException as e:
                        raise
                    except Exception as e:
                        iteration_logger.critical(f"Could not pull BPF-Log from remote Host: {filename_bpf}")
                        iteration_logger.info(e.__str__())
                        raise e
    
                if isinstance(tcp_dump_pro, Promise):
                    tcp_dump_result = tcp_dump_pro.join()
                    try:
                        self._bottleneckrouter.get_connection().get(remote=filename_tcpdump, local=folder_path)
                        self._bottleneckrouter.get_connection().run(f"rm {filename_tcpdump}")
                        subprocess.Popen(["/usr/bin/brotli", "--rm", "-f", "--quality=7", os.path.join(folder_path, filename_tcpdump)], stdin=None, stdout=None, stderr=None, close_fds=True)
                    except WatchDogException as e:
                        raise
                    except Exception as e:
                        iteration_logger.critical(f"Could not pull TCP-Dump remote Host: {filename_tcpdump}")
                        iteration_logger.info(e.__str__())
                        raise e

                print("Collect client data")
                print("Iteration Result Folder Path:", folder_path)

                for index, client in enumerate(client_results):
                    device_folder_path = os.path.join(folder_path, f"client_{client[0].client_number}/")
                    
                    try:
                        os.mkdir(device_folder_path)
                    except:
                        iteration_logger.error(f"Could not create folder: {device_folder_path}; Skipped data gathering")
                        continue
                    
                    if isinstance(client[1], Result):
                        log_file_path:str = ""
                        if isinstance(client[0].implementation, IPERF_UDP):
                            log_file_path:str = client[0].implementation.get_client_log_file_path(client[0])
                        else:
                            log_file_path:str = client[0].implementation.get_client_log_file_path(client[1].stdout)
                        print("client log file path:", log_file_path)
                        ExperimentConfiguration._dump_quic_data(device_folder_path, client[0], client[1])
                        try:
                            if (not isinstance(client[0].implementation, TCP)) and (not isinstance(client[0].implementation, IPERF_UDP)):
                                if self._load_qlog_data:
                                    print("Get Client File: ", log_file_path)
                                    client[0].device.get_connection().get(remote=log_file_path, local=device_folder_path)
                                    subprocess.Popen(["/usr/bin/brotli", "--rm", "-f", "--quality=7", os.path.join(device_folder_path, log_file_path)], stdin=None, stdout=None, stderr=None, close_fds=True)
                                else:
                                    print(f"Loading client file ({log_file_path}) disabled.")
                                client[0].device.get_connection().run(f"sudo rm {log_file_path}") 
                            if isinstance(client[0].implementation, IPERF_UDP):
                                print(f"Get Client File: {log_file_path}")
                                client[0].device.get_connection().get(remote=log_file_path, local=device_folder_path) 
                                client[0].device.get_connection().run(f"sudo rm {log_file_path}") 

                            if isinstance(client[0].implementation, TCP):
                                if self._deploy_TCP_classifier:
                                    LOG_FILE_NAME = f"{client[0].client_number}_TCPlog_client.csv"
                                    if self._load_qlog_data:
                                        print("Get Client File: ", LOG_FILE_NAME)
                                        client[0].device.get_connection().get(remote=LOG_FILE_NAME, local=device_folder_path)
                                        subprocess.Popen(["/usr/bin/brotli", "--rm", "-f", "--quality=7", os.path.join(device_folder_path, LOG_FILE_NAME)], stdin=None, stdout=None, stderr=None, close_fds=True)
                                    else:
                                        print(f"Loading client file ({LOG_FILE_NAME}) disabled.")
                                    client[0].device.get_connection().run(f"rm {LOG_FILE_NAME}")

                        except WatchDogException as e:
                            raise
                        
                        except Exception as e:
                            print(e)
                            iteration_logger.error(f"Could not pull client log-file: {log_file_path} for {str(client[0])}")
                            raise e
                    else:
                        if client[0].__class__.__name__ != "IPERF3_UDP_Client_Config":
                            iteration_logger.error(f"Client did not join: {client[0].__str__()}")
                        else:
                            if isinstance(client[0].implementation, IPERF_UDP):
                                log_file_path:str = client[0].implementation.get_client_log_file_path(client[0])
                                print(f"Get Client File: {log_file_path}")
                                client[0].device.get_connection().get(remote=log_file_path, local=device_folder_path) 
                                client[0].device.get_connection().run(f"sudo rm {log_file_path}") 
                            else:
                                pass

                for server in self._server_list:
                    try:
                        server.device.get_connection().run(server.implementation.stop_server_command())
                    except exceptions.UnexpectedExit as e:
                        if "iperf3: interrupt - the client has terminated" in str(e.result):
                            pass
                        elif "pkill --signal SIGINT iperf3" in e.__str__() and "Exit code: 1" in e.__str__():
                            print("IPERF_UDP server stopped by SIGINT command.")
                            pass
                        elif "sudo pkill --signal SIGKILL -f custom-tcp" in e.__str__() and "Exit code: -1" in e.__str__():
                            print("AQM-TEST TCP server stopped correctly, no need to kill")
                            pass
                        elif "pkill --signal SIGINT picoquic" in e.__str__() and "Exit code: 1" in e.__str__():
                            print("pico quic server stopped correctly, no need to kill")
                            pass
                        else:
                            print(e.__str__())
                            print("Server stopping did not work properly.")
                            raise(e)
                    except WatchDogException as e:
                        raise
                    except Exception as e:
                        print(f"Could not stop server{server.device}")
                        raise e

                print("servers joined")
                print("Collect SERVER data")
                
                server_results:List[QUIC_Server_Promise_Tuple] = ExperimentConfiguration._join_server_promises(server_promises)

                if self._deploy_TCP_classifier:
                    self._stop_TCP_logging_servers()

                self._join_TCP_logging_servers_promises(server_TCP_logging_promises, iteration_logger, folder_path)

                for index, server in enumerate(server_results):
                    device_folder_path = os.path.join(folder_path, f"server_{index+1}/")
                    try:
                        os.mkdir(device_folder_path)
                    except:
                        iteration_logger.error(f"Could not create folder: {device_folder_path}; Skipped data gathering")
                        continue
                    if isinstance(server[1], Result):
                        log_file_paths:List[str] = []
                        if isinstance(server[0].implementation, IPERF_UDP):
                            log_file_paths = server[0].implementation.get_server_log_file_paths(server[0])
                        else:
                            log_file_paths = server[0].implementation.get_server_log_file_paths(server[1].stdout)
                        
                        print("Server log_file_paths:", log_file_paths)
                        ExperimentConfiguration._dump_quic_data(device_folder_path, server[0], server[1])
                        if ((not isinstance(server[0].implementation, TCP)) and (not isinstance(server[0].implementation, IPERF_UDP))):
                            for file_path in log_file_paths:
                                try:
                                    if self._load_qlog_data:
                                        print("Get Server File: ", f"{file_path}")
                                        server[0].device.get_connection().get(remote=file_path, local=device_folder_path)
                                        subprocess.Popen(["/usr/bin/brotli", "--rm", "-f", "--quality=7", os.path.join(device_folder_path, os.path.basename(file_path))], stdin=None, stdout=None, stderr=None, close_fds=True)
                                    else:
                                        print(f"Loading server file ({file_path}) disabled.")
                                    server[0].device.get_connection().run(f"rm {file_path}")
                                except WatchDogException as e:
                                    raise
                                except Exception as e:
                                    print(e)
                                    iteration_logger.error(f"Could not pull server log-file: {file_path}")
                                    raise e
                        if isinstance(server[0].implementation, TCP):
                            try:
                                for client_config in self._client_start_list:
                                    LOG_FILE_NAME = f"{client_config.client_number}_TCPlog_server.csv"
                                    if isinstance(client_config.implementation, TCP) and client_config.target_ip == server[0].device.local_ip and server[0]._server_port == client_config.target_port:
                                        if self._deploy_TCP_classifier:

                                            if self._load_qlog_data:
                                                print("Get Server File: ", LOG_FILE_NAME)
                                                server[0].device.get_connection().get(remote=LOG_FILE_NAME, local=device_folder_path)
                                                subprocess.Popen(["/usr/bin/brotli", "--rm", "-f", "--quality=7", os.path.join(device_folder_path, LOG_FILE_NAME)], stdin=None, stdout=None, stderr=None, close_fds=True)
                                            else:
                                                print(f"Loading server file ({LOG_FILE_NAME}) disabled.")
                                            server[0].device.get_connection().run(f"rm {LOG_FILE_NAME}")
                                            break
                            except WatchDogException as e:
                                raise
                            except Exception as e:
                                print(e)
                                iteration_logger.error(f"Could not pull TCP server log-file of server {client_config.client_number}")
                                raise e
                        if (isinstance(server[0].implementation, IPERF_UDP)):
                            for file_path in IPERF_UDP.get_server_log_file_paths(server[0]):
                                try:
                                    print("Get Server File: ", f"{file_path}")
                                    server[0].device.get_connection().get(remote=file_path, local=device_folder_path)
                                    server[0].device.get_connection().run(f"rm {file_path}")
                                except WatchDogException as e:
                                    raise
                                except Exception as e:
                                    print(e)
                                    iteration_logger.error(f"Could not pull UDP Iperf server log-file {file_path}")
                                    raise e
                    else:
                        if server[0].__class__.__name__ != "IPERF3_UDP_Server_Config":
                            iteration_logger.error(f"Server did not join successfully: {server[0]}")
                        else:
                            pass
                signal.alarm(0)

                self._get_tc_debug(iteration_logger, folder_path = os.path.join(self._result_folder_path, f"iter_{iteration:03}/"))

                print("Clear TC after experiment iteration.")
                self._clear_tc(iteration_logger)

            except WatchDogException as e:
                print(f"Watchdog triggered: {e}")
                print("WatchDog: Terminate all processes")
                for process in processes:
                    for client in process:
                        try:
                            client[0].device.get_connection().run(client[0].implementation.stop_client_command())
                            interrupt_process_by_name(client[0].device.get_connection(), "tcp_probe_bpf.py")
                        except:
                            pass
                    for server in process:
                        try:
                            client[0].device.get_connection().run(server[0].implementation.stop_server_command())
                            interrupt_process_by_name(client[0].device.get_connection(), "tcp_probe_bpf.py")
                        except:
                            pass

                    interrupt_process_by_name(self._bottleneckrouter.get_connection(), "python")
                    interrupt_process_by_name(self._bottleneckrouter.get_connection(), "tcpdump")

                print("WatchDog: terminated all processes")

                logger.error(f"Iteration {iteration:03} failed!:")
                print(f"Iteration {iteration:03} failed!:")
                if iteration_logger is not None:
                    iteration_logger.critical("Error:\n" + "WatchDog timer expired")
                    logger.info(e.__dict__)
                else:
                    logger.error("Error:\n" + "WatchDog timer expired")
                    logger.info(e.__dict__)

            except Exception as e:
                logger.error(f"Iteration {iteration:03} failed!:")
                print(f"Iteration {iteration:03} failed!:")
                if iteration_logger is not None:
                    iteration_logger.critical("Error:\n" + e.__str__())
                    logger.info(e.__dict__)
                else:
                    logger.error("Error:\n" + e.__str__())
                    logger.info(e.__dict__)
            else:
                logger.info(f"Complete iteration {iteration:03}")
            finally:
                self.kill_everything()
                self.resetSshConnections()
            reset_logger(iteration_logger)
        reset_logger(logger)

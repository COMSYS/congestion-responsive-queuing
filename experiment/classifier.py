import sys
import ctypes as ct
import ipaddress as ia
from bcc import BPF
from pyroute2 import IPRoute
import socket

output_file = open(sys.argv[1], "w")
output_file.write(f"IP-Source,IP-Destination,Port-Source,Port-Destination,Timestamp,RTT,Class-ID,Bytes,ECN,Drops,NewClass,RespCnt_ECN,UnrespCnt_ECN,RespCnt_drop,UnrespCnt_drop,Protocol\n")

class Data(ct.Structure):
    _fields_ = [("srcIP", ct.c_uint),
                ("dstIP", ct.c_uint),
                ("srcPort", ct.c_ushort),
                ("dstPort", ct.c_ushort),
                ("timestamp", ct.c_ulong),
                ("rtt", ct.c_ulong),
                ("classID", ct.c_uint),
                ("lastSpins", ct.c_uint),
                ("bytes", ct.c_uint),
                ("ecn_markings", ct.c_uint),
                ("num_drops", ct.c_uint),
                ("newclass", ct.c_ushort),
                ("responsive_count_ECN", ct.c_uint),
                ("unresponsive_count_ECN", ct.c_uint),
                ("responsive_count_drop", ct.c_uint),
                ("unresponsive_count_drop", ct.c_uint),
                ("protocol", ct.c_char * 5)]

def print_event(cpu, data, size):
    event = ct.cast(data, ct.POINTER(Data)).contents
    output_file.write(f"{ia.IPv4Address(event.srcIP)},{ia.IPv4Address(event.dstIP)},{event.srcPort},{event.dstPort},{event.timestamp},{event.rtt},{event.classID},{event.bytes},{int(event.ecn_markings & 0xFF)},{int(event.num_drops & 0xFF )},{event.newclass},{event.responsive_count_ECN},{event.unresponsive_count_ECN},{event.responsive_count_drop},{event.unresponsive_count_drop},{event.protocol.decode('utf-8').strip('\x00')}\n") 

device = BOTTLENECK_CLIENT # interface bottleneck->client (track server->client traffic)
device_client = BOTTLENECK_LOAD # interface bottleneck->loads (track client->server traffic)
device_ifb = FIRST_IFB # ifb used for server->client direction

ipr = IPRoute()

b = BPF(src_file="classifier.c")
fn = b.load_func("entrypoint_classifier", BPF.SCHED_CLS)
if_index = ipr.link_lookup(ifname=device)[0]

b["cycleUpdates"].open_perf_buffer(print_event)

try:
    ipr.tc("add-filter", "bpf", if_index, ":1", fd=fn.fd, parent="ffff:fff3", classid=1, direct_action=True)

    ecn_trace = BPF(src_file="tracepoint_ecn.c")
    drop_trace = BPF(src_file="tracepoint_drops.c")

    tcp_client = BPF(src_file="tracepoint_tcp.c")
    
    drop_trace.attach_kprobe(event="htb_enqueue", fn_name="enqueue_skb")
    drop_trace.attach_kretprobe(event="htb_enqueue", fn_name="ret_enqueue_skb")
    drop_trace.attach_kprobe(event="tbf_enqueue", fn_name="enqueue_skb")
    drop_trace.attach_kretprobe(event="tbf_enqueue", fn_name="ret_enqueue_skb")

    drop_trace.attach_kprobe(event="kfree_skb_reason", fn_name="kfree_skb_own")
        
    print("Ready:")
    while 1:
        b.perf_buffer_poll()        
except KeyboardInterrupt:
    print("Done")
finally:
    for k,v in b["drop_results"].items():
        print(f"DROPS: {ia.IPv4Address(socket.ntohl(k.srcIP))}:{socket.ntohs(k.srcPrt)} <TO> {ia.IPv4Address(socket.ntohl(k.dstIP))}:{socket.ntohs(k.dstPrt)} DROP {v.value}")
    print("\n")
    for k,v in b["ecn"].items():
        print(f"ECN: {ia.IPv4Address(socket.ntohl(k.srcIP))}:{socket.ntohs(k.srcPrt)} <TO> {ia.IPv4Address(socket.ntohl(k.dstIP))}:{socket.ntohs(k.dstPrt)} ECN {v.value}")
    ipr.tc("del-filter",  index=if_index, parent="ffff:fff3")
    output_file.close()

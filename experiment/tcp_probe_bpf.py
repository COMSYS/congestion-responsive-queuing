#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# tcp_probe_bpf Trace TCP connection parameters.
#           For Linux, uses BCC, eBPF. Embedded C.
#
# USAGE: tcp_probe ["filter"]
#
# The filter syntax is inspired by tcpdump style filters
# use can use "host IP", "net IP/NETMASK", "saddr IP", "daddr IP", "port NUMBER",
# "sport NUMBER", "dport NUMBER" as well as "and", "or" and "not", and "(" and ")"
# only packets matching the filter will get to the userspace.
# Operator precedence follows that of the C language.
#
#
# This uses dynamic tracing of the kernel tcp_rcv_established() socket function
# , and will need to be modified to match kernel changes.
#
# IPv4 addresses are printed as dotted quads. Currently only IPv4 matchting is
# supported
#
# Copyright (c) 2017 Jan Rüth.
# Licensed under the Apache License, Version 2.0 (the "License")
#

from __future__ import print_function

from bcc import BPF
import ctypes as ct
import traceback
import socket
import struct
import shlex
import time
from argparse import ArgumentParser

import signal
import sys

def custom_signal_handler(signal,frame):
    print("Exitted")
    sys.exit(0)
signal.signal(signal.SIGTERM, custom_signal_handler)

parser = ArgumentParser(description="Tcp Probe")

parser.add_argument('--filter', '-f',
                    dest="filter",
                    action="store",
                    help="What kind of filter is to be applied to the tcpProbe?",
                    required=False)

parser.add_argument('--output', '-o', dest="output", action="store", help="Output file name")

args = parser.parse_args()

output_file = None
OUTPUT_CALL = print

if args.output != None:
    output_file = open(args.output, "w")
    OUTPUT_CALL = output_file.write

# define BPF program
prog = """
    #define KBUILD_MODNAME "tcp_prober"
    #include <net/tcp.h>
    #include <linux/tcp.h>
    #include <linux/socket.h>
    #include <uapi/linux/in.h>
    #include <uapi/linux/in6.h>
    #include <linux/ipv6.h>

    // define output data structure in C
    struct tcp_log {
        u64 ts;
        union {
            struct sockaddr         raw;
            struct sockaddr_in      v4;
            struct sockaddr_in6     v6;
        } src, dst;
        u16     length;
        u32     seq;
        u32     ack_seq;
        u32     snd_nxt;
        u32     rcv_nxt;
        u32     snd_una;
        u32     snd_wnd;
        u32     rcv_wnd;
        u32     snd_cwnd;
        u32     ssthresh;
        u32     srtt;
        u32     lost_out;
        u32     sacked_out;
        //u32     fackets_out;
        u32     retrans_out;
        u32     segs_out;
        u32     segs_in;
        u32     total_retrans;
        u64     bytes_received;
        u64     bytes_acked;
        u64     rate;
        u64     intervalus;
        u64     skbuf_pacingrate;
    };

    struct access_bitfield_ca_state {
        u8 pad0[offsetof(struct inet_connection_sock, icsk_retransmits)-2];
        u8 ca_state;
    };

    BPF_PERF_OUTPUT(events);

    static inline int check_network4(u32 cmp, u32 truth, u32 bitmask)
    {
        u32 masked_addr = truth & bitmask;
        return masked_addr != cmp;
    }



    void my_rcv_established(struct pt_regs *ctx, struct sock *sk, struct sk_buff *skb, const struct tcphdr *th, unsigned int len)
    {
        struct tcp_sock *tp = (struct tcp_sock *)sk;
        struct inet_connection_sock *inet = (struct inet_connection_sock *)sk;


        struct tcp_log data = {};
        
        
        // for pacing rate
        data.rate = tp->rate_delivered; // byte per second
        data.intervalus = tp->rate_interval_us;
        data.skbuf_pacingrate = sk->sk_pacing_rate;
        

        switch (tp->inet_conn.icsk_inet.sk.sk_family) {
            case AF_INET:

                data.src.v4.sin_family = AF_INET;
                data.src.v4.sin_port = inet->icsk_inet.inet_sport;
                data.src.v4.sin_addr.s_addr = inet->icsk_inet.inet_saddr;

                data.dst.v4.sin_port = inet->icsk_inet.inet_dport;
                data.dst.v4.sin_addr.s_addr = inet->icsk_inet.inet_daddr;

                break;
            case AF_INET6:

                memset(&data.src.v6, 0, sizeof(data.src.v6));
                memset(&data.dst.v6, 0, sizeof(data.dst.v6));

            #if IS_ENABLED(CONFIG_IPV6)
                data.src.v6.sin6_family = AF_INET6;
                data.src.v6.sin6_port = inet->icsk_inet.inet_sport;
                data.src.v6.sin6_addr = inet->icsk_inet.pinet6->saddr;

                data.dst.v6.sin6_family = AF_INET6;
                data.dst.v6.sin6_port = inet->icsk_inet.inet_dport;
                data.dst.v6.sin6_addr = inet->icsk_inet.sk.sk_v6_daddr;
            #endif

                break;

            default:
                return;
        }

        // VERIFY NETWORK


        data.ts = bpf_ktime_get_ns();
        data.length = skb->len;
        data.seq = th->seq;
        data.seq = ntohl(data.seq);
        data.ack_seq = th->ack_seq;
        data.ack_seq = ntohl(data.ack_seq);
        data.snd_nxt = tp->snd_nxt;
        data.rcv_nxt = tp->rcv_nxt;
        data.snd_una = tp->snd_una;
        data.snd_cwnd = tp->snd_cwnd;
        data.snd_wnd = tp->snd_wnd;
        data.rcv_wnd = tp->rcv_wnd;
        struct access_bitfield_ca_state* accessor = (struct access_bitfield_ca_state*)tp;
        u8 ca_state = 0;
        ca_state = accessor->ca_state;
        ca_state &= 0x3F;

        data.ssthresh = tp->snd_ssthresh;

        if(!(TCPF_CA_CWR | TCPF_CA_Recovery) & (1 << ca_state)) {
            int cwnd_thresh = ((data.snd_cwnd >> 1) + (data.snd_cwnd >> 2));
            if (data.ssthresh < cwnd_thresh)
                data.ssthresh = cwnd_thresh;
        }

        data.srtt = tp->srtt_us >> 3;
        data.lost_out = tp->lost_out;
        data.sacked_out = tp->sacked_out;
        //data.fackets_out = tp->fackets_out;
        data.retrans_out = tp->retrans_out;
        data.segs_out = tp->segs_out;
        data.segs_in = tp->segs_in;
        data.total_retrans = tp->total_retrans;
        data.bytes_received = tp->bytes_received;
        data.bytes_acked = tp->bytes_acked;

        events.perf_submit(ctx, &data, sizeof(data));

        return;
    }

    """

test_net = "({0} == (data.src.v4.sin_addr.s_addr & {1}) || {0} == (data.dst.v4.sin_addr.s_addr & {1}))"
test_host= "(data.src.v4.sin_addr.s_addr == {0} || data.dst.v4.sin_addr.s_addr == {0})"
test_saddr="(data.src.v4.sin_addr.s_addr == {0})"
test_daddr="(data.dst.v4.sin_addr.s_addr == {0})"

test_port="(ntohs(data.src.v4.sin_port) {0} {1} || ntohs(data.dst.v4.sin_port) {0} {1})"
test_sport="(ntohs(data.src.v4.sin_port) {0} {1})"
test_dport="(ntohs(data.dst.v4.sin_port) {0} {1})"


def parse_ip(ip_string):
    net = socket.inet_aton(ip_string)
    net, = struct.unpack("@I", net)
    return net

def parse_filter(filter):
    expr = ""

    args = shlex.split(filter)

    cmds = []
    apply_stack = []
    args.append("")
    real_args = []
    map(lambda x: str.replace(x, "(", "( "), args)
    map(lambda x: str.replace(x, ")", " )"), args)
    for arg in args:
        if arg.startswith("("):
            real_args.append("(")
            arg = arg[1:]
        if arg.endswith(")"):
            real_args.append(arg[:-1])
            real_args.append(")")
        else:
            real_args.append(arg)
    args = real_args

    idx = 0
    while(idx < len(args)):
        arg = args[idx]
        if len(cmds) > 0:
            cmd = cmds.pop(0)
            if cmd == "parse_net":
                netandmask = arg.split("/")
                if len(netandmask) != 2:
                    raise Exception("Networks must be specified by 0.0.0.0/x, e.g. 10.0.0.0/8: ", arg, netandmask)
                ip = parse_ip(netandmask[0])
                netmask = (1 << int(netandmask[1]))-1
                apply_stack.append((ip, netmask))
                idx += 1
                continue
            if cmd == "parse_ip":
                ip = parse_ip(arg)
                apply_stack.append((ip,))
                idx += 1
                continue
            if cmd == "parse_operator":
                if arg in [">", ">=", "<", "<=", "==", "=", "!="]:
                    if arg == "=":
                        arg = "=="
                    apply_stack.append((arg,))
                    idx += 1
                else:
                    apply_stack.append(("==",))
                continue
            if cmd == "parse_port":
                idx += 1
                port = int(arg)
                apply_stack.append((port,))
                continue

        if len(apply_stack) > 0:
            params = tuple([elem for tup in apply_stack[1:] for elem in tup])
            expr += apply_stack[0](*params)
            apply_stack = []


        if arg == "not":
            expr += "!"
            idx += 1
            continue
        if arg == "and":
            expr += " && "
            idx += 1
            continue
        if arg == "or":
            expr += " || "
            idx += 1
            continue
        if arg == "(":
            expr += "("
            idx += 1
            continue
        if arg == ")":
            expr += ")"
            idx += 1
            continue
        if arg == "net":
            cmds.append("parse_net")
            apply_stack = [test_net.format]
            idx += 1
            continue
        if arg == "host":
            cmds.append("parse_ip")
            apply_stack = [test_host.format]
            idx += 1
            continue
        if arg == "saddr":
            cmds.append("parse_ip")
            apply_stack = [test_saddr.format]
            idx += 1
            continue
        if arg == "daddr":
            cmds.append("parse_ip")
            apply_stack = [test_daddr.format]
            idx += 1
            continue
        if arg == "port":
            cmds.append("parse_operator")
            cmds.append("parse_port")
            apply_stack = [test_port.format]
            idx += 1
            continue
        if arg == "sport":
            cmds.append("parse_operator")
            cmds.append("parse_port")
            apply_stack = [test_sport.format]
            idx += 1
            continue
        if arg == "dport":
            cmds.append("parse_operator")
            cmds.append("parse_port")
            apply_stack = [test_dport.format]
            idx += 1
            continue
        idx += 1
    return expr



if not args.filter:
    expr = ""
else:
    expr = "if (!( " + parse_filter(args.filter) + " )) return;"

print("Using filter expression: {}".format(expr), file=sys.stderr)
b = BPF(text=prog.replace("// VERIFY NETWORK", expr), debug=0x00)
b.attach_kprobe(event="tcp_rcv_established", fn_name="my_rcv_established")

class SocketAddrRaw(ct.Structure):
    _fields_ = [("sa_family", ct.c_ushort),
                ("sa_data", ct.c_uint8*14)]

class SocketAddr_IN(ct.Structure):
    _fields_ = [("sa_family", ct.c_ushort),
                ("sin_port", ct.c_ushort),
                ("sin_addr", ct.c_uint8 * 4),
                ("sin_zero", ct.c_uint8 * 8)]

class SocketAddr_IN6(ct.Structure):
    _fields_ = [("sa_family", ct.c_uint16),
                ("sin6_port", ct.c_uint16),
                ("sin6_flowinfo", ct.c_uint32),
                ("sin_addr", ct.c_uint8*16),
                ("sin6_scope_id", ct.c_uint32)]

class SocketAddr(ct.Union):
    _fields_ = [("raw", SocketAddrRaw),
                ("v4", SocketAddr_IN),
                ("v6", SocketAddr_IN6)]

class Data(ct.Structure):
    _fields_ = [("ts", ct.c_uint64),
                ("src", SocketAddr),
                ("dst", SocketAddr),
                ("length", ct.c_uint16),
                ("ack_seq", ct.c_uint32),
                ("seq", ct.c_uint32),
                ("snd_nxt", ct.c_uint32),
                ("rcv_nxt", ct.c_uint32),
                ("snd_una", ct.c_uint32),
                ("snd_wnd", ct.c_uint32),
                ("rcv_wnd", ct.c_uint32),
                ("snd_cwnd", ct.c_uint32),
                ("ssthresh", ct.c_uint32),
                ("srtt", ct.c_uint32),
                ("lost_out", ct.c_uint32),
                ("sacked_out", ct.c_uint32),
                ("retrans_out", ct.c_uint32),
                ("segs_out", ct.c_uint32),
                ("segs_in", ct.c_uint32),
                ("total_retrans", ct.c_uint32),
                ("bytes_received", ct.c_uint64),
                ("bytes_acked", ct.c_uint64),
                ("rate", ct.c_uint64),
                ("intervalus", ct.c_uint64),
                ("skbuf_pacingrate", ct.c_uint64)]

print("Ready")
print("\n")
format_string = "{:<14}\t{:<21}\t{:<21}\t{:<6}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<10}\t{:<20}\t{:<20}\t{:<21}\t{:<21}\t{:<21}"

OUTPUT_CALL(format_string.format("TIME(s)", "src", "dst", "length", "seq", "ack_seq", "snd_nxt", "rcv_nxt", "snd_una", "snd_wnd", "rcv_wnd", "snd_cwnd", "ssthresh", "srtt", "lost_out", "sacked_out", #"fackets_out", 
"retrans_out", "segs_out", "segs_in", "total_retrans", "bytes_received", "byted_acked", "rate", "intervalus", "skbuf_pacingrate"))

total = 0
totalerr = 0
start = 0
def store_event(cpu, data, size):
    global total
    global start
    total += 1
    event = ct.cast(data, ct.POINTER(Data)).contents
    if start == 0:
        start = event.ts
    time_s = float(event.ts) / 1000000000
    src = "{}:{}".format(socket.inet_ntoa(event.src.v4.sin_addr), socket.ntohs(event.src.v4.sin_port))
    dst = "{}:{}".format(socket.inet_ntoa(event.dst.v4.sin_addr), socket.ntohs(event.dst.v4.sin_port))
    OUTPUT_CALL(format_string.format(time_s, src, dst, event.length, event.seq, event.ack_seq, event.snd_nxt, event.rcv_nxt,
                               event.snd_una, event.snd_wnd, event.rcv_wnd, event.snd_cwnd, event.ssthresh, event.srtt,
                               event.lost_out, event.sacked_out, event.retrans_out, event.segs_out,
                               event.segs_in, event.total_retrans, event.bytes_received, event.bytes_acked,
                               event.rate, event.intervalus, event.skbuf_pacingrate))

def lost(x):
    global total
    global totalerr
    totalerr += 1
    OUTPUT_CALL("{}/{} {}\n".format(totalerr, total, total+totalerr), file=sys.stderr)

b["events"].open_perf_buffer(lambda cpu, data, size: store_event(cpu, data, size), page_cnt=32, lost_cb=lost)

startTime = time.time()
try:

    counter = 0
    previousTime = time.time()
    print("")

    while counter < 4 or time.time() - previousTime < 0.5:

        if counter < 4:
            timeout = 10000
        else:
            timeout = 500

        previousTime = time.time()
        b.kprobe_poll(timeout=timeout)

        counter += 1


except Exception as thrown_exception:

    print("Error during tcp_probe_bpf")
    print("----------------------------------------------------------------")
    print(thrown_exception)
    print(traceback.print_exc())
    pass


finally:
    b.detach_kprobe("tcp_rcv_established")
    running = False
    OUTPUT_CALL("Total: {} Errors: {}".format(total, totalerr))
    if output_file:
        output_file.close()

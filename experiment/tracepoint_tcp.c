#include <linux/skbuff.h>
#include <linux/bpf.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/byteorder/generic.h>
#define MAX_UINT32 4294967295U

struct connectionID {
        u32 srcIP;
        u32 dstIP;
        u16 srcPrt;
        u16 dstPrt;
};

struct seqAndAck {
        u32 highestAck;
        u32 expectedAckOnAck;
        bool active;
};

BPF_TABLE("extern", struct connectionID, struct seqAndAck, highestAckMap, 10240);


TRACEPOINT_PROBE(qdisc, qdisc_dequeue) {
    if (args->skbaddr == NULL) {
        return 0;
    }

    struct sk_buff* skb = (struct sk_buff*)(args->skbaddr);
    if (skb == NULL) {
        return 0;
    }

    struct iphdr ip_hdr;
    if (bpf_probe_read_kernel(&ip_hdr, sizeof(struct iphdr), skb->head + skb->network_header) != 0) {
        bpf_trace_printk("Error tracepoint_tcp: Copy IP header");
        return 0;
    }
    if (ip_hdr.protocol != IPPROTO_TCP){ 
        return 0;
    }
    
    struct tcphdr transport_hdr;
    if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct tcphdr), skb->head + skb->transport_header) != 0) {
        bpf_trace_printk("Error tracepoint_tcp: Copy TCP header");
        return 0;
    }

    u32 seqNumber = bpf_ntohl(transport_hdr.seq);
    u32 ackNumber = bpf_ntohl(transport_hdr.ack_seq);

    u16 total_length = bpf_ntohs(ip_hdr.tot_len);
    u8 ip_header_length = ip_hdr.ihl * 4;
    u8 tcp_header_length = transport_hdr.doff * 4;
    u32 payload_length = total_length - ip_header_length - tcp_header_length;

    u32 expectedAck = seqNumber + payload_length;

    struct connectionID cid= {ip_hdr.daddr, ip_hdr.saddr, transport_hdr.dest, transport_hdr.source};

    struct seqAndAck* curr_seqAndAck = highestAckMap.lookup(&cid);
    if (curr_seqAndAck == NULL){
        bpf_trace_printk("Error highestAckMap : No entry in highestAckMap");
        struct seqAndAck new_seqAck = {ackNumber, expectedAck, false};
        highestAckMap.insert(&cid, &new_seqAck);
        return 0;
    } else {
        u32 highestAck = curr_seqAndAck->highestAck;
        u32 curr_expectedAck = curr_seqAndAck->expectedAckOnAck;

        if (ackNumber >= highestAck || ((highestAck > MAX_UINT32 - (MAX_UINT32 / 4) && ackNumber < (MAX_UINT32 / 4))) ){
            curr_seqAndAck->highestAck = ackNumber;
        }
        if (curr_seqAndAck->active == false) {
            curr_seqAndAck->active = true;
            curr_seqAndAck->expectedAckOnAck = expectedAck;
        }
        return 0;
    }
}
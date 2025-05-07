#include <linux/skbuff.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/bpf.h>

struct connectionID {
        u32 srcIP;
        u32 dstIP;
        u16 srcPrt;
        u16 dstPrt;
};

BPF_TABLE("extern", struct connectionID, u32, ecn, 10240);

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
        bpf_trace_printk("Error tracepoint_tcp : Copy IP header");
        return 0;
    }

    __u8 ecn_field = ip_hdr.tos & 0b00000011;
    if (ecn_field != 0b00000011) {
        return 0;
    }

    struct connectionID cid= {};

    if (ip_hdr.protocol == IPPROTO_TCP){
        struct tcphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct tcphdr), skb->head + skb->transport_header) != 0) {
            bpf_trace_printk("Error ECN: Copy TCP header");
            return 0;
        }
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    } else if (ip_hdr.protocol == IPPROTO_UDP){
        struct udphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct udphdr), skb->head + skb->transport_header) != 0) {
            bpf_trace_printk("Error ECN: Copy UDP header");
            return 0;
        }
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    } else {
        return 0; 
    }
    
    u32* ecn_markings = ecn.lookup(&cid);
    if (ecn_markings == NULL){
        u32 ecn_markings = 0;
        ecn.insert(&cid, &ecn_markings);
        return 0;
    }

    if ((*ecn_markings & 0xFF) != 0xFF) {
        *ecn_markings = *ecn_markings + 1;
        ecn.update(&cid, ecn_markings);
    }
    return 0;
}
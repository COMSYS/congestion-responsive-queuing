#include <net/sch_generic.h>
#include <net/pkt_sched.h>
#include <linux/rbtree.h>
#include <uapi/linux/gen_stats.h>
#include <uapi/linux/if.h>
#include <linux/skbuff.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/bpf.h>
#include <linux/netdevice.h>
#include <linux/byteorder/generic.h>  // For ntohl and ntohs
#include <net/dropreason-core.h> // for skb drop reason

#define MAX(x, y) (((x) > (y)) ? (x) : (y))
#define MIN(x, y) (((x) < (y)) ? (x) : (y))

#define IP_FIRST {IP_FIRST_FOUR}
#define IP_SECOND {IP_SECOND_FOUR}
#define IP_THIRD {IP_THIRD_FOUR}

#define RD 0
#define RE 1

struct entry {{
    struct Qdisc *qdisc;
    struct sk_buff *skb;
    struct sk_buff **to_free;
}};

struct entry_key {{
    u32 pid;
    u32 cpu;
}};

struct connectionID {{
    u32 srcIP;
    u32 dstIP;
    u16 srcPrt;
    u16 dstPrt;
}};

struct output {{
    u32 srcIP;
    u32 dstIP;
    u16 srcPrt;
    u16 dstPrt;
    u32 drops;
}};

BPF_PERF_OUTPUT(events);
BPF_HASH(currqdisc_en, struct entry_key, struct entry);
BPF_TABLE("extern", struct connectionID, u32, drops, 10240);
BPF_TABLE("extern", struct connectionID, u32, drop_results, 10240);

void enqueue_skb(struct pt_regs *ctx, struct sk_buff *skb, struct Qdisc *q, struct sk_buff **to_free) {{
    struct entry e = {{}};
    e.qdisc = q;
    e.skb = skb;
    e.to_free = to_free;

    struct entry_key k = {{}};
    k.pid = bpf_get_current_pid_tgid();
    k.cpu = bpf_get_smp_processor_id();
    currqdisc_en.update(&k, &e);      

    struct iphdr ip_hdr;
    if (bpf_probe_read_kernel(&ip_hdr, sizeof(struct iphdr), skb->head + skb->network_header) != 0) {{
        bpf_trace_printk("Error Drop: Copy IP header");
    }}

    struct connectionID cid= {{}};

    if (ip_hdr.protocol == IPPROTO_TCP){{
        struct tcphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct tcphdr), skb->head + skb->transport_header) != 0) {{
            bpf_trace_printk("Error Drop: Copy TCP header");
        }}
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    }} else if (ip_hdr.protocol == IPPROTO_UDP){{
        struct udphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct udphdr), skb->head + skb->transport_header) != 0) {{
            bpf_trace_printk("Error Drop: Copy UDP header");
        }}
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    }}

    u32 *num_drops = drops.lookup(&cid);
    if (num_drops == NULL){{
        u32 tmp_drop = 0;
        drops.insert(&cid, &tmp_drop);
    }}
}}

// packet loss detection for codel: infer the information of a dropped skb
void kfree_skb_own(struct pt_regs *ctx, struct sk_buff *skb, enum skb_drop_reason *reason) {{   
    // See https://elixir.bootlin.com/linux/v6.8.12/source/include/net/dropreason-core.h

    if (*reason == SKB_DROP_REASON_NOT_SPECIFIED) {{
        return;
    }}

    struct iphdr ip_hdr;
    if (bpf_probe_read_kernel(&ip_hdr, sizeof(struct iphdr), skb->head + skb->network_header) != 0) {{
        bpf_trace_printk("Error kfree: Copy IP header");
    }}

    u32 srcIP = ntohl(ip_hdr.saddr);
    u32 dstIP = ntohl(ip_hdr.daddr);
    if ((((srcIP >> 24) & 0xFF) != IP_FIRST) || (((srcIP >> 16) & 0xFF) != IP_SECOND) || (((srcIP >> 8) & 0xFF) != IP_THIRD)){{
        return;
    }}

    struct connectionID cid= {{}};
    if (ip_hdr.protocol == IPPROTO_TCP){{
        struct tcphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct tcphdr), skb->head + skb->transport_header) != 0) {{
            bpf_trace_printk("Error Drop: Copy TCP header");
        }}
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    }} else if (ip_hdr.protocol == IPPROTO_UDP){{
        struct udphdr transport_hdr;
        if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct udphdr), skb->head + skb->transport_header) != 0) {{
            bpf_trace_printk("Error Drop: Copy UDP header");
        }}
        cid.srcIP = ip_hdr.saddr;
        cid.dstIP = ip_hdr.daddr;
        cid.srcPrt = transport_hdr.source;
        cid.dstPrt = transport_hdr.dest;
    }}

    u32 *num_drops = drops.lookup(&cid);
    u32 res_drops;
    if (num_drops == NULL){{
        u32 tmp_drop = 0;
        res_drops = 0;
        drops.insert(&cid, &tmp_drop);
        bpf_trace_printk("In kfree_skb: kein Eintrag bisher vorhanden");
    }} else {{
        *num_drops = *num_drops + 1;
        res_drops = *num_drops;
        drops.update(&cid, num_drops);
    }}

    u32 *res_num_drops = drop_results.lookup(&cid);
    
    if (res_num_drops == NULL){{
        u32 tmp_drop = 1;
        drop_results.insert(&cid, &tmp_drop);
    }} else {{
        if ((*res_num_drops & 0xFF) != 0xFF) {{
            *res_num_drops = *res_num_drops + 1;
            drop_results.update(&cid, res_num_drops);
        }}
    }}

    struct connectionID cid_res = {{1, 1, 1, 1}};
    drop_results.update(&cid_res, &res_drops);
}}

int ret_enqueue_skb(struct pt_regs *ctx) {{
    int ret = (int)PT_REGS_RC(ctx);

    if(ret != NET_XMIT_SUCCESS) {{
        struct entry_key k = {{}};
        k.pid = bpf_get_current_pid_tgid();
        k.cpu = bpf_get_smp_processor_id();

        struct entry *entryp;
        entryp = currqdisc_en.lookup(&k);

        if(entryp == NULL){{
            currqdisc_en.delete(&k);
            return 0;
        }}
        currqdisc_en.delete(&k);

        struct sk_buff * skb = entryp->skb;

        struct iphdr ip_hdr;
        if (bpf_probe_read_kernel(&ip_hdr, sizeof(struct iphdr), skb->head + skb->network_header) != 0) {{
            bpf_trace_printk("Error LOSS2: Copy IP header");
        }}

        struct connectionID cid= {{}};
        if (ip_hdr.protocol == IPPROTO_TCP){{
            struct tcphdr transport_hdr;
            if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct tcphdr), skb->head + skb->transport_header) != 0) {{
                bpf_trace_printk("Error Drop: Copy TCP header");
                return 0;
            }}
            cid.srcIP = ip_hdr.saddr;
            cid.dstIP = ip_hdr.daddr;
            cid.srcPrt = transport_hdr.source;
            cid.dstPrt = transport_hdr.dest;
        }} else if (ip_hdr.protocol == IPPROTO_UDP){{
            struct udphdr transport_hdr;
            if (bpf_probe_read_kernel(&transport_hdr, sizeof(struct udphdr), skb->head + skb->transport_header) != 0) {{
                bpf_trace_printk("Error Drop: Copy UDP header");
                return 0;
            }}
            cid.srcIP = ip_hdr.saddr;
            cid.dstIP = ip_hdr.daddr;
            cid.srcPrt = transport_hdr.source;
            cid.dstPrt = transport_hdr.dest;
        }} else {{
            return 0; 
        }}

        u32 *num_drops = drops.lookup(&cid);
        
        if (num_drops == NULL){{
            bpf_trace_printk("Error NO ENTRY FOR CID");
            u32 tmp_drop = 1;
            drops.insert(&cid, &tmp_drop);
        }} else {{
            *num_drops = *num_drops + 1;
            drops.update(&cid, num_drops);
        }}

        u32 tmp_drop = 0;
        if (num_drops != NULL){{
            bpf_probe_read_kernel(&tmp_drop, sizeof(tmp_drop), num_drops);
        }}

        u32 *res_num_drops = drop_results.lookup(&cid);
        
        if (res_num_drops == NULL){{
            u32 tmp_drop = 1;
            drop_results.insert(&cid, &tmp_drop);
        }} else {{
            if ((*res_num_drops & 0xFF) != 0xFF) {{
                *res_num_drops = *res_num_drops + 1;
                drop_results.update(&cid, res_num_drops);
            }}
        }}
                
        struct Qdisc * qdisc = entryp->qdisc;
        struct connectionID cid_res = {{1, 1, 1, 1}};
        u32 res_drops = qdisc->qstats.drops;
        drop_results.update(&cid_res, &res_drops);
        return 0;
    }} else {{
        struct entry_key k = {{}};
        k.pid = bpf_get_current_pid_tgid();
        k.cpu = bpf_get_smp_processor_id();

        struct entry *entryp;
        entryp = currqdisc_en.lookup(&k);

        if(entryp == NULL){{
            return 0;
        }}
        struct Qdisc * qdisc = entryp->qdisc;
    }}
    return 0;
}}








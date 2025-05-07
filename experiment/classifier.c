#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>

#define QUIC_INITIAL 0x00
#define QUIC_0RTT 0x01
#define QUIC_HANDSHAKE 0x10
#define QUIC_RETRY 0b00000110
#define EDGE_THRESHOLD 1
#define EDGE_THRESHOLD {edge_threshold}

#define BOTH_UNCLASSIFIED {BOTH_UNCLASSIFIED_classid}
#define BOTH_RESPONSIVE {BOTH_RESPONSIVE_classid}
#define BOTH_UNRESPONSIVE {BOTH_UNRESPONSIVE_classid}
#define ECN_RESP_LOSS_UNCLASS {ECN_RESP_LOSS_UNCLASS_classid}
#define ECN_RESP_LOSS_UNRESP {ECN_RESP_LOSS_UNRESP_classid}
#define ECN_UNRESP_LOSS_UNCLASS {ECN_UNRESP_LOSS_UNCLASS_classid}
#define ECN_UNRESP_LOSS_RESP {ECN_UNRESP_LOSS_RESP_classid}
#define ECN_UNCLASS_LOSS_UNRESP {ECN_UNCLASS_LOSS_UNRESP_classid}
#define ECN_UNCLASS_LOSS_RESP {ECN_UNCLASS_LOSS_RESP_classid}

#define INITIALBYTELENGTH 1
#define VERSIONLENGTH 4
#define DSTCIDFIELDLENGTH 1
#define SRCCIDFIELDLENGTH 1
#define MAX_UINT32 4294967295U
#define MSS 1500

struct connectionID {{
        u32 srcIP;
        u32 dstIP;
        u16 srcPrt;
        u16 dstPrt;
}};

struct connectionInfo {{
        u64 timestamp;
        u32 classID;
        u32 lastSpins;
        u64 rtt;
        u32 bytes;
        u32 bytes2;
        u32 bytes3;
        u32 bytes4;
        u32 responsive_count_ECN;
        u32 unresponsive_count_ECN;
        u32 responsive_count_drop;
        u32 unresponsive_count_drop;
        u32 expectedAck;
}};

struct output {{
        u32 srcIP;
        u32 dstIP;
        u16 srcPrt;
        u16 dstPrt;
        u64 timestamp;
        u64 rtt;
        u32 classID;
        u32 lastSpins;
        u32 bytes;
        u32 ecn_markings;
        u32 num_drops;
        u16 newclass;
        u32 responsive_count_ECN;
        u32 unresponsive_count_ECN;
        u32 responsive_count_drop;
        u32 unresponsive_count_drop;
        char protocol[5];
}};

struct quichdrs {{
        u16 packetNumberLengthField : 2;
        bool keyPhase : 1;
        u16 reservedBits : 2;
        bool spinBit : 1;
        bool fixedBit : 1;
        bool headerForm : 1;
        u8 measurementHeader;
}};

struct quichdrl {{
        u8 packetNumberLengthField : 2;
        u8 reservedBits : 2;
        u8 longHeaderType : 2;
        bool fixedBit : 1;
        bool headerForm : 1;
}};

struct seqAndAck {{
        u32 highestAck;
        u32 expectedAckOnAck;
        bool active;
}};

BPF_HASH(infoMap, struct connectionID, struct connectionInfo);
BPF_TABLE_SHARED("hash", struct connectionID, u32, drops, 10240);
BPF_TABLE_SHARED("hash", struct connectionID, u32, drop_results, 10240);
BPF_TABLE_SHARED("hash", struct connectionID, u32, ecn, 10240);
BPF_TABLE_SHARED("hash", struct connectionID, struct seqAndAck, highestAckMap, 10240);

BPF_PERF_OUTPUT(cycleUpdates);

static int createNewCinEntry(u32 bytes, u32 expectedAck, struct connectionID cid, struct __sk_buff *skb) {{
    struct connectionInfo cin = {{}};
    u64 time_now = bpf_ktime_get_ns();
    cin.timestamp = time_now;
    cin.classID = 0;
    cin.rtt = 0;
    cin.bytes = bytes;
    cin.responsive_count_ECN = 0;
    cin.responsive_count_drop = 0;
    cin.unresponsive_count_ECN = 0;
    cin.unresponsive_count_drop = 0;
    cin.expectedAck = expectedAck;
    
    infoMap.insert(&cid, &cin);
    u32 ecn_markings = 0;
    ecn.insert(&cid, &ecn_markings);
    u32 drop = 0;
    drops.insert(&cid, &drop);
    drop_results.insert(&cid, &drop);

    // calc_class is used to label the flows based on their responsiveness
    /* MAP_CLASSES is defined in ClassifierConfiguration.py. Effectively, it is a switch-case statement that uses the mapping given
    as class_mapping in the start-script */ 
    u32 calc_class = 9;
    {MAP_CLASSES}
    skb->tc_classid = calc_class;
    skb->tc_index = calc_class;
    return TC_ACT_OK;
}}

static void handleOutput(struct output *out, struct connectionInfo* cin, struct connectionID cid, u32 new_bytes, struct __sk_buff *skb){{
    u64 time = bpf_ktime_get_ns();
    u64 rtt = time - cin->timestamp;
    cin->timestamp=time;

    u32 * ecn_markings = ecn.lookup(&cid);
    u32* num_drops = drops.lookup(&cid);
    u16 new_class = 0;

    u32 old_class_mapped;

    {MAP_CLASSES_OLD_CLASS_ID}

    u32 new_class_mapped;

    out->bytes = cin->bytes;
    out->ecn_markings = (ecn_markings != NULL) ? ((*ecn_markings)) & 0xFF : 0;
    out->num_drops = (num_drops != NULL) ? ((*num_drops)) & 0xFF : 0; 
    
    if (ecn_markings != NULL && num_drops != NULL && (cin->bytes >= 4 * MSS)){{ 
        {responsive_code}
    }} 

    if (new_class == 1){{
        {MAP_CLASSES_NEW_CLASS_ID}

        if (old_class_mapped != new_class_mapped) {{
            *ecn_markings = 0;
            ecn.update(&cid, ecn_markings);

            *num_drops = 0;
            drops.update(&cid, num_drops);
        }}
    }}

    cin->bytes4 = cin->bytes3;
    cin->bytes3 = cin->bytes2;
    cin->bytes2 = cin->bytes;
    cin->bytes = new_bytes;  
    
    if (ecn_markings != NULL){{
        *ecn_markings = *ecn_markings << 8;
        ecn.update(&cid, ecn_markings);
    }}

    if (num_drops == NULL){{
        u32 tmp_drop = 0;
        drops.update(&cid, &tmp_drop);
    }}
    if (num_drops != NULL){{
        *num_drops = *num_drops << 8;
        drops.update(&cid, num_drops);
    }}

    out->srcIP = bpf_ntohl(cid.srcIP);
    out->dstIP = bpf_ntohl(cid.dstIP);
    out->srcPrt = bpf_ntohs(cid.srcPrt);
    out->dstPrt = bpf_ntohs(cid.dstPrt);
    out->timestamp = cin->timestamp;
    out->rtt = rtt;
    out->classID = cin->classID;
    
    out->newclass = new_class; 
    out->responsive_count_ECN = cin->responsive_count_ECN;
    out->unresponsive_count_ECN = cin->unresponsive_count_ECN;
    out->responsive_count_drop = cin->responsive_count_drop;
    out->unresponsive_count_drop = cin->unresponsive_count_drop;
    cycleUpdates.perf_submit(skb, out, sizeof(struct output));
}}

static int classifier_tcp(struct __sk_buff *skb){{
    void *data = (void *)(unsigned long)skb->data;
    void *data_end = (void *)(unsigned long)skb->data_end;
    int minPacketSizeIP = sizeof(struct ethhdr) + sizeof(struct iphdr);
    int minPacketSizeTCP = sizeof(struct ethhdr) + sizeof(struct iphdr) + 20; 
    if (data + minPacketSizeTCP >= data_end){{
        return TC_ACT_UNSPEC;
    }}

    struct iphdr *ip = data + sizeof(struct ethhdr);
    struct tcphdr *tcp = data + sizeof(struct ethhdr) + sizeof(struct iphdr);

    u64 bytes = 0;
    
    if (data + minPacketSizeTCP >= data_end){{
        return TC_ACT_UNSPEC;
    }}

    unsigned char *tcp_start = (unsigned char *) data + sizeof(struct ethhdr) + sizeof(struct iphdr);

    u32 seqNumber = bpf_ntohl(tcp->seq); 
    u32 serverSentAckNumber = bpf_ntohl(tcp->ack_seq); 

    if ((void *)(tcp_start + 13) > data_end) {{
        return TC_ACT_UNSPEC;
    }}

    u16 total_length = bpf_ntohs(ip->tot_len);
    u8 ip_header_length = ip->ihl * 4;
    u8 tcp_header_length = tcp->doff * 4;
    u32 tcpLength = total_length - ip_header_length - tcp_header_length;

    struct connectionID cid= {{ip->saddr, ip->daddr, tcp->source, tcp->dest}};

    struct connectionInfo* cin = infoMap.lookup(&cid);
    if (cin == NULL) {{
        u32 expectedAck = seqNumber + tcpLength;
        return createNewCinEntry(bytes, expectedAck, cid, skb);
    }} else {{
        struct seqAndAck* curr_seqAndAck = highestAckMap.lookup(&cid);

        if (curr_seqAndAck != NULL) {{
            u32 highestClientAck = curr_seqAndAck->highestAck;
            u32 expectedAckByClient = curr_seqAndAck->expectedAckOnAck;

            if ((highestClientAck >= cin->expectedAck) || (cin->expectedAck > MAX_UINT32 - (MAX_UINT32 / 4) && highestClientAck < (MAX_UINT32 / 4)) && ((serverSentAckNumber >= expectedAckByClient) && (curr_seqAndAck->active == true))){{
                
                curr_seqAndAck->active = false;
                cin->expectedAck = seqNumber + tcpLength;

                struct output out = {{}};
                strcpy(out.protocol, "TCP");
                handleOutput(&out, cin, cid, tcpLength, skb);  
                       
            }} else {{
                cin->bytes += tcpLength;
            }}
        }} else {{
            struct seqAndAck curr_seqAck = {{0, 0, false}};
            highestAckMap.insert(&cid, &curr_seqAck);
        }}
        infoMap.update(&cid, cin); 
        u32 calc_class = cin->classID;{MAP_CLASSES}
        skb->tc_classid = calc_class; 
        skb->tc_index = calc_class;
        return TC_ACT_OK;
    }}
}}

static int classifier_quic(struct __sk_buff *skb){{
    void *data = (void *)(unsigned long)skb->data; 
    void *data_end = (void *)(unsigned long)skb->data_end;
    int minQuicPacketSize = sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr) +  2;
    if (data + minQuicPacketSize >= data_end){{ 
        return TC_ACT_UNSPEC; 
    }}

    struct iphdr *ip = data + sizeof(struct ethhdr);
    struct udphdr *udp = data + sizeof(struct ethhdr) + sizeof(struct iphdr);
    struct quichdrs *quicS = data + sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr);

    if (!quicS->fixedBit){{
        return TC_ACT_UNSPEC;
    }}
    u64 bytes = 0;

    if (quicS->headerForm){{
        void* temp_data_end = data_end;
        int length = data_end - (data + sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr));
        
        int minQuicPacketSizeLong = sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr) + 9;
        if (data + minQuicPacketSizeLong >= data_end){{ 
            return TC_ACT_UNSPEC;
        }}
        struct quichdrl *quicL = data + sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr);

        unsigned char *quic_start = (unsigned char *) data + sizeof(struct ethhdr) + sizeof(struct iphdr) + sizeof(struct udphdr);
        if ((void *)(quic_start + 1) > data_end) return TC_ACT_UNSPEC;
        unsigned char *quic_ptr = quic_start;

        while ((void *)(quic_ptr + 1) < data_end) {{
            if ((void *)(quic_ptr + 1) > data_end) break;
            uint8_t long_packet_type = (quic_ptr[0] & 0b00110000) >> 4;

            if (long_packet_type == 0b00110000) {{
                return TC_ACT_OK;
            }}

            if (!(long_packet_type == QUIC_RETRY)){{
               
                if ((void *)(quic_ptr + INITIALBYTELENGTH + VERSIONLENGTH + DSTCIDFIELDLENGTH) > data_end) break;
                uint8_t dst_cid_len = *((uint8_t *)quic_ptr + INITIALBYTELENGTH + VERSIONLENGTH);

                if ((void *)(quic_ptr + INITIALBYTELENGTH + VERSIONLENGTH + DSTCIDFIELDLENGTH + dst_cid_len + SRCCIDFIELDLENGTH) > data_end) break;
                uint8_t src_cid_len = *((uint8_t *)quic_ptr + INITIALBYTELENGTH + VERSIONLENGTH + DSTCIDFIELDLENGTH + dst_cid_len);
                bpf_trace_printk("dst_cid_length: %d, src_cid_length: %d", dst_cid_len, src_cid_len);

                uint8_t length_after_scid = INITIALBYTELENGTH + VERSIONLENGTH + DSTCIDFIELDLENGTH + dst_cid_len + SRCCIDFIELDLENGTH + src_cid_len;
                unsigned char *token_ptr = quic_ptr + length_after_scid;
                uint64_t tokenLength = 0;
                uint8_t tokenLengthfieldLength = 0;

                if (long_packet_type == QUIC_INITIAL) {{
                    if ((void *)(token_ptr + 1) > data_end) break;

                    uint8_t first_two_bits_token = (token_ptr[0] & 0b11000000) >> 6;
                    u16 *tokenPointer_twoByte = ((u16 *)token_ptr);
                    u32 *tokenPointer_fourByte = ((u32 *)token_ptr);
                    u64 *tokenPointer_eightByte = ((u64 *)token_ptr);

                    switch (first_two_bits_token) {{
                    case 0:
                        tokenLength = *token_ptr;
                        tokenLength =  tokenLength & 0x3F;
                        tokenLengthfieldLength = 1;
                        break;
                    case 1: 
                        if ((void *)token_ptr + 2 >= data_end){{ 
                            return TC_ACT_UNSPEC; 
                        }}
                        tokenLength = bpf_ntohs(*tokenPointer_twoByte);
                        tokenLength = tokenLength & 0x3FFF;
                        tokenLengthfieldLength = 2;
                        break;
                    case 2: 
                        if ((void *)token_ptr + 4 >= data_end){{ 
                            return TC_ACT_UNSPEC; 
                        }}
                        tokenLength = bpf_ntohl(*tokenPointer_fourByte);
                        tokenLength = tokenLength & 0x3FFFFFFF;
                        tokenLengthfieldLength = 4;
                        break;
                    case 3: 
                        if ((void *)token_ptr + 8 >= data_end){{ 
                            return TC_ACT_UNSPEC; 
                        }}
                        tokenLength = bpf_ntohll(*tokenPointer_eightByte);
                        tokenLength = tokenLength & 0x3FFFFFFFFFFFFFFF;
                        tokenLengthfieldLength = 8;
                        break;
                    }};
                    bpf_trace_printk("tokenLength: %x",tokenLength);
                }}

                if(!(tokenLength < 0) & (tokenLength < 1500)){{
                        bpf_trace_printk("tokenLengthfieldLength %d", tokenLengthfieldLength);
                        bpf_trace_printk("tokenLength %d", tokenLength);
                }} else {{
                    return TC_ACT_UNSPEC;
                }}

                unsigned char *payload_length_ptr = token_ptr + tokenLengthfieldLength + tokenLength;
                uint8_t payloadLengthfieldLength = 0;
                u64 payload_length = 0;
                if ((void *)(payload_length_ptr + 2) > data_end) return TC_ACT_UNSPEC;

                uint8_t first_two_bits_payload = (payload_length_ptr[0] & 0b11000000) >> 6;
                u16 *payloadPointer_twoByte = (u16 *)payload_length_ptr;
                u32 *payloadPointer_fourByte = (u32 *)payload_length_ptr;
                u64 *payloadPointer_eightByte = (u64 *)payload_length_ptr;

                switch (first_two_bits_payload) {{
                case 0:
                    payload_length = (*payload_length_ptr);
                    payload_length = payload_length & 0x3F;
                    payloadLengthfieldLength = 1;
                    break;
                case 1:
                    if ((void *)payload_length_ptr + 2 >= data_end){{ 
                        return TC_ACT_UNSPEC; 
                    }}
                    payload_length = bpf_ntohs(*payloadPointer_twoByte);
                    payload_length = payload_length & 0x3FFF;
                    payloadLengthfieldLength = 2;
                    break;
                case 2:
                    if ((void *)payload_length_ptr + 4 >= data_end){{ 
                        return TC_ACT_UNSPEC; 
                    }}
                    payload_length = bpf_ntohl(*payloadPointer_fourByte);
                    payload_length = payload_length & 0x3FFFFFFF;
                    payloadLengthfieldLength = 4;
                    break;
                case 3:
                    if ((void *)payload_length_ptr + 8 >= data_end){{ 
                        return TC_ACT_UNSPEC; 
                    }}
                    payload_length = bpf_ntohll(*payloadPointer_eightByte);
                    payload_length = payload_length & 0x3FFFFFFFFFFFFFFF;
                    payloadLengthfieldLength = 8;
                    break;
                }};

                if(!(payload_length < 0) & (payload_length < 1500)){{
                    bpf_trace_printk("payload_length: %d",payload_length);
                    bpf_trace_printk("payloadLengthfieldLength: %x", payloadLengthfieldLength);
                    quic_ptr = payload_length_ptr + payloadLengthfieldLength + payload_length;
                }} else {{
                    return TC_ACT_UNSPEC;
                }}

                if ((void *)quic_ptr + INITIALBYTELENGTH + VERSIONLENGTH + DSTCIDFIELDLENGTH + SRCCIDFIELDLENGTH >= data_end){{ 
                    return TC_ACT_UNSPEC; 
                }}
            }}

            bpf_trace_printk("whole Packet Length: %d", length);
            bpf_trace_printk("Current Packet Length: %d", quic_ptr - (u8 *)quicL);
            bpf_trace_printk("Remaining: %d", length - (quic_ptr - (u8 *)quicL));

            quicL = ((void *)quic_ptr);

            uint8_t value = *quic_ptr;
            char binary[9] = {{0}};
            for (int i = 0; i < 8; i++) {{
                binary[7 - i] = (value & (1 << i)) ? '1' : '0';
            }}
            bpf_trace_printk("next byte: %s", binary);
            
            if((void *)(quicL) + 2 >= data_end){{
                return TC_ACT_UNSPEC;
            }}
            
            bpf_trace_printk("Lookup Next Header HeaderForm : %x ",quicL->headerForm);
            if (!(quicL->headerForm)){{
                bytes = data_end - (void *)quicL; 
                bpf_trace_printk("----- Found Short Header Packet with %d bytes", bytes);
                struct connectionID cid= {{ip->saddr, ip->daddr, udp->source, udp->dest}};
                struct connectionInfo* cin = infoMap.lookup(&cid);
                if (cin == NULL) {{ 
                    struct connectionID cid = {{ip->saddr, ip->daddr, udp->source, udp->dest}}; 
                    struct connectionInfo cin = {{}}; 
                    cin.lastSpins = 0 - quicL->longHeaderType & 0b01;
                    bpf_trace_printk("new connection, create entry");
                    cin.timestamp = bpf_ktime_get_ns();
                    cin.classID = 0;
                    cin.rtt = 0;
                    cin.bytes = bytes;
                    cin.responsive_count_ECN = 0;
                    cin.responsive_count_drop = 0;
                    cin.unresponsive_count_ECN = 0;
                    cin.unresponsive_count_drop = 0;
                    
                    infoMap.insert(&cid, &cin); 
                    u32 ecn_markings = 0;
                    ecn.insert(&cid, &ecn_markings);
                    u32 drop = 0;
                    struct connectionID cid2 = {{0,0,0,0}}; 
                    drops.insert(&cid2, &drop);
                    drop_results.insert(&cid2, &drop);
                    return TC_ACT_OK;
                }} else {{ 
                    cin->bytes += bytes;
                    bpf_trace_printk("already existing connection, update spinbit with %d ", quicL->longHeaderType & 0b01);
                    infoMap.update(&cid, cin); 
                    return TC_ACT_OK;
                }}
            }}
            else {{
                return TC_ACT_UNSPEC;
            }}  
        }} 
        return TC_ACT_UNSPEC;
    }}

    struct connectionID cid= {{ip->saddr, ip->daddr, udp->source, udp->dest}};
    struct connectionInfo* cin = infoMap.lookup(&cid);
    if (cin == NULL) {{
        u32 bytes = skb->len - minQuicPacketSize + 2;
        return createNewCinEntry(bytes, 0, cid, skb);
    }} else {{ 
        if ((cin->lastSpins + quicS->spinBit) % (1 << (EDGE_THRESHOLD)) == (1 << (EDGE_THRESHOLD - 1))) {{
            struct output out = {{}};
            strcpy(out.protocol, "QUIC");
            out.lastSpins = cin->lastSpins;
            cin->lastSpins = (cin->lastSpins << 1) + quicS->spinBit; 
            
            u32 new_bytes = skb->len - minQuicPacketSize + 2;
            handleOutput(&out, cin, cid, new_bytes, skb); 
        }}else {{
            cin->bytes += skb->len - minQuicPacketSize + 2;
            cin->lastSpins = (cin->lastSpins << 1) + quicS->spinBit;
        }}
        infoMap.update(&cid, cin);
        u32 calc_class = cin->classID;{MAP_CLASSES}
        skb->tc_classid = calc_class; 
        skb->tc_index = calc_class;
        return TC_ACT_OK;
    }}
}}

int entrypoint_classifier(struct __sk_buff *skb){{
    void *data = (void *)(unsigned long)skb->data;
    void *data_end = (void *)(unsigned long)skb->data_end; 
    int minPacketSize = sizeof(struct ethhdr) + sizeof(struct iphdr); 
    if (data + minPacketSize >= data_end){{
        return TC_ACT_UNSPEC;
    }}

    struct iphdr *ip = data + sizeof(struct ethhdr);

    if (ip->protocol == IPPROTO_TCP){{ 
        return classifier_tcp(skb);
    }} else if (ip->protocol == IPPROTO_UDP){{ 
        return classifier_quic(skb);
    }} else {{
        return TC_ACT_UNSPEC;
    }}
}}
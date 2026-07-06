def generate_dns_mimic(domain: str) -> str:
    """
    Generates a dynamic AmneziaWG obfuscation payload representing a DNS query
    for the specified domain. 
    Uses <r 2> to randomize the DNS Transaction ID for every packet.
    """
    if not domain:
        domain = "www.yahoo.com"
        
    # DNS Header (minus the 2-byte Transaction ID, which is randomized by <r 2>)
    # Flags: 0x0100 (Standard Query)
    # Questions: 0x0001 (1 Question)
    # Answer RRs: 0x0000
    # Authority RRs: 0x0000
    # Additional RRs: 0x0000
    header = b"\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    
    # QNAME
    qname = b""
    for part in domain.split('.'):
        if part:
            qname += bytes([len(part)]) + part.encode('utf-8')
    qname += b"\x00"
    
    # QTYPE (A = 0x0001) and QCLASS (IN = 0x0001)
    footer = b"\x00\x01\x00\x01"
    
    packet_hex = (header + qname + footer).hex()
    
    return f"<r 2><b 0x{packet_hex}>"

MAX_TRANSMISSION_UNIT = 1500
TS_PACKET_SIZE = 188
TS_PACKET_NUM = 7
TS_PAYLOAD_SIZE = TS_PACKET_NUM * TS_PACKET_SIZE


def _get_pcr(tsPacket):
    if len(tsPacket) < 188:
        return -1
    if not (tsPacket[3] & 32):
        return -1
    length = tsPacket[4]
    if length == 0:
        return -1
    if not (tsPacket[5] & 16):
        return -1

    pref = tsPacket[6:10]
    vRef = int.from_bytes(pref, 'big')
    vRef = vRef << 1
    vRef += tsPacket[10] / 128
    vExt = (tsPacket[10] % 2) * 256 + tsPacket[11]
    all = vRef * 300 + vExt
    return all // 27000


def get_ts_payload(f):
    while True:
        payload = f.read(TS_PAYLOAD_SIZE)
        if not payload:
            print('Finished reading the file.')
            break
        length = len(payload)
        for i in range(length // 188):
            if payload[i * TS_PACKET_SIZE] != 0x47:
                print('Packet does not begin with 0x47')
        yield payload

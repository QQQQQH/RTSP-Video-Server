MAX_TRANSMISSION_UNIT = 1500
TS_PACKET_SIZE = 188
TS_PACKET_NUM = 7


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


def unit_start(tsPacket):
    return tsPacket[1] & 64


def get_ts_payload(f):
    finished = False
    while True:
        if finished:
            break
        payload = bytes()
        unitStart = False
        for i in range(TS_PACKET_NUM):
            tsPacket = f.read(TS_PACKET_SIZE)
            if not tsPacket:
                finished = True
                print('Finished reading .ts file')
                break
            if unit_start(tsPacket):
                if i == 0:
                    unitStart = True
                else:
                    f.seek(-len(tsPacket), 1)
                    break
            if tsPacket[0] != 0x47:
                print('Package dose not start with 0x47')
            payload += tsPacket
        yield payload, unitStart

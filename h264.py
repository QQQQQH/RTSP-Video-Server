from rtpPacket import RtpPacket
import socket

RTP_MAX_PKT_SIZE = 1400


def _start_code3(buf):
    return buf[0] == 0 and buf [1] == 0 and buf [2] == 0 and buf[3] == 1


def _start_code4(buf):
    return buf[0] == 0 and buf [1] == 0 and buf [2] == 0 and buf[3] == 0 and buf[4] == 1


def _get_next_start_index(buf):
    bufLen = len(buf)
    for i in range(3, bufLen - 4):
        t = buf[i:i + 4]
        if _start_code3(t) or _start_code4(t):
            return i
    t = buf[bufLen - 3:]
    if _start_code3(t):
        return bufLen - 3
    return -1


def get_H264_frame(f, size):
    buf = f.read(size)
    if not _start_code3(buf) and not _start_code4(buf):
        return None
    nextStartIdx = _get_next_start_index(buf)
    if nextStartIdx == -1:
        return None
    else:
        frameSize = nextStartIdx
        f.seek(frameSize - len(buf), 1)
    return buf[:frameSize]


def send_H264_frame(scoket, target, rtpPacket, frame, frameSize):
    naluType = frame[0]
    if frameSize <= RTP_MAX_PKT_SIZE:
        rtpPacket.set_payload(frame)
        packet = rtpPacket.get_packet()
        scoket.sendto(packet, target)
        rtpPacket.seqNum += 1
        return len(packet)
    else:
        sentBytes = 0
        pktNum = frameSize // RTP_MAX_PKT_SIZE
        remainPktSize = frameSize % RTP_MAX_PKT_SIZE
        pos = 1
        payload0 = bytes([(naluType & 96) | 28])
        for i in range(0, pktNum):
            if i == 0:
                payload1 = bytes([naluType & 31 | 128])
            elif remainPktSize == 0 and i == pktNum - 1:
                payload1 = bytes([naluType & 31 | 64])
            else:
                payload1 = bytes([naluType & 31])
            payload = payload0 + payload1 + frame[pos:pos + RTP_MAX_PKT_SIZE]
            rtpPacket.set_payload(payload)

            packet = rtpPacket.get_packet()
            scoket.sendto(packet, target)
            rtpPacket.seqNum += 1
            sentBytes += len(packet)
            pos += RTP_MAX_PKT_SIZE

        if remainPktSize > 0:
            payload1 = bytes([naluType & 31 | 64])
            payload = payload0 + payload1 + frame[pos:pos + RTP_MAX_PKT_SIZE]
            rtpPacket.set_payload(payload)
            
            packet = rtpPacket.get_packet()
            scoket.sendto(packet, target)
            rtpPacket.seqNum += 1
            sentBytes += len(packet)
            pos += RTP_MAX_PKT_SIZE
    return sentBytes

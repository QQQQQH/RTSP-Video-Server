from string import Template

version = 'RTSP/1.0'
okMessage = version + ' 200 OK\r\n'


def parse_request(requestLines):
    requestDic = {}
    for line in requestLines:
        words = line.split(': ')
        if len(words) != 2:
            continue
        requestDic[words[0].strip()] = words[1].strip()
    return requestDic


def generate_response(responseDic, append=None):
    response = okMessage
    for key, value in responseDic.items():
        response += str(key) + ': ' + str(value) + '\r\n'
    response += '\r\n'
    if append:
        response += append + '\r\n'
    return response


def generate_session_sdp(sessionId, sdpVersion=0, user='-', sessionVersion=1, networkType='IN', ipType='IP4',
                         ip='127.0.0.1'):
    sdp = Template('v=${sdpVersion}\r\n'
                   'o=${user} ${sessionId} ${sessionVersion} ${networkType} ${ipType} ${ip}\r\n'
                   't=0 0\r\n'
                   'a=control:*\r\n')
    return sdp.substitute(sdpVersion=str(sdpVersion),
                          user=user,
                          sessionId=sessionId,
                          sessionVersion=sessionVersion,
                          networkType=networkType,
                          ipType=ipType,
                          ip=ip)


def generate_ts_media_sdp(port=0, protocol='RTP/AVP', rate=90000, frameRate=30, networkType='IN', ipType='IP4',
                          ip='127.0.0.1'):
    sdp = Template('m=video ${port} ${protocol} 33\r\n'
                   'a=rtpmap:33 MP2T/${rate}\r\n'
                   'a=framerate:${frameRate}\r\n'
                   'c=${networkType} ${ipType} 127.0.0.1\r\n')
    return sdp.substitute(port=str(port),
                          protocol=protocol,
                          rate=str(rate),
                          frameRate=str(frameRate),
                          networkType=networkType,
                          ipType=ipType,
                          ip=ip)

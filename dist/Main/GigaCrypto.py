from operator import xor

class GigaCrypto:
    def __init__(self):
        self.CRC_PRESET = 0xFFFF
        self.CRC_POLYNOM = 0xA001
        self.m_bDefaultEncodeKey = bytearray([0xFF, 0xFF])

    def Decode(self, pbKey, uHeaderLength, pbCoded, pbUncoded):
        iLen = 0
        uKeyLen = 0
        if pbKey is not None:
            uKeyLen = len(pbKey)

        if pbCoded is not None:
            uCodedLen = len(pbCoded)
            uUncodedLen = (uCodedLen - 1)
            pbUncoded = bytearray(uUncodedLen)

            iLenANDpbUncoded = self.Decode8(pbKey, uKeyLen, uHeaderLength, pbCoded, uCodedLen, pbUncoded, uUncodedLen)
        return iLenANDpbUncoded

    def Decode8(self, pbKey, uKeyLen, uHeaderLength, pbCoded, uCodedLen, pbUncoded, uUncodedLen):
        if uCodedLen > 0 :
            uCodedLen = uCodedLen -1
            uRand = self.GetRandKey(int(pbCoded[uCodedLen]), pbKey, uKeyLen)

            if uCodedLen > uUncodedLen:
                uCodedLen = uUncodedLen
            if (pbKey is None) or (uKeyLen == 0):
                pbKey[:] = self.m_bDefaultEncodeKey
                uKeyLen = len(self.m_bDefaultEncodeKey)
            bRnd = uRand & 0xFF

            for i in range(0, uCodedLen):
                bData = bRnd
                bRnd = pbCoded[i]
                bKey = pbKey[xor(uRand, i) % uKeyLen]

                if uHeaderLength == 0:
                    R = uRand & 7

                uRand = xor(xor(uRand, int(bKey)), i)

                if i < uHeaderLength:
                    pbUncoded[i] = bRnd
                    bRnd = xor(bData, uRand & 0xFF)
                else:
                    bData = xor(bData, bRnd)
                    bData = xor(bData, (uRand & 0xFF) )

                    if uHeaderLength > 0:
                        R = uRand & 7

                    mask = 127
                    bData = ( ((bData >> (8-R)) & mask) | ((bData << R) & mask) )

                    pbUncoded[i] = bData
                uRand = ((uRand >> 15) | (uRand << 1)) & 0xFFFF
                
        iLenANDpbUncoded = [uCodedLen, pbUncoded]

        return iLenANDpbUncoded

    def GetRandKey(self, uRand, pbKey, uKeyLen):
        uRand = xor(uRand, self.CRC_PRESET)
        for i in range(0, uKeyLen):
            uRand = xor(uRand, pbKey[i])
            if uRand & 1:
                uRand = xor((uRand >> 1), self.CRC_POLYNOM)
            else:
                uRand = uRand >> 1
        return  uRand




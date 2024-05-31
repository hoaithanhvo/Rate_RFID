from enum import Enum
from operator import xor
import GigaCrypto
import BarcodeInfo
import sys

class EncodeTag:
    class HeaderConstants(Enum):
        Nothing = 0
        Barcode = 0x10

    class BarcodeTypeConstants(Enum):
        Nothing = 0
        Bundle = 1
        Machine = 2
        Employee = 3

    class HeaderTypeConstants(Enum):
        Nothing = 0
        Bundle = (0x10 | (1 << 8))
        Machine = (0x10 | (2 << 8))
        Employee = (0x10 | (3 << 8))

    class RandByteTypeConstants(Enum):
        SystemTicks = 0
        DataCRC16 = 1

    def __init__(self, bCustomCodes, bApplicationCodes):
        self.GEN2_PC_BYTE_LEN = 2
        self.FLAG_RND_BYTE_LEN = 1
        self.FLAG_WITH_DATA = 0x80
        self.FLAG_WITH_HEADER = 0x40
        self.DATA_FLAG_RND_BYTE_LEN = 2

        self.m_bCustomCodes = bytearray()
        self.m_bApplicationCodes = bytearray()
        self.m_bFactoryKey = bytearray()
        self.m_iRandByteType = self.RandByteTypeConstants

        self.bCustomCodes = self.HexToBytes(bCustomCodes)

        self.bApplicationCodes = self.HexToBytes(bApplicationCodes)

        self.m_bFactoryKey = self.MergeBytes(self.bCustomCodes, self.bApplicationCodes)

    def HexToBytes(self, szHex):
        bResults = bytearray()
        i = 0
        j = 0
        iLen = 0
        if szHex is not None:
            iLen = len(szHex)
            if (iLen & 1) == 1:
                szHex = "0" + szHex
                iLen = len(szHex)
            bResults = bytearray((iLen >> 1))
            for i in range(1, iLen, 2):
                try:
                    bResults[j] = int(self.mid(szHex, i, 2), 16)
                except Exception as e:
                    print (e)
                    bResults = None
                j = j+1
        return bResults

    def MergeBytes(self, bArrayA, bArrayB):
        if bArrayA is not None:
            iLenA = len (bArrayA)
        if bArrayB is not None:
            iLenB = len (bArrayB)
        iLen = (iLenA + iLenB)

        if iLen > 0:
            bBuffer = bytearray(iLen)
            iLen = 0
        if iLenA > 0:
            bBuffer = bytearray(bArrayA)
            iLen = iLen + iLenA
        if iLenB > 0:
            bBuffer = bBuffer + bArrayB
            iLen = iLen + iLenB

        return bBuffer
    
    def BytesToHex(self, bArray):
        szHex = None
        if bArray is not None:
            a=0
            #szHex = 0 Unfinished
        return szHex
    
    def ToBarcode(self, bEncodeEPCs):
        iHeaderType = self.HeaderTypeConstants.Nothing
        bEncodeEPCs = self.HexToBytes(bEncodeEPCs)
        bBarcodes = bytearray()
        if bEncodeEPCs is not None:
            iLen = len(bEncodeEPCs)
            iHeaderLen = 0
            if (iLen & 1) == 0 and iLen > 2:
                iLen = ((bEncodeEPCs[0] & 0xF8) >> 2)
                iLen = iLen + 2
                if len(bEncodeEPCs) < iLen:
                    iLen = 0
            if iLen > 0:
                bFactoryKeys = bytearray(self.m_bFactoryKey)
                try:
                    bFlagAndRnd = bEncodeEPCs[iLen-1]
                    if bFlagAndRnd & self.FLAG_WITH_HEADER:
                        iHeaderLen = 2
                        try:
                            iHeaderType = self.HeaderTypeConstants( int(bEncodeEPCs[3] << 8) | int(bEncodeEPCs[2]) )
                        except Exception as e:
                            print (e)
                            iHeaderType = self.HeaderTypeConstants(0)
                    
                    iLen = iLen - self.GEN2_PC_BYTE_LEN
                    bEncodeBarcodes = bytearray(iLen)

                    bEncodeBarcodes[0:] = bEncodeEPCs[self.GEN2_PC_BYTE_LEN : self.GEN2_PC_BYTE_LEN + iLen]

                    iLenANDbBarcodes = GigaCrypto.GigaCrypto().Decode(bFactoryKeys, iHeaderLen, bEncodeBarcodes, bBarcodes)
                    iLen = iLenANDbBarcodes[0]
                    bBarcodes = iLenANDbBarcodes[1]
                    
                    if (bFlagAndRnd & self.FLAG_WITH_DATA) == 0:
                        iLen = iLen - 1
                        bBarcodes = bBarcodes[:iLen]

                        
                except Exception as ex:
                    bBarcodes = bytearray()
                    print ('Error {0}'.format(ex))
                    print (sys.exc_info())
                    
        return BarcodeInfo.BarcodeInfo(iHeaderType, bBarcodes)

    def left(self, s, amount):
        return s[:amount]

    def right(self, s, amount):
        return s[-amount:]

    def mid(self, s, offset, amount):
        return s[offset-1:offset + amount-1]
    
    def ToUDC(self, epc):
        gigaKey = [0x33, 0x41, 0x35, 0x42, 0x36, 0x43, 0x37, 0x44, 0x39, 0x45]
        header = epc[0:2]
        dataType = 0
        dataLength = 0       
        barcode = ""       
        try:
            # BSE Mode
            if header == "BA":
                epcBytes = self.HexToBytes(epc)
                
                barcodeInfo = str(bin(epcBytes[1])[2:])
                dataLength = epcBytes[1]
                
                if len(barcodeInfo) != 8:
                    dataType = 0
                else:
                    dataType = 1
           
                if dataType == 0:
                    # BCD Data Type
                    if dataLength % 2 == 0:
                        dataLength = dataLength/2
                    else:
                        dataLength = dataLength/2 + 1
                else:
                    # ASCII Data Type
                    dataLength = dataLength - 128
                    pass
                
                for i in range(0, dataLength):
                    
                    epcHexInt = epcBytes[2+i]
                    if i >= len(gigaKey):
                        gigaKeyHexInt = gigaKey[i%len(gigaKey)]
                    else:
                        gigaKeyHexInt = gigaKey[i]
                    
                    barcode_tmp = hex(xor(epcHexInt, gigaKeyHexInt))[2:]
                    
                    if dataType == 0:
                        if len(barcode_tmp) == 1:
                            barcode_tmp = "0" + barcode_tmp
                        barcode = barcode + barcode_tmp
                    else:
                        barcode = barcode + barcode_tmp.decode("hex")
                    
                barcode = barcode[:epcBytes[1]]               
        except:
                barcode = ""
                    
        return barcode
    
    def ToASCII(self, epc):
        epcAscii = ""
        for i in range(4, len(epc), 2):
            try:
                if int(epc[i:i+2], 16) > 31 and int(epc[i:i+2], 16) < 127:
                    epcAscii = epcAscii + bytes.fromhex(epc[i:i+2]).decode("ASCII")
            except:
                pass
        return epcAscii
        
    
    def ToTitasCode(self, epcString):
        epcString = epcString[4:]
        epcBinaryString = ""
        for i in range(2, len(epcString)+2, 2):
            epcBinaryString = epcBinaryString + bin(int(epcString[i-2:i], 16))[2:].zfill(8)
        itemBinaryString = epcBinaryString[0:90]
        serialBinaryString = epcBinaryString[90:]
        serialNumber = int(serialBinaryString, 2)
        itemName = ""
        numOfBytes = int(len(itemBinaryString) / 6)
        for i in range(0, numOfBytes):
            itemName = itemName + self.GS1BinaryToString(itemBinaryString[6*i:6*i+6])
        return (itemName, serialNumber)
    
    def hexToBinary(self, data):
        result = ""
        for i in range(0, len(data), 2):
            result = result + bin(int(data[i:i+2], 16))[2:].zfill(8)
        return result

    def SPEC2000Decoder(self, data):
        
        data = self.hexToBinary(data)
        
        n = 6
        binArray = [data[i:i+n] for i in range(0, len(data), n)]
        result = []
        for b in binArray:
            if b[0] == "0":
                result.append(chr(int("01"+b, 2)))
                
            elif b[0] == "1":
                result.append(chr(int("00"+b, 2)))
        return result
    
    
        
    def GS1BinaryToString(self, bitVal):
        bitInt = int("00"+bitVal, 2)
        GS1String = ""
        if 0 <= bitInt <= 26:
            GS1String = chr(64+bitInt)
        elif 48 <= bitInt <= 57:
            GS1String = chr(bitInt)
            
        return GS1String
    
    def hexStringToBinaryString(self, hexString):
        binaryStr = ""
        for i in range(0, len(hexString), 2):
            binaryStr = binaryStr + bin(int(hexString[i:i+2], 16))[2:].zfill(8)
            
        return binaryStr
    
    def parseSGTINPartition(self, partition):
        company = None
        reference = None
        
        if partition == 0:
            company = 40
            reference = 4
        elif partition == 1:
            company = 37
            reference = 7
        elif partition == 2:
            company = 34
            reference = 10
        elif partition == 3:
            company = 30
            reference = 14
        elif partition == 4:
            company = 27
            reference = 17
        elif partition == 5:
            company = 24
            reference = 20
        elif partition == 6:
            company = 20
            reference = 24
            
        return company, reference
             
    def parseSGTIN96HexString(self, epcString):
        if len(epcString) != 24:
            print ("Incorrect data length for sgtin-96 hexstring")
            return None, None
        try:
            binaryStr = self.hexStringToBinaryString(epcString)
            str_header = binaryStr[0:8]
            str_filterValue = binaryStr[8:11]
            str_partitionValue = binaryStr[11:14]
            filterValue = int(str_filterValue, 2)
            partitionValue = int(str_partitionValue, 2)
            
            company_length, reference_length = self.parseSGTINPartition(partitionValue)
            
            temp = binaryStr[14:58]
            str_companyPrefix = temp[0:company_length]
            str_referencePrefix = temp[company_length:]
            
            cp_digit_length = 12 - partitionValue
            ir_digit_length = partitionValue + 1
            
            str_companyPrefix = str(int(str_companyPrefix, 2))
            str_referencePrefix = str(int(str_referencePrefix, 2))
            
            while (len(str_companyPrefix) < cp_digit_length):
                str_companyPrefix = "0" + str_companyPrefix
            
            while (len(str_referencePrefix) < ir_digit_length):
                str_referencePrefix = "0" + str_referencePrefix
            
            gtin_temp = str_referencePrefix[0:1] + str_companyPrefix + str_referencePrefix[1:]
            
            if (len(gtin_temp) != 13):
                return None
            else:
                checkSum = 0
                index = 0
                for i in range(0, len(gtin_temp)):
                    index = len(gtin_temp) - 1 - i
                    if i%2 == 0:
                        checkSum = checkSum + int(gtin_temp[index], 36) * 3
                    elif i%2 == 1:
                        checkSum = checkSum + int(gtin_temp[index], 36)
                        
                check_bit = 0
                if checkSum % 10 > 0:
                    check_bit = str(10 - (checkSum%10))
                
                str_GTIN14 = gtin_temp + check_bit
            
            # Last 38 bits are serial number
            str_serialNumber = binaryStr[58:96]
            serialNumber = int(str_serialNumber, 2)
            """
            serialNumber = str(int(str_serialNumber, 2))
            
            while (len(serialNumber) < 12):
                serialNumber = "0" + serialNumber
            """
            
            return str_GTIN14, serialNumber
        
        except:
            return None, None
            
        

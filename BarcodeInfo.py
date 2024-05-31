import EncodeTag

class BarcodeInfo:
    def __init__(self, iHeaderType, bBarcodes):

        self.Barcodes = bytearray()
        self.encodeTag = EncodeTag.EncodeTag("0000000003171215", "01215A01")
        self.HeaderType = self.encodeTag.HeaderTypeConstants
        self.mask = 127

        bNewBarcodes = bytearray()
        iLen = 0
        iHeaderLen = 0
        if bBarcodes is not None:
            iLen = len(bBarcodes)
            if iLen >2:

                try:
                    iType = self.encodeTag.HeaderTypeConstants(((bBarcodes[1] << 8)) | ((bBarcodes[0])))
                except Exception as e:
                    iType = self.encodeTag.HeaderTypeConstants(0)
                    #print (e)

                if iHeaderType.value == self.encodeTag.HeaderTypeConstants.Nothing.value:
                    if isinstance(iType, self.encodeTag.HeaderTypeConstants):
                        iHeaderType = iType
                elif iHeaderType.value != iType.value:
                    iHeaderLen = 2

            elif iHeaderType != self.encodeTag.HeaderTypeConstants.Nothing:
                iHeaderLen = 2

        if iHeaderLen == 2:
            bNewBarcodes = bytearray(iLen+2)
            bNewBarcodes[0] = iHeaderType.value & 0xFF
            bNewBarcodes[1] = (iHeaderType.value >> 8) & 0xFF
            if iLen > 0:
                bNewBarcodes[2:iLen-1] = list(bBarcodes)
        else:
            bNewBarcodes = bBarcodes

        self.HeaderType = iHeaderType.name

        self.Barcodes = bBarcodes
        
        
    def Text(self):
        szBarcode = ""
        if (self.Barcodes is not None) and (len(self.Barcodes) > 0) :
            bIsPrintable = True
            iHeaderLen = 0

            if self.HeaderType == self.encodeTag.HeaderConstants.Nothing.name:
                if self.encodeTag.HeaderConstants.Nothing.value == ( (int(self.Barcodes[1]) << 8)  | int(self.Barcodes[0]) ):
                    iHeaderLen = 2
            else:
                iHeaderLen = 2

            for i in range(iHeaderLen, len(self.Barcodes)):
                if self.Barcodes[i] < 32 or self.Barcodes[i] > 127:
                    bIsPrintable = False
                    break
            if bIsPrintable:
                if iHeaderLen < len(self.Barcodes):
                    szBarcode = self.Barcodes[iHeaderLen:len(self.Barcodes)-iHeaderLen+2].decode("ascii")
        
        return szBarcode

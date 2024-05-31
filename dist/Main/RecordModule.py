import datetime
import os
import csv
import glob
import threading

class RecordModule:
    def __init__(self, ):
        self.script_dir = os.getcwd() + "/Tag Log/"
        self.fileName = self.getTodayDate() + ".csv"
        self.fileNameWithPath = os.path.join(self.script_dir,  self.fileName)

    def getTodayDate(self):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        return today

    def writeLog(self, rowData=None, blUpdateDB=0, fileName=None, writeType="a"):
        if fileName is not None:
            fileName = fileName + "-" + str(blUpdateDB) + ".csv"
        else:
            fileName = self.getTodayDate() + "-" + str(blUpdateDB) + ".csv"
        fileNameWithPath = os.path.join(self.script_dir, fileName)

        with open( fileNameWithPath, writeType) as text_file:
            writer = csv.writer(text_file)
            if rowData is not None:        
                writer.writerow(rowData)
            else:
                writer.writerow([epc, readerId, antenna, time, blUpdateDB])

    def deleteFile(self, file):
        if os.path.exists(file):
            os.remove(file)
        else:
            print("The file does not exist")
            
    def getFullLocation(self, fileName):
        fileNameWithPath = os.path.join(self.script_dir,  fileName)
        return fileNameWithPath

    # return a list of file in folder
    def globFile(self, location, file):
        return glob.glob( os.path.join(location, file) )
    
    # return only file name without whole file path
    def globOneFileName(self, fileLoation):
        fileName = fileLoation.split("/")[-1]
        return (fileName)

    # Return Two-dimensional array of each tag log
    def ckFileDateToDB(self):
        #threading.Timer(10.0, self.ckFileDateToDB, nDays).start()

        unInsertDict = {}
        unInsertDataList = []
        
        fileList = self.globFile( self.script_dir, "*-0.csv")
        fileList.sort()

        for csvFileName in fileList:
            fileLocation = os.path.join(self.script_dir,  csvFileName)
            with open( fileLocation ) as csvFile:
                rows = csv.reader(csvFile) # A two-dimensional array
                for row in rows:
                        unInsertDataList.append(row)
            unInsertDict[self.globOneFileName(csvFileName).split(".")[0][0:-2]] = unInsertDataList
            unInsertDataList = []
        return  unInsertDict

    # Delete Log File which date over n days
    def ckFileOutOfDate(self, nDays):
        fileName = os.path.basename(csvFileName)
        fileDate = datetime.datetime.strptime(fileName.split(".")[0], "%Y-%m-%d")
        if (datetime.datetime.now() - fileDate).days > nDays:
            os.remove(fileLocation)











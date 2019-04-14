#############################################################
###########  CAPTURE ENGINE  ################################

import serial
import serial.tools.list_ports
import time
import struct
import sys
from itertools import chain


# fileName = "unpacked" + str(time.time())
# filePath = "./" + fileName + ".csv"
# dumpFile = open(filePath, "w")

#############################################################
######  GLOBAL VAR ##########################################
val =''
duration=3
serWaiting = 0
toGetatATime = 4096
ser = serial.tools.list_ports.comports()[0]
com =''
CHA = []; CHB= []

userParam = {"testMode":"", "isDual":False, "isLogic": False, \
    "CHA":False, "CHB": False, "sampleRate":200, "duration":1, \
    "toGet":2000, "COM1":"","COM2":"","BSModel1":"","BSModel2":"", \
    "L0":False,"L1":False,"L2":False,"L3":False,"L4":False,"L5":False,"L6":False,"L7":False  }

summaryDict = {"dataPt":0, "actualDuration":0, "sample_rate":0}


#############################################################
######  FIND BITSCOPE #######################################

def findBS():
    global com
    connectedBS = []; comPort =[]
    if sys.platform == 'linux':       
        idx = 12        
    else:
        idx =4        
    comlist = serial.tools.list_ports.comports()
    print(comlist)
    
    for cnt in range(len(comlist)):
        ser = serial.Serial(comlist[cnt].device, 115200, timeout= 1)
        ser.write(b"?")
        time.sleep(0.05)
        tempStr = (ser.read(20)[2:9])   
        print(tempStr)
        tempCom = str(comlist[cnt])[0:idx] 
        comPort.append(tempCom) if tempStr.startswith(b'BS') else None
        connectedBS.append((str(tempStr)[1:]).strip("'").strip("b")) if tempStr.startswith(b'BS') else None            

    userParam.update({"COM1":comPort[0]})
    userParam.update({"BSModel1":connectedBS[0]})

    if len(connectedBS) > 1:
        userParam.update({"COM2":comPort[1]})
        userParam.update({"BSModel1":connectedBS[1]})
    com = comPort[0]
    print('system os',sys.platform)
    print(connectedBS)
    ser.close()
    return connectedBS

def connectBS():
    global ser
    print('connectBSBSmachine',com)
    ser = serial.Serial(com, 115200, timeout=1.0)
    return ser


#############################################################
###### SETTINGS FROM FRONT PANEL ############################
    
    # return com
def testMode(input):
    global val
    if input == "Dual" or input == "Mixed":
        val = "01"
    elif input == "SingleFast":
        val = "02"
    elif input == "DualMacro":
        val = "03"
    elif input == "SingleMacro":
        val = "04"
    else:
        print("error mode!!")
    return val

def channelMode(isDual,CHA,CHB):
    global val
    if isDual:
        val = "03"
    elif CHA:
        val = "01"
    elif CHB:
        val = "02"
    else:
        print("error mode!!")
    return val

def mixed(mode):
    global val
    if mode == "Mixed":
        val = "01"
    else:
        val = "00"
    return val


def setupBS():
    print('setUpBS started')
    print(userParam)
    ser.close()
    connectBS()
    """ Standard setup procedure. """
    issueWait(".!K")
    issueWait(
        "[21]@[%s]s" % testMode(userParam["testMode"]) #Trace Mode=> Stream mode (Macro Analogue Chop (is 03))
        + "[37]@[%s]s" % channelMode(userParam["isDual"],userParam["CHA"],userParam["CHB"]) #Analog channel enable (bitmap) Analogue ch enable (both)
        + "[38]@[%s]s" % mixed(userParam["testMode"])
        + "[2e]@[%s]sn[%s]s" % srInputToHex(userParam["sampleRate"]) # Master Sample (clock) period (ticks) :Clock ticks
        + "[14]@[01]sn[00]s" # Clock divide by N (low byte) : Clock scale (Doesn't work for streaming mode)
        + "[36]@[af]s" # Stream data token
        + "[64]@[f7]sn[68]s" # Convertor High (Set the convertor range high side)
        + "[66]@[9a]sn[f4]s" # Convertor Low  (Set the convertor range low side)
    )
    issueWait("U")
    issueWait(">")


#############################################################
###### SERIAL HELPERS #######################################

def serClose():
    print(userParam["COM1"])
    serial.Serial(userParam["COM1"]).close()

def terminate():
    ser.write(str.encode('\x03'))
    ser.close()

def srInputToHex(sr):    
    hexTicks = hex(sr)[2:]
    zeroAdds = "0" * (4 - len(hexTicks))
    combined = zeroAdds + hexTicks
    return combined[2:], combined[:2]

def issue(message):
    global serWaiting
    ser.write(message.encode())
    serWaiting += len(message)

def issueWait(message):
    global serWaiting
    ser.write(message.encode())
    print("message: " +  message)
    serWaiting += len(message)
    clearWaiting()

def read(count):
    return ser.read(count)

def readAll():
    return ser.read(ser.inWaiting())

def clearWaiting():
    global serWaiting
    r = ser.read(serWaiting)
    serWaiting = serWaiting - len(r)

""" Utilities """
def freqToHexTicks(freq):
    ticks = int((freq ** -1) / 0.000000025)
    hexTicks = hex(ticks)[2:]
    zeroAdds = "0" * (4 % len(hexTicks))
    combined = zeroAdds + hexTicks
    return combined[2:], combined[:2]

def getToRange(fromRange, toRange):
    fr, tr = fromRange, toRange
    slope = float(tr[1] - tr[0]) / float(fr[1] - fr[0])
    return lambda v : round((tr[0] + slope * float(v - fr[0])), 3)

#############################################################
###### DECODING #############################################

def decodeChannel(data):    

    token = 175
    unpackArg = "<" + str(len(data)) + "B"
    unpacked = struct.unpack(unpackArg, data)

    if userParam["testMode"] == "SingleFast":        
        return list(unpacked)

    elif userParam["testMode"] == "Dual":
        # unpackArg = "<" + str(len(data)) + "B"
        # unpacked = struct.unpack(unpackArg, data)
        index = unpacked[0:130].index(token)
        unpacked = unpacked[index:] 
        # writeToFile(dumpFile,unpacked)
        chA =[]; chB=[]; logic=[]
        for cnt in range(len(unpacked)):
            if cnt%4==2:
                chA.append(unpacked[cnt]) 
            elif cnt%4==3:
                chB.append(unpacked[cnt])
        return chA, chB

    elif userParam["testMode"] == "Mixed":
        index = unpacked[0:].index(token)
        unpacked = unpacked[index:]
       
        # writeToFile(dumpFile,unpacked)
        chA =[]; chB=[]; logic=[]
        for cnt in range(int(len(unpacked)/5)): 
            if unpacked[cnt] == token:
                chA.append(unpacked[cnt+2])
                chB.append(unpacked[cnt+3])
                logic.append(unpacked[cnt+4])
            elif unpacked[cnt+1] == token:
                chA.append(unpacked[cnt+3])
                chB.append(unpacked[cnt+4])
                logic.append(unpacked[cnt])
            elif unpacked[cnt+2] == token:
                chA.append(unpacked[cnt+4])
                chB.append(unpacked[cnt])
                logic.append(unpacked[cnt+1])
            elif unpacked[cnt+3] == token:
                chA.append(unpacked[cnt])
                chB.append(unpacked[cnt+1])
                logic.append(unpacked[cnt+2])
            elif unpacked[cnt+4] == token:           
                chA.append(unpacked[cnt+1])
                chB.append(unpacked[cnt+2])
                logic.append(unpacked[cnt+3])
            cnt =+5
        return chA, chB, logic


def decode1ChMacro(data):
    unpackArg = "<" + str(int(len(data) / 2)) + "h"
    unpacked = list(struct.unpack(unpackArg, data))
    for i in unpacked:
        a = (i & 0x00ff) >> 4
        b = (i & 0xff00) << 4
        i = a + b
    return unpacked


def decode2ChMacro(data):
    # cha + token-nibble, cha, chb + token-nibble, chb
    unpackArg = "<" + str(int(len(data) / 2)) + "h"
    unpacked = struct.unpack(unpackArg, data)
    rmToken = lambda x : x & ~0x000f
    formatted = map(rmToken, unpacked)
    return list(formatted)

def writeToFile(file, data):
    # Write to file
    dataStr = '\n'.join(map(str, data))
    toWrite = dataStr + '\n'
    file.write(toWrite)



#############################################################
###### STREAMING ############################################


def startStreaming():
    print('strm started')
    issueWait("T")    
    time.sleep(0.5)
    startTime = float(time.time())
    return startTime

def stopStreaming():
    print('strm stoppend')
    issueWait("K!.")
    issueWait(">")
    issueWait(".")
    issueWait("U")
    ser.write(str.encode('\x03'))
    stopTime = float(time.time())
    return stopTime



def streamData(startTime, duration):
    chA =[]
    duration=duration
    state = True
    i = 0
    ser.read(1000)
    while state:
        if (time.time()-startTime> duration) or (toGetatATime*i>1000000):
            print('strttime',startTime)
            state = False
        data = bytearray()
        data = ser.read(toGetatATime)
        levelData = decodeChannel(data)
        voltData = list(levelData)
        # writeToFile(dumpFile,voltData)
        chA.append(voltData)
        i = i + 1
    return chA   


def streamDataDual(startTime, duration):
    duration=duration
    state = True
    i = 0
    # ser.read(1000)
    chAA =[]; chBB= []; logicC =[]
    while state:
        if (time.time()-startTime> duration) or (toGetatATime*i>1000000):
            print('strttime',startTime)
            state = False
        data = bytearray()
        data = ser.read(toGetatATime)

        if userParam["testMode"][0:6] == "Single":
            chA = decodeChannel(data)
            chAA.append(chA)
        elif userParam["testMode"][0:4]=="Dual":
            chA,chB = decodeChannel(data)
            chAA.append(chA)
            chBB.append(chB)
        else:
            chA,chB,logic = decodeChannel(data)
            chDict ={"chA":chA, "chB":chB, "logic":logic}
            chAA.append(chA)
            chBB.append(chB)
            logicC.append(logic)
        i = i + 1
   
    if userParam["testMode"]=="Mixed":
        chDict ={"chA":list(chain(*chAA)), "chB":list(chain(*chBB)), "logic":list(chain(*logicC))} 
    elif userParam["testMode"][0:4]=="Dual":
        chDict ={"chA":list(chain(*chAA)), "chB":list(chain(*chBB))}  
    else:
        chDict ={"chA":list(chain(*chAA)), "chB":list(chain(*chBB))}  
    return chDict
    




def getStreamFast(sample):
    startTime = time.time()
    data = bytearray()
    data = ser.read(sample)
    if userParam["testMode"]=="Mixed":
        chA,chB,logic = decodeChannel(data)
        chDict ={"chA":chA, "chB":chB, "logic":logic}

    elif userParam["testMode"][0:4]=="Dual":
        chA,chB = decodeChannel(data)
        chDict ={"chA":chA, "chB":chB}

    else:
        chA = decodeChannel(data)
        chB =[]
        chDict ={"chA":chA, "chB":chB}

    actualDuration = (time.time()-startTime)
    sampleRate = 0
    summaryDict.update({"dataPt": len(chDict["chA"]), "actualDuration": actualDuration,"sampleRate": sampleRate})
    return chDict

def getStreamDual():
    startTime = time.time()
    results = (streamDataDual(startTime,userParam["duration"]))
    stopStreaming()
    actualDuration = time.time()-startTime
    sampleRate = ((len(results["chA"]))+ser.in_waiting)/actualDuration/1000
    summaryDict.update({"dataPt": len(results["chA"]), "actualDuration": actualDuration,"sampleRate": sampleRate})
    return results
   

def main2():
    findBS()

if __name__ == '__main__':
    main2()
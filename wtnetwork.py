###################################################################################################
# Network Python script
# by Patrick EGLOFF aka TK5EP
#
# connects to a Dxcluster & CW Skimmer, receive spots and broadcast them to be received by WinTest
# handles Skimmer & Wintest commands
###################################################################################################

__Title = "Python DXcluster Telnet/UDP script"
__Version = "0.23"
__VersionDate = "06/02/2023"

# 0.21 03/02/23 in decode(), changed spot detections to REGEX and added SH/DX cluster answer, changes in decodeWT()
# 0.22 05/02/23 added timeouts in both classes dxcluster & UDPtoolbox
# 0.23 06/02/23 added configuration file handling

# import standard libraries
import socket
from time import sleep
import re
import sys
import configparser
import os

# import own libraries
from KwdCat import KwdCat

DEBUG = False       # for displaying debug infos

#########################################
# class to handle a DXcluster connection
# extracts spot and send them via UDP to Wintest
# decodes Wintest and CW skimmer commands
#########################################
class dxcluster(object):
    def __init__ (self,host:str,port:int,user:str,password:str,prompt:str,login_prompt,timeout:int):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.prompt = prompt
        self.login_prompt = login_prompt
        self.timeout = timeout

    #####################################
    # sends a cmd to server
    #####################################
    def sendCmd(self,msg):
        try:
            msg = msg + '\n'                    # adds a feedline
            self.sock.send(msg.encode())      # encode and send
        except socket.error as msg:
            if DEBUG:
                print ("socket exception in send(): %s" % msg)
                #sys.exit()
            pass

    #####################################
    # Make connection to DXC server
    #####################################
    def connect(self) -> bool:
        self.loggedin = False
        server = (self.host,self.port)        # variable for socket connection
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # create socket for TELNET
            self.sock.settimeout(self.timeout)
            if DEBUG:
                print("\nDXC socket OK")
        except socket.error as msg:
            if DEBUG:
                print ("socket exception in connect(): %s" % msg)
            pass

        loggedin = False
        try:
            self.sock.connect(server)
            print(f'Connected to {self.host} {self.port}','\n')

            while not loggedin :
                #print("loggedin",loggedin)
                welcomemsg = self.sock.recv(4096).decode(errors='ignore')
                if DEBUG:
                    print("Welcome msg:",welcomemsg)
                for line in welcomemsg.splitlines():        # display received lines
                    print(line)
                    if (self.login_prompt in line):                       # check for callsign prompt
                        self.sendCmd(self.user)   # send own callsign
                    if (self.prompt in line):                # wait for cluster prompt
                        self.loggedin = True
                        return self.loggedin
        except socket.error as msg:
            if DEBUG:
                print ("socket exception in connect(): %s" % msg)
                print(f'Connection to {self.host}:{self.port} failed')
            return self.loggedin


    #####################################
    # Disconnect from DXC server
    #####################################
    def disconnect(self)->bool:
        try:
            self.sendCmd('BYE')
            msg = self.sock.recv(2048).decode(errors='ignore')    # get received datas
            print(msg)
            if (self.sock.close()):
                return True
        except socket.error as msg:
            if DEBUG:
                print ("socket exception in receive(): %s" % msg)
            pass

    def receive(self):
    #####################################
    # Receive spots and commands
    # needs to have a non blocking socket
    # needs timeouts to be set
    #####################################
        try:
            msg = self.sock.recv(8192).decode(errors='ignore')             # get received datas
            if DEBUG:
                print("TCP datas recvd:",msg)
            return msg
        except (socket.timeout):
            if DEBUG:
                print ("Timeout in receive()")
            pass
        except socket.error as msg:
            if DEBUG:
                print ("socket exception in receive(): %s" % msg)
            self.connect()
            pass

    def decode(self,msg:str):
    ##########################################
    # decode cluster frames
    # extracts spots, remove bells, decodes Skimmer commands
    # remote control of radio
    #
    # decodes cmds coming from CWskimmer server
    ##########################################
    # dl8bh/py3-cqrcluster
    # DX de DG1KDA:   144174.0  DO5HMK       FT8 +3 dB 1435 Hz              0930Z
    # 144174.0 DF5DE        6-Feb-2023 0929Z FT8 +23 dB 1401 Hz           <DG1KDA>
        skimmer_low=0
        skimmer_high=0
        freq_pattern = "([0-9]{3,8}\.[0-9])"            # frequency pattern from 182.5 et 10196000.0
        de_callsign_pattern = "([a-z|0-9|/|#|-]+)"      # callsign pattern includes SKIMMER #
        dx_callsign_pattern = "([a-z|0-9|/]+)"          # callsign pattern without SKIMMER
        # cluster and sh/dx patterns
        cluster_pattern = re.compile("^DX de "+ de_callsign_pattern + ":\s+" + freq_pattern + "\s+" + dx_callsign_pattern + "\s+(.*)\s+(\d{4}Z)", re.IGNORECASE)
        shdx_pattern =re.compile("\s+" + freq_pattern + "\s+" + dx_callsign_pattern + "\s+(.*)\s+(\d{4}Z)\s+(.*)\s+(<.*>)", re.IGNORECASE)

        self.msg = msg
        for line in self.msg.splitlines():                      # extracts received lines
            try:
                shdxmatch = shdx_pattern.match(line)            # search for a SH/DX answer
                clustermatch = cluster_pattern.match(line)      #search for a DXcluster spot
            except:
                print("No match found in decode()")

            if clustermatch or shdxmatch:                   # if we have a pattern match either for a spot or a sh/dx
                if clustermatch:
                    comment = clustermatch.group(4).strip() # this should be the comment field in spot
                if shdxmatch:
                    comment = shdxmatch.group(5).strip()    # this should be the comment field in sh/dx

                #print(comment)
                if removedigi and 'FT8' in comment.upper() or 'FT4' in comment.upper():  # remove all spots if FT8 or FT4 found in the comment field :-(
                    break
                if removebell:                              # remove bell in spots
                    line = line.replace('\x07', '')

                print(line)                                 # display received spot
                try:
                    UDP_spot = 'RCVDPKT: "TELNET" "" "' + line + '\x0a"'    # formating Wintest TELNET message,adding line feed at the end
                    checksum_spot = self.checksum(UDP_spot)                 # calculates checksum
                    msg = UDP_spot.encode() + checksum_spot                 # concatenate spot + checksum
                    UDP_sock.send(msg)                                      # send UDP broadcast
                except:
                    print("No UDP connector, can't broadcast !")

            if wtfollowskimmer:                                             # if we decide that a click in the SKIMMER window should interact with radio
                if 'To ALL de SKIMMER' in line:                             # if we have a command send from W skimmer
                    try:
                        QSYfreq = self.findfreq(line)[0]                        # extract frequency from frame
                        QSYfreq = QSYfreq.replace('.','')                       # remove the frequency dot
                        CATstr = f"FB{QSYfreq.rjust(10,'0')}0"                  # format to Kenwood FA/FB 11 charactes format string 7024.06 -> 00070240600
                        if DEBUG:
                            print (line)
                            print("QSYfreq:",QSYfreq)
                            print("CATstr:",CATstr)
                        ts590.query(CATstr,0)                                   # send to radio
                    except:
                        if DEBUG:
                            print("ERROR in QSYfreq calculation")
                if 'SETT' in line:                      # we received an answer to SKIMMER/SETT cmd like "SETT: vlNormal 7072.5-7120.3"
                    try:
                        #print("SETT:",line)
                        a = line.split()
                        skimmer_low = float((a[2].split("-"))[0])
                        skimmer_high = float((a[2].split("-"))[1])
                        print ("Skimmer limits:",skimmer_low,"-",skimmer_high)
                    except:
                        if DEBUG:
                            print("ERROR in SETT answer. Is the Skimmer running ?")

    def findfreq(self,input_text):
    #############################################
    # find freq in string
    #############################################
        #print (input_text)
        pattern = re.compile(r"[0-9]{4,5}\.[0-9]{2}", re.IGNORECASE)
        return pattern.findall(input_text)

    def checksum(self,spot):
    #############################################
    # calculate spot checksum
    # calculates a checksum à la Wintest to be added at the end of each broacast frame
    #############################################
        try:
            sum = 0                                         # sum of all char in string
            for i in spot:
                sum += ord(i)                               # sum in int10
            sumMSB = (sum % 128) + 128                      # get LSByte and force MSBit to 1
            checksum = sumMSB.to_bytes(1,byteorder='little')   # convert to bytes format to be added to frame
            return checksum
        except:
            print("Exception in checksum()")
            pass

class UDP_toolbox(object):
    def __init__ (self,bind_ip:str,bind_port:int,broadcast_ip:str,broadcast_port:int,timeout:int):
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.broadcast_ip = broadcast_ip
        self.broadcast_port = broadcast_port
        self.timeout = timeout

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # UDP
        self.sock.bind((self.bind_ip, self.bind_port))                            # bind to address
        self.sock.settimeout(self.timeout)                              # timeout for non blocking receive
        print("UDP socket created")

    def close(self):
        try:
            self.sock.close()
        except socket.error as msg:
            print ("socket exception in close(): %s" % msg)
            pass

    def receive(self):
        try:
            self.datas,self.addr = self.sock.recvfrom(8092)
            if DEBUG:
                print("UDP datas recvd:",self.datas)
            return self.datas
        except (socket.timeout):
            if DEBUG:
                print ("Timeout in UDPreceive()")
            pass

    def send(self,udpmsg:str):
        try:
            #self.sock.sendto(msg.encode(), (self.broadcast_ip, self.broadcast_port))
            self.sock.sendto(udpmsg, (self.broadcast_ip, self.broadcast_port))
        except socket.error as msg:
            print ("socket exception in UDP send(): %s" % msg)
            pass


    def decodeWT(self,to_decode):
    #####################################
    # decodes different datas from UDP frame like
    # b'STATUS: "STN1" "" 0 5 1 0 140751 "0" 0 "1"  143400 "TK5EP"\xd6\x00'
    # b'SENDPKT: "STN1" "" "SH/DX\r"\x98\x00'
    #
    # handles SKIMMER/QSY, SKIMMER/SETT
    #####################################
        global oldskimmerfreq
        skimmerfreq='0'
        self.UDP_frame = to_decode
        try:
            if DEBUG:
                print ("UDP datas ready to decode:",self.UDP_frame)
            if self.UDP_frame != None:
                udpmsg = UDP_frame.decode(errors='ignore')

                if skimmerfollowwt == '1':
                    if 'STATUS' in udpmsg:                      # if we find the string STATUS
                        # maybe we can try to split the datas with .split function and not slicing like below ?
                        freq = (udpmsg[25:32].strip())          # extract frequency
                        freqint = int(freq[:-1])                # freq in kHz and integer needed for skimmerfreq calculation
                        freq = freq[:-1]+'.'+ freq[-1:]          # freq in hundreed Hz in string

                        if DEBUG:
                            print ("WT STATUS received on:",freq)
                        if 1810 <= freqint <= 2000:             # if we stay in band limits
                            skimmerfreq = '1820'                # this is mean freq. (not used for now, only a flag)
                        elif 3500 <= freqint <= 4000:           # with my Perseus 195kHe bandwith, no tracking needed
                            skimmerfreq = '3550.0'              # all the CW portion/bands are covered
                        elif 5350 <= freqint <= 5370:           # if necessary, needs some mods to track the center frequency
                            skimmerfreq = '5360'
                        elif 7000 <= freqint <= 7200:
                            skimmerfreq = '7025.0'
                        elif 10100 <= freqint <= 10150:
                            skimmerfreq = '10075'
                        elif 14000 <= freqint <= 14350:
                            skimmerfreq = '14050.0'
                        elif 18000 <= freqint <= 18200:
                            skimmerfreq = '18150'
                        elif 21000 <= freqint <= 21450:
                            skimmerfreq = '21050'
                        elif 24890 <= freqint <= 24990:
                            skimmerfreq = "24940"
                        elif 28000 <= freqint <= 29000:
                            skimmerfreq = '28050'
                        elif 50000 <= freqint <= 51000:
                            skimmerfreq = '50100'

                        if skimmerfreq != oldskimmerfreq:           #if we have a band change
                            oldskimmerfreq = skimmerfreq            #send a SKIMMER/QSY cmd
                            if skimmer.loggedin:
                                msgtoskimmer = 'SKIMMER/QSY '+ freq     # QSY on operating freq, can be changed to mean using skimmerfreq var.
                                skimmer.sendCmd(msgtoskimmer)
                                sleep(0.2)                              #wait to let CWskimmer answer
                                skimmer.sendCmd('SKIMMER/SETT')         #ask CWskimmer for band limits

                if skimmerfollowwt == '2':      # skimmer follows WT using the ObBanChang msg, needs to add a Lua script in WT
                    # REMOTE: "STN1" "SNIFFER" "QSY/80" 2

                    #remote_pattern = re.compile('REMOTE:\s+".*"\s+"SNIFFER"\s+"QSY/([0-9]{1,3})"\s+[0-9]')
                    remote_pattern = re.compile('REMOTE:\s+".*"\s+"'+UDP_user+'"\s+"QSY/([0-9]{1,3})"\s+[0-9]')

                    remoteqsy_match = remote_pattern.match(udpmsg)
                    if remoteqsy_match:

                        band = remoteqsy_match.group(1)
                        if band == "160":
                            skimmerfreq = '1820'                # this is mean freq. (not used for now, only a flag)
                        elif band == "80":           # with my Perseus 195kHe bandwith, no tracking needed
                            skimmerfreq = '3550.0'              # all the CW portion/bands are covered
                        elif band == "60":           # if necessary, needs some mods to track the center frequency
                            skimmerfreq = '5360'
                        elif band == "40":
                            skimmerfreq = '7050'
                        elif band == "30":
                            skimmerfreq = '10125'
                        elif band == "20":
                            skimmerfreq = '14050'
                        elif band == "17":
                            skimmerfreq = '18150'
                        elif band == "15":
                            skimmerfreq = '21050'
                        elif band == "12":
                            skimmerfreq = '24940'
                        elif band == "10":
                            skimmerfreq = '28050'
                        elif band == "50":
                            skimmerfreq = '50100'
                        #print(band)
                        #  print(skimmerfreq)
                        try:
                            if skimmer.loggedin:
                                msgtoskimmer = 'SKIMMER/QSY '+ skimmerfreq     # QSY on operating freq, can be changed to mean using skimmerfreq var.
                                skimmer.sendCmd(msgtoskimmer)
                                sleep(0.2)                              #wait to let CWskimmer answer
                                skimmer.sendCmd('SKIMMER/SETT')         #ask CWskimmer for band limits
                        except:
                            print("ERROR in decodeWT()")


                if 'SENDPKT' in udpmsg:                     # if we find SENDPKT
                    cmd = udpmsg[20:udpmsg.find('\r')]      # extract the command in frame (SH/DX, etc...)
                    if 'SH/DX' in cmd:                      #if cmd is SH/DX or SH/DX xxxx
                        try:
                            if DEBUG:
                                print("SENDPKT cmd detected:",cmd)
                            DXcluster.sendCmd(cmd)
                        except:
                            print("error in DXC send")
        except:
            if DEBUG:
                print("Problem in decodeWT")

def read_config(filename):
    global removebell,removedigi,skimmerfollowwt,wtfollowskimmer,UDP_IP,UDP_PORT,UDP_user,UDPbind_IP,UDPbind_PORT
    global skimmer_host,skimmer_port,skimmer_user,skimmer_password,skimmer_prompt,skimmer_login_prompt
    global radiomodel,comport,baudrate,bytesize,stopbits,parity,xonxoff,rtscts,dsrdtr,rts,dtr,polltime,rxtimeout,txtimeout
    global DXC_host,DXC_port,DXC_user,DXC_prompt,DXC_password,DXC_login_prompt
    try:
        # Check the file exists.
        if not os.path.isfile(filename):
            logging.critical("Config file %s does not exist!" % filename)
            return None
        config = configparser.ConfigParser()
        config.read(filename)

        # check if global section exists
        if config.has_section('global'):
            removebell = config.getboolean('global','removebell')
            removedigi = config.getboolean('global','removedigi')
            skimmerfollowwt = config.get('global','skimmerfollowwt')
            wtfollowskimmer = config.getboolean('global','wtfollowskimmer')
        else:
            input("global section missing in config file. Please correct this !\nCTRL-C to exit")
            sys.exit(1)
        # check if udp section exists
        if config.has_section('udp'):
            UDP_IP = config.get('udp','UDP_IP')
            UDP_PORT = config.getint('udp','UDP_PORT')
            UDP_user = config.get('udp','UDP_user')
            UDPbind_IP = config.get('udp','UDPbind_IP')
            UDPbind_PORT = config.getint('udp','UDPbind_PORT')
        else:
            input("udp section missing in config file. Please correct this !\nCTRL-C to exit")
            sys.exit(1)
        # skimmer section
        if config.has_section('skimmer'):
            skimmer_host = config.get('skimmer','skimmer_host')
            skimmer_port = config.getint('skimmer','skimmer_port')
            skimmer_user = config.get('skimmer','skimmer_user')
            skimmer_password = config.get('skimmer','skimmer_password')
            skimmer_prompt = config.get('skimmer','skimmer_prompt')
            skimmer_login_prompt = config.get('skimmer','skimmer_login_prompt')
        else:
            input("skimmer section missing in config file. Please correct this !\nCTRL-C to exit")
            sys.exit(1)
        # radio section
        if config.has_section('radio'):
            radiomodel = config.get('radio','radiomodel')
            comport = config.get('radio','comport')
            baudrate = config.getint('radio','baudrate')
            bytesize = config.getint('radio','bytesize')
            stopbits = config.getint('radio','stopbits')
            parity = config.get('radio','parity')
            xonxoff = config.getboolean('radio','xonxoff')
            rtscts = config.getboolean('radio','rtscts')
            dsrdtr = config.getboolean('radio','dsrdtr')
            rts = config.getboolean('radio','rts')
            dtr = config.getboolean('radio','dtr')
            polltime = config.getint('radio','polltime')
            rxtimeout = config.getint('radio','rxtimeout')
            txtimeout = config.getint('radio','txtimeout')
        else:
            input("radio section missing in config file. Please correct this !\nCTRL-C to exit")
            sys.exit(1)
        # dxcluster section
        if config.has_section('dxcluster'):
            DXC_name = config.get('dxcluster','DXC_name')
            DXC_host = config.get('dxcluster','DXC_host')
            DXC_port = config.getint('dxcluster','DXC_port')
            DXC_user = config.get('dxcluster','DXC_user')
            DXC_password = config.get('dxcluster','DXC_password')
            DXC_prompt = config.get('dxcluster','DXC_prompt')
            DXC_login_prompt = config.get('dxcluster','DXC_login_prompt')
        else:
            input("dxcluster section missing in config file. Please correct this !\nCTRL-C to exit")
            sys.exit(1)
    except:
        print("Could not parse config file.")
        return None
    else:   # otherwise, we're happy
        print ("Config file correctly read & parsed")
        return True


if __name__ == "__main__":
    print ("\n%s - (c) Patrick EGLOFF aka TK5EP" %(__Title))
    print ("Version %s %s made in Corsica :-) \n" % (__Version, __VersionDate) )
    if read_config("wtnetwork.cfg"):
        pass
    else:
        input("CTRL-C to exit")
        sys.exit()

    oldskimmerfreq = 0  # used as a flag in decodeWT()
    polltime = polltime /1000   # conversion ms in secs

    # create and UDP socket
    UDP_sock =UDP_toolbox(UDPbind_IP,UDPbind_PORT,UDP_IP,UDP_PORT,0.1)
    #UDP_sock.send(b'hello')            # test

    # create connection to SKIMMER
    skimmer = dxcluster(skimmer_host,skimmer_port,skimmer_user,skimmer_password,skimmer_prompt,skimmer_login_prompt,0.1)
    if skimmer.connect():
        pass
    else:
        print('Could not connect to: SKIMMER')

    # create connection to DXCluster
    DXcluster = dxcluster(DXC_host,DXC_port,DXC_user,DXC_password,DXC_prompt,DXC_login_prompt,0.1)
    if DXcluster.connect():
        pass
    else:
        print("Could not connect to: DXcluster")

    if skimmerfollowwt or wtfollowskimmer :
        ts590 = KwdCat()                                        # create instance of KwdCat the Kenwood CAT library
        # create object
        if (ts590.open_port(port=comport,baudrate=baudrate,bytesize=bytesize,stopbits=stopbits,xonxoff=xonxoff,rtscts=rtscts,dsrdtr=dsrdtr,parity=parity,rts=rts,dtr=dtr,rxtimeout=rxtimeout,txtimeout=txtimeout)):
            print ('Radio model :',radiomodel,'on',ts590.serial.port)
            print ('Baudrate=',ts590.serial.baudrate,'Bits=',ts590.serial.bytesize,'Stop=',ts590.serial.stopbits,'Parity=',ts590.serial.parity)
            print ("Flow controls: XOn/XOff=",ts590.serial.xonxoff,"RTS/CTS=",ts590.serial.rtscts,"DSR/DTR=",ts590.serial.dsrdtr)
            print ("Lines: RTS=",ts590.serial.rts,"DTR=",ts590.serial.dtr,"RXtimeout=",ts590.serial.timeout,"TXtimeout=",ts590.serial.write_timeout,"\n")
        else:
            print(comport,"not available, busy or bad setting !")
            print("Below are available ports, set one in the configuration file")
            ts590.find_ports()                                  # show a list of found comports
            input('\nStopping. CTRL-C to stop')
            sys.exit()

        if (ts590.checkradio()):                                # check is radio is answering
            print ("Radio communication OK\n")
        else:                                                   # if no answer
            ts590.close_port()                                  # close port
            input('\nCTRL-C to EXIT')
            sys.exit(0)

    print("Waiting for spots to come in ...")

    ##############################
    # loop
    ##############################
    i=0
    j=0
    while True:
        try:
            if skimmer.loggedin:                    # if we've a valid connection
                SKIMMERmsg = skimmer.receive()      # receive datas in none blocking mode with help of timeout
                if SKIMMERmsg != None:              # if datas are present
                    skimmer.decode(SKIMMERmsg)      # decode them
            else:
                if i == 100:                                             # if conenction failed init a counter for 30 loops, about 30s with set timeouts
                    print("\nNo connection to SKIMMER, trying again..")
                    skimmer.connect()                                   # try to connect
                    i = 0                                               # reset flag
                i +=1                                                   #

            if DXcluster.loggedin:
                DXCmsg = DXcluster.receive()
                if DXCmsg != None:
                    DXcluster.decode(DXCmsg)
            else:
                if j == 100:
                    print("\nNo connection to DXcluster, trying again..")
                    DXcluster.connect()
                    j = 0
                j +=1

            UDP_frame = UDP_sock.receive()              # receive UDP datas
            if UDP_frame != None:                       # if something has been received
                UDP_sock.decodeWT(UDP_frame)            # decode it

            #print(".")                                 # to test the loop

        except KeyboardInterrupt:                       # if we press CTRL-C to interrupt the program
            #ts590.close_port()                         # close radio port
            if skimmer.loggedin:                        # if connection to skimmer is active
                skimmer.disconnect()                    # disc by sending BYE
                skimmer.sock.close()                    # just in case, close the socket
            if DXcluster.loggedin:
                DXcluster.disconnect()
                DXcluster.sock.close()
            UDP_sock.close()                            # close UDP socket
            if skimmerfollowwt or wtfollowskimmer :
                ts590.close_port()
            print('CTLR-C received, exiting in 2s')
            sleep(polltime)
            sys.exit()
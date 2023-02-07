# WtNetwork
A Python script to interface CWskimmer, a DXcluster and Wintest

## For what is is good for ?<br />
The contest logging software Wintest package has a Telnet software that can connect to a DXcluster and send the received spots to Wintest.<br />
It makes its job, but I was in a need of some additionnal features, mainly with the CWskimmer interface.<br />
This script has been written to fit my needs :<br />
- dual connection to a CWskimmer and a DXcluster<br />
- spot filtering in removing FT4 & FT8 spots, it also removes the bell that some clusters are sending<br />
- CAT control of the TS590 (probably many other HF Kenwood tranceivers too)<br />
- clicking on the CWskimmer window sets VFO B<br /> 
- when a band change occurs in Wintest or on the transceiver, CWskimmer is set to the mid CW band portion

## Requirements<br />
This script uses standard Python librairies but needs a Kenwood CAT library I've written and that can be found on this Git.

## Usage<br />
This script reads some configuration from a configuration file : wtnetwork.cfg

        # configuration file for wtnetwork
        # v0.23
        #
        [global]
        # declare global variables
        # remove bells in spots
        removebell = True
        # remove FT4 and FT8 spots
        removedigi = False
        # do we want SKIMMER to track Wintest band changes 0=No, 1=using  2=using WT onbandchange()
        skimmerfollowwt = 0
        # do we want Wintest to track Skimmer on band click
        wtfollowskimmer = True

        [udp]
        UDP_IP = 127.255.255.255
        UDP_PORT = 9871
        UDP_user = SNIFFER
        UDPbind_IP = 127.0.0.1
        UDPbind_PORT = 9871

        [skimmer]
        # local SKIMMER
        skimmer_host = localhost
        skimmer_port = 7300
        skimmer_user = TK5EP
        skimmer_password =
        skimmer_prompt = CwSkimmer >
        skimmer_login_prompt = callsign

        [radio]
        radiomodel = TS590s
        comport = COM8
        baudrate = 57600
        bytesize = 8
        stopbits = 1
        parity = N
        xonxoff = False
        rtscts = False
        dsrdtr = False
        rts = True
        dtr = True
        polltime = 100
        rxtimeout = 0
        txtimeout = 0

        [dxcluster]
        #DXC_name = DB0ERF
        #DXC_host = db0erf.de
        #DXC_port = 7300
        #DXC_user = TK5EP
        #DXC_password =
        #DXC_prompt = dxspider >
        #DXC_login_prompt = login:

        # cluster IK5PWJ-6
        DXC_name = IK5PWJ-6
        DXC_host = ik5pwj-6.dyndns.org
        DXC_port = 8000
        DXC_user = TK5EP
        DXC_password =
        DXC_prompt = dxspider >
        DXC_login_prompt = login:
        
## FAQ

## References & links

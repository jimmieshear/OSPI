# OSPI
Open Source Sprinkler Python modules

OSPIUtility.py 
The main utility file that provides most of the heavy lifting to the rest of the class flies

OSPIGetLogData.py
A class that connect to the OSPI host and retrieve log information from it. I've been having
a problem with the logs on the OSPI system. They seem to get corrupt / broken after a few 
days. I believe a recent update fixed this, but my gardener and like getting the emails each
day.

OSPIAdjustProgramData.py
A class to get the current weather for the location, and provide some simple temperature 
adjustment to the watering times. I attempt to keep the minimum watering times and adjust
up due to our drought. 


#!/usr/bin/env python
"""
################################################################################
# Copyright (c) 2017 Robert Hill. All rights reserved.
################################################################################
        NAME:
        OSPIVerifyFlow.py

        DESCRIPTION:
        Verify flow system on the Open Sprinkler. Make sure it's not 
	running outside of the schedule. 

        NOTES:
        js = Sprinkler status and returns the binary value (on off) for each
        jc = Controller variables (also returns Flow controller value)
	
	Not working yet. !!!

        HISTORY:
        06/19/17 -RH
        Initial developtment

################################################################################
"""

################################################################################
# IMPORT
################################################################################
import os, logging, sys,  urllib2, json, time, smtplib, pyowm, datetime, argparse
from email.mime.multipart import MIMEMultipart
from email.MIMEText import MIMEText
from datetime import datetime

################################################################################
# LOGGING
################################################################################
log = logging.getLogger('ospiverifyflow')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

logger1 = logging.FileHandler('/tmp/ospiverifyflow.log')
logger1.setLevel(logging.DEBUG)
logger1.setFormatter(formatter)
log.addHandler(logger1)

################################################################################
# CLASSES
################################################################################

class ExecuteScript(object):
        """ExecuteScript - run the script"""

        @classmethod
        def run(self):

		# TEST
		opcs = OSPICheckStatus()
		opcs.return_program_data()

		# Is the schedule running? 
		cospi = OSPICheckStatus()
		cospi.check_stations_running()
		log.debug("ExecuteScript:run: stations running {0}".format(cospi.stations_running))

		if cospi.stations_running:
			cospi.check_flow_control_running()

		if cospi.stations_running != None:
			# We're done if there's currently scheduled activity
			log.debug("ExecuteScript:run: exiting, schedule is running")
			sys.exit(0)

		# Check the flow control
		cospi.check_flow_control_running()

		if cospi.flow_value == 0:
			# We're done if there's currently scheduled activity
			log.debug("ExecuteScript:run: exiting, flow is currently ZERO")
			sys.exit(0)
		else:
			# Heavy lifting section
			ospiwait = OSPIWaitAndVerify()
			ospiwait.verify_flow_activity()

			log.debug("ExecuteScript:run: CAUTION! There's no Scheudled Activity but the Flow Control is reading {0}".format(cospi.flow_value))

class OSPIWaitAndVerify(object):
	"""OSPIWaitAndVerify - Flow control showed a positive feed, however scheuduled activity was Zero"""

	def __init__(self):
		self.pass_count = 5
		self.warning_level = 0

	def verify_flow_activity(self):
		# Each pass we'll see if the flow control changes, and if scheduled activity starts
		self.flow_value = self.ospiprop.flow_value	# Sets initial value, we'll use to compare with later value
		while self.pass_count != 0:
			# Check if scheduled activity started
			cospi = CheckOSPIStatus(self.ospiprop)
			cospi.check_stations_running()
			cospi.check_flow_control_running()
			log.debug("OSPIWaitAndVerify:verify_flow_activity: stations running is {0} and flow control is {1}".format(self.ospiprop.stations_running,self.ospiprop.flow_value))
			
			if self.ospiprop.stations_running != None:
				# Scheduled activity started, we're done
				sys.exit(0)

			if self.ospiprop.flow_value == 0:
				# Flow control is now Zero
				sys.exit(0)
			elif self.flow_value != self.ospiprop.flow_value:
				self.warning += 1

			self.pass_count -= 1
			time.sleep(90)

		# Check the warning level
		if self.warning_level > 0:
			# Need to notify the user that there's a problem
			ospiemail = OSPIEmail()
			if self.warning_level == 1:
				# Message via email? 
				ospiemail.send_email_message("WARNING LEVEL EVENT")
				log.debug("OSPIWaitAndVerify:verify_flow_activity: WARNING level")
			if self.warning_level > 2 and self.warning_level < 4:
				# Message via email and text?
				ospiemail.send_email_message("CAUTION LEVEL EVENT")
				log.debug("OSPIWaitAndVerify:verify_flow_activity: CAUTION level")
			if self.warning_level == 5:
				# Message via email, text and ?? 
				ospiemail.send_email_message("EMERGENCY LEVEL EVENT")
				log.debug("OSPIWaitAndVerify:verify_flow_activity: EMERGENCY level")

class OSPICheckStatus(object):
	"""OSPICheckStatus - A class to interact with the Open Sprinkler and return various pieces of information"""

	def __init__(self, ospiprop):
		self.ospiprop = ospiprop
		self._stations_running = None
		self._flow_value = None
		self._watering_times = []

	################################################################################
	# PROPERTIES
	################################################################################
	@property
	def stations_running(self):
		log.debug("OSPIProperties:stations_running: stations running {0}".format(self._stations_running))
		return self._stations_running

	@stations_running.setter	
	def stations_running(self, stations):
		self._stations_running = stations
		log.debug("OSPIProperties:stations_running: setting stations running {0}".format(self._stations_running))

	@property
	def flow_value(self):
		log.debug("OSPIProperties:flow_value: flow value is {0}".format(self._flow_value))
		return self._flow_value

	@flow_value.setter
	def flow_value(self, value):
		self._flow_value = value
		log.debug("OSPIProperties:flow_value: setting new flow value {0}".format(self._flow_value))

	@property
	def watering_times(self):
		log.debug("OSPIProperties:watering_times: {0}".format(self._watering_times))
		return self._watering_times

	@watering_times.setter
	def watering_times(self, watering_time):
		self._watering_times.append(watering_time)
		log.debug("OSPIProperties:stations_running: setting stations running {0}".format(self._stations_running))

	################################################################################
	# FUNCTIONS
	################################################################################
	def check_stations_running(self):
		cg = OSPIQuery()
		cg.cgi_query= "{0}/js?pw={1}".format(OSPI,MD5PASS)
		stations_active = cg.cgi_query
		log.debug("CheckOSPIStatus:check_stations_running: CGIQuery return {0}".format(stations_active))

		# Look for "sn" in the json output and read in the list
		list_stations = stations_active["sn"]

		station_count = 0
		for station in list_stations:
			station_count += 1
			if station != 0:
				log.debug("CheckOSPIStatus:check_stations_running: Station {0} is running".format(station_count))
				self.stations_running = station
				# We have a active scheduled run, terminate

	def check_flow_control_running(self):
		cg = OSPIQuery()
		cg.cgi_query= "{0}/jc?pw={1}".format(OSPI,MD5PASS)
		flow_control_active = cg.cgi_query
		log.debug("CheckOSPIStatus:check_flow_control_running: CGIQuery return {0}".format(flow_control_active))

		# Look for "flcrt" in the json output and read in the value
		flow_control_running = flow_control_active["flcrt"]
		self.flow_value = flow_control_running

	def return_program_data(self):
		cg = OSPIQuery()
		cg.cgi_query= "{0}/jp?pw={1}".format(OSPI,MD5PASS)
		program_data = cg.cgi_query
		log.debug("CheckOSPIStatus:return_program_data: CGIQuery return {0}".format(flow_control_active))
		print "Here's what we returned {0}".format(program_data)


class OSPIWeatherInformation(object):
	"""OSPIWeatherInformation - get the weather information for tomorrow"""

	def __init__(self):
		self.max_temp = None

	def get_weather_information(self):
		owm = pyowm.OWM(OWM)
		my_online = owm.is_API_online()
	
		# OWM is not available	
		if not my_online:
			log.debug("OSPIWeatherInformation:get_weather_information: OWM is not available, returning None type")
			return None

		# Get tomorrow's weather to adjust for heat range
		tomorrow = pyowm.timeutils.tomorrow()
		fc = owm.daily_forecast(CITY)
		weather_tomorrow = fc.get_weather_at(tomorrow)
		temperature_t = weather_tomorrow.get_temperature("fahrenheit")
		for i in temperature_t:
			if 'max' in i:
				value = temperature_t[i]
				string_value = str(value)
				whole_value,not_used = string_value.split(".")
				self.max_temp = int(whole_value)
				log.debug('OSPIWeatherInformation:max: Max Temp {0}'.format(whole_value))

		# There are my own personal values, feel free to make this as fancy as you want
		if max_temp > 80 and max_temp < 90:
			# Increase watering time by 20%

			log.debug("OSPIWeatherInformation: Adjussted weather by 20%, tomorrow's weather range will be {0}".format(self.max_temp))
			
		elif max_temp > 91:
			# Increase watering time by another 10% (30% overall)

			log.debug("OSPIWeatherInformation: Adjussted weather by 30%, tomorrow's weather range will be {0}".format(self.max_temp))


class OSPIQuery(object):
	"""OSPIQuery - class to query the device and return it's status"""

	def __init__(self):
		self._query = None
		self._query_return = None

	@property
	def ospi_query(self):
		log.debug('OSPIQuery:getter: returning query {0}'.format(self._query_return))
		return self._query_return

	@ospi_query.setter
	def ospi_query(self, query):
		self._query = query
		self.run_query()
		log.debug('OSPIQuery:setter: setting query to {0}'.format(self._query))

	def run_query(self):
		try:
			response = urllib2.urlopen(self._query)
			chk = json.load(response)
			log.debug('CGIQuery:run_query: chk return {0}'.format(chk))
			response.close()
			self._query_return = chk
			log.debug('CGIQuery:run_query: query_return {0}'.format(self._query_return))

		except urllib2.URLError, e:
			log.error('CGIQuery: Could not connect to server, received error {0}. Attempted: {1}'.format(e,self._query))
		except IndexError:
			log.error('CGIQuery: Response from CGI returned nothing. The DB probably does not know about this update')

class OSPIEmail(object):
	"""OSPIEmail - sends notifications"""
	
	def send_email_message(self, warning):
		server = smtplib.SMTP('smtp.gmail.com:587')
		server.starttls()
		user = "{0}".format(USER)
		passwd = "{0}".format(PASS.decode('hex'))
		server.login(user, passwd)
		
		message = MIMEText("FLOW CONTROL NOTIFICATION! \n{0}".format(warning))

		message['Subject']	= "Sprinkler Alert"
		message['From']		= SENDER
		message['To']		= ", ".join(RECP)
		log.debug('OSPIEmail:send_email_message: smtp variables sent {0}'.format(message))
		server.sendmail(SENDER, RECP, message.as_string())
		server.quit()

################################################################################
# RUN AS SCRIPT
################################################################################

if __name__ == "__main__":
	# Maybe we just don't keep this and make some new python executables. 
	parser = argparse.ArgumentParser(description = "Set of classes to interact with the Open Sprinkler")

	parser.add_argument('-f', '--flow',	default="flow", help = "Check the flow control and send out a notification if activity is incorrect")
	parser.add_argument('-w', '--weather',	default="weather", help = "Check weather information and adjust based on temperature")
	args = parser.parse_args()

	ExecuteScript.run()


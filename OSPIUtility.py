#!/usr/bin/env python
"""
################################################################################
# Copyright (c) 2017 Robert Hill. All rights reserved.
################################################################################
	NAME:
	OSPIUtility.py

	DESCRIPTION:
	A set of classes that encapsulates various sprinkler functions

	NOTES:
	js = Sprinkler status and returns the binary value (on off) for each
	jc = Controller variables (also returns Flow controller value)

	HISTORY:
	06/19/17 -RH
	Initial developtment

################################################################################
"""

################################################################################
# IMPORT
################################################################################
import os, logging, sys, urllib2, json, time, smtplib, pyowm, datetime
from email.mime.multipart import MIMEMultipart
from email.MIMEText import MIMEText
from datetime import datetime

################################################################################
# LOGGING
################################################################################
log = logging.getLogger('ospiutility')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logger1 = logging.FileHandler('/tmp/ospiutility.log')
logger1.setLevel(logging.DEBUG)
logger1.setFormatter(formatter)
log.addHandler(logger1)

################################################################################
# CLASSES
################################################################################

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

class OSPIDefaultZoneInformation(object):
	"""OSPIDefaultZoneInformation - get the default zone information in a dictionary"""

	def __init__(self):
		self.zone_dict = {}

	def return_default_zone_times(self, program_data):
		# Get the zone information, it's the last record in the programs list
		my_programs = program_data.get("pd")
		my_zone_info = my_programs[-1]
		log.debug("OSPIDefaultZoneInformation:return_default_zone_times: my_zone_info {0}".format(my_zone_info))
		my_zone_times_list = my_zone_info[4]
		log.debug("OSPIDefaultZoneInformation:return_default_zone_times: my_zone_times_list {0}".format(my_zone_times_list))

		# Count for the zone position
		my_count = 0
		for i in my_zone_times_list:
			self.zone_dict[my_count] = i
			my_count += 1

		log.debug("OSPIDefaultZoneInformation:return_default_zone_times: self.zone_dict {0}".format(self.zone_dict))
		return self.zone_dict

class OSPICheckStatus(object):
	"""OSPICheckStatus - A class to interact with the Open Sprinkler and return various pieces of information"""

	def __init__(self, station_address, passwd):
		self.station_address = station_address
		self.passwd = passwd
		self._stations_running = None
		self._program_data = None
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

	@property
	def program_data(self):
		log.debug("OSPIProperties:watering_times: {0}".format(self._program_data))
		return self._program_data

	@program_data.setter
	def program_data(self, program_data):
		self._program_data = program_data
		log.debug("OSPIProperties:stations_running: setting stations running {0}".format(self._program_data))

	@property
	def station_names(self):
		log.debug("OSPIProperties:station_names: {0}".format(self._station_names))
		return self._station_names

	@station_names.setter
	def station_names(self, station_names):
		self._station_names = station_names
		log.debug("OSPIProperties:station_names: setting station names {0}".format(self._station_names))

	################################################################################
	# FUNCTIONS
	################################################################################
	def check_stations_running(self):
		my_ospi_query= "{0}/js?pw={1}".format(self.station_address,self.passwd)
		stations_active = self.run_query_and_return(my_ospi_query)
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
		my_ospi_query= "{0}/jc?pw={1}".format(self.station_address,self.passwd)
		flow_control_active = self.run_query_and_return(my_ospi_query)

		# Look for "flcrt" in the json output and read in the value
		flow_control_running = flow_control_active["flcrt"]
		self.flow_value = flow_control_running

	def return_program_data(self):
		my_ospi_query= "{0}/jp?pw={1}".format(self.station_address,self.passwd)
		self.program_data = self.run_query_and_return(my_ospi_query)

	def return_log_data(self):
		my_ospi_query = "{0}/jl?pw={1}&hist={2}".format(self.station_address,self.passwd,1)
		self.program_data = self.run_query_and_return(my_ospi_query)

	def return_station_names(self):
		my_ospi_query = "{0}/jn?pw={1}".format(self.station_address,self.passwd)
		self.station_names = self.run_query_and_return(my_ospi_query)
	
	def remove_logs(self):
		my_ospi_query = "{0}/dl?pw={1}&day=all".format(self.station_address,self.passwd)
		self.run_query_and_return(my_ospi_query)

	@staticmethod
	def run_query_and_return(query):
		cg = OSPIQuery()
		cg.ospi_query = query
		my_return = cg.ospi_query
		log.debug("CheckOSPIStatus:run_query_and_return: CGIQuery return {0}".format(my_return))
		return my_return

class OSPIWaterAdjustment(object):

	def __init__(self, program_data):
		self.program_data = program_data
		odzi = OSPIDefaultZoneInformation()
		self.base_zone_times_dict = odzi.return_default_zone_times(self.program_data)
		self.adjusted_programs = []

	def adjust_duration_default(self):
		self.programs = self.program_data.get("pd")
		my_count = 0
		for my_item in self.programs:
			my_duration_list = my_item[4]
			my_default_by_position = self.base_zone_times_dict.get(my_count)
			if my_default_by_position != None:
				my_item[4][my_count] = int(my_default_by_position)
				log.debug("OSPIWaterAdjustment:adjust_duration_default: my_item adjusted {0}".format(my_item))
				self.adjusted_programs.append(my_item)
			my_count += 1
		log.debug("OSPIWaterAdjustment:adjust_duration_positive: self.adjusted_programs {0}".format(self.adjusted_programs.append))
		return self.adjusted_programs

	def adjust_duration_positive(self, percentage):
		self.programs = self.program_data.get("pd")
		my_count = 0
		for my_item in self.programs:
			my_duration_list = my_item[4]
			my_default_by_position = self.base_zone_times_dict.get(my_count)
			if my_default_by_position != None:
				my_new_duration_by_percent = (my_default_by_position * percentage) + my_default_by_position
				log.debug("OSPIWaterAdjustment:adjust_duration_positive: my_new_duration_by_percent {0}".format(my_new_duration_by_percent))
				my_item[4][my_count] = int(my_new_duration_by_percent)
				log.debug("OSPIWaterAdjustment:adjust_duration_positive: my_item after adjustment {0}".format(my_item))
				self.adjusted_programs.append(my_item)
			my_count += 1
		log.debug("OSPIWaterAdjustment:adjust_duration_positive: self.adjusted_programs {0}".format(self.adjusted_programs.append))
		return self.adjusted_programs
			
	def adjust_duration_negative(self, percentage):
		self.programs = self.program_data.get("pd")
		my_count = 0
		for my_item in self.programs:
			my_duration_list = my_item[4]
			my_default_by_position = self.base_zone_times_dict.get(my_count)
			if my_default_by_position != None:
				my_new_duration_by_percent = (my_default_by_position * percentage) - my_default_by_position
				log.debug("OSPIWaterAdjustment:adjust_duration_positive: my_new_duration_by_percent {0}".format(my_new_duration_by_percent))
				my_item[4][my_count] = int(my_new_duration_by_percent)
				log.debug("OSPIWaterAdjustment:adjust_duration_positive: my_item after adjustment {0}".format(my_item))
				self.adjusted_programs.append(my_item)
			
			my_count += 1
		log.debug("OSPIWaterAdjustment:adjust_duration_positive: self.adjusted_programs {0}".format(self.adjusted_programs.append))
		return self.adjusted_programs


class OSPIWeatherInformation(object):
	"""OSPIWeatherInformation - get the weather information for tomorrow"""

	def __init__(self):
		self._max_temp = None

	@property
	def max_temp(self):
		log.debug("OSPIWeatherInformation:max_temp: {0}".format(self._max_temp))
		return self._max_temp

	@max_temp.setter	
	def max_temp(self, temp):
		self._max_temp = temp
		log.debug("OSPIWeatherInformation:max_temp: setting new temp {0}".format(temp))

	def get_weather_information(self, city=None):
		ors = OSPIReadSettings()
		my_setting = ors.add_settings()
		my_owm = my_setting['open_weather_api']
		my_city = my_setting['weather_location']
                log.debug("OSPIWeatherInformation:get_weather_information: my_city {0}".format(my_city))
		owm = pyowm.OWM(my_owm)
		my_online = owm.is_API_online()
	
		# OWM is not available	
		if not my_online:
			log.debug("OSPIWeatherInformation:get_weather_information: OWM is not available, returning None type")
			return None

		# Get tomorrow's weather to adjust for heat range
		tomorrow = pyowm.timeutils.tomorrow()
		if city:
			fc = owm.daily_forecast(city)
			log.debug("OSPIWeatherInformation:get_weather_information: {0}".format(city))
		else:
			fc = owm.daily_forecast(my_city)
			log.debug("OSPIWeatherInformation:get_weather_information: {0}".format(my_city))

		weather_tomorrow = fc.get_weather_at(tomorrow)
		temperature_t = weather_tomorrow.get_temperature("fahrenheit")
		for i in temperature_t:
			if 'max' in i:
				value = temperature_t[i]
				string_value = str(value)
				whole_value,not_used = string_value.split(".")
				self.max_temp = int(whole_value)
				log.debug('OSPIWeatherInformation:max: Max Temp {0}'.format(whole_value))

class OSPIQuery(object):
	"""OSPIQuery - class to query the device and return it's status"""

	def __init__(self):
		self._query = None

	@property
	def ospi_query(self):
		log.debug('OSPIQuery:getter: returning query {0}'.format(self._query))
		return self._query

	@ospi_query.setter
	def ospi_query(self, query):
		self._query = query
		self.run_query()
		log.debug('OSPIQuery:setter: setting query to {0}'.format(query))

	def run_query(self):
		try:
			response = urllib2.urlopen(self._query)
			chk = json.load(response)
			log.debug('CGIQuery:run_query: chk return {0}'.format(chk))
			response.close()
			self._query = chk
			log.debug('CGIQuery:run_query: query {0}'.format(self._query))

		except urllib2.URLError, e:
			log.error('CGIQuery: Could not connect to server, received error {0}. Attempted: {1}'.format(e,self._query))
		except IndexError:
			log.error('CGIQuery: Response from CGI returned nothing. The DB probably does not know about this update')

class OSPIEmail(object):
	"""OSPIEmail - sends notifications"""
	def __init__(self,user,passwd,sender,recipients):
		self.user = user
		self.passwd = passwd
		self.sender = sender
		self.recipients = recipients
	
	def send_email_message(self, subject, body):
		server = smtplib.SMTP('smtp.gmail.com:587')
		server.starttls()
		my_user = "{0}".format(self.user)
		my_passwd = "{0}".format(self.passwd.decode('hex'))
		server.login(my_user, my_passwd)
	
		message = MIMEMultipart('alternative')
		message['From']		= self.sender
		message['To']		= ", ".join(self.recipients)

		if not subject:
			message['Subject'] = "Sprinkler Alert"
		else:
			message['Subject'] = subject

		if not body:
			body = "Notification email with no body"
	
		my_body = MIMEText(body, 'html')	
		message.attach(my_body)

		log.debug('OSPIEmail:send_email_message: smtp variables sent {0}'.format(message))
		server.sendmail(self.sender, self.recipients,  message.as_string())
		server.quit()

class CommunicateWithDB(object):

	def __init__(self, host, user, passwd, dbname, sql_cmd=None):
		self.host = host
		self.user = user
		self.passwd = passwd.decode('hex')
		self.dbname = dbname
		self.sql_cmd = sql_cmd

	def connect_to_db(self):
		log.debug("CommunicateWithDB:connect_to_db: Connecting to host: {0} with user: {1}".format(self.host,self.user))
		# General connection to the db. Make sure to close it when done
		self.db = MySQLdb.connect(self.host, self.user, self.passwd, self.dbname)
		self.cursor = self.db.cursor()

	def disconnect_db(self):
		# Close the db after the object is done
		log.debug("CommunicateWithDB:disconnect_db: closing db")
		self.db.close()

	def execute_sql(self,sql_cmd):
		# Take a single command and return results
		log.debug("CommunicateWithDB:execute_sql: running {0}".format(sql_cmd))
		self.cursor.execute(sql_cmd)
		data = self.cursor.fetchall()
		self.db.commit()
		return data

	def insert_sql(self,sql_cmd):
		log.debug("CommunicateWithDB:insert_sql: {0}".format(sql_cmd))
		# Add a record to the db
		try:
			# Execute the SQL command
			self.cursor.execute(sql_cmd)
			self.db.commit()
		except Exception, e:
			log.debug(repr(e))
			# Rollback in case there is any error
			log.debug("CommunicateWithDB:insert_sql: running ROLLBACK .. we failed")
			self.db.rollback()

class OSPIReadSettings(object):

	def __init__(self):
		self.settings = {}

	def add_settings(self):
		my_json_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'ospi_settings.json')
		my_json_file = open(my_json_file_path, 'r')
		my_json_values = json.load(my_json_file)
		my_json_file.close()

		for key, value in my_json_values.iteritems():
			self.settings[key] = value

		return self.settings

class CreateNotificationObject(object):

	def __init__(self):
		self.html_header = None
		self.html_body = ""
		self.html_footer = None

	def create_header(self):
		self.html_header = """\
		<html>
			<head></head>
			<body>
		"""
		log.debug("CreateNotificationObject:create_header: created header")

	def create_table(self, date):
		my_html_table = """\
				<table border="0" width="350">
					<tr>
						<th align="left">{0}</th>
						<th align="left">Duration</th>
						<th align="left">Zone</th>
					</tr>
		""".format(date)

		self.html_body += my_html_table
		log.debug("CreateNotificationObject:create_table: added table to existing body {0}".format(self.html_body))

	def conjure_context(self, body):
		self.html_body += body
		log.debug("CreateNotificationObject:create_table: added content to existing body {0}".format(self.html_body))

	def perform_footer(self):
		self.html_footer = """\
			</body>
		</html>
		"""
		log.debug("CreateNotificationObject:perform_footer: created footer")

	def conjure_finished_html(self):
		self.create_header()
		self.perform_footer()
		my_final = "{0}{1}{2}".format(self.html_header,self.html_body,self.html_footer)
		return my_final

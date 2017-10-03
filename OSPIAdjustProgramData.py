#!/usr/bin/env python
"""
################################################################################
# Copyright (c) 2017 Robert Hill. All rights reserved.
################################################################################
	NAME:
	OSPIAdjustProgramData.py

	DESCRIPTION:
	A Script to adjust my watering times based on weather.
	The last zone is not enabled, but contains all the watering times
	as a baseline for weather adjustments.

	NOTES:
	My landscaper wants me to adjust the overall time based on temperature 
	and seaons. Nothing really fit very well on the OSPI so I figured I
	would just make my own. It's a bit static, but it works for my needs
	http://0.0.0.0.0:port/cp?pw=password&pid=1&v=[1,21,0,[380,0,0,0],[0,1320,0,0,0,0,0,0]

	HISTORY:
	06/19/17 -RH
	Initial developtment

################################################################################
"""

################################################################################
# IMPORT
################################################################################
import OSPIUtility, logging, urllib2
from OSPIUtility import *
from urllib import quote
from urllib2 import URLError

################################################################################
# LOGGING
################################################################################
log = logging.getLogger('ospiadjustprogramdata')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
logger1 = logging.FileHandler('/tmp/ospiadjustprogramdata.log')
logger1.setLevel(logging.DEBUG)
logger1.setFormatter(formatter)
log.addHandler(logger1)

################################################################################
# CLASSES
################################################################################

def main():
	"""main - runs the main script"""

	# Read in the weather info
	ors = OSPIReadSettings()
	my_settings = ors.add_settings()
	my_ospi_ip = my_settings['open_sprinkler_ip']
	my_ospi_pass = my_settings['md5_pass']
	owi = OSPIWeatherInformation()
	owi.get_weather_information()
	my_max_temp = owi.max_temp
	log.debug("OSPIAdjustProgramData:main: Tomorrow's max temp will be {0}".format(my_max_temp))

	# Get the sprinkler information 
	opcs = OSPICheckStatus(my_ospi_ip,my_ospi_pass)
	opcs.return_program_data()
	my_program_data = opcs.program_data
	log.debug("OSPIDefaultZoneInformation:return_default_zone_times: my_program_data {0}".format(my_program_data))

	# Can't connect to weather service?
	if my_max_temp == None:
		print "OSPIAdjustProgramData could not communicate with the Weather Service. Quitting"
		log.debug("OSPIAdjustProgramData:main: Weather service could not be reached, quitting")
		sys.exit(0)

	# These are my own personal values, feel free to make this as fancy as you want
	if my_max_temp >= 80 and my_max_temp <= 95:
		my_percentage = .15
		adjust_water_duration(my_program_data, my_percentage, 1)
		send_weather_change_notification(my_max_temp, my_percentage)
	elif my_max_temp > 95:
		my_percentage = .30
		adjust_water_duration(my_program_data, my_percentage, 1)
		send_weather_change_notification(my_max_temp, my_percentage)
		
	# Weather is normal, no adjustment needed
	else:
		# Make sure the zones are set to default values
		adjust_water_duration(my_program_data, 0, None, None, 1)
		log.debug("OSPIAdjustProgramData:main: Tomorrow's max temp will be {0}, no adjustment made".format(my_max_temp))

def send_weather_change_notification(max_temp, percentage):
	"""send_weather_change_notification - email a notification about adjustment"""

	# Send a notification that we've adjusted the water duration
	cno = CreateNotificationObject()
	cno.create_header()
	my_percentage = None
	ors = OSPIReadSettings()
	my_settings = ors.add_settings()
	my_ospi_email = my_settings['email_login_user']
	my_ospi_email_pass = my_settings['email_passwd']
	my_ospi_email_from = my_settings['email_from']
	my_ospi_email_to = my_settings['email_to']

	# Send a EMAIL every day with the log
	osem = OSPIEmail(my_ospi_email,my_ospi_email_pass,my_ospi_email_from,my_ospi_email_to)
	my_tmp_percentage = str(percentage)
	my_tp_percentage = my_tmp_percentage[2:]
	# Fix percentage
	if len(my_tp_percentage) == 1:
		my_percentage = "{0}0".format(my_tp_percentage)
	else:
		my_percentage = my_tp_percentage
	my_subject = "Watering Adjustment Notification"
	my_add_to_body = """
		<p>Weather adjustment made.</br>
		Temperature tomorrow will be {0}.</br>
		Watering times adjusted by {1}%.</p>
			""".format(max_temp, my_percentage)

	cno.conjure_context(my_add_to_body)
	my_body = cno.conjure_finished_html()
	log.debug("send_weather_change_notification: sending email notification {0}".format(my_body))
	osem.send_email_message(my_subject,my_body)

def adjust_water_duration(program_data, percentage, positive=None, negative=None, default=None):
	"""adjust_water_duration - calls the OSPI module and adjusts value postive or negative"""

	ors = OSPIReadSettings()
	my_settings = ors.add_settings()
	my_ospi_ip = my_settings['open_sprinkler_ip']
	my_ospi_pass = my_settings['md5_pass']
	my_adjustment_prefix = "{0}/cp?pw={1}".format(my_ospi_ip,my_ospi_pass)
	my_adjustment = None
	owa = OSPIWaterAdjustment(program_data)

	if default:
		my_adjustment_list = owa.adjust_duration_default()
	elif positive:
		my_adjustment_list = owa.adjust_duration_positive(percentage)
	elif negative:
		my_adjustment_list = owa.adjust_duration_negative(percentage)

	my_count = 0
	for my_adjustment in my_adjustment_list:
		my_program_name = my_adjustment[-1]
		my_adjustment = my_adjustment[:-1]
		my_encoded_name = quote(my_program_name)
		my_tmp_adjustment = "{0}&pid={1}&v={2}&name={3}".format(my_adjustment_prefix,my_count,my_adjustment,my_encoded_name)
		my_adjustment = "".join(my_tmp_adjustment.split())
		my_count += 1
		log.debug("adjust_water_duration: my_adjustment {0}".format(my_adjustment))

		# Run command for each adjustment
		run_adjustment(my_adjustment)

def run_adjustment(ospi_cmd):
	"""run_adjustment - takes the OSPI command and runs it"""

	# Execute the command for adjusting the water duration based on the temp.
	try:
		fh = urllib2.urlopen(ospi_cmd)
		my_result = fh.read()
		log.debug("run_adjustment: urllib returned {0}".format(my_result))
	except HTTPError, e:
		log.debug("run_adjustment: {0}".format(e))

main()

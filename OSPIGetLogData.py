#!/usr/bin/env python
"""
################################################################################
# Copyright (c) 2017 Robert Hill. All rights reserved.
################################################################################
        NAME:
        OSPIGetLogData.py

        DESCRIPTION:
	Pull the log data from the sprikler and distribute it

        NOTES:
        jl = Get Log Data
	dl = Delete Log Data
	[pid, sid, dur, end] 
	pid is useless
	sid is station id
	dur is duration
	end is end time

	Curiously the logs on the OpenSprinkler don't persist very long.
	I get a error after a few days of logs, and can no longer access
	them. So, we'll collect them daily and send them on.
	Collect the logs and parse them, then send it along to interested
	parties.

        HISTORY:
        06/19/17 -RH
        Initial developtment

################################################################################
"""

################################################################################
# IMPORT
################################################################################
import OSPIUtility, logging, time
from OSPIUtility import *

################################################################################
# LOGGING
################################################################################
log = logging.getLogger('ospigetloginfo')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

logger1 = logging.FileHandler('/tmp/ospigetloginfo.log')
logger1.setLevel(logging.DEBUG)
logger1.setFormatter(formatter)
log.addHandler(logger1)

################################################################################
# CLASSES
################################################################################

def main():

	my_run = 0
	my_date = None

	# Check stations and return content
	ors = OSPIReadSettings()
	my_settings = ors.add_settings()
	my_ospi_ip = my_settings['open_sprinkler_ip']
	my_ospi_pass = my_settings['md5_pass']
	my_ospi_email = my_settings['email_login_user']
	my_ospi_email_pass = my_settings['email_passwd']
	my_ospi_email_from = my_settings['email_from']
	my_ospi_email_to = my_settings['email_to']
	opcs = OSPICheckStatus(my_ospi_ip,my_ospi_pass)
	cno = CreateNotificationObject()
	cno.create_header()

	# Stations names is a dict
	opcs.return_station_names()
	my_station_names = opcs.station_names
	my_stations_list = my_station_names.get("snames")

	# First pass over the list for each run
	opcs.return_log_data()
	my_return = opcs.program_data

	if not my_return:
		log.debug("OSPIGetLogInfo: NO LOG DATA TO PARSE, QUITTING")
		sys.exit(0)

	for run in my_return:
		my_run += 1
		my_tmp_date = my_date

		# The date for the run
		my_run_time = run[3]
		log.debug("OSPIGetLogInfo: my_run_time {0}".format(my_run_time))
		my_date = time.strftime('%m/%d/%Y', time.gmtime(my_run_time))
		log.debug("OSPIGetLogInfo: my_date {0}".format(my_date))
		# See if we need a new date section
		if my_date != my_tmp_date:
			# See if we already had a previous section
			if my_tmp_date != None:
				# Close the section
				cno.conjure_context("</table>")
			
			my_tmp_date = my_date # Set new tmp date
			cno.create_table(my_date)

		# The zone start time
		my_time = time.strftime('%H:%M', time.gmtime(my_run_time))
		log.debug("OSPIGetLogInfo: my_time {0}".format(my_time))

		# Get the station id and name
		my_raw_zone = run[1]
		my_named_zone = my_stations_list[my_raw_zone]
		my_zone = "Zone {0} {1}".format(my_raw_zone, my_named_zone)
		log.debug("OSPIGetLogInfo:main: Adding zone information {0}".format(my_zone))

		# Get the run time in minutes, if it's zero seconds, don't add it to the report
		my_run_return = run[2]
		my_min, my_sec = divmod(my_run_return, 60)
		if my_sec != 0:
			my_run_time = "{0}m:{1}s".format(my_min, my_sec)
		else:
			my_run_time = "{0}m".format(my_min)

		my_add_to_body = """
				<tr>
					<td>{0}</td>
					<td>{1}</td>
					<td>{2}</td>
				</tr>
				""".format(my_time,my_run_time,my_zone)
		cno.conjure_context(my_add_to_body)
		log.debug("OSPIGetLogInfo:main: created html_report {0}".format(my_add_to_body))

	# Make sure the table is closed
	cno.conjure_context("</table>")

	# Delete logs (since the log function isn't great right now anyway)
	opcs.remove_logs()

	# Send a EMAIL every day with the log
	osem = OSPIEmail(my_ospi_email,my_ospi_email_pass,my_ospi_email_from,my_ospi_email_to)

	my_subject = "Daily watering report"
	my_body = cno.conjure_finished_html()
	osem.send_email_message(my_subject,my_body)

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

main()

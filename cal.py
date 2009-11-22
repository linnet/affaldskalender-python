# -*- coding: iso-8859-1 -*-

import os
from google.appengine.ext.webapp import template

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

class Garbage(db.Model):
    address = db.StringProperty()
    content = db.TextProperty()
    updateDate = db.DateProperty()
    fetchTime = db.DateTimeProperty(auto_now_add=True)

class GarbagePickup:
    def __init__(self, description, date):
        self.description = description
        self.date = date
    
    def __repr__(self):
        return '%s: %s' % (self.description, self.date)

class Register(webapp.RequestHandler):
    def get(self):
        template_values = { }
    
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        address = self.request.get('address')
        
        garbageQuery = Garbage.gql("WHERE address = :1", address)
        garbage = garbageQuery.get()
        if not garbage:
            garbage = Garbage()
            garbage.address = address
            garbage.updateDate = date.today()
            garbage.put()
            
        address_id = garbage.key()
        calendar_url = self.request.relative_url('/calendar/%s.ics' % address_id)

        template_values = {
                            'calendar_url': calendar_url,
                            'address': address
                          }

        path = os.path.join(os.path.dirname(__file__), 'calendar.html')
        self.response.out.write(template.render(path, template_values))

class Calendar(webapp.RequestHandler):

    def expand_date_list(self, description, date_list):
        expanded_dates = [GarbagePickup(description, date) for date in date_list]
        return expanded_dates
        
    def expand_dates(self, dates):
        expanded_dates = [self.expand_date_list(garbage_type, dates[garbage_type]) for garbage_type in dates]
        flattened_dates = [item for sublist in expanded_dates for item in sublist]
        return flattened_dates
        
    def should_refresh_data(self, garbage):
        return not garbage.content or (date.today() - garbage.updateDate).days > 1
    
    def get(self, calendar_id):
        logging.info("Calendar ID: %s" % calendar_id)
        self.response.headers['Content-Type'] = 'text/calendar'

        garbage = Garbage.get(calendar_id)
        logging.info("Address of calendar: %s" % garbage.address)

        refresh = self.should_refresh_data(garbage)
        if refresh:
            logging.info("Fetching new content")
            resp = Fetcher().fetch(garbage.address)
            garbage.content = db.Text(resp, encoding='latin-1')
            garbage.updateDate = date.today()
            garbage.put()
        else:
            logging.info("Reusing content")
            resp = garbage.content

        garbage_types = Parser().parse(resp)

        dates = self.expand_dates(garbage_types)

        ics = IcsGenerator().generate(dates)
        self.response.out.write(ics)

class IcsGenerator:
    def generate_type(self, description, date_list):
        
        events = []
        for date in date_list:
            event = event_template % (date, date.today(), description)
            events.append(event)

        return event.join('\n')

    def generate(self, dates):
        header = """BEGIN:VCALENDAR
PRODID:-//Jesper Kamstrup Linnet//Affaldskalender 1.0//EN
VERSION:2.0
CALSCALE:GREGORIAN
"""

        footer = "END:VCALENDAR"

        event_template = """BEGIN:VEVENT
DTSTAMP:%s
DTSTART;VALUE=DATE:%s
SUMMARY:%s
END:VEVENT
"""

        today = date.today().strftime('%Y%m%dT000048Z')
        events = [event_template % (today, pickup.date.strftime('%Y%m%d'), pickup.description) for pickup in dates]
        events_string = ""
        for event in events:
            events_string = events_string + event

        return header + events_string + footer


import logging
import urllib
from google.appengine.api import urlfetch

class Fetcher:
    def fetch(self, address):
        base_url = "http://kk.sites.itera.dk/apps/kk_afhentningstider/afhentningstider.asp"
        form_fields = {
          "mode": "detalje",
          "id": address.encode('iso-8859-1')
        }
        url_values = urllib.urlencode(form_fields)

        logging.info("URL parameters: " + url_values)

        url = base_url + '?' + url_values
        logging.info("URL: " + url)
        result = urlfetch.fetch(url=url,
                                method=urlfetch.GET,
                                headers={
                                    'Accept': '*/*',
                                    'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2b2) Gecko/20091108 Firefox/3.6b2'
                                })
        logging.info("Data fetched: status code: %d, length: %d" % (result.status_code, len(result.content)))
        return result.content


import re
from datetime import date
from datetime import datetime

class Parser:
    def parse_date(self, date_string):
        dt = datetime.strptime(date_string, "%d.%m.%y")
        return dt.date()
        
    def parse_dates(self, dates):
        date_list = re.split(', ', dates)
        dates_as_objects = [self.parse_date(d) for d in date_list]
        return dates_as_objects

    def parse(self, data):
        pattern = r'<div class="title">(?P<garbage_type>\w+).*?</div>\s*.*[Hh]entes.*? den (?P<dates>\d{2}.+\d{2})\.'
        
        garbage_types = {}
        
        matches = re.finditer(pattern, data)
        for m in matches:
            (garbage_type, dates) = m.group(1, 2)
            dates_as_list = self.parse_dates(dates)
            garbage_types[garbage_type] = dates_as_list
            
        return garbage_types



application = webapp.WSGIApplication(
                                     [
                                        (r'/calendar/(\w+)\.ics', Calendar),
                                        ('/.*', Register)
                                     ],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()

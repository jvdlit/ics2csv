#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 21 21:28:10 2020

@author: twerkhov
"""

from icalendar import Calendar
import re
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime

# config should contain
config = yaml.safe_load(open("utrechtcarpool.yaml"))
calfile = config['calfile']
validamlocs = config['validamlocs']
validpmlocs = config['validpmlocs']

def get_driver_passengers(topic):
    """
    From event topic (summary), get driver and passenger
    
    Expected syntax:
        'carpool([\W]+([\w]+))+'
    e.g.
        Carpool - Peter + Martin + Wolfgang
        carpool Peter    Martin Wolfgang
        carpool Peter, Martin, Wolfgang
        carpool Peter + Martin + Wolfgang +1 (+1 is dropped in accounting, guests are free)
        helloworld Peter+++Martin_,8123,,---Wolfgang

    Not OK:
        Peter Martin Wolfgang (lacks Carpool magic word)
        carpool PeterMartinWolfgang (cannot split names)
        carpool Peter, Martin Wu, Wolfgang (names must be one word only)
        carpool - Peter, Bart-Jan (names must be only alphanumeric, all other tokens are used as separator)
    """
    # Regexp pattern to strip non-alphanumeric characters
    # https://stackoverflow.com/questions/1276764/stripping-everything-but-alphanumeric-chars-from-a-string-in-python
    # Split topic by non-alphanumeric characters - https://docs.python.org/2/library/re.html
    names = re.split('[^a-zA-Z]+',topic.lower(), re.UNICODE)

    # Remove empty hits in case string ends in non-alphanumeric char (e.g. 
    # space). Alternatively we could strip() the string using all 
    # non-alphanumeric charactere, but another regexp is probably slower
    names = list(filter(None, names))

    driver = names[1]
    passengers = names[2:]
        
    return driver, passengers

def get_location(location, time):
    """
    From event location string, get validated carpool location
    """
    # Depending on time, we assume different locations
    if time.dt.hour < 12:
        validlocs = validamlocs
        locdefault = "UNKNOWN-EVERDINGEN"
    else:
        validlocs = validpmlocs
        locdefault = "UNKNOWN-B7"

    # For each valid location, check if it's found in the actual location string
    loc = location.lower()
    for v in validlocs:
        if v in loc:
            # If valid location found, return immediately
            return v
    # If nothing found, return default location
    return locdefault

def normalize_ics(file='calendar.ics'):
    """
    Given ICS file, normalize for carpool accounting to fixed set of drivers, times, locations.
    Only look for past events
    """

    now = datetime.datetime.now()
    
    with open(file,'rb') as g:
        gcal = Calendar.from_ical(g.read())
        # Only look at events (name == 'VEVENT') that are not cancelled (STATUS != 'TRANSPARENT')
        # Get people from SUMMARY, get valid location from LOCATION/DTSTART
        normed = [get_driver_passengers(c.get('SUMMARY')) +
                (get_location(c.get('LOCATION'),
                c.get('DTSTART')),c.get('DTSTART').dt) 
                    for c in gcal.walk() 
                        if (c.name == 'VEVENT' and 
                            c.get('TRANSP') != 'TRANSPARENT' and
                            c.get('DTSTART').dt < now)]
    return normed

def carpool_account(lastevents, tripcost=16):
    """
    Given normalized ICS input (driver, passengers, departure location, 
    start time), distribute tripcost over driver and passenger.
    """

    balance = {}

    for driver, passengers, loc, time in lastevents:
        # print("d: {}, d: {}, p: {}".format(time, driver, ",".join(passengers)))
        npers = 1 + len(passengers)
        balance[driver] = balance.get(driver,0) + tripcost - tripcost/npers
        for p in passengers:
            balance[p] = balance.get(p,0) - tripcost/npers
    return balance

def export_as_html(lastevents, balance, htmltemplate='./web/index_templ.html'):
    """
    Given normalized ICS input (driver, passengers, departure location, 
    start time), export results to HTML report for human review.
    """
    env = Environment(
        loader=FileSystemLoader('./'),
        autoescape=False
    )
    # select_autoescape(['html', 'xml'])

    template = env.get_template(htmltemplate)
    render = template.render(
        lastevents=lastevents,
        balance=balance)
        # activetop10=stats[30]['active']['allday'],
        # stats30daily=stats30daily,
        # stats30alltime=stats30alltime)

    with open('./web/index.html', 'w') as fd:
        fd.write(render)

def find_dest(lastevents):
    """
    Given normalized ICS input (driver, passengers, departure location, 
    start time), find matching destination location by checking what is the 
    departure location of the next trip by the same driver.
    
    Typically a driver departs from location X in the morning, then departs
    from locaiton Y in the afternoon, meaning the trip was X->Y and Y->X.
    """
    pass

lastevents = normalize_ics(calfile)
balance = carpool_account(lastevents)
print(lastevents[0])
export_as_html(lastevents, balance)


# matchedics = find_dest(lastevents)
# carpool_account_distance(lastevents)

#!/usr/bin/env python
from datetime import datetime
from bs4 import BeautifulSoup
from pprint import pprint
from sys import argv, exit
from time import sleep
import requests
import logging
import json
import re

# local settings
import settings

VERSION = "0.1.0"

class SearchEngine(object):

    # file to store the rooms in
    file_name = 'rooms.json'

    # preferences used to make queries to the web application
    preferences = {}

    # variables that need to be in the settings module
    required_settings = ['SLEEP', 'MIN_AVAILABLE_TIME']

    def __init__(self, preferences=None, areas=None, cookies=None, required_settings=None):
        """
        Create a SearchEngine object.

        preferences -- preferences to be merged with the default preferences
        areas -- areas to search rooms in
        cookies -- cookies to be used when making requests to the server
        required_settings -- settings to merge with required_settings
        """

        # merges the required settings and verify if they exist
        if required_settings:
            self.required_settings = list(set(required_settings + self.required_settings))

        for prop in self.required_settings:
            if not hasattr(settings, prop):
                print('Required settings property {prop} not found in the settings module'.format(prop=prop))
                exit(0)

        self.AREAS = areas or []
        self.cookies = cookies or {}

        # merges the preferences from the settings file
        if preferences:
            for key in preferences:
                self.preferences[key] = preferences[key]

        # will hold all the rooms found in self engine
        self.rooms = {}

        # loads rooms from file
        self.load_rooms(settings.MARK_OLD)

    def make_get_request(self, url=None, headers=None, cookies=None, proxies=None):
        if settings.DEBUG:
            print('Sleeping for {secs} seconds'.format(secs=settings.SLEEP))
        sleep(settings.SLEEP)
        return requests.get(url, cookies=self.cookies, headers=self.headers).text

    def load_rooms(self, clean=True):
        """
        Loads rooms from file if it exists. In case of error will clean the
        rooms variable.

        clean -- if set to true will mark the loaded rooms as not new
        """

        try:
            # try opening the files with the rooms and load it as a json file
            with open(self.file_name, 'r') as f:
                self.rooms = json.loads(f.read())

            # mark all loaded rooms as old if clean=True
            if clean:
                self.mark_as_old()

        # catch exception if the file does not exist or if json.loads fail
        except (IOError, ValueError) as e:
            logging.warning(e.strerror, extra={'engine': self.__class__.__name__, 'function': 'load_rooms'})
            # don't load any rooms
            self.rooms = {}

    def save_rooms(self):
        """Saves the found rooms in the defined file."""

        # save the rooms found in the file
        try:
            with open(self.file_name, 'w') as f:
                f.write(json.dumps(self.rooms))

        # catch exceptions in case it cannot create the file or something wrong
        # with json.dumps
        except (IOError, ValueError) as e:
            logging.error(e.strerror, extra={'engine': self.__class__.__name__, 'function': 'save_rooms'})

    def mark_as_old(self):
        """Marks the loaded rooms as not new."""

        for room in self.rooms:
            self.rooms[room]['new'] = False
        self.save_rooms()

    def get_sorted(self):
        """Returns an array of rooms sorted by score."""

        nrooms = {}
        for room in self.rooms:
            nrooms[int(room)] = self.rooms[room]
        return [nrooms[room] for room in sorted(nrooms, key=lambda k: nrooms[k]['score'] if 'score' in nrooms[k] else 0, reverse=True)]

    def rate(self):
        for room in self.rooms:
            try:
                self.rooms[room]['new'] = True
                self.rate_room(room)
            except:
                continue
        self.save_rooms()

    def update(self):
        for room in self.rooms:
            try:
                self.get_room_info(room, self.rooms[room]['search'])
            except:
                self.rooms[room]['new'] = False
                continue
        self.save_rooms()

    def generate_report(self, fields=None, pref_ids=[], max_range=-1, when=False, areas=False):
        name = str(self.__class__.__name__).split(' ')[0]
        html = '<html><head><title>{name} Classified Ads</title><link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css"></head><body>'.format(name=name)
        html += '<table class="table">'
        html += '<thead><tr>'
        for field in fields:
            html += '<th>{field}</th>'.format(field=field.replace('_', ' ').capitalize())
        html += '</tr></thead><tbody>'
        for i, room in enumerate(self.get_sorted()):
            if when:
                try:
                    available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S")
                    if available_time < WHEN:
                        continue
                except:
                    available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S.%f")
                    if available_time < WHEN:
                        continue

            if (room['new'] or room['id'] in pref_ids) and room['search'] in self.AREAS:
                htmlclass = 'success' if room['new'] else 'danger' if room['id'] in pref_ids else 'info'
                html += '<tr class="{css}">'.format(css=htmlclass)
                for field in fields:
                    if field == 'id':
                        url = '{location}/{endpoint}{id}'.format(location=self.location, endpoint=self.details_endpoint, id=room['id'])
                        html += '<td><a href="{url}">{field}</td>'.format(url=url, field=room[field])
                    elif field == 'images':
                        pics = ['<a href="{url}"><img src="{src}" height="100" width="100"></a>'.format(url=img, src=img) for img in room['images']]
                        images = ''
                        for i in range(5):
                            images += pics[i] if len(pics) > i else ''
                        html += '<td>{images}</td>'.format(images=images)
                    else:
                        html += '<td>{value}</td>'.format(value=room[field])
                html += '</tr>'
                max_range -= 1

            if max_range == 0:
                break

        html += '<tbody></table><script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/js/bootstrap.min.js"></script></body></html>'

        with open(self.file_name.replace('.json', '.html'), 'w') as f:
            f.write(html.encode('utf-8'))

    def rate_room(self, key=None):
        if not key or key not in self.rooms:
            return

        """Score variables:
        price + deposit - 0.10
        bills inc - 0.05
        area - 0.25
        rooms - 0.20
        housemates - 0.20
        pictures - 0.05
        available - 0.15

        all score from 0 to 100
        """

        room = self.rooms[key]

        areas = [area.lower() for area in self.AREAS]
        # check station, give better score if first stations
        area_score = (len(areas) - areas.index(room['station'].lower()))*(100/len(areas)) if room['station'].lower() in areas else 0

        score = area_score * 0.25

        if settings.DEBUG:
            print("AREA SCORE: {score}".format(score=area_score))

        # lower price -> better score
        price = min(room['prices'])
        MAX_RENT_PM = self.preferences['max_rent']
        difference = abs(int(price) - MAX_RENT_PM)
        price_score = max(0, 50 - (difference)/10) if price >= MAX_RENT_PM else min(100, 50 + (difference)/10)

        if settings.DEBUG:
            print("PRICE SCORE: {score}".format(score=price_score))

        score += price_score*0.05

        #score += 100 if price < MAX_RENT_PM - 150 else 80 if price < MAX_RENT_PM - 100 else 50 if price < MAX_RENT_PM - 50 else 20 if price < MAX_RENT_PM else 0

        deposit = min(room['deposits']) if len(room['deposits']) > 0 else 0
        difference = abs(int(deposit) - MAX_RENT_PM)
        deposit_score = max(0, 50 - (difference)/10) if deposit >= MAX_RENT_PM else min(50, 50 + (difference)/10)
        #score += 20 if deposit != -1 and deposit <= price else 0

        if settings.DEBUG:
            print("DEPOSIT SCORE: {score}".format(score=deposit_score))

        score += deposit_score*0.05

        # bills includes - better score - 0.05
        score += 5 if room['bills'] else 0

        rooms_score = max(0, 100 - (int(room['rooms']) - 1)*15)

        if settings.DEBUG:
            print("ROOMS SCORE: {score}".format(score=rooms_score))

        score += rooms_score*0.20

        # less housemates - better score
        if room['housemates'] != -1:
            housemates_score = max(0, 100 - (int(room['housemates']) - 1)*10)/2
            housemates_score += int(room['females'])/int(room['housemates'])*100/2
            #score += 50 if room['housemates'] < 0 else 40 if room['housemates'] < 2 else 30 if room['housemates'] < 4 else 0

            if settings.DEBUG:
                print("HOUSEMATES SCORE: {score}".format(score=housemates_score))

            score += housemates_score*0.20

        # more images - better score
        # no images -> -100
        #score += 7*len(room['images']) if len(room['images']) > 0 else - 100
        image_score = min(100, 25*len(room['images']))

        if settings.DEBUG:
            print("IMAGE SCORE: {score}".format(score=image_score))

        score += image_score*0.05

        # if phone - better score
        #score += 100 if room['phone'] else 0

        # the closer (or now) the room is available to desired - better score
        try:
            available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S")
        except:
            available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S.%f")

        difference = abs((self.preferences['when'] - available_time).total_seconds())
        #score += 100 if difference > 0 else 80 if difference > -2880 else 50 if difference > -7200 else 0
        available_score = max(0, 100 - (difference/60/60/24))

        if settings.DEBUG:
            print("AVAILABLE SCORE: {score}".format(score=available_score))

        score += image_score*0.15

        if settings.DEBUG:
            print("FINAL SCORE: {score}".format(score=score))

        if (settings.MIN_AVAILABLE_TIME - available_time).total_seconds() > 0:
            self.rooms[key]['new'] = False
            score = 0

        self.rooms[key]['score'] = score

class SpareRoom(SearchEngine):
    headers = {'User-Agent': 'SpareRoomUK 3.1'}

    api_location = 'http://iphoneapp.spareroom.co.uk'
    api_search_endpoint = 'flatshares'
    api_details_endpoint = 'flatshares'

    location = 'http://www.spareroom.co.uk'
    details_endpoint = 'flatshare/flatshare_detail.pl?flatshare_id='
    file_name = 'spareroom.json'

    preferences = {
        'format': 'json',
        'max_rent': settings.MAX_RENT_PM,
        'per': 'pcm',
        'page': 1,
        'room_types': settings.TYPE,
        'rooms_for': settings.FOR,
        'max_per_page': settings.MAX_RESULTS,
        'where': 'london',
        'ensuit': 'Y',
    }

    def get_new_rooms(self):
        for area in self.AREAS:
            self.search_rooms_in(area)
            self.save_rooms()

    def search_rooms_in(self, area):
        if settings.VERBOSE:
            print('Searching for {area} flats in SpareRoom'.format(area=area))

        self.preferences['page'] = 1
        self.preferences['where'] = area.lower()
        params = '&'.join(['{key}={value}'.format(key=key, value=self.preferences[key]) for key in self.preferences])
        url = '{location}/{endpoint}?{params}'.format(location=self.api_location, endpoint=self.api_search_endpoint, params=params)

        try:
            results = json.loads(self.make_get_request(url=url, cookies=self.cookies, headers=self.headers))
            if settings.VERBOSE:
                print('Parsing page {page}/{total} flats in {area}'.format(page=results['page'], total=results['pages'], area=area))

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                if settings.FAST:
                    self.get_short_room_info(room_id, area, room)
                else:
                    self.get_room_info(room_id, area)

                self.rate_room(room_id)
        except Exception as e:
            if settings.VERBOSE:
                print('Error parsing first page: {message}'.format(message=e.message))
            return None

        for page in range(1, min(int(results['pages']), settings.MAX_PAGES)):
            self.preferences['page'] = page + 1
            params = '&'.join(['{key}={value}'.format(key=key, value=self.preferences[key]) for key in self.preferences])
            url = '{location}/{endpoint}?{params}'.format(location=self.api_location, endpoint=self.api_search_endpoint, params=params)
            try:
                results = json.loads(self.make_get_request(url=url, cookies=self.cookies, headers=self.headers))
            except Exception as e:
                if settings.VERBOSE:
                    print('Error Getting {page}/{total}: {message}'.format(page=page, total=results['pages'], message=e.message))

            if settings.VERBOSE:
                print('Parsing page {page}/{total} flats in {area}'.format(page=results['page'], total=results['pages'], area=area))

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                if settings.FAST:
                    self.get_short_room_info(room_id, area, room)
                else:
                    self.get_room_info(room_id, area)

                self.rate_room(room_id)

    def get_short_room_info(self, room_id, search, room_details):
        if settings.VERBOSE:
            print('Parsing {id} flat short details'.format(id=room_id))

        if 'days_of_wk_available' in room_details and room_details['days_of_wk_available'] != '7 days a week':
            if settings.VERBOSE:
                print('Room availability: {avail} -> Removing'.format(avail=room_details['days_of_wk_available']))
            return None

        bills = True if 'bills_inc' in room_details and room_details['bills_inc'] == 'Yes' else False
        rooms_no = room_details['rooms_in_property'] if 'rooms_in_property' in room_details else 100
        station = room_details['station_name'] if 'station_name' in room_details else "No Details"

        images = [room_details['main_image_square_url']] if 'main_image_square_url' in room_details else []

        deposits = prices = []
        if 'min_rent' in room_details:
            price = int(room_details['min_rent'].split('.', 1)[0])
            price = price if 'per' in room_details and room_details['per'] == 'pcm' else price * 52 / 12
            prices.append(price)

        if 'max_rent' in room_details:
            price = int(room_details['max_rent'].split('.', 1)[0])
            price = price if 'per' in room_details and room_details['per'] == 'pcm' else price * 52 / 12
            prices.append(price)

        phone = False
        available = "No Details"
        available_timestamp = datetime.now()

        housemates = males = females = 100

        self.rooms[room_id] = {
            'id': room_id,
            'search': search,
            'images': images,
            'station': station,
            'prices': prices,
            'available': available,
            'timestamp': str(available_timestamp),
            'deposits': deposits,
            'bills': bills,
            'rooms': rooms_no,
            'housemates': housemates,
            'females': females,
            'males': males,
            'phone': phone,
            'new': True,
        }

    def get_room_info(self, room_id, search):
        if settings.VERBOSE:
            print('Getting {id} flat details'.format(id=room_id))

        url = '{location}/{endpoint}/{id}?format=json'.format(location=self.api_location, endpoint=self.api_details_endpoint, id=room_id)
        try:
            room = json.loads(self.make_get_request(url=url, cookies=self.cookies, headers=self.headers))
            if settings.DEBUG:
                pprint(room)
        except:
            return None

        if 'days_of_wk_available' in room['advert_summary'] and room['advert_summary']['days_of_wk_available'] != '7 days a week':
            if settings.VERBOSE:
                print('Room availability: {avail} -> Removing'.format(avail=room['advert_summary']['days_of_wk_available']))
            return None

        phone = room['advert_summary']['tel'] if 'tel' in room['advert_summary'] else room['advert_summary']['tel_formatted'] if 'tel_formatted' in room['advert_summary'] else False
        bills = True if 'bills_inc' in room['advert_summary'] and room['advert_summary']['bills_inc'] == 'Yes' else False
        station = room['advert_summary']['nearest_station']['station_name'] if 'nearest_station' in room['advert_summary'] else "No Details"
        images = [img['large_url'] for img in room['advert_summary']['photos']] if 'photos' in room['advert_summary'] else []
        available = room['advert_summary']['available'] if 'available' in room['advert_summary'] else 'Now'
        females = room['advert_summary']['number_of_females'] if 'number_of_females' in room['advert_summary'] else 0
        males = room['advert_summary']['number_of_males'] if 'number_of_males' in room['advert_summary'] else 0

        try:
            available_timestamp = datetime.now() if available == 'Now' else datetime.strptime(available, "%d %b %Y")
        except:
            available_timestamp = datetime.now()

        rooms_no = room['advert_summary']['rooms_in_property'] if 'rooms_in_property' in room['advert_summary'] else -1
        housemates = room['advert_summary']['occupants'] if 'occupants' in room['advert_summary'] else -1

        #if 'rooms' not in room['advert_summary']:
            #return None

        prices = deposits = []
        if 'rooms' in room['advert_summary']:
            for r in room['advert_summary']['rooms']:
                if 'security_deposit' in r and r['security_deposit']:
                    deposits.append(int(r['security_deposit'].split('.', 1)[0]))
                if 'room_price' in r and r['room_price']:
                    price = int(r['room_price'].split('.', 1)[0])
                    price = price if r['room_per'] == 'pcm' else price * 52 / 12
                    prices.append(price)
        else:
            prices.append(room['advert_summary']['min_rent'] if 'min_rent' in room['advert_summary'] else room['advert_summary']['max_rent'] if 'max_rent' in room['advert_summary'] else None)

        new = True

        self.rooms[room_id] = {
            'id': room_id,
            'search': search,
            'images': images,
            'station': station,
            'prices': prices,
            'available': available,
            'timestamp': str(available_timestamp),
            'deposits': deposits,
            'bills': bills,
            'rooms': rooms_no,
            'housemates': housemates,
            'females': females,
            'males': males,
            'phone': phone,
            'new': new,
        }

        return self.rooms[room_id]

def main():
    print('Room Finder v{version} (c) Ruben de Campos'.format(version=VERSION))

    # setup logging configuirations
    LOG_FORMAT = '%(asctime)s - %(engine)s - %(function)s - %(message)s'
    logging.basicConfig(format=LOG_FORMAT)

    if not hasattr(settings, 'AREAS'):
        print('Required settings property AREAS not found in the settings module')
        exit(0)

    # Create settings defaults if they don't exist
    if not hasattr(settings, 'DEBUG'):
        settings.DEBUG = False

    if not hasattr(settings, 'VERBOSE'):
        settings.VERBOSE = False

    if not hasattr(settings, 'FORCE'):
        settings.FORCE = False

    if not hasattr(settings, 'MARK_OLD'):
        settings.MARK_OLD = False

    if not hasattr(settings, 'FAST'):
        settings.FAST = False

    if not hasattr(settings, 'SLEEP'):
        settings.SLEEP = 1

    max_range = -1
    if '--max-rooms' in argv:
        try:
            max_range = int(argv[argv.index('--max-rooms') + 1])
        except (ValueError, IndexError):
            print('Error: no max rooms given...'); exit(0)

    settings.MAX_PAGES = 10;
    if '--max-pages' in argv:
        try:
            settings.MAX_PAGES = int(argv[argv.index('--max-pages') + 1])
        except (ValueError, IndexError):
            print('Error: no max pages given...'); exit(0)

    if '--sleep' in argv:
        try:
            settings.SLEEP = float(argv[argv.index('--sleep') + 1])
        except (ValueError, IndexError):
            print('Error: no sleep seconds given...'); exit(0)

    if '-v' in argv or '--verbose' in argv:
        settings.VERBOSE = True

    if '-d' in argv or '--debug' in argv:
        settings.DEBUG = True

    if '-f' in argv or '--force' in argv:
        settings.FORCE = True

    if '--fast' in argv:
        settings.FAST = True

    if len(argv) < 2 or '--help' in argv or '-h' in argv:
        print('Usage: {command} --spareroom [ -v | -f ] [ --max-rooms rooms ] [ --max-pages pages ] [ --sleep sec ] [ --fast ]'.format(command=argv[0]))
        print('    -v : verbose')
        print('    -f : mark all rooms as not seen and re-rates them again')
        print('    --max-rooms rooms : max rooms in final report')
        print('    --max-pages pages : max to search in every area')
        print('    --sleep sec : sec to sleep on every request (spareroom\'s sending 500 responses)')
        print('    --fast : does not make a request for every room (worst scores in the algorithm)')
        print('    --room room : fetchs the information of a room, re-rates it and displays it in the terminal')
        exit(0)

    if '--spareroom' in argv:
        spareroom_preferences = {
            'when': settings.WHEN,
            'max_rent': settings.MAX_RENT_PM,
            'rooms_for': settings.FOR,
            'room_types': settings.TYPE,
            'max_per_page': settings.MAX_RESULTS
        }

        if not hasattr(settings, 'SPAREROOM_COOKIES'):
            print('Required settings property SPAREROOM_COOKIES not found in the settings module')
            exit(0)

        spareroom = SpareRoom(spareroom_preferences, settings.AREAS, settings.SPAREROOM_COOKIES, ['TYPE', 'FOR', 'MAX_RENT_PM', 'MAX_RESULTS', 'MARK_OLD', 'SPAREROOM_PREF_IDS', 'FIELDS'])

    if '--rate' in argv:
        if '--spareroom' in argv:
            spareroom.rate()

    elif '--room' in argv:
        room_id = argv[argv.index('--room') + 1]
        if '--spareroom' in argv:
            pprint(spareroom.get_room_info(room_id, room_id))
            spareroom.rate_room(room_id)
            exit(0)
    else:
        if '--spareroom' in argv:
            spareroom.get_new_rooms()

    if '--spareroom' in argv:
        spareroom.generate_report(fields=settings.FIELDS, pref_ids=settings.SPAREROOM_PREF_IDS, max_range=max_range)

if __name__ == "__main__":
    main()

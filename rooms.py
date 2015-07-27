#!/usr/bin/env python
from datetime import datetime
from bs4 import BeautifulSoup
from pprint import pprint
from sys import argv, exit
import requests
import logging
import json
import re

# local settings
import settings

class SearchEngine(object):

    # file to store the rooms in
    file_name = 'rooms.json'

    # preferences used to make queries to the web application
    preferences = {}

    def __init__(self, preferences=None, areas=None, cookies=None):
        """
        Create a SearchEngine object.

        preferences -- preferences to be merged with the default preferences
        areas -- areas to search rooms in
        cookies -- cookies to be used when making requests to the server
        """

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
            print("IMAGE SCORE: {score}".format(score=imntage_score))

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

class Zoopla(SearchEngine):

    location = 'http://www.zoopla.co.uk'
    #search_endpoint = 'to-rent/property'
    search_endpoint = 'to-rent/property/station/tube'
    details_endpoint = 'to-rent/details/'
    preferences = {
        'include_rented': 'true',
        'include_shared_accommodation': 'true',
        'price_frequency': 'per_month',
        'price_max': settings.MAX_RENT_PM,
        'radius': 0,
        'results_sort': 'newest_listings',
        'q': '',
        'radius': 1,
        'page_size': 100,
        'pn': 1
    }

    file_name = 'zoopla.json'

    def get_new_rooms(self):
        for area in self.AREAS:
            print('Searching for {area} flats in Zoopla'.format(area=area))

            # first request
            self.preferences['q'] = area.replace(' ', '+').lower()

            for page in range(1, self.preferences['max_range']+1):
                print('Search in page {page} of {area}'.format(page=page, area=area))
                self.preferences['pn'] = page
                get_params = '&'.join(['{key}={value}'.format(key=key, value=self.preferences[key]) if key != 'when' and key != 'max_range' else '' for key in self.preferences]).replace('&&', '&').lower()
                url = '{location}/{endpoint}/{query}/?{params}'.format(location=self.location, endpoint=self.search_endpoint, query=self.preferences['q'].replace('+', '-'), params=get_params)
                soup = BeautifulSoup(requests.get(url).text)

                if not soup('div', {'class': 'result-count'}):
                    url = '{location}/{endpoint}/{query}/?{params}'.format(location=self.location, endpoint=self.search_endpoint, query=self.preferences['q'].replace('+', '-'), params=get_params)
                    soup = BeautifulSoup(requests.get(url).text)

                if soup('div', {'class': 'result-count'}) and re.search('of \d+', soup('div', {'class': 'result-count'})[0].text):
                    try:
                        results = int(re.search('of \d+', soup('div', {'class': 'result-count'})[0].text).group().replace('of ', ''))
                    except:
                        break
                    # parse results in this page
                    for room in soup('li', {'itemtype': 'http://schema.org/Place'}):
                        room_id = room.attrs['data-listing-id']
                        if room_id not in self.rooms:
                            try:
                                self.get_room_info(room_id, area)
                                self.rate_room(room_id)
                            except:
                                continue
                    # if all results in this page -> break loop
                    if self.preferences['page_size']*page > results:
                        break
                else:
                    break

            self.save_rooms()

    def get_room_info(self, room_id, search):
        print('Getting {id} flat details'.format(id=room_id))
        # http://www.zoopla.co.uk/to-rent/details/35664773
        url = '{location}/{endpoint}{id}'.format(location=self.location, endpoint=self.details_endpoint, id=room_id)
        soup = BeautifulSoup(requests.get(url).text)

        prices = [int(re.search('\d+', soup('div', {'class': 'text-price'})[0].text).group())] # pcm
        prices_all = re.findall('\d+', soup('div', {'class': 'text-price'})[0].text)
        if len(prices_all) == 4:
            prices = prices_all[0] + prices_all[1]

        station = soup('h2', {'itemprop': 'streetAddress'})[0].text
        phone = False
        if soup('a', {'data-ga-action': 'Call'}):
            phone = soup('a', {'data-ga-action': 'Call'})[0].text

        available_timestamp = datetime.now()
        available = 'Now'
        if len(soup('div',{'id': 'listings-agent'})[0]('div', {'class': 'sidebar sbt'})) > 1:
            available = re.search('\d{1,2} .{3} \d{4}', soup('div',{'id': 'listings-agent'})[0]('div', {'class': 'sidebar sbt'})[1].text.replace('th', '')).group()
            available_timestamp = datetime.strptime(available, "%d %b %Y")

        # images
        images = []
        for img in soup('meta', {'property': 'og:image'}):
            images.append(img.attrs['content'])

        self.rooms[room_id] = {
            'id': room_id,
            'search': search,
            'images': images,
            'station': station,
            'prices': prices,
            'available': available,
            'timestamp': str(available_timestamp),
            'deposits': [],
            'bills': False,
            'rooms': -1,
            'housemates': -1,
            'phone': phone,
            'new': True,
        }


class Gumtree(SearchEngine):
    location = 'http://www.gumtree.com'
    search_endpoint = 'search'
    details_endpoint = 'p/1-bedroom-rent/room/'
    preferences = {
        'sort': 'date',
        'page': '1',
        'distance': 0,
        'search_category': '1-bedroom-rent',
        'search_location': '',
        'max_price': settings.MAX_RENT_PW,
        'max_rent': settings.MAX_RENT_PM
    }

    file_name = 'gumtree.json'

    def get_new_rooms(self):
        for area in self.AREAS:
            print('Searching for {area} flats in Gumtree'.format(area=area))

            # first request
            self.preferences['search_location'] = area.replace(' ', '+')

            for page in range(1, self.preferences['max_range']+1):
                print('Search in page {page} of {area}'.format(page=page, area=area))
                self.preferences['page'] = page
                get_params = '&'.join(['{key}={value}'.format(key=key, value=self.preferences[key]) if key != 'when' and key != 'max_range' else '' for key in self.preferences]).replace('&&', '&').lower()
                url = '{location}/{endpoint}?{params}'.format(location=self.location, endpoint=self.search_endpoint, params=get_params)

                soup = BeautifulSoup(requests.get(url).text)
                for link in soup('a', {'class': 'listing-link'}):
                    room_id = str(link.attrs['href'].rsplit('/', 1)[1])
                    if room_id not in self.rooms:
                        try:
                            self.get_room_info(room_id, area)
                            self.rate_room(room_id)
                        except:
                            continue

            self.save_rooms()

    def get_room_info(self, room_id, search):
        print('Getting {id} flat details'.format(id=room_id))
        # http://www.gumtree.com/p/1-bedroom-rent/room/1097015914
        url = '{location}/{endpoint}{id}'.format(location=self.location, endpoint=self.details_endpoint, id=room_id)
        soup = BeautifulSoup(requests.get(url).text)

        phone = soup('strong', {'itemprop': 'telephone'})[0].text if len(soup('strong', {'itemprop': 'telephone'})) > 0 else None

        raw = {}
        for dl in soup('dl', {'class': 'dl-attribute-list'}):
            for i, dt in enumerate(dl('dt')):
                if dt.text == 'Price frequency':
                    raw['freq'] = dl('dd')[i].text
                elif dt.text == 'Rental amount':
                    raw['price'] = dl('dd')[i].text
                elif dt.text == 'Date available':
                    raw['available'] = dl('dd')[i].text

        available = raw['available']
        available_timestamp = datetime.strptime(available, "%d %b %Y")
        price = int(re.search('\d+', raw['price']).group())
        prices = [price] if 'freq' in raw and raw['freq'] == 'pm' else [price*52/12]

        if not phone:
            description = soup('p', {'class': 'ad-description'})[0].text.replace(' ', '')
            phone = re.search('\d{10,14}', description)
            phone = phone.group() if phone else False

        station = soup('strong', {'class': 'ad-location'})[0].text.replace('\n', '').lower().replace(', london', '')

        # images
        images = []
        if soup('div', {'class': 'filmstrip', 'data-filmstrip': 'channel:adimages'}):
            for img in soup('div', {'class': 'filmstrip', 'data-filmstrip': 'channel:adimages'})[0]('img', {'itemprop': 'image'}):
                images.append(img.attrs['src'] if 'src' in img.attrs else img.attrs['data-lazy'])

        self.rooms[room_id] = {
            'id': room_id,
            'search': search,
            'images': images,
            'station': station,
            'prices': prices,
            'available': available,
            'timestamp': str(available_timestamp),
            'deposits': [],
            'bills': False,
            'rooms': -1,
            'housemates': -1,
            'phone': phone,
            'new': True,
        }


class SpareRoom(SearchEngine):
    # http://iphoneapp.spareroom.co.uk/flatshares/3140871?api_key=502&api_sig=7f2fd77f90f013577d693ee202f61c8e&format=json
    # http://iphoneapp.spareroom.co.uk/flatshares?api_key=502&api_sig=170380c09d6aa765d561e678ec3f390f&format=json&max_per_page=10&max_rent=950&min_rent=403&page=1&per=pcm&room_types=double&rooms_for=males&where=paddington
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
        'where': 'paddington',
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
            results = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
            if settings.VERBOSE:
                print('Parsing page {page}/{total} flats in {area}'.format(page=results['page'], total=results['pages'], area=area))

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                self.get_room_info(room_id, area)
                self.rate_room(room_id)
        except Exception as e:
            print(e)
            return None

        for page in range(1, int(results['pages'])):
            self.preferences['page'] = page + 1
            params = '&'.join(['{key}={value}'.format(key=key, value=self.preferences[key]) for key in self.preferences])
            url = '{location}/{endpoint}?{params}'.format(location=self.api_location, endpoint=self.api_search_endpoint, params=params)
            results = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
            if settings.VERBOSE:
                print('Parsing page {page}/{total} flats in {area}'.format(page=results['page'], total=results['pages'], area=area))

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                self.get_room_info(room_id, area)
                self.rate_room(room_id)

    def get_room_info(self, room_id, search):
        if settings.VERBOSE:
            print('Getting {id} flat details'.format(id=room_id))

        url = '{location}/{endpoint}/{id}?format=json'.format(location=self.api_location, endpoint=self.api_details_endpoint, id=room_id)
        try:
            room = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
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
        station = room['advert_summary']['nearest_station']['station_name'] if 'nearest_station' in room['advert_summary'] else search
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

def main():

    # setup logging configuirations
    LOG_FORMAT = '%(asctime)s - %(engine)s - %(function)s - %(message)s'
    logging.basicConfig(format=LOG_FORMAT)

    max_range = -1
    if '--max-range' in argv:
        try:
            max_range = int(argv[argv.index('--max-range') + 1])
        except (ValueError, IndexError):
            print('Error: no max range given...'); exit(0)

    if '-v' in argv or '--verbose' in argv:
        settings.VERBOSE = True

    if '-d' in argv or '--verbose' in argv:
        settings.DEBUG = True

    if '-f' in argv or '--force' in argv:
        settings.FORCE = True

    if len(argv) < 2 or '--help' in argv or '-h' in argv:
        print('Usage: {command} --spareroom --gumtree --zoopla [ -v | -f ] [ --max-range range ]'.format(command=argv[0]))
        print('    -v : verbose')
        print('    -f : mark all rooms as not seen and re-rates them again')
        print('    -max-range range: max pages to search in each search engine / area')
        exit(0)

    if '--spareroom' in argv:
        spareroom_preferences = {
            'when': settings.WHEN,
            'max_rent': settings.MAX_RENT_PM,
            'rooms_for': settings.FOR,
            'room_types': settings.TYPE,
            'max_per_page': settings.MAX_RESULTS
        }
        spareroom = SpareRoom(spareroom_preferences, settings.AREAS, settings.SPAREROOM_COOKIES)

    if '--gumtree' in argv:
        gumtree_preferences = {
            'when': settings.WHEN,
            'max_rent': settings.MAX_RENT_PM,
            'max_price': settings.MAX_RENT_PW,
            'max_range': 10
        }
        gumtree = Gumtree(gumtree_preferences, settings.AREAS)

    if '--zoopla' in argv:
        zoopla_preferences = {
            'when': settings.WHEN,
            'max_range': 5,
            'price_max': settings.MAX_RENT_PM,
            'max_rent': settings.MAX_RENT_PM,
        }
        zoopla = Zoopla(zoopla_preferences, settings.AREAS)

    if '--rate' in argv:
        if '--spareroom' in argv:
            spareroom.rate()
        if '--gumtree' in argv:
            gumtree.rate()
        if '--zoopla' in argv:
            zoopla.rate()
    elif '--room' in argv:
        room_id = argv[argv.index('--room') + 1]
        if '--spareroom' in argv:
            pprint(spareroom.get_room_info(room_id, room_id))
            spareroom.rate_room(room_id)
            exit(0)
    else:
        if '--spareroom' in argv:
            spareroom.get_new_rooms()
        if '--gumtree' in argv:
            gumtree.get_new_rooms()
        if '--zoopla' in argv:
            zoopla.get_new_rooms()

    if '--spareroom' in argv:
        spareroom.generate_report(fields=settings.FIELDS, pref_ids=settings.SPAREROOM_PREF_IDS, max_range=max_range)
    if '--gumtree' in argv:
        gumtree.generate_report(fields=settings.FIELDS, pref_ids=settings.GUMTREE_PREF_IDS, max_range=max_range)
    if '--zoopla' in argv:
        zoopla.generate_report(fields=settings.FIELDS, pref_ids=settings.ZOOPLA_PREF_IDS, max_range=max_range)

if __name__ == "__main__":
    main()

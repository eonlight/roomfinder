#!/usr/bin/env python
from datetime import datetime
from bs4 import BeautifulSoup
from sys import argv
import settings
import requests
import json
import re

class SearchEngine(object):

    file_name = 'rooms.json'
    preferences = {}

    def __init__(self, preferences={}, areas=None, cookies={}):
        self.AREAS = areas or []
        self.cookies = cookies
        if preferences:
            for key in preferences:
                self.preferences[key] = preferences[key]
        self.rooms = {}
        self.load_rooms(settings.MARK_OLD)

    def load_rooms(self, clean=True):
        try:
            with open(self.file_name, 'r') as f:
                self.rooms = json.loads(f.read())
            if clean:
                self.mark_as_old()
        except:
            self.rooms = {}

    def save_rooms(self):
        with open(self.file_name, 'w') as f:
            f.write(json.dumps(self.rooms))

    def mark_as_old(self):
        for room in self.rooms:
            self.rooms[room]['new'] = False
        self.save_rooms()

    def get_sorted(self):
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

    def generate_report(self, fields=None, pref_ids=[], max_range=-1, when=False):
        name = str(self.__class__.__name__).split(' ')[0]
        html = '<html><head><title>%s Classified Ads</title><link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.1/css/bootstrap.min.css"></head><body>' % name
        html += '<table class="table">'
        html += '<thead><tr>'
        for field in fields:
            html += '<th>%s</th>' % field.replace('_', ' ').capitalize()
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

            if room['new'] or room['id'] in pref_ids:
                htmlclass = 'success' if room['new'] else 'danger' if room['id'] in pref_ids else 'info'
                html += '<tr class="%s">' % htmlclass
                for field in fields:
                    if field == 'id':
                        url = '%s/%s%s' % (self.location, self.details_endpoint, room['id'])
                        html += '<td><a href="%s">%s</td>' % (url, room[field])
                    elif field == 'images':
                        pics = ['<a href="%s"><img src="%s" height="100" width="100"></a>' % (img, img) for img in room['images']]
                        images = ''
                        for i in range(5):
                            images += pics[i] if len(pics) > i else ''
                        html += '<td>%s</td>' % images
                    else:
                        html += '<td>%s</td>' % room[field]
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

        score = 0
        room = self.rooms[key]

        areas = [area.lower() for area in self.AREAS]
        # check station, give better score if first stations
        score += (len(areas) - areas.index(room['station'].lower()))*50 if room['station'].lower() in areas else 0

        # lower price -> better score
        price = min(room['prices'])
        MAX_RENT_PM = self.preferences['max_rent']
        score += 100 if price < MAX_RENT_PM - 150 else 80 if price < MAX_RENT_PM - 100 else 50 if price < MAX_RENT_PM - 50 else 20 if price < MAX_RENT_PM else 0

        # lower deposit -> better score
        # if not deposit information -> 0
        deposit = min(room['deposits']) if len(room['deposits']) > 0 else -1
        score += 20 if deposit != -1 and deposit <= price else 0

        # bills includes - better score
        score += 100 if room['bills'] else 0

        # less housemates - better score
        if room['housemates'] != -1:
            score += 50 if room['housemates'] < 0 else 40 if room['housemates'] < 2 else 30 if room['housemates'] < 4 else 0

        # more images - better score
        # no images -> -100
        score += 7*len(room['images']) if len(room['images']) > 0 else - 100

        # if phone - better score
        score += 100 if room['phone'] else 0

        # the closer (or now) the room is available to desired - better score
        try:
            available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S")
        except:
            available_time = datetime.strptime(room['timestamp'], "%Y-%m-%d %H:%M:%S.%f")

        difference = (self.preferences['when'] - available_time).total_seconds()
        score += 100 if difference > 0 else 80 if difference > -2880 else 50 if difference > -7200 else 0
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
            print 'Searching for %s flats in Zoopla' % area

            # first request
            self.preferences['q'] = area.replace(' ', '+').lower()

            for page in range(1, self.preferences['max_range']+1):
                print 'Search in page %s of %s' % (page, area)
                self.preferences['pn'] = page
                get_params = '&'.join(['%s=%s' % (key, self.preferences[key]) if key != 'when' and key != 'max_range' else '' for key in self.preferences]).replace('&&', '&').lower()
                #url = '%s/%s/london/%s/?%s' % (self.location, self.search_endpoint, self.preferences['q'].replace('+', '-'), get_params)
                url = '%s/%s/%s/?%s' % (self.location, self.search_endpoint, self.preferences['q'].replace('+', '-'), get_params)
                soup = BeautifulSoup(requests.get(url).text)

                if not soup('div', {'class': 'result-count'}):
                    url = '%s/%s/%s/?%s' % (self.location, self.search_endpoint, self.preferences['q'].replace('+', '-'), get_params)
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
        print 'Getting %s flat details' % room_id
        # http://www.zoopla.co.uk/to-rent/details/35664773
        url = '%s/%s%s' % (self.location, self.details_endpoint, room_id)
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
            print 'Searching for %s flats in Gumtree' % area

            # first request
            self.preferences['search_location'] = area.replace(' ', '+')

            for page in range(1, self.preferences['max_range']+1):
                print 'Search in page %s of %s' % (page, area)
                self.preferences['page'] = page
                get_params = '&'.join(['%s=%s' % (key, self.preferences[key]) if key != 'when' and key != 'max_range' else '' for key in self.preferences]).replace('&&', '&').lower()
                url = '%s/%s?%s' % (self.location, self.search_endpoint, get_params)

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
        print 'Getting %s flat details' % room_id
        # http://www.gumtree.com/p/1-bedroom-rent/room/1097015914
        url = '%s/%s%s' % (self.location, self.details_endpoint, room_id)
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
        'where': 'paddington'
    }

    def get_new_rooms(self):
        for area in self.AREAS:
            self.search_rooms_in(area)
            self.save_rooms()

    def search_rooms_in(self, area):
        if settings.VERBOSE:
            print 'Searching for %s flats in SpareRoom' % area

        self.preferences['page'] = 1
        self.preferences['where'] = area.lower()
        params = '&'.join(['%s=%s' % (key, self.preferences[key]) for key in self.preferences])
        url = '%s/%s?%s' % (self.api_location, self.api_search_endpoint, params)

        try:
            results = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
            if settings.VERBOSE:
                print 'Parsing page %s/%s flats in %s' % (results['page'], results['pages'], area)

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                self.get_room_info(room_id, area)
                self.rate_room(room_id)
        except:
            return None

        for page in range(1, int(results['pages'])):
            self.preferences['page'] = page + 1
            params = '&'.join(['%s=%s' % (key, self.preferences[key]) for key in self.preferences])
            url = '%s/%s?%s' % (self.api_location, self.api_search_endpoint, params)
            results = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
            if settings.VERBOSE:
                print 'Parsing page %s/%s flats in %s' % (results['page'], results['pages'], area)

            for room in results['results']:
                room_id = room['advert_id']

                if room_id in self.rooms and not settings.FORCE:
                    continue

                self.get_room_info(room_id, area)
                self.rate_room(room_id)

    def get_room_info(self, room_id, search):
        if settings.VERBOSE:
            print 'Getting %s flat details' % room_id

        url = '%s/%s/%s?format=json' % (self.api_location, self.api_details_endpoint, room_id)
        try:
            room = json.loads(requests.get(url, cookies=self.cookies, headers=self.headers).text)
        except:
            return None

        if 'days_of_wk_available' in room['advert_summary'] and room['advert_summary']['days_of_wk_available'] != '7 days a week':
            if settings.VERBOSE:
                print 'Room availability: %s -> Removing' % room['advert_summary']['days_of_wk_available']
            return None

        phone = room['advert_summary']['tel'] if 'tel' in room['advert_summary'] else room['advert_summary']['tel_formatted'] if 'tel_formatted' in room['advert_summary'] else False
        bills = True if 'bills_inc' in room['advert_summary'] and room['advert_summary']['bills_inc'] == 'Yes' else False
        station = room['advert_summary']['nearest_station']['station_name'] if 'nearest_station' in room['advert_summary'] else search
        images = [img['large_url'] for img in room['advert_summary']['photos']] if 'photos' in room['advert_summary'] else []
        available = room['advert_summary']['available'] if 'available' in room['advert_summary'] else 'Now'

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
            'phone': phone,
            'new': new,
        }

def main():

    max_range = -1
    if '--max-range' in argv:
        try:
            max_range = int(argv[argv.index('--max-range') + 1])
        except (ValueError, IndexError):
            print 'Error: o max range given...'; exit(0)

    if '-v' in argv or '--verbose' in argv:
        settings.VERBOSE = True

    if '-f' in argv or '--force' in argv:
        settings.FORCE = True

    if not '--no-spareroom' in argv:
        spareroom_preferences = {
            'when': settings.WHEN,
            'max_rent': settings.MAX_RENT_PM,
            'rooms_for': settings.FOR,
            'room_types': settings.TYPE,
            'max_per_page': settings.MAX_RESULTS
        }
        spareroom = SpareRoom(spareroom_preferences, settings.AREAS, settings.SPAREROOM_COOKIES)

    if not '--no-gumtree' in argv:
        gumtree_preferences = {
            'when': settings.WHEN,
            'max_rent': settings.MAX_RENT_PM,
            'max_price': settings.MAX_RENT_PW,
            'max_range': 10
        }
        gumtree = Gumtree(gumtree_preferences, settings.AREAS)

    if not '--no-zoopla' in argv:
        zoopla_preferences = {
            'when': settings.WHEN,
            'max_range': 5,
            'price_max': settings.MAX_RENT_PM,
            'max_rent': settings.MAX_RENT_PM,
        }
        zoopla = Zoopla(zoopla_preferences, settings.AREAS)

    if '--rate' in argv:
        if not '--no-spareroom' in argv:
            spareroom.rate()
        if not '--no-gumtree' in argv:
            gumtree.rate()
        if not '--no-zoopla' in argv:
            zoopla.rate()
    else:
        if not '--no-spareroom' in argv:
            spareroom.get_new_rooms()
        if not '--no-gumtree' in argv:
            gumtree.get_new_rooms()
        if not '--no-zoopla' in argv:
            zoopla.get_new_rooms()

    if not '--no-spareroom' in argv:
        spareroom.generate_report(fields=settings.FIELDS, pref_ids=settings.SPAREROOM_PREF_IDS, max_range=max_range)
    if not '--no-gumtree' in argv:
        gumtree.generate_report(fields=settings.FIELDS, pref_ids=settings.GUMTREE_PREF_IDS, max_range=max_range)
    if not '--no-zoopla' in argv:
        zoopla.generate_report(fields=settings.FIELDS, pref_ids=settings.ZOOPLA_PREF_IDS, max_range=max_range)

if __name__ == "__main__":
    main()

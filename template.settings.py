from datetime import datetime
SPAREROOM_COOKIES = {'session_id': '00000000', 'session_key': '000000000000000', 'user_id': '0000000', 'login_id': '000000000'}

#WHEN = datetime.strptime("2015-03-01 00:00:00", "%Y-%m-%d %H:%M:%S")
WHEN = datetime.now()
MIN_AVAILABLE_TIME = datetime.strptime("2014-12-01 00:00:00", "%Y-%m-%d %H:%M:%S")
MAX_RENT_PM = 750
MAX_RENT_PW = 150
FOR = 'males'
TYPE = 'double'

AREAS = ['Paddington', 'Marble Arch', 'Baker Street', 'Oxford Circus', 'Picadilly Circus']

SPAREROOM_PREF_IDS = ['1234567', '1234566', '0000000']
GUMTREE_PREF_IDS = ['1234567', '1234566', '0000000']
ZOOPLA_PREF_IDS = ['1234567', '1234566', '0000000']


FIELDS = ['score', 'id', 'images', 'prices', 'search', 'available', 'phone']

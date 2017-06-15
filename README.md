# RoomFinder

Finds and Scores rooms on Spareroom
(There is also a SearchEngine class that can be extended to adapt to other search engines)

### How to Install
* git clone https://github.com/eonlight/roomfinder.git


#### Running Examples

* Simple fast fetch and score 100 rooms
```
python rooms.py --preferences price,bills,areas,rooms,housemates,images,when --areas "Earl's Court" "Wimbeldon" "Wimbeldon Park" --max-pages 3 --date 2017-06-16 --min-date 2017-06-15 --max-rooms 100 --rent 1100 --fast
```

* Simple full fetch
```
python rooms.py --preferences price,bills,areas,rooms,housemates,images,when --areas "Earl's Court" "Wimbeldon" "Wimbeldon Park" --max-pages 10 --date 2017-06-16 --min-date 2017-06-15 --max-rooms 100 --rent 1100

```

* python rooms.py --help
```
Room Finder v0.2.0 (c) Ruben de Campos
usage: rooms.py [-h] [-n PREFERENCES] -a AREAS [AREAS ...] [-o MAX_RESULTS]
                [-m MAX_ROOMS] [-p MAX_PAGES] [-s SLEEP] [-t RENT] -w DATE -i
                MIN_DATE [-g {males,females}] [-y {single,double}] [-r] [-u]
                [-f] [-d] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -n PREFERENCES, --preferences PREFERENCES
                        Preferences seperated by ,
                        (price,bills,areas,rooms,housemates,images,when)
  -a AREAS [AREAS ...], --areas AREAS [AREAS ...]
                        Prefered areas to search for
  -o MAX_RESULTS, --max-results MAX_RESULTS
                        Number of rooms in the final report (default: 100)
  -m MAX_ROOMS, --max-rooms MAX_ROOMS
                        Number of rooms each page search (default: 100)
  -p MAX_PAGES, --max-pages MAX_PAGES
                        Number of result pages to parse on every area
                        (default: 10)
  -s SLEEP, --sleep SLEEP
                        Sleep between requests (default: 1)
  -t RENT, --rent RENT  Maximum monthly rent (default: 700)
  -w DATE, --date DATE  Ideal date to move into the room (Format: YYYY-MM-DD)
  -i MIN_DATE, --min-date MIN_DATE
                        Minimum date to move into the room (Format: YYYY-MM-
                        DD)
  -g {males,females}, --gender {males,females}
                        Gender accepted rooms (default: males)
  -y {single,double}, --room-type {single,double}
                        Room types to search for (default: double)
  -r, --rate            Re-rates the rooms in the database
  -u, --update          Updates room information when rating the room (use
                        with --rate)
  -f, --fast            Gets only information from the list only (worst
                        ratings)
  -d, --debug           Prints debug messages
  -v, --verbose         Prints verbose messages
```

### Reports

An HTML report will be generated with the name of the SearchEngine used (.html)

### Future and other stuffs

Nothing to do right now, if you have sugestions, please feel free to ask.

Edit and do whatever you want with the code, it helped me find a place to live, maybe it will also help you.

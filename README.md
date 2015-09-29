# RoomFinder

Finds and Scores rooms on Spareroom (removed the support for Gumtree and Zoopla)

### How to Install
* git clone https://github.com/eonlight/roomfinder.git

### How to Configure
* cp template.settings.py settings.py
* edit the required fields

#### Running Examples

* Simple fast fetch and score max 100 rooms
```
python rooms.py --spareroom -v -f --fast --sleep 0.2 --max-rooms 100 --max-pages 3
```

* Simple full fetch
```
python rooms.py --spareroom -v -f --sleep 0.5 --max-rooms 500 --max-pages 10
```

* --help
```
Usage: rooms.py --spareroom [ -v | -f ] [ --max-rooms rooms ] [ --max-pages pages ] [ --sleep sec ] [ --fast ]
    -v : verbose
    -f : mark all rooms as not seen and re-rates them again
    --max-rooms rooms : max rooms in final report
    --max-pages pages : max to search in every area
    --sleep sec : sec to sleep on every request (spareroom's sending 500 responses)
    --fast : does not make a request for every room (worst scores in the algorithm)
    --room room : fetchs the information of a room, re-rates it and displays it in the terminal
```

### Reports

You can choose what fields appear on the report, I found that that these are the ones that most help me.

### Future and other stuffs

Nothing to do right now, if you have sugestions, please feel free to ask.

Edit and do whatever you want with the code, it helped me find a place to live, maybe it will also help you.

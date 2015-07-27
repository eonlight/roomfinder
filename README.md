# RoomFinder

### Short Description
Finds and Scores rooms on Spareroom, Gumtree and Zoopla

### How to:

#### Install
* git clone https://github.com/eonlight/roomfinder.git

#### Configure
* cp template.settings.py settings.py
* edit at least:
    * MAX\_RENT\_PM
    * MAX\_RENT\_PW
    * AREAS
    * FOR

#### Run
* Normal (Fetches new results)
    * python rooms.py
* Rate (Re-rates the fetched rooms and marks them as new)
    * python rooms.py --rate
* Optional Parameter (number of rooms to be included on the report)
    * python rooms.py --max-range 100
* Other Options (only on spare room for now)
    * --force or -f (forces fetch information of already fetched room)
    * --verbose or -v
* Also added the options to add specific search engines from the script
    * --spareroom
    * --gumtree
    * --zoopla

### Reports

You can choose what fields appear on the report, I found that that these are the ones that most help me.

It generates 3 HTML files with the fetched rooms for each website.

### Future and other stuffs

Nothing to do right now, if you have sugestions, please feel free to ask.

Edit and do whatever you want with the code, it helped me find a place to live, maybe it will also help you.

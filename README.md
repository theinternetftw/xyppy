# xyppy - infocom's z-machine in python

### Usage:

* python xyppy.py &lt;FILE\_OR\_URL&gt;

### Features:

* Supports all modern Z-machine games (versions 3, 4, 5, 7, and 8, and zblorb files)
* Quetzal support, so saves are portable to and from many other zmachine apps
* Healthy terminal support on windows and linux
* Run games straight from the web by passing in a URL
* A major focus was "feel." Lines scroll in like it's the 80s.

### "Features":

* Doesn't support mid-input interrupts
* No character font
* Not fast enough to play really unoptimized Inform 7 games (so far I've found 2 offenders)

### TODO:
* More features, implement the last few bits of the spec
* Config file/options: e.g. turn slow scroll mode off (you monster)
* Pack it up a little nicer, e.g. have just one file to run, or py2exe and friends

# xyppy - infocom's z-machine in python

### Usage:

* python xyppy &lt;FILE\_OR\_URL&gt; (in module/dev mode)
* python xyppy.py &lt;FILE\_OR\_URL&gt; (in single file mode)
* run ./build.py to get that handy single-file xyppy.py

### Quick Look:

![Color Support](https://github.com/theinternetftw/xyppy/raw/master/screens/color_support.gif)

More screens can be found on [their dedicated page.](https://github.com/theinternetftw/xyppy/tree/master/screens)

### Features:

* Supports all modern Z-machine games (versions 3, 4, 5, 7, and 8, and zblorb files)
* Everything, including the build system, requires nothing but modern python 2
* Quetzal support, so saves are portable to and from many other zmachine apps
* Healthy color terminal support on windows 10 and linux
* Run games straight from the web by passing in a URL
* A major focus was "feel." Lines scroll in like it's the 80s.

### "Features":

* Doesn't support mid-input interrupts
* No character font
* Not fast enough to play really unoptimized Inform 7 games (so far I've found 2 offenders)

### TODO:
* More features, implement the last few bits of the spec
* Config file/options: e.g. turn slow scroll mode off (you monster)
* Python 2/3 compat?

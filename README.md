# ![Dashboard](static/img/launcher-icon-1x.png) PiFire
## Raspberry Pi Zero W based Smoker Grill Controller using Python 3 and Flask/Gunicorn/nginx
*Also uses Bootstrap 4 (http://getbootstrap.com/) w/jQuery and Popper support*

***Note:*** *This project is continuously evolving, and thus this readme will likely be improved over time, as I find the inspiration to make adjustments.  That being said, I'm sure there will be many errors that I have overlooked or sections that I haven't updated. This project is something I've done for both fun and for self-education.  If you decide to implement this project for yourself, and run into issues/challenges, feel free to submit an issue here on GitHub.  However, I would highly encourage you to dig in and debug the issue as much as you can on your own for the sake of growing your own knowledge.  Also, I have a very demanding day job, a family, and lots of barbeque to make - so please have patience with me.*

***Warning:*** *The creator of this project takes no responsibility for any damage that you may do to your personal property including modifications to your smoker grill if you choose to use this project.  The creator also takes no responsibility for any resulting harm or damages that may come from issues with the hardware or software design.*  ***This project is provided for educational purposes, and should be attempted only by individuals who wish to assume all risks involved.***

***Note: (2020-12-29)*** *Full documentation including hardware and software installation guide are now located [here](https://nebhead.github.io/PiFire/) at the [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/).*

### Introduction
This project was inspired by user dborello and his excellent PiSmoker project (http://engineeredmusings.com/pismoker/ and https://github.com/DBorello/PiSmoker).  I encourage you to check it out and get a rough idea of how this all works.  This particular project was built around a Traeger Texas smoker grill platform, but should work for most older Traeger models (or other brands with similar parts like the older Pit Boss) built with similar parts (fan, auger, and igniter).  I've built the code in a way to be somewhat modular & extensible such that you can replace the grill platform with your own specific platform instead.  Newer Traeger grills with their newer wifi enabled controllers have DC components (instead of the AC Fan / Auger) and aren't covered by this project.  

Just as with the PiSmoker project, I had a few goals in mind.  I also wanted to have tighter temperature controls, wireless control, and plotting of the grill / meat temperatures.  In addition, I wanted to design this project such that original smoker controller could be used if needed.  This way, if I wanted to, I could use my controller as a monitoring device for temperatures instead of controlling the temperature and leave that up to the original controller.  Basically, it was my fallback plan in case my project didn't work out, or if I wanted to do a quick cook on the Traeger without using the fancy GUI.  

### Screenshots & Videos

The dashboard is where most of your key information and controls are at.  This is the screen that greets you when you access the PiFire WebUI on your PC, Mac or Tablet in a browser.

![Dashboard](docs/webui/PiFire-Dashboard-00.png)

For those of us who like to see the data, PiFire allows you to graph and save your cook history.  It's also a great way to monitor your cook in realtime.  

![History](docs/webui/PiFire-History-00.png)

This is what PiFire looks like on your mobile device.

![Mobile Dashboard](docs/webui/PiFire-Mobile-00.jpg)

![Mobile History](docs/webui/PiFire-Mobile-01.jpg)

Example comparison that I did on a real cook of the Traeger controller attempting to hold 275F and the PiFire holding at the same temperature.  The difference is very impressive.  The Traeger swings massively up to 25F over and under the set temperature.  However the PID in from PiSmoker does a great job holding roughly +-7 degrees.  And this is without any extra tuning. 

![Performance](docs/photos/SW-Performance.jpg)

Here's a brief YouTube video giving a basic overview of the PiFire web interfaces.

##### PiFire Demo Video

[![YouTube Demo](http://img.youtube.com/vi/ni4YX5BMBWQ/0.jpg)](http://www.youtube.com/watch?v=ni4YX5BMBWQ)

A shot of the splash screen on the display when booting up.  

![Splash](docs/photos/HW-Splash.jpg)

Typical temperature display for the grill. [Edit: The display has been enhanced to show status for the fan, auger, igniter, mode and notifications]

![Display Temp](docs/photos/HW-Display-Temp.jpg)


## Full Documentation / Hardware and Software Installation

The full documentation has been moved to a GitHub page here: [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/)

### Future Ideas To Be (possibly) Implemented  

In this section, I'm going to keep a running list of ideas for possible upgrades for PiFire in the future.  No guarantees that these will be implemented, but it gives you some idea of what I have planned for the future.  

```
Known Issues
	* Issue where sometimes temperature readings from the ADC fail.  Not sure if this is an i2c bus problem or something else.  Does not effect overall functionality, but can be annoying when looking at the history data.  
	* Issue where if the history page is left open too long the auto-refresh may eventually cause the tab to crash with out of memory errors.  

Ideas for WebUI / App
	Dashboard
		New: Smoke+ Mode (Toggle Fan On/Off) - Experimental feature to increase smoke output by modulating the fan on/off time. This will require some experimentation.

	History
		New: Annotation when mode changes?

	Recipes Page
		New: Custom Programs (or Recipes)
			Event Triggers (Pit Temp, Probe Temp, Timer) w/Notifications

	Debug interface for prototype testing
		New: Prototype Increase Temp, Decrease Temperature (Turn on/off outputs, inputs)

	Settings
		New: Name your Smoker (give your install a unique name)

	Admin
		New: Check for Updates / Pull latest updates from GitHub

	API
		New: API interface to control functions and return JSON data structures for status/history (could be used to develop an Android or iPhone native app) (partially implemented - read status only)

Ideas for Control process
	New: Smart Probe Enable (i.e. enable when plugged in, disable when unplugged)
	New: Physical Buttons / Control Dial for grill control while you are standing in front of it.  

Ideas for display
	New: Display Probe Temperature
	New: Display Not Connected to Internet Symbol if not connected
	New: Display IP Address (or QR Code?) https://pypi.org/project/qrcode/
	New: Larger display with more display capabilities
```

### Updates

* 9/2020 Initial Release
* 12/2020 Moved documentation to [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/)

### Credits

Web Application created by Ben Parmeter, copyright 2020. Check out my other projects on [github](https://github.com/nebhead). If you enjoy this software and feel the need to donate a cup of coffee, a frosty beer or a bottle of wine to the developer you can click [here](https://paypal.me/benparmeter).

Of course, none of this project would be available without the wonderful and amazing folks below.  If I forgot anyone please don't hesitate to let me know.  

* **PiSmoker** - The project that served as the inspiration for this project and where the PID controller is wholesale borrowed from.  Special mention to Dan for providing encouraging feedback from day one of this project.  Many thanks!  Copyright Dan Borello. [engineeredmusings.com](http://engineeredmusings.com/pismoker/) [github](https://github.com/DBorello/PiSmoker)

* **Circliful** - Beautiful Circle Gauges on the dashboard. Extra special mention for Patric for providing great support to me via GitHub.  Copyright Patric Gutersohn & other contributors. [gutersohn.com](http://gutersohn.com/) [github](https://github.com/pguso/js-plugin-circliful)

* **Bootstrap** - WebUI Based on Bootstrap 4.  Bootstrap is released under the MIT license and is copyright 2018 Twitter. [getbootstrap.com](http://getbootstrap.com)

* **JQuery** - Required by Bootstrap. Copyright JS Foundation and other contributors. Released under MIT license. [jquery.org/license](https://jquery.org/license/)

* **Popper** - Required by Bootstrap. Copyright 2016, 2018 FEDERICO ZIVOLO & CONTRIBUTORS. Released under MIT license. [popper.js.org](https://popper.js.org/)

* **Chartjs** - For the fancy charts. Copyright 2018 Chart.js Contributors. Released under MIT license. [chartjs.org](https://chartjs.org/)

* **FontAwesome** - Amazing FREE Icons that I use throughout this project.  Copyright Font Awesome.  Released under the Font Awesome Free License. [fontawesome.com](https://fontawesome.com/) [github.com](https://github.com/FortAwesome/Font-Awesome)

* **Luma OLED** - The OLED display module for Python that I use.  This is not distributed in this project, but deserves a shout-out.  Copyright 2014-2020 Richard Hull and contributors. Released under MIT License. [readthedocs.io](https://luma-oled.readthedocs.io/en/latest/) [github.com](https://github.com/rm-hull/luma.oled)

* **ADS1115 Python Module** - Python module to support the ADS1115 16-Bit ADC. Also not actually distributed with this project, but also deserveds recognition.  Copyright David H Hagan. [pypi.com](https://pypi.org/project/ADS1115/) [github.com](https://github.com/vincentrou/ads1115_lib)

### Licensing

This project is licensed under the MIT license.

```
MIT License

Copyright (c) 2020 Ben Parmeter

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

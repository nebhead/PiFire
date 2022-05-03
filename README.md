# ![Dashboard](static/img/launcher-icon-1x.png) PiFire
## Raspberry Pi Zero W based Smoker Grill Controller

***Note:*** *This project is continuously evolving, and thus this readme will likely be improved over time, as I find the inspiration to make adjustments.  That being said, I'm sure there will be many errors that I have overlooked or sections that I haven't updated. This project is something I've done for both fun and for self-education.  If you decide to implement this project for yourself, and run into issues/challenges, feel free to submit an issue here on GitHub.  However, I would highly encourage you to dig in and debug the issue as much as you can on your own for the sake of growing your own knowledge.  Also, I have a very demanding day job, a family, and lots of barbeque to make - so please have patience with me.*

***Warning:*** *The creator of this project takes no responsibility for any damage that you may do to your personal property including modifications to your smoker grill if you choose to use this project.  The creator also takes no responsibility for any resulting harm or damages that may come from issues with the hardware or software design.*  ***This project is provided for educational purposes, and should be attempted only by individuals who wish to assume all risks involved.***

***Note: (2020-12-29)*** *Full documentation including hardware and software installation guide are now located [here](https://nebhead.github.io/PiFire/) at the [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/).*

### Introduction
This project was inspired by user dborello and his excellent PiSmoker project (http://engineeredmusings.com/pismoker/ and https://github.com/DBorello/PiSmoker).  I encourage you to check it out and get a rough idea of how this all works.  This particular project was built around a Traeger Texas smoker grill platform, but should work for most older Traeger models (or other brands with similar parts like the older Pit Boss) built with similar parts (fan, auger, and igniter).  I've built the code in a way to be somewhat modular & extensible such that you can replace the grill platform with your own specific platform instead.  Newer Traeger grills with their newer wifi enabled controllers have DC components (instead of the AC Fan / Auger) and aren't covered by this project.  

Just as with the PiSmoker project, I had a few goals in mind.  I also wanted to have tighter temperature controls, wireless control, and plotting of the grill / meat temperatures.  In addition, I wanted to design this project such that original smoker controller could be used if needed.  This way, if I wanted to, I could use my controller as a monitoring device for temperatures instead of controlling the temperature and leave that up to the original controller.  Basically, it was my fallback plan in case my project didn't work out, or if I wanted to do a quick cook on the Traeger without using the fancy GUI.  **UPDATE (11/2021)** After spending lots of time with PiFire, I've finally removed the original controller in favor of using PiFire exclusivesly.  However, this doesn't mean that you can't still retain your original controller if you want.  Both modes work fine. 

### Features

* WiFi Enabled Access & Control (WebUI) via computer, phone or tablet
* Multiple Cook Modes
	* _Startup Mode_ (fixed auger on times with igniter on)
	* _Smoke Mode_ (fixed auger on times)
	* _Hold Mode_ (variable auger on times) using PID for higher accuracy
	* _Shutdown Mode_ (auger off, fan on) to burn off pellets after cook is completed
	* _Monitor Mode_ - See temperatures of grill / probes and get notifications if using another controller or if just checking the temperatures any time.  
	* _Manual Mode_ - Control fan, auger and igniter manually.  
* Supports several different OLED and LCD screens
	* SSD1306 OLED Display
	* ST7789 TFT Display
	* ILI9341 TFT Display
* Physical Button Input / Control (depending on the display, three button inputs)
* One (1) Grill Probe and Two (2) Food Probes
	* Tunable probe inputs to allow for many different probe manufacturers
	* Probe tuning tool to help develop probe profiles
* Cook Timer
* Notifications (Grill / Food Probes / Timer)
	* Supports IFTTT, Pushover, and Pushbullet Notification Services 
* Smoke Plus Feature to deliver more smoke during Smoke / Hold modes
* Safety settings to prevent over-temp, startup failure, or firepot flameout (and overload)
* Temperature History for all probes / set points
* Wood Pellet Tracking Manager
* Pellet Level Sensor Support
	* VL53L0X Time of Flight Sensor
	* HCSR04 Ultrasonic Sensor
* Socket IO for Android Application Support _(GitHub User [@weberbox](https://github.com/weberbox) has made a Android client app under development here: [https://github.com/weberbox/PiFire-Android](https://github.com/weberbox/PiFire-Android))_
* ...And much more!  

### Screenshots & Videos

The dashboard is where most of your key information and controls are at.  This is the screen that greets you when you access the PiFire WebUI on your computer, smart phone or tablet in a browser.

![Dashboard](docs/webui/PiFire-Dashboard-00.png)

For those of us who like to see the data, PiFire allows you to graph and save your cook history.  It's also a great way to monitor your cook in realtime.  

![History](docs/webui/PiFire-History-00.png)

PiFire also provides an optional Pellet Manager which can help you track your pellet usage, store ratings, check your pellet level if you have a pellet sensor equipped.  

![Pellet Manager](docs/webui/PiFire-PelletManager-00.png)

This is what PiFire looks like on your mobile device.  And in these screen shots you'll notice that we have dark mode enabled.  This helps for viewing at night, or just if you like the dark theme better.  Personally I think it looks pretty slick.  

![Mobile Dashboard](docs/webui/PiFire-Mobile-00.jpg)

![Mobile History](docs/webui/PiFire-Mobile-01.jpg)

Below is an example comparison that I did on a real cook of the Traeger controller attempting to hold 275F and the PiFire holding at the same temperature.  The difference is very impressive.  The Traeger swings massively up to 25F over and under the set temperature.  However the PID in from PiSmoker does a great job holding roughly +-7 degrees.  And this is without any extra tuning. 

![Performance](docs/photos/SW-Performance.jpg)

Here's a brief YouTube video giving a basic overview of the PiFire web interfaces.

### PiFire Overview Video

I recommend at least taking a peek at the PiFire overview video below.  It covers the basics of operation, settings and control.  

[![YouTube Demo](docs/photos/Video-Link-Image-sm.png)](https://youtu.be/zifl0_sfFBA)

[Link to our channel on YouTube](https://www.youtube.com/channel/UCYYs50U5QvHHhogx_rqs0Yg)

Here is a the latest version 2.0 of the hardware w/TFT screen and hardware buttons in a custom 3D printed enclosure. We've come a long way since v1.0.

![Hardware v2](docs/photos/HW-V2-Display.jpg)

And if you're interested in seeing more builds from other users, we have a discussions thread [here](https://github.com/nebhead/PiFire/discussions/28) where others have posted pictures of their unique builds.  

## Full Documentation / Hardware and Software Installation

The full documentation has been moved to a GitHub page here: [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/)

### Updates

* 9/2020 - Initial Release
* 12/2020 - Moved documentation to [https://nebhead.github.io/PiFire/](https://nebhead.github.io/PiFire/)
* 11/2021 - Many new features, bug fixes, and improvements.  New hardware support etc. which have been in incorporated over the last year, have been mreged from the development branch
* **4/2022** - Release v1.3.1 - Another HUGE release with many new features including an updater, a new configuration wizard, bug fixes, Smart Start feature and much, much more!   

### Credits

Web Application created by Ben Parmeter, copyright 2020, 2021. Check out my other projects on [github](https://github.com/nebhead). If you enjoy this software and feel the need to donate a cup of coffee, a frosty beer or a bottle of wine to the developer you can click [here](https://paypal.me/benparmeter).

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

Copyright (c) 2020 - 2022 Ben Parmeter and Contributors

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

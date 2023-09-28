#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This is a base class for displays, with 
 a modular/flexible display size and layout.
 Other display libraries will inherit this 
 base class and add device specific features.

*****************************************
'''

'''
 Imported Libraries
'''
import time
import logging
import socket
import qrcode 
import io
import os
import pygame
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from common import read_control, write_control, is_raspberry_pi, read_generic_json

'''
Display object class definition 
'''
class DisplayObjects:
    def __init__(self, objectType, objectData, background):
        self.objectType = objectType
        self.objectData = objectData
        self.objectState = {
                'animation_active' : False,
                'animation_start' : False
            }
        self.background = background
        self._init_surface()
        self._init_background()
        self.update_object_data(objectData) 
    
    def _init_background(self):
        ''' saves the slice of background image in PIL to be used for background '''
        crop_region = (self.objectData['position'][0], self.objectData['position'][1], self.objectData['position'][0] + self.objectData['size'][0], self.objectData['position'][1] + self.objectData['size'][0])
        self.objectBG = self.background.crop(crop_region)

    def _init_surface(self):
        ''' pygame surface for output '''
        self.objectSurface = pygame.Surface(self.objectData['size'], pygame.SRCALPHA, 32)  # Foreground Surface

    def _canvas_to_surface(self):
        # Create Temporary Canvas 
        canvas = Image.new("RGBA", self.objectData['size'])
        # Paste Background Chunk onto canvas 
        canvas.paste(self.objectBG, (0,0))
        # Paste Working Canvas onto canvas 
        if self.objectData['glow']:
            glow = self.objectCanvas.filter(ImageFilter.GaussianBlur(radius = 5))
            canvas.paste(glow, (0,0), glow)
        canvas.paste(self.objectCanvas, (0,0), self.objectCanvas)

        # Convert temporary canvas to PyGame surface 
        strFormat = canvas.mode
        size = canvas.size
        raw_str = canvas.tobytes("raw", strFormat)
    
        self.objectSurface = pygame.image.fromstring(raw_str, size, strFormat)

    def update_object_data(self, updated_objectData=None):
        if updated_objectData is not None:
            if updated_objectData['animation_enabled']:
                self.objectState['animation_active'] = True
                self.objectState['animation_start'] = True
                self.objectState['animation_lastData'] = {}
                for key, value in self.objectData.items():
                    self.objectState['animation_lastData'][key] = value
            for key, value in updated_objectData.items():
                self.objectData[key] = value
            '''
            if len(self.objectData['label']) > 5: 
                self.objectState['animation_active'] = True 
                self.objectState['animation_label_position'] = 0
            '''
        if self.objectType == 'gauge':
            if self.objectState['animation_active']:
                self.objectCanvas = self._animate_gauge()
            else:
                self.objectCanvas = self._draw_gauge(self.objectData['size'], self.objectData['fg_color'], self.objectData['bg_color'], 
                                                 self.objectData['temps'], self.objectData['label'], units=self.objectData['units'], 
                                                 max_temp=self.objectData['max_temp'])
            self._define_generic_touch_area()

        if self.objectType == 'gauge_compact':
            self.objectCanvas = self._draw_gauge_compact()
            self._define_generic_touch_area()

        if self.objectType == 'mode_bar': 
            self.objectCanvas = self._draw_mode_bar(self.objectData['size'], self.objectData['text'])
        
        if self.objectType == 'control_panel':
            self.objectCanvas = self._draw_control_panel(self.objectData['size'], self.objectData['button_list'], active=self.objectData['button_active'])
            self._define_control_panel_touch_areas()

        if self.objectType == 'status_icon':
            if self.objectState['animation_active']:
                self.objectCanvas = self._animate_status_icon()
            else:
                self.objectCanvas = self._draw_status_icon()

        if self.objectType == 'menu_icon':
            self.objectCanvas = self._draw_menu_icon(self.objectData['size'])
            self._define_generic_touch_area()

        if self.objectType == 'menu':
            self.objectCanvas = self._draw_menu()

        if self.objectType == 'qrcode':
            self.objectCanvas = self._draw_qrcode()
            self._define_generic_touch_area()

        self._canvas_to_surface()

        return self.objectSurface 

    def get_object_data(self):
        current_objectData = dict(self.objectData)
        return current_objectData

    def get_object_canvas(self):
        return self.objectCanvas

    def get_object_surface(self):
        return self.objectSurface

    def get_object_state(self):
        current_objectState = self.objectState.copy()
        return current_objectState

    def _animate_gauge(self):
        if self.objectState['animation_start']:
            self.objectState['animation_start'] = False  # Run animation start only once 
            self.objectState['animation_temps'] = self.objectData['temps'].copy()
            self.objectState['animation_temps'][0] = self.objectState['animation_lastData']['temps'][0]
            target_temp = self.objectData['temps'][0]
            last_temp = self.objectState['animation_lastData']['temps'][0]
            self.delta = target_temp - last_temp

            if self.delta == 0:
                self.objectState['animation_active'] = False
                self.step_value = 0
            elif self.delta > 0: 
                self.step_value = int(self.delta / 3) if int(self.delta / 3) != 0 else 1
            else: 
                self.step_value = int(self.delta / 3) if int(self.delta / 3) != 0 else -1

        if self.objectState['animation_temps'][0] != self.objectData['temps'][0]:
            self.objectState['animation_temps'][0] += self.step_value

            if self.objectState['animation_temps'][0] <= 0:
                self.objectState['animation_temps'][0] = self.objectData['temps'][0]
                self.objectState['animation_active'] = False #if len(self.objectData['label']) <= 5 else True

            elif (self.delta >= 0) and (abs(self.objectState['animation_temps'][0]) >= abs(self.objectData['temps'][0])):
                self.objectState['animation_temps'][0] = self.objectData['temps'][0]
                self.objectState['animation_active'] = False #if len(self.objectData['label']) <= 5 else True

            elif (self.delta <= 0) and (abs(self.objectState['animation_temps'][0]) <= abs(self.objectData['temps'][0])):
                self.objectState['animation_temps'][0] = self.objectData['temps'][0]
                self.objectState['animation_active'] = False #if len(self.objectData['label']) <= 5 else True
        '''
        if len(self.objectData['label']) > 5:
            self.objectState['animation_label_position'] += 1
            if self.objectState['animation_label_position'] >= 100:
                self.objectState['animation_label_position'] = 0
        '''
                
        return self._draw_gauge(self.objectData['size'], self.objectData['fg_color'], self.objectData['bg_color'], 
                                self.objectState['animation_temps'], self.objectData['label'], units=self.objectData['units'], 
                                max_temp=self.objectData['max_temp'])

    def _draw_gauge(self, size, fg_color, bg_color, temps, label, set_point_color=(0, 200, 255, 255), notify_point_color=(255, 255, 0, 255), units='F', max_temp=600):
        '''
        Draw a gauge and return an Image canvas with that gauge. 

        :param size: The size of the gauge to produce in (width, height) format. 
        :type size: tuple(int, int)
        :param fg_color: The foreground color of the gauge in (r,g,b,a) format.
        :type fg_color: tuple(int, int, int, int)
        :param bg_color: The background color of the gauge in (r,g,b,a) format.
        :type bg_color: tuple(int, int, int, int)
        :param temps: The list of temperatures to display. [current, notify_point, set_point]
        :type temps: list[float, float, float]
        :param set_point_color: The set point color of the gauge in (r,g,b,a) format.  This is used mainly for the primary gauge.
        :type set_point_color: tuple(int, int, int, int)
        :param notify_point_color: The notify point color of the gauge in (r,g,b,a) format.
        :type notify_point_color: tuple(int, int, int, int)
        :param str units: Either 'F' for fahrenheit or 'C' for celcius. 
        :param int max_temp: Maximum temperature to display on the gauge arc. 
        :return: Image object. 
        '''

        output_size = size 

        size = (400,400)

        # Create drawing object
        gauge = Image.new("RGBA", (size[0], size[1]))
        draw = ImageDraw.Draw(gauge)

        # Get coordinates for the gauge arcs 
        coords = (0 + int(size[0] * 0.05), 0 + int(size[1] * 0.05), size[0] - int(size[0] * 0.05), size[1] - int(size[0] * 0.05))

        # Draw Arc for Temperature (Percent)
        start_rad = 135

        # Determine the radian (0-270) for the current temperature   
        temp_rad = 270 * min(temps[0]/max_temp, 1)
        end_rad = start_rad + temp_rad
        
        # Draw Temperature Arc
        draw.arc(coords, start=start_rad, end=end_rad, fill=fg_color, width=30)
        
        # Draw Background Arc 
        draw.arc(coords, start=end_rad, end=45, fill=bg_color, width=30)
        
        # Current Temperature (Large Centered)
        cur_temp = str(temps[0])[:5]
        if len(cur_temp) < 5:
            font_point_size = round(size[1] * 0.3)  # Font size as a ratio of the object size
        else:
            font_point_size = round(size[1] * 0.25)  # Font size as a ratio of the object size
        font = ImageFont.truetype("trebuc.ttf", font_point_size)
        font_bbox = font.getbbox(cur_temp)  # Grab the width of the text
        font_width = font_bbox[2] - font_bbox[0]
        font_height = font_bbox[3] - font_bbox[1]
        label_x = (size[0] // 2) - (font_width // 2)
        label_y = (size[1] // 2) - (font_height // 1.1)
        label_origin = (label_x, label_y)

        draw.text(label_origin, cur_temp, font=font, fill=fg_color)

        # Units Label (Small Centered)
        unit_label = f'{units}°'
        font_point_size = font_point_size = round((size[1] * 0.35) / 4)  # Font size as a ratio of the object size
        font = ImageFont.truetype("trebuc.ttf", font_point_size)
        font_bbox = font.getbbox(units)  # Grab the width of the text
        font_width = font_bbox[2] - font_bbox[0]
        font_height = font_bbox[3] - font_bbox[1]

        label_x = (size[0] // 2) - (font_width // 2)
        label_y = round((size[1] * 0.60)) 
        label_origin = (label_x, label_y)
        draw.text(label_origin, unit_label, font=font, fill=(255, 255, 255))

        # Gauge Label

        # Gauge Label Text
        if len(label) > 7:
            label_displayed = label[0:7]
        else:
            label_displayed = label 
        font_point_size = round((size[1] * 0.55) / 4)  # Font size as a ratio of the object size
        font = ImageFont.truetype("trebuc.ttf", font_point_size)
        font_bbox = font.getbbox(label_displayed)  # Grab the width of the text
        font_width = font_bbox[2] - font_bbox[0]
        font_height = font_bbox[3] - font_bbox[1]
        #print(f'Font bbox= {font_bbox}')

        label_x = (size[0] // 2) - (font_width // 2)
        label_y = round((size[1] * 0.75)) 
        label_origin = (label_x, label_y)
        draw.text(label_origin, label_displayed, font=font, fill=(255, 255, 255))
        # Gauge Label Rectangle
        # rounded_rectangle = (label_x-6, label_y+4, label_x + font_width + 8, label_y + font_height + 16)
        rounded_rectangle = (label_x-8, label_y+(font_bbox[1] - 8), label_x + font_width + 8, label_y + font_bbox[1] + font_height + 8)
        draw.rounded_rectangle(rounded_rectangle, radius=8, outline=(255,255,255), width=3)


        # Set Points Labels 
        if temps[1] > 0 and temps[2] > 0:
            dual_label = 1
        else:
            dual_label = 0

        # Notify Point Label 
        if temps[1] > 0:
            notify_point_label = f'{temps[1]}'
            font_point_size = round((size[1] * (0.5 - (dual_label * 0.15))) / 4)  # Font size as a ratio of the object size
            font = ImageFont.truetype("trebuc.ttf", font_point_size)
            font_bbox = font.getbbox(notify_point_label)  # Grab the width of the text
            font_width = font_bbox[2] - font_bbox[0]
            font_height = font_bbox[3] - font_bbox[1]

            label_x = (size[0] // 2) - (font_width // 2) - (dual_label * ((font_width // 2) + 10))
            label_y = round((size[1] * (0.20 + (dual_label * 0.05)))) 
            label_origin = (label_x, label_y)
            draw.text(label_origin, notify_point_label, font=font, fill=notify_point_color)
            # Notify Point Label Rectangle
            rounded_rectangle = (label_x-8, label_y+(font_bbox[1] - 8), label_x + font_width + 8, label_y + font_bbox[1] + font_height + 8)
            # (label_x-6, label_y+2, label_x + font_width + 6, label_y + font_height + 4)
            draw.rounded_rectangle(rounded_rectangle, radius=8, outline=notify_point_color, width=3)

            # Draw Tic for notify point
            setpoint = 270 * min(temps[1]/max_temp, 1)
            setpoint += start_rad 
            draw.arc(coords, start=setpoint - 1, end=setpoint + 1, fill=notify_point_color, width=30)

        # Set Point Label 
        if temps[2] > 0:
            set_point_label = f'{temps[2]}'
            font_point_size = round((size[1] * (0.5 - (dual_label * 0.15))) / 4)  # Font size as a ratio of the object size
            font = ImageFont.truetype("trebuc.ttf", font_point_size)
            font_bbox = font.getbbox(set_point_label)  # Grab the width of the text
            font_width = font_bbox[2] - font_bbox[0]
            font_height = font_bbox[3] - font_bbox[1]

            label_x = (size[0] // 2) - (font_width // 2) + (dual_label * ((font_width // 2) + 10))
            label_y = round((size[1] * (0.20 + (dual_label * 0.05)))) 
            label_origin = (label_x, label_y)
            draw.text(label_origin, set_point_label, font=font, fill=set_point_color)
            # Set Point Label Rectangle 
            rounded_rectangle = (label_x-8, label_y+(font_bbox[1] - 8), label_x + font_width + 8, label_y + font_bbox[1] + font_height + 8)
            draw.rounded_rectangle(rounded_rectangle, radius=8, outline=set_point_color, width=3)

            # Draw Tic for set point
            setpoint = 270 * min(temps[2]/max_temp, 1)
            setpoint += start_rad 
            draw.arc(coords, start=setpoint - 1, end=setpoint + 1, fill=set_point_color, width=30)

        # Create drawing object
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        gauge = gauge.resize(output_size)
        canvas.paste(gauge, (0, 0), gauge)

        return canvas
    
    def _draw_gauge_compact(self):
        output_size = self.objectData['size']
        size = (400,200)  # Working Canvas Size 

        # Create drawing object
        gauge = Image.new("RGBA", size)
        draw = ImageDraw.Draw(gauge)

        # Gauge Background 
        draw.rounded_rectangle((15, 15, size[0]-15, size[1]-15), radius=20, fill=(255,255,255,100))

        # Draw Gauge Label on Top Portion of Box 
        if len(self.objectData['label']) > 11:
            label_displayed = self.objectData['label'][0:11]
        else:
            label_displayed = self.objectData['label']

        gauge_label = self._draw_text(label_displayed, 'trebuc.ttf', 50, (255,255,255))
        gauge.paste(gauge_label, (40,30), gauge_label)

        # Draw Temperature Value
        current_temp = self._draw_text(self.objectData['temps'][0], 'trebuc.ttf', 100, (255,255,255))
        gauge.paste(current_temp, (40, 75), current_temp)

        # Determine if Displaying Notify Point AND Set Point 
        dual_temp = True if self.objectData['temps'][1] != 0 and self.objectData['temps'][2] != 0 else False 

        if dual_temp:
            font_size = 30
            y_position_offset = 0   
        else: 
            font_size = 50 
            y_position_offset = 15


        # Draw Notify Point Value
        if self.objectData['temps'][1]:
            notify_point_temp = self._draw_text(self.objectData['temps'][1], 'trebuc.ttf', font_size, (255, 255, 0), rect=True)
            gauge.paste(notify_point_temp, (215, 75 + y_position_offset), notify_point_temp)

        # Draw Set Point Value
        if self.objectData['temps'][2]:
            set_point_temp = self._draw_text(self.objectData['temps'][2], 'trebuc.ttf', font_size, (0, 255, 255), rect=True)
            if dual_temp: 
                y_position_offset = notify_point_temp.size[1] + 2
            gauge.paste(set_point_temp, (215, 75 + y_position_offset), set_point_temp)

        # Draw Units
        text = f'{self.objectData["units"]}°'
        units_label = self._draw_text(text, 'Trebuchet_MS_Bold.ttf', 50, (255,255,255))
        #units_label_size = units_label.size() 
        units_label_position = (330, (size[1] // 2))
        gauge.paste(units_label, units_label_position, units_label)

        # Draw Bar
        temp_bar = (40, 160, 360, 170)
        max_temp = self.objectData['max_temp']
        current_temp_adjusted = int((self.objectData['temps'][0] / max_temp) * 320) + 40 if self.objectData['temps'][0] > 0 else 40
        if current_temp_adjusted > 360:
            current_temp_adjusted = 360
        current_temp_bar = (40, 160, current_temp_adjusted, 170)
        draw.rounded_rectangle(temp_bar, radius=10, fill=(0,0,0,200))
        draw.rounded_rectangle(current_temp_bar, radius=10, fill=(255,255,255,255))

        # Draw Notify Point Polygon 
        if self.objectData['temps'][1]:
            notify_temp_adjusted = int((self.objectData['temps'][1] / max_temp) * 320) + 40 if self.objectData['temps'][1] > 0 else 0
            if notify_temp_adjusted > 360:
                notify_temp_adjusted = 360
            triangle_coords = [(notify_temp_adjusted, 168), (notify_temp_adjusted + 10, 150), (notify_temp_adjusted - 10, 150)]
            draw.polygon(triangle_coords, fill=(255,255,0,255))

        # Draw Set Point Polygon 
        if self.objectData['temps'][2]:
            set_temp_adjusted = int((self.objectData['temps'][2] / max_temp) * 320) + 40 if self.objectData['temps'][2] > 0 else 0
            if set_temp_adjusted > 360:
                set_temp_adjusted = 360
            triangle_coords = [(set_temp_adjusted, 168), (set_temp_adjusted + 10, 150), (set_temp_adjusted - 10, 150)]
            draw.polygon(triangle_coords, fill=(0,255,255,255))

        # Create drawing object
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        gauge = gauge.resize(output_size)
        canvas.paste(gauge, (0, 0), gauge)

        return canvas 

    def _draw_text(self, text, font_name, font_point_size, color, rect=False):
        font = ImageFont.truetype(font_name, font_point_size)
        font_bbox = font.getbbox(str(text))  # Grab the width of the text
        font_canvas_size = (font_bbox[2], font_bbox[3])
        font_canvas = Image.new('RGBA', font_canvas_size)
        font_draw = ImageDraw.Draw(font_canvas)
        font_draw.text((0,0), str(text), font=font, fill=color)
        if rect:
            font_canvas = font_canvas.crop(font_canvas.getbbox())
            font_canvas_size = font_canvas.size 
            rect_canvas_size = (font_canvas_size[0] + 16, font_canvas_size[1] + 16)
            rect_canvas = Image.new('RGBA', rect_canvas_size)
            rect_draw = ImageDraw.Draw(rect_canvas)
            rect_draw.rounded_rectangle((0, 0, rect_canvas_size[0], rect_canvas_size[1]), radius=8, outline=color, width=3)
            rect_canvas.paste(font_canvas, (8,8)) 
            return rect_canvas 
        return font_canvas.crop(font_canvas.getbbox())

    def _draw_mode_bar(self, size, text):
        output_size = size 

        size = (400,60)

        # Create drawing object
        mode_bar = Image.new("RGBA", (size[0], size[1]))
        draw = ImageDraw.Draw(mode_bar)

        # Text Rectangle from top
        draw.rounded_rectangle((10, -20, size[0]-10, size[1]-10), radius=8, outline=(255,255,255,255), width=2, fill=(0, 0, 0, 100))

        # Mode Text
        if len(text) > 16:
            label_displayed = text[0:16]
        else:
            label_displayed = text 
        font_point_size = round(size[1] * 0.80)  # Font size as a ratio of the object size
        font = ImageFont.truetype("trebuc.ttf", font_point_size)
        font_bbox = font.getbbox(label_displayed)  # Grab the width of the text
        font_width = font_bbox[2] - font_bbox[0]
        font_height = font_bbox[3] - font_bbox[1]

        label_x = (size[0] // 2) - (font_width // 2)
        label_y = (size[1] // 2) - (font_height // 2) - 18
        label_origin = (label_x, label_y)
        draw.text(label_origin, label_displayed, font=font, fill=(255, 255, 255))

        # Create drawing object
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        mode_bar = mode_bar.resize(output_size)
        canvas.paste(mode_bar, (0, 0), mode_bar)

        return canvas 

    def _create_icon(self, charid, font_size, color):
        # Get font and character size 
        font = ImageFont.truetype("./static/font/FA-Free-Solid.otf", font_size)
        # Create canvas
        font_bbox = font.getbbox(charid)  # Grab the width of the text
        font_width = font_bbox[2]
        font_height = font_bbox[3]

        icon_canvas = Image.new('RGBA', (font_width, font_height))

        # Create drawing object
        draw = ImageDraw.Draw(icon_canvas)
        draw.text((0, 0), charid, font=font, fill=color)
        icon_canvas = icon_canvas.crop(icon_canvas.getbbox())
        return icon_canvas

    def _draw_control_panel(self, size, button_type, active='Stop'):
        output_size = self.objectData['size'] 
        button_type = self.objectData['button_type']
        active = self.objectData['button_active']

        # Establish working size 
        size = (400,100)
        padding = 10

        # Create drawing object
        control_panel = Image.new("RGBA", (size[0], size[1]))
        draw = ImageDraw.Draw(control_panel)

        # Text Rectangle from top
        draw.rounded_rectangle((padding, padding, size[0]-padding, size[1]-padding), radius=8, outline=(255,255,255,255), width=2, fill=(0, 0, 0, 100))

        spacing = int((size[0] - 20) / (len(button_type)))
        # Draw Dividing Lines
        for index in range(1, len(button_type) + 1):
            x_position = (index * spacing) + 10

            # Draw vertical dividing line unless on the last icon space 
            if index < len(button_type):
                coords = (x_position, padding, x_position, size[1]-padding)
                draw.line(coords, fill=(255,255,255,255), width=2)

            # Draw icon
            font_size = 40
            if button_type[index - 1] == active:
                font_color = (255, 255, 255, 255)  # Color for active button
            else: 
                font_color = (255, 255, 255, 200)  # Color for inactive button

            if button_type[index - 1] == 'Startup':
                char_id = '\uf04b'  # FontAwesome Play Icon
            elif button_type[index - 1] == 'Prime':
                char_id = '\uf101'  # FontAwesome Double Arrow Right Icon
            elif button_type[index - 1] == 'Monitor':
                char_id = '\uf530'  # FontAwesome Glasses Icon
            elif button_type[index - 1] == 'Stop':
                char_id = '\uf04d'  # FontAwesome Stop Icon
            elif button_type[index - 1] == 'Smoke':
                char_id = '\uf0c2'  # FontAwesome Cloud Icon
            elif button_type[index - 1] == 'Hold':
                char_id = '\uf05b'  # FontAwesome Crosshairs Icon
            elif button_type[index - 1] == 'Shutdown':
                char_id = '\uf11e'  # FontAwesome Finish Flag Icon
            else:
                char_id = '\uf071'  # FontAwesome Error Triangle Icon 
            icon_canvas = self._create_icon(char_id, font_size, font_color)
            icon_size = icon_canvas.getbbox()
            control_panel.paste(icon_canvas, (x_position - (spacing // 2) - (icon_size[2] // 2), (size[1] // 2) - (icon_size[3] // 2) ), icon_canvas)

        # Create final canvas output object
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        control_panel = control_panel.resize(output_size)
        canvas.paste(control_panel, (0, 0), control_panel)

        return canvas 

    def _define_control_panel_touch_areas(self):
        spacing = int((self.objectData['size'][0]) / (len(self.objectData['button_list'])))
        # Draw Dividing Lines
        self.objectData['touch_areas'] = []
        for index in range(0, len(self.objectData['button_list'])):
            x_left = self.objectData['position'][0] + (index * spacing)
            y_top = self.objectData['position'][1]
            width = spacing
            height = self.objectData['size'][1]
            touch_area = pygame.Rect(x_left, y_top, width, height)
            # Create button rectangle / touch area and append to list
            self.objectData['touch_areas'].append(touch_area) 
            #print(f'Index: {index}  Button: {self.objectData["button_list"][index]}  Touch Area: {touch_area}')

    def _draw_status_icon(self, rotation=0, breath_step=0):
        # Save output size 
        output_size = self.objectData['size']
        type = self.objectData['icon']
        icon_color = self.objectData['active_color'] if self.objectData['active'] else self.objectData['inactive_color'] 
        animation_breath_steps = [1, 0.95, 0.90, 0.80, 0.70, 0.80, 0.90, 0.95, 1]

        # Working Size
        size = (100,100)

        if type == 'Fan':
            char_id = '\uf863'  # Font Awesome Fan Icon

        elif type == 'Auger':
            char_id = '\uf101'  # Font Awesome Right Chevron Arrows Icon

        elif type == 'Igniter':
            char_id = '\uf46a'  # Font Awesome Flame Icon

        elif type == 'SmokePlus':
            char_id = '\uf0c2'  # Font Awesome Icon for Cloud (Smoke)
            text = '\uf067'  # Font Awesome Icon for PLUS

        elif type == 'Notify':
            char_id = '\uf0f3'  # Font Awesome Bell Icon

        elif type == 'Recipe':
            char_id = '\uf46d'  # Font Awesome Clipboard Icon

        elif type == 'Pause':
            char_id = '\uf04c'  # Font Awesome Pause Icon

        else:
            char_id = '\uf071'  # FontAwesome Error Triangle Icon 

        if 'animation_breathe' in self.objectState.keys():
            if self.objectState['animation_breathe'] >= len(animation_breath_steps):
                self.objectState['animation_breathe'] = breath_step = 0

        font_size = int(animation_breath_steps[breath_step] * 80)

        icon = self._create_icon(char_id, font_size, icon_color)

        # Determine Bounding Box of Icon
        icon_size = icon.getbbox()
        
        if rotation:
            icon = icon.rotate(rotation)
        
        icon = icon.crop(icon_size)
        # Upper Left Corner of Centered Icon
        center = ((size[0] // 2) - (icon_size[2] // 2), (size[1] // 2) - (icon_size[3] // 2))
        
        # Create final canvas output object
        canvas = Image.new("RGBA", size)
        canvas.paste(icon, center, icon)

        canvas = canvas.resize(output_size)

        return canvas 

    def _animate_status_icon(self):
        if self.objectState['animation_start']:
            self.objectState['animation_start'] = False  # Run animation start only once 
            self.objectState['animation_rotation'] = 0  # Set initial rotation 
            self.objectState['animation_breathe'] = 0  # Set initial animation breath step 
        
        # Fans Rotate, so increase rotation by 15 degrees on each step
        if self.objectData['icon'] == 'Fan':
            self.objectState['animation_rotation'] += 15
            if self.objectState['animation_rotation'] > 360:
                self.objectState['animation_rotation'] = 0

        # Some Icons Breathe
        if self.objectData['icon'] in ['Auger', 'Igniter', 'Recipe']:
            self.objectState['animation_breathe'] += 1

        return self._draw_status_icon(rotation=self.objectState['animation_rotation'], breath_step=self.objectState['animation_breathe'])


    def _draw_menu_icon(self, size):
        # Save output size 
        output_size = size 

        # Working Size
        size = (40,40)
        if self.objectData['icon'] == 'Hamburger':
            char_id = '\uf0c9'  # Font Awesome Hamburger Menu 
        else: 
            char_id = '\uf00d'  # Font Awesome Times for closing the window

        font_size = 30
        color = (255,255,255,255)

        menu_icon = self._create_icon(char_id, font_size, color)

        menu_icon_size = menu_icon.getbbox()

        center_offset = (size[0] // 2) - (menu_icon_size[2] // 2), (size[1] // 2) - (menu_icon_size[3] // 2)

        # Create final canvas output object
        canvas = Image.new("RGBA", size)
        canvas.paste(menu_icon, center_offset, menu_icon)

        canvas = canvas.resize(output_size)

        return canvas 

    def _define_generic_touch_area(self):
        touch_area = pygame.Rect((self.objectData['position'], self.objectData['size']))
        # Create button rectangle / touch area and append to list
        self.objectData['touch_areas'] = [touch_area] 

    def _scale_touch_area(self, rectangle, screen_size_old, screen_size_new):
        """Scales a rectangle size and position according to the screen size change.

        Args:
            rectangle: A tuple of (x, y, width, height).
            screen_size_old: The old screen size.
            screen_size_new: The new screen size.

        Returns:
            A tuple of (x, y, width, height) of the scaled rectangle.
        """
        x, y, width, height = rectangle
        scaled_width = int(width * (screen_size_new[0] / screen_size_old[0]))
        scaled_height = int(height * (screen_size_new[1] / screen_size_old[1]))
        xlated_x = int(x * (screen_size_new[0] / screen_size_old[0]))
        xlated_y = int(y * (screen_size_new[1] / screen_size_old[1]))
        return (xlated_x, xlated_y, scaled_width, scaled_height)

    def _draw_menu(self):
        size = (600, 400)  # Define working size
        canvas = Image.new("RGBA", size)  # Create canvas output object
        draw = ImageDraw.Draw(canvas)  # Create drawing object 

        # Clear any touch areas that might have been defined before 
        self.objectData['touch_areas'] = []  

        # Rounded rectangle that fills the canvas size
        menu_padding = 10  # Define padding around outside of the menu rectangle 
        draw.rounded_rectangle((menu_padding, menu_padding, size[0]-menu_padding, size[1]-menu_padding), radius=8, outline=(0,0,0,225), fill=(0, 0, 0, 250))

        # Menu Title
        title_text = self.objectData['title_text']
        font_point_size = 35
        font = ImageFont.truetype(self.objectData['font'], font_point_size)
        font_bbox = font.getbbox(title_text)  # Grab the width of the text
        font_width = font_bbox[2]
        font_height = font_bbox[3]
        title_x = (size[0] // 2) - (font_width // 2)
        title_y = 15
        title_origin = (title_x, title_y)
        draw.text(title_origin, title_text, font=font, fill=(255, 255, 255))

        # Index through button_list to create menu items
        #button_height = (size[1] - (padding * 2)) // len(self.objectData['button_list'])
        button_height = 50
        button_padding = 10
        button_offset = 80  # Crude offset for the button spacing 

        for index, button in enumerate(self.objectData['button_list']):
            if '_close' in button and self.objectData['button_text'][index] == 'Close Menu':
                # Close Icon Upper Right
                close_icon = self._create_icon('\uf00d', 34, (255,255,255))
                close_position = (size[0] - (menu_padding * 4), (menu_padding * 2))
                canvas.paste(close_icon, close_position, close_icon)
                close_touch_area = (close_position[0]+self.objectData['position'][0], close_position[1]+self.objectData['position'][1], close_icon.width, close_icon.height)
                close_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
                scaled_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
                self.objectData['touch_areas'].append(pygame.Rect(scaled_touch_area))
            else:
                # Rounded rectangle for each button / menu item
                rect_position = (button_padding + menu_padding, button_offset + ((button_height + button_padding) * index))
                #print(rect_position)
                rect_size = (size[0] - ((menu_padding * 2) + (button_padding * 2)), button_height)
                rect_coords = (rect_position[0], rect_position[1], rect_position[0] + rect_size[0], rect_position[1] + rect_size[1])
                draw.rounded_rectangle(rect_coords, radius=8, outline=(255,255,255,255), fill=(0, 0, 0, 250))

                # Put button text inside rectangle  
                if len(self.objectData['button_text'][index]) > 25:
                    label_displayed = self.objectData['button_text'][index][0:25]
                else:
                    label_displayed = self.objectData['button_text'][index]
                font_point_size = 35
                font = ImageFont.truetype(self.objectData['font'], font_point_size)
                font_bbox = font.getbbox(label_displayed)  # Grab the width of the text
                font_width = font_bbox[2]
                font_height = font_bbox[3]

                label_x = rect_position[0] + (rect_size[0] // 2) - (font_width // 2)
                label_y = rect_position[1] + (rect_size[1] // 2) - (font_height // 2)
                label_origin = (label_x, label_y)
                draw.text(label_origin, label_displayed, font=font, fill=(255, 255, 255))

                # Define touch area for button
                original_touch_area = (rect_position[0] + self.objectData['position'][0], rect_position[1] + self.objectData['position'][1], rect_size[0], rect_size[1])
                scaled_touch_area = self._scale_touch_area(original_touch_area, size, self.objectData['size'])
                touch_area = pygame.Rect(scaled_touch_area)

                # Create button rectangle / touch area and append to list
                self.objectData['touch_areas'].append(touch_area) 

        # Resize for output
        canvas = canvas.resize(self.objectData['size'])

        return canvas

    def _draw_qrcode(self):
        size = (600, 400)  # Define working size
        canvas = Image.new("RGBA", size)  # Create canvas output object
        draw = ImageDraw.Draw(canvas)  # Create drawing object 

        # Rounded rectangle that fills the canvas size
        menu_padding = 10  # Define padding around outside of the menu rectangle 
        draw.rounded_rectangle((menu_padding, menu_padding, size[0]-menu_padding, size[1]-menu_padding), radius=8, outline=(0,0,0,225), fill=(0, 0, 0, 250))

        # Menu Title
        title_text = self.objectData['ip_address']
        font_point_size = 35
        font = ImageFont.truetype(self.objectData['font'], font_point_size)
        font_bbox = font.getbbox(title_text)  # Grab the width of the text
        font_width = font_bbox[2]
        font_height = font_bbox[3]
        title_x = (size[0] // 2) - (font_width // 2)
        title_y = 15
        title_origin = (title_x, title_y)
        draw.text(title_origin, title_text, font=font, fill=(255, 255, 255))

        # Draw QR Code 
        img_qr = qrcode.make(f'http://{self.objectData["ip_address"]}')
        img_qr = img_qr.resize((300,300))
        position = (150, 80)
        canvas.paste(img_qr, position)

        return canvas 


'''
Display base class definition
'''
class DisplayBase:

    def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F', config={}):
        # Init Global Variables and Constants
        self.config = config 

        self.dev_pins = dev_pins
        self.units = units

        self.in_data = None
        self.last_in_data = {}
        self.status_data = None
        self.last_status_data = {}
        self.input_enabled = False

        self.display_active = None 
        self.display_timeout = None
        self.TIMEOUT = 10
        self.command = 'splash'

        self.raspberry_pi = True if is_raspberry_pi() else False
        # Attempt to set the log level of PIL so that it does not pollute the logs
        logging.getLogger('PIL').setLevel(logging.CRITICAL + 1)
        
        # Setup logger
        self.eventLogger = logging.getLogger('control')
        # Init Display Device, Input Device, Assets
        self._init_globals()
        self._init_framework()
        self._init_input()
        self._init_display_device()

    def _init_globals(self):
        # Init constants and variables
        '''
        0 = Zero Degrees Rotation
        90, 1 = 90 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        180, 2 = 180 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        270, 3 = 270 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
        '''
        self.rotation = self.config.get('rotation', 0)
        self.buttonslevel = self.config.get('buttonslevel', 'HIGH')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.ip_address = s.getsockname()[0]
        except:
            self.ip_address = '0.0.0.0'
            self.eventLogger.error('Unable to get IP address of the system.')

    def _init_framework(self):
        '''
        Initialize the dash/home/menu framework 
        '''
        self.display_data = read_generic_json(self.config['display_data_filename'])
        self.WIDTH = self.display_data['metadata']['screen_width']
        self.HEIGHT = self.display_data['metadata']['screen_height']
        if self.display_data['home'] == []:
            self.HOME_ENABLED = False
        else:
            self.HOME_ENABLED = True

        self.display_data['menus']['qrcode']['ip_address'] = self.ip_address

        self._fixup_display_data()

        self._init_assets()

    def _fixup_display_data(self):
        for index, object in enumerate(self.display_data['home']):
            for key in list(object.keys()):
                if key in ['position', 'size', 'fg_color', 'bg_color', 'color', 'active_color', 'inactive_color']:
                    self.display_data['home'][index][key] = tuple(object[key])
        for index, object in enumerate(self.display_data['dash']):
            #print(f'Object Name: {object["name"]}')
            for key in list(object.keys()):
                if key in ['position', 'size', 'fg_color', 'bg_color', 'color', 'active_color', 'inactive_color']:
                    #print(f'[{key}] = {object[key]}')
                    self.display_data['dash'][index][key] = tuple(object[key])
                    #print(f'converted = {tuple(object[key])}')
        for menu, object in self.display_data['menus'].items():
            for key in list(object.keys()):
                if key in ['position', 'size', 'fg_color', 'bg_color', 'color', 'active_color', 'inactive_color']:
                    self.display_data['menus'][menu][key] = tuple(object[key])
        #print(f'Fixed Up: \n{self.display_data["menus"]}')


    def _init_display_device(self):
        '''
        Inheriting classes will override this function to init the display device and start the display thread.
        '''
        pass

    def _init_input(self):
        '''
        Inheriting classes will override this function to setup the inputs.
        '''
        self.input_enabled = False  # If the inheriting class does not implement input, then clear this flag
        self.input_counter = 0
        #self.touch_pos = (0,0)

    def _init_menu(self):
        self.menu_active = False
        self.menu_time = 0
        self.menu_item = ''

        self.menu = {}

        ''' TODO Load Menus from JSON '''

    def _display_loop(self):
        """
        Main display loop
        """
        while True:
            time.sleep(0.1)

    def _zero_dash_data(self):
        self.last_in_data = {}
        self.last_status_data = {}
        self.status_data['mode'] = 'Stop'
        for outpin in self.status_data['outpins']:
            if outpin != 'pwm':
                self.status_data['outpins'][outpin] = False  
        for probe in self.in_data['probe_history']['primary']:
            self.in_data['probe_history']['primary'][probe] = 0
        for probe in self.in_data['probe_history']['food']:
            self.in_data['probe_history']['food'][probe] = 0
        for probe in self.in_data['probe_history']['aux']:
            self.in_data['probe_history']['aux'][probe] = 0
        for probe in self.in_data['probe_history']['tr']:
            self.in_data['probe_history']['tr'][probe] = 0

        self.in_data['primary_setpoint'] = 0

        for probe in self.in_data['notify_targets']:
            self.in_data['notify_targets'][probe] = 0

    '''
    ============== Input Callbacks ============= 
    
    Inheriting classes will override these functions for all inputs.
    '''
    def _enter_callback(self):
        '''
        Inheriting classes will override this function.
        '''
        pass

    def _up_callback(self, held=False):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass
    
    def _down_callback(self, held=False):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass

    '''
    ============== Graphics / Display / Draw Methods ============= 
    '''
    def _init_assets(self): 
        self._init_background()
        self._init_splash()

    def _init_background(self):
        background_image_path = self.display_data['metadata']['dash_background']
        self.background = Image.open(background_image_path)
        self.background = self.background.resize((self.WIDTH, self.HEIGHT))
        ''' Convert image to PyGame surface ''' 
        strFormat = self.background.mode
        size = self.background.size
        raw_str = self.background.tobytes("raw", strFormat)
        self.background_surface = pygame.image.fromstring(raw_str, size, strFormat)

    def _init_splash(self):
        splash_image_path = self.display_data['metadata']['splash_image']
        self.splash = Image.open(splash_image_path)
        self.splash = self.splash.resize((self.WIDTH, self.HEIGHT))
        ''' Convert image to PyGame surface ''' 
        strFormat = self.splash.mode
        size = self.splash.size
        raw_str = self.splash.tobytes("raw", strFormat)
        self.splash = pygame.image.fromstring(raw_str, size, strFormat)
    
    def _display_clear(self):
        '''
        Inheriting classes will override this function to clear the display device.
        '''
        pass

    def _display_canvas(self, canvas):
        '''
        Inheriting classes will override this function to show the canvas on the display device.
        '''
        pass

    def _display_splash(self):
        '''
        Inheriting classes will override this function to display the splash screen.
        '''
        pass

    def _display_background(self):
        '''
        Inheriting classes will override this function to display the stored background image.
        '''
        pass

    '''
     ====================== Input/Event Handling ========================
    '''
    def _event_detect(self):
        """
        Called to detect input events from buttons, encoder, touch, etc.
        This function should be overridden by the inheriting class. 
        """
        pass

    def _command_handler(self):
        '''
        Called to handle commands
        '''
        print(' > Command Handler Called < ')
        if 'monitor' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Monitor'
            }
            write_control(data, origin='display')
            print('Sent Monitor Mode Command!')
        
        if 'startup' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Startup'
            }
            write_control(data, origin='display')
            print('Sent Startup Mode Command!')
            self.display_active = 'dash'
            self.display_init = True

        if 'smoke' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Smoke'
            }
            write_control(data, origin='display')
        
        if 'hold' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Hold',
                'primary_setpoint' : self.command_data['primary_setpoint']    
            }
            write_control(data, origin='display')
            self.display_active = 'dash'
            self.display_init = True
        
        if 'shutdown' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Shutdown',
            }
            write_control(data, origin='display')

        if 'stop' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Stop',
            }
            write_control(data, origin='display')

            self._init_framework()
            self._zero_dash_data()
            self.display_active = 'dash'
            self.display_init = True
            self.display_timeout = time.time() + self.TIMEOUT

        if 'smoke_plus' in self.command:
            data = {
                's_plus' : self.command_data['smoke_plus'],
            }
            write_control(data, origin='display')

        if 'prime' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Prime', 
                'prime_amount' : self.command_data['prime_amount'],
                'next_mode' : self.command_data['next_mode']
            }
            write_control(data, origin='display')
            self.display_active = 'dash'
            self.display_init = True

        if 'next_step' in self.command:
            data = read_control()
            # Check if currently in 'Paused' Status
            if 'triggered' in data['recipe']['step_data'] and 'pause' in data['recipe']['step_data']:
                if data['recipe']['step_data']['triggered'] and data['recipe']['step_data']['pause']:
                    # 'Unpause' Recipe 
                    data['recipe']['step_data']['pause'] = False
                    write_control(data, origin='display')
                else:
                    # User is forcing next step
                    data['updated'] = True
                    write_control(data, origin='display')
            else:
                # User is forcing next step
                data['updated'] = True
                write_control(data, origin='display')

        if 'notify' in self.command:
            ''' Set notification targets for probes/grill '''
            pass

        if 'reboot' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Stop',
            }
            write_control(data, origin='display')
            if self.raspberry_pi:
                os.system('sleep 3 && sudo reboot &')
            else:
                pass
            self.display_active = 'dash'
            self.display_init = True

        if 'poweroff' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Stop',
            }
            write_control(data, origin='display')
            if self.raspberry_pi:
                os.system('sleep 3 && sudo shutdown -h now &')
            else:
                pass
            self.display_active = 'dash'
            self.display_init = True

        if 'restart' in self.command:
            data = {
                'updated' : True,
                'mode' : 'Stop',
            }
            write_control(data, origin='display')
            if self.raspberry_pi:
                os.system('sleep 3 && sudo service supervisor restart &')
            else:
                pass 
            self.display_active = 'dash'
            self.display_init = True

        self.command = None 


    '''
    ================ Externally Available Methods ================
    '''

    def display_status(self, in_data, status_data):
        """
        - Updates the current data for the display loop, if in a work mode
        """
        self.units = status_data['units']

        ''' Wake the display to the dash if it's currently off '''
        if self.display_active == None:
            self.display_active = 'dash'
            self.display_init = True 
        
        self.display_timeout = None
        
        if self.in_data is None:
            self.last_in_data = {}
        
        self.in_data = in_data 

        if self.status_data is None:
            self.last_status_data = {}

        self.status_data = status_data 

    def display_splash(self):
        """
        - Calls Splash Screen
        """
        self.display_command = 'splash'

    def clear_display(self):
        """
        - Clear display and turn off backlight
        """
        self.display_command = 'clear'

    def display_text(self, text):
        """
        - Display some text
        """
        self.display_command = 'text'
        self.display_data = text

    def display_network(self):
        """
        - Display Network IP QR Code
        """
        self.display_command = 'network'

'''
 Imported Libraries
'''
import qrcode 
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pygame import Rect  # Needed for touch support 

'''
Display Flex Object Class Definition 
'''
class FlexObject:
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

        if self.objectType == 'input_number':
            self._process_number_input()

            if self.objectState['animation_active']:
                self.objectCanvas = self._animate_input_number()
            else:
                self.objectCanvas = self._draw_input_number()
        
        if self.objectType == 'timer':
            self.objectCanvas = self._draw_timer()

        if self.objectType == 'alert':
            self.objectCanvas = self._draw_alert()

        if self.objectType == 'p_mode_control':
            self.objectCanvas = self._draw_pmode_status()
            self._define_generic_touch_area()
        
        if self.objectType == 'splus_control':
            self.objectCanvas = self._draw_splus_status()
            self._define_generic_touch_area()

        if self.objectType == 'hopper_status':
            self.objectCanvas = self._draw_hopper_status()
            self._define_generic_touch_area()

        return self.objectCanvas

    def get_object_data(self):
        current_objectData = dict(self.objectData)
        return current_objectData

    def get_object_canvas(self):
        return self.objectCanvas

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

    def _draw_text(self, text, font_name, font_point_size, color, rect=False, bg_fill=None):
        font = ImageFont.truetype(font_name, font_point_size)
        font_bbox = font.getbbox(str(text))  # Grab the width of the text
        font_canvas_size = (font_bbox[2], font_bbox[3])
        font_canvas = Image.new('RGBA', font_canvas_size)
        font_draw = ImageDraw.Draw(font_canvas)
        font_draw.text((0,0), str(text), font=font, fill=color)
        font_canvas = font_canvas.crop(font_canvas.getbbox())
        if rect:
            font_canvas_size = font_canvas.size 
            rect_canvas_size = (font_canvas_size[0] + 16, font_canvas_size[1] + 16)
            rect_canvas = Image.new('RGBA', rect_canvas_size)
            if bg_fill is not None:
                rect_canvas.paste(bg_fill, (0,0) + rect_canvas.size)
            rect_draw = ImageDraw.Draw(rect_canvas)
            rect_draw.rounded_rectangle((0, 0, rect_canvas_size[0], rect_canvas_size[1]), radius=8, outline=color, width=3)
            rect_canvas.paste(font_canvas, (8,8), font_canvas) 
            return rect_canvas 
        elif bg_fill is not None:
            output_canvas = Image.new('RGBA', font_canvas.size)
            output_canvas.paste(bg_fill, (0,0) + font_canvas.size)
            output_canvas.paste(font_canvas, (0,0), font_canvas)
            return output_canvas
        else:
            return font_canvas

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

    def _create_icon(self, charid, font_size, color, bg_fill=None):
        # Get font and character size 
        font = ImageFont.truetype("./static/font/FA-Free-Solid.otf", font_size)
        # Create canvas
        font_bbox = font.getbbox(charid)  # Grab the width of the text
        font_width = font_bbox[2]
        font_height = font_bbox[3]

        icon_canvas = Image.new('RGBA', (font_width, font_height))
        if bg_fill is not None:
            icon_canvas.paste(bg_fill, (0,0) + icon_canvas.size)

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
            elif button_type[index - 1] == 'Next':
                char_id = '\uf051'  # FontAwesome Step Icon
            elif button_type[index - 1] == 'None':
                char_id = '\uf068'  # FontAwesome Minus Icon
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
            touch_area = Rect(x_left, y_top, width, height)
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
        touch_area = Rect((self.objectData['position'], self.objectData['size']))
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

    def _transform_touch_area(self, touch_area, origin):
        """ Transforms the touch area to the correct place on the screen. """
        return (touch_area[0] + origin[0], touch_area[1] + origin[1], touch_area[2], touch_area[3])
    
    def _draw_menu(self):
        size = (600, 400)  # Define working size
        canvas = Image.new("RGBA", size)  # Create canvas output object
        draw = ImageDraw.Draw(canvas)  # Create drawing object 
        fg_color = self.objectData['color']

        # Clear any touch areas that might have been defined before 
        self.objectData['touch_areas'] = []  

        # Rounded rectangle that fills the canvas size
        menu_padding = 10  # Define padding around outside of the menu rectangle 
        draw.rounded_rectangle((menu_padding, menu_padding, size[0]-menu_padding, size[1]-menu_padding), radius=8, outline=(0,0,0,225), fill=(0, 0, 0, 250))

        # Menu Title
        title = self._draw_text(self.objectData['title_text'], 'trebuc.ttf', 35, fg_color)
        title_position = ((size[0] // 2) - (title.width // 2), 20)
        canvas.paste(title, title_position, title)
       
        # Index through button_list to create menu items

        number_of_buttons = len(self.objectData['button_list'])

        two_column_mode = True if number_of_buttons > 5 else False 

        if two_column_mode:
            button_height = 50
            button_padding = 10
            button_width = size[0] // 2 - menu_padding - (button_padding * 2)
            column = 0
            button_area_position = (menu_padding + button_padding, 80)
            button_area_size = (size[0] - (menu_padding * 2) - (button_padding * 2), size[1] - button_area_position[1] - menu_padding - button_padding)
            row_height = 60
        else: 
            button_height = 50
            button_padding = 10
            button_width = size[0] - (menu_padding * 2) - (button_padding * 2)
            button_area_position = (menu_padding + button_padding, 60)
            button_area_size = (size[0] - (menu_padding * 2) - (button_padding * 2), size[1] - button_area_position[1] - menu_padding - button_padding)
            row_height = button_area_size[1] // (number_of_buttons - 1)

        button_count = 0
        row = 0

        for index, button in enumerate(self.objectData['button_list']):
            if '_close' in button and self.objectData['button_text'][index] == 'Close Menu':
                # Close Icon Upper Right
                close_icon = self._create_icon('\uf00d', 34, (255,255,255))
                close_position = (size[0] - (menu_padding * 4), (menu_padding * 2))
                canvas.paste(close_icon, close_position, close_icon)
                close_touch_area = (close_position[0]+self.objectData['position'][0], close_position[1]+self.objectData['position'][1], close_icon.width, close_icon.height)
                close_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
                scaled_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
                self.objectData['touch_areas'].append(Rect(scaled_touch_area))
            else:
                if button_count > 10:
                    break   # Stop if at 11 items

                if two_column_mode:
                    if button_count in [0, 2, 4, 6, 8, 10]:
                        rect_position = (button_area_position[0], button_area_position[1] + (row * row_height))
                    else:
                        rect_position = (button_area_position[0] + button_width + (button_padding * 2), button_area_position[1] + (row * row_height))
                        row += 1
                else:
                    rect_position = (button_area_position[0], button_area_position[1] + (button_count * row_height) + ((row_height // 2) - (button_height // 2)))

                rect_size = (button_width, button_height)
                rect_coords = (rect_position[0], rect_position[1], rect_position[0] + rect_size[0], rect_position[1] + rect_size[1])

                draw.rounded_rectangle(rect_coords, radius=8, outline=(255,255,255,255), fill=(0, 0, 0, 250))

                # Put button text inside rectangle  
                if len(self.objectData['button_text'][index]) > 25:
                    label_displayed = self.objectData['button_text'][index][0:25]
                else:
                    label_displayed = self.objectData['button_text'][index]

                label = self._draw_text(label_displayed, self.objectData['font'], 35, fg_color)
                label_x = rect_position[0] + (rect_size[0] // 2) - (label.width // 2)
                label_y = rect_position[1] + (rect_size[1] // 2) - (label.height // 2)
                label_position = (label_x, label_y)
                canvas.paste(label, label_position, label)

                # Define touch area for button
                button_touch_area = rect_position + rect_size
                scaled_touch_area = self._scale_touch_area(button_touch_area, size, self.objectData['size'])
                transformed_touch_area = self._transform_touch_area(scaled_touch_area, self.objectData['position'])
                touch_area = Rect(transformed_touch_area)

                # Create button rectangle / touch area and append to list
                self.objectData['touch_areas'].append(touch_area) 

                button_count += 1 

        # Resize for output
        canvas = canvas.resize(self.objectData['size'])

        return canvas

    def _draw_qrcode(self):
        size = (600, 400)  # Define working size
        canvas = Image.new("RGBA", size)  # Create canvas output object
        draw = ImageDraw.Draw(canvas)  # Create drawing object
        fg_color = self.objectData['color']

        # Rounded rectangle that fills the canvas size
        menu_padding = 10  # Define padding around outside of the menu rectangle 
        draw.rounded_rectangle((menu_padding, menu_padding, size[0]-menu_padding, size[1]-menu_padding), radius=8, outline=(0,0,0,225), fill=(0, 0, 0, 250))

        # Draw Close Icon in upper right 
        close_icon = self._create_icon('\uf00d', 34, (255,255,255))
        close_position = (size[0] - (menu_padding * 4), (menu_padding * 2))
        canvas.paste(close_icon, close_position, close_icon)

        # Menu Title
        title = self._draw_text(self.objectData['ip_address'], 'trebuc.ttf', 35, fg_color)
        title_position = ((size[0] // 2) - (title.width // 2), 20)
        canvas.paste(title, title_position, title)

        # Draw QR Code 
        img_qr = qrcode.make(f'http://{self.objectData["ip_address"]}')
        img_qr = img_qr.resize((300,300))
        position = (150, 60)
        canvas.paste(img_qr, position)

        return canvas 

    def _draw_input_number(self):
        size = (600, 400)  # Define working size
        canvas = Image.new("RGBA", size)  # Create canvas output object
        draw = ImageDraw.Draw(canvas)  # Create drawing object 
        button_pushed = self.objectState.get('animation_input', '')
        self.objectData['touch_areas'] = []
        self.objectData['button_list'] = []
        
        # Rounded rectangle that fills the canvas size
        menu_padding = 10  # Define padding around outside of the menu rectangle 
        draw.rounded_rectangle((menu_padding, menu_padding, size[0]-menu_padding, size[1]-menu_padding), radius=8, outline=(0,0,0,225), fill=(0, 0, 0, 250))

        # Close Icon Upper Right
        close_icon = self._create_icon('\uf00d', 34, (255,255,255))
        close_position = (size[0] - (menu_padding * 4), (menu_padding * 2))
        canvas.paste(close_icon, close_position, close_icon)
        close_touch_area = (close_position[0]+self.objectData['position'][0], close_position[1]+self.objectData['position'][1], close_icon.width, close_icon.height)
        close_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
        scaled_touch_area = self._scale_touch_area(close_touch_area, size, self.objectData['size'])
        self.objectData['touch_areas'].append(Rect(scaled_touch_area))
        self.objectData['button_list'].append('menu_close')

        # Menu Title
        title = self._draw_text(self.objectData['title_text'], self.objectData['font'], 35, self.objectData['color'], rect=False, bg_fill=(0,0,0,250))
        title_x = (size[0] // 2) - (title.width // 2)
        title_y = 15
        canvas.paste(title, (title_x, title_y))

        # Number Display 
        number_entry_position = (60, 75)
        number_entry_size = (240, 100)
        number_entry_coords = number_entry_position + (number_entry_position[0] + number_entry_size[0], number_entry_position[1] + number_entry_size[1])
        number_entry_bg_color = (50,50,50)
        draw.rounded_rectangle(number_entry_coords, radius=8, fill=number_entry_bg_color)
        number_digits = self._draw_text(self.objectData['data']['value'], self.objectData['font'], 80, self.objectData['color'], bg_fill=number_entry_bg_color)
        number_digits_position = (number_entry_position[0] + ((number_entry_size[0] // 2) - (number_digits.width // 2)), number_entry_position[1] + (number_entry_size[1] // 2) - (number_digits.height // 2)) 
        canvas.paste(number_digits, number_digits_position)

        # Up Arrow
        if button_pushed == 'up':
            bg_fill = (255,255,255,255)
            fg_fill = (0,0,0,255)
        else:
            bg_fill = (0,0,0,255)
            fg_fill = self.objectData['color']
        button_position = (60, 195)
        button_size = (110, 70)
        button_coords = button_position + (button_position[0] + button_size[0], button_position[1] + button_size[1])
        draw.rounded_rectangle(button_coords, radius=8, outline=fg_fill, fill=bg_fill, width=3)
        button_icon = self._create_icon('\uf077', 35, fg_fill, bg_fill=bg_fill)
        button_icon_position = (button_position[0] + ((button_size[0] // 2) - (button_icon.width // 2)), button_position[1] + (button_size[1] // 2) - (button_icon.height // 2))
        canvas.paste(button_icon, button_icon_position)
        # Scale and Store Touch Area
        button_touch_area = button_position + button_size
        scaled_touch_area = self._scale_touch_area(button_touch_area, size, self.objectData['size'])
        transform_touch_area = self._transform_touch_area(scaled_touch_area, self.objectData['position'])
        self.objectData['touch_areas'].append(Rect(transform_touch_area))
        self.objectData['button_list'].append('button_up')

        # Down Arrow
        if button_pushed == 'down':
            bg_fill = (255,255,255,255)
            fg_fill = (0,0,0,255)
        else:
            bg_fill = (0,0,0,255)
            fg_fill = self.objectData['color']
        button_position = (190, 195)
        button_size = (110, 70)
        button_coords = button_position + (button_position[0] + button_size[0], button_position[1] + button_size[1])
        draw.rounded_rectangle(button_coords, radius=8, outline=fg_fill, fill=bg_fill, width=3)
        button_icon = self._create_icon('\uf078', 35, fg_fill, bg_fill=bg_fill)
        button_icon_position = (button_position[0] + ((button_size[0] // 2) - (button_icon.width // 2)), button_position[1] + (button_size[1] // 2) - (button_icon.height // 2))
        canvas.paste(button_icon, button_icon_position)
        # Scale and Store Touch Area
        button_touch_area = button_position + button_size
        scaled_touch_area = self._scale_touch_area(button_touch_area, size, self.objectData['size'])
        transform_touch_area = self._transform_touch_area(scaled_touch_area, self.objectData['position'])
        self.objectData['touch_areas'].append(Rect(transform_touch_area))
        self.objectData['button_list'].append('button_down')

        # Enter Button
        button_position = (60, 290)
        button_size = (240, 80)
        button_coords = button_position + (button_position[0] + button_size[0], button_position[1] + button_size[1])
        draw.rounded_rectangle(button_coords, radius=8, outline=self.objectData['color'], width=3)
        button_text = self._draw_text('ENTER', self.objectData['font'], 60, self.objectData['color'], bg_fill=(0,0,0))
        button_text_position = (button_position[0] + ((button_size[0] // 2) - (button_text.width // 2)), button_position[1] + (button_size[1] // 2) - (button_text.height // 2))
        canvas.paste(button_text, button_text_position)
        # Scale and Store Touch Area
        button_touch_area = button_position + button_size
        scaled_touch_area = self._scale_touch_area(button_touch_area, size, self.objectData['size'])
        transform_touch_area = self._transform_touch_area(scaled_touch_area, self.objectData['position'])
        self.objectData['touch_areas'].append(Rect(transform_touch_area))
        self.objectData['button_list'].append(self.objectData['command'])

        # Draw Number Pad
        pad_position = (250, 75)
        button_size = (70,70)
        button_padding = 5
        button_position = [pad_position[0] - button_size[0] - button_padding, pad_position[1] - button_size[0] - button_padding]

        pad_button_list = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['DEL', '0', '.']]
        for row in pad_button_list:
            button_position[1] += button_size[1] + button_padding
            button_position[0] = pad_position[0]
            for col in row:
                if button_pushed == col:
                    bg_fill = (255,255,255,255)
                    fg_fill = (0,0,0,255)
                else:
                    bg_fill = (0,0,0,255)
                    fg_fill = self.objectData['color']
                button_position[0] += button_size[0] + button_padding
                if col == 'DEL':
                    button_text = self._create_icon('\uf55a', 35, fg_fill, bg_fill=bg_fill)
                else:
                    button_text = self._draw_text(col, self.objectData['font'], 35, fg_fill, rect=False, bg_fill=bg_fill)
                # Draw Rectangle
                button_coords = tuple(button_position) + (button_position[0] + button_size[0], button_position[1] + button_size[1])
                draw.rounded_rectangle(button_coords, radius=8, outline=fg_fill, fill=bg_fill, width=3)
                text_position = (button_position[0] + (button_size[0] // 2) - (button_text.width // 2), button_position[1] + (button_size[1] // 2) - (button_text.height // 2))
                canvas.paste(button_text, text_position)
                button_touch_area = (button_position[0]+self.objectData['position'][0], button_position[1]+self.objectData['position'][1]) + button_size
                scaled_touch_area = self._scale_touch_area(button_touch_area, size, self.objectData['size'])
                self.objectData['touch_areas'].append(Rect(scaled_touch_area))
                self.objectData['button_list'].append(f'button_{col}')
        
        return canvas 

    def _animate_input_number(self):
        if self.objectState['animation_start']:
            self.objectState['animation_start'] = False  # Run animation start only once
            self.objectState['animation_counter'] = 0  # Setup a counter for number of frames to produce
            self.objectState['animation_input'] = self.objectData['data']['input']  # Save input from user
            self.objectData['data']['input'] = ''  # Clear user input

        if self.objectState['animation_counter'] > 1:
            self.objectState['animation_active'] = False  # Disable animation after one frame
            self.objectState['animation_input'] = ''

        canvas = self._draw_input_number()

        self.objectState['animation_counter'] += 1  # Increment the frame counter 

        return canvas 

    def _process_number_input(self):
        
        if self.objectData['data']['input'] != '':
            ''' Check first for up / down input '''
            if self.objectData['data']['input'] == 'up':
                self.objectData['data']['value'] += self.objectData['step']

            if self.objectData['data']['input'] == 'down':
                self.objectData['data']['value'] -= self.objectData['step']
                if self.objectData['data']['value'] < 0:
                    self.objectData['data']['value'] = 0

            ''' Convert value to list of characters '''
            temp_string = str(self.objectData['data']['value'])
            self.objectState['value'] = [char for char in temp_string]

            if self.objectData['data']['input'] == 'DEL':

                if len(self.objectState['value']) > 1:
                    ''' If a float, delete back to the decimal value '''
                    if '.' in self.objectState['value'] and self.objectState['value'][-2] == '.':
                        self.objectState['value'].pop()
                        self.objectState['value'].pop()
                    else:
                        self.objectState['value'].pop()
                else:
                    self.objectState['value'] = ['0']
            
            if '.' in self.objectState['value'] and self.objectData['data']['input'] == '.':
                pass
            elif self.objectData['data']['input'] in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '.']:

                if len(self.objectState['value']) > 5:
                    pass 
                if '.' in self.objectState['value']:
                    self.objectState['value'].pop()
                    self.objectState['value'].append(self.objectData['data']['input'])
                elif len(self.objectState['value']) == 3 and self.objectData['data']['input'] == '.':
                    self.objectState['value'].append(self.objectData['data']['input'])
                elif len(self.objectState['value']) < 3:
                    self.objectState['value'].append(self.objectData['data']['input'])

            ''' Combine list of characters back to string and then back to a float or int '''    
            temp_string = "".join([str(i) for i in self.objectState['value']])

            if '.' in temp_string:
                self.objectData['data']['value'] = float(temp_string)
            else:
                self.objectData['data']['value'] = int(temp_string)

    def _draw_timer(self):
        output_size = self.objectData['size']
        size = (400,200)  # Working Canvas Size 
        fg_color = self.objectData['color']

        # Create drawing object
        canvas = Image.new("RGBA", size)
        draw = ImageDraw.Draw(canvas)

        # If not in use, display empty box
        if self.objectData['data']['seconds'] > 0:
            # Timer Background 
            draw.rounded_rectangle((15, 15, size[0]-15, size[1]-15), radius=20, fill=(255,255,255,100))

            # Draw Stopwatch Icon 
            timer_icon = self._create_icon('\uf2f2', 35, fg_color)
            canvas.paste(timer_icon, (40,30), timer_icon)

            # Draw Timer Label on Top Portion of Box 
            if len(self.objectData['label']) > 11:
                label_displayed = self.objectData['label'][0:11]
            else:
                label_displayed = self.objectData['label']

            timer_label = self._draw_text(label_displayed, 'trebuc.ttf', 50, fg_color)
            canvas.paste(timer_label, (80,30), timer_label)

            # Draw Seconds Remaining
            seconds_remaining = f'{self.objectData["data"]["seconds"]}s'
            timer_text = self._draw_text(seconds_remaining, 'trebuc.ttf', 100, fg_color)
            timer_text_position = ((size[0] // 2) - (timer_text.width // 2), 90)
            canvas.paste(timer_text, timer_text_position, timer_text)

        # Resize and Prepare Output 
        resized = canvas.resize(output_size)
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))

        canvas.paste(resized, (0, 0), resized)

        return canvas 

    def _draw_alert(self):
        output_size = self.objectData['size']
        size = (400,200)  # Working Canvas Size 
        fg_color = self.objectData['color']

        # Create canvas & drawing object
        canvas = Image.new("RGBA", size)
        draw = ImageDraw.Draw(canvas)

        if self.objectData['active']:
            # Draw Rectangle
            draw.rounded_rectangle((15, 15, size[0]-15, size[1]-15), radius=20, outline=fg_color, width=6)
            
            # Draw Alert Icon
            fg_color_alpha = list(fg_color)
            fg_color_alpha[3] = 125
            fg_color_alpha = tuple(fg_color_alpha)

            alert_icon = self._create_icon('\uf071', 100, fg_color_alpha)
            alert_icon_pos = ((size[0] // 2) - (alert_icon.width // 2), (size[1] // 2) - (alert_icon.height // 2))
            canvas.paste(alert_icon, alert_icon_pos)

            text_lines = self.objectData['data']['text']
            num_lines = len(text_lines)
            padding = 50
            line_height = (size[1] - padding) // num_lines
            font_size = int(line_height * 0.8)
            for index, text in enumerate(text_lines):
                if len(text) > 11:
                    text_displayed = text[0:11]
                else:
                    text_displayed = text

                text_line = self._draw_text(text_displayed, 'trebuc.ttf', font_size, fg_color)
                text_pos = ((size[0] // 2) - (text_line.width // 2), (padding // 2) + (line_height * index) + (line_height // 2) - (text_line.height // 2))
                canvas.paste(text_line, text_pos, text_line)

        # Resize and Prepare Output 
        resized = canvas.resize(output_size)
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        canvas.paste(resized, (0, 0), resized)

        return canvas 

    def _draw_pmode_status(self):
        output_size = self.objectData['size']
        size = (400,200)  # Working Canvas Size 
        fg_color = self.objectData['color']

        # Create canvas & drawing object
        canvas = Image.new("RGBA", size)

        if self.objectData['active']:
            draw = ImageDraw.Draw(canvas)
            # Draw Rectangle
            draw.rounded_rectangle((15, 15, size[0]-15, size[1]-15), radius=20, outline=fg_color, width=6)
            
            # Draw PMode Icon
            fg_color_alpha = list(fg_color)
            fg_color_alpha[3] = 125
            fg_color_alpha = tuple(fg_color_alpha)

            pmode_icon = self._create_icon('\uf83e', 100, fg_color_alpha)
            pmode_icon_pos = ((size[0] // 2) - (pmode_icon.width // 2), (size[1] // 2) - 25)
            canvas.paste(pmode_icon, pmode_icon_pos)

            # Draw Title
            text_displayed = self.objectData['label']
            font_size = 40
            text_line = self._draw_text(text_displayed, 'trebuc.ttf', font_size, fg_color)
            text_pos = ((size[0] // 2) - (text_line.width // 2), 25)
            canvas.paste(text_line, text_pos, text_line)

            # Draw PMode Number 
            text_displayed = self.objectData['data']['pmode']
            font_size = 100
            text_line = self._draw_text(text_displayed, 'trebuc.ttf', font_size, fg_color)
            text_pos = ((size[0] // 2) - (text_line.width // 2), (size[1] // 2) - 25)
            canvas.paste(text_line, text_pos, text_line)

        # Resize and Prepare Output 
        resized = canvas.resize(output_size)
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        canvas.paste(resized, (0, 0), resized)

        return canvas 

    def _draw_splus_status(self):
        output_size = self.objectData['size']
        size = (200,200)  # Working Canvas Size 
        

        # Create canvas & drawing object
        canvas = Image.new("RGBA", size)
        draw = ImageDraw.Draw(canvas)
        
        fg_color = self.objectData['color']

        if not self.objectData['active']:
            fg_color = (255,255,255,125)
        
        # Draw Rectangle
        padding = 25
        draw.rounded_rectangle((padding, padding, size[0]-padding, size[1]-padding), radius=20, outline=fg_color, width=6)
        
        # Draw Smoke Plus Icon(s)
        cloud_icon = self._create_icon('\uf0c2', 85, fg_color)
        cloud_icon_pos = ((size[0] // 2) - (cloud_icon.width // 2) - 8, (size[1] // 2) - (cloud_icon.height // 2))
        canvas.paste(cloud_icon, cloud_icon_pos, cloud_icon)

        plus_icon = self._create_icon('\uf067', 50, fg_color)
        plus_icon_pos = (120, 50)
        #plus_icon_pos = ((size[0] // 2) - (plus_icon.width // 2), (size[1] // 2) - (plus_icon.height // 2))
        canvas.paste(plus_icon, plus_icon_pos, plus_icon)

        # Resize and Prepare Output 
        resized = canvas.resize(output_size)
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        canvas.paste(resized, (0, 0), resized)

        return canvas 

    def _draw_hopper_status(self):
        output_size = self.objectData['size']
        size = (400,200)  # Working Canvas Size 
        #fg_color = self.objectData['color']

        color_index = int(self.objectData['data']['level'] // (100 / len(self.objectData['color_levels'])))
        #print(f'color_index = {color_index-1} level={self.objectData["data"]["level"]}')
        fg_color = self.objectData['color_levels'][max(color_index-1, 0)]

        # Create canvas & drawing object
        canvas = Image.new("RGBA", size)
        draw = ImageDraw.Draw(canvas)

        # Draw Transparent Rectangle
        bg_color = (255,255,255,100) if color_index != 0 else fg_color
        bg_color = list(bg_color)
        bg_color[3] = 100
        bg_color = tuple(bg_color)
        draw.rounded_rectangle((15, 15, size[0]-15, size[1]-15), radius=20, fill=bg_color)

        # Draw Title
        text_displayed = self.objectData['label']
        font_size = 40
        text_line = self._draw_text(text_displayed, 'trebuc.ttf', font_size, fg_color)
        text_pos = ((size[0] // 2) - (text_line.width // 2), 25)
        canvas.paste(text_line, text_pos, text_line)

        # Draw Hopper Percentage 
        text_displayed = str(self.objectData['data']['level']) + '%'
        font_size = 100
        text_line = self._draw_text(text_displayed, 'trebuc.ttf', font_size, fg_color)
        text_pos = ((size[0] // 2) - (text_line.width // 2), (size[1] // 2) - 25)
        canvas.paste(text_line, text_pos, text_line)

        # Draw Bar
        level_bar = (40, 160, 360, 170)
        current_level_adjusted = int((self.objectData['data']['level'] / 100) * 320) + 40 if self.objectData['data']['level'] > 0 else 40
        if current_level_adjusted > 360:
            current_level_adjusted = 360
        current_level_bar = (40, 160, current_level_adjusted, 170)
        draw.rounded_rectangle(level_bar, radius=10, fill=(0,0,0,200))
        draw.rounded_rectangle(current_level_bar, radius=10, fill=fg_color)

        # Resize and Prepare Output 
        resized = canvas.resize(output_size)
        canvas = Image.new("RGBA", (output_size[0], output_size[1]))
        canvas.paste(resized, (0, 0), resized)

        return canvas 

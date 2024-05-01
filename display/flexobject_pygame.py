'''
 Imported Libraries
'''

from pygame import Surface, SRCALPHA
from pygame import image as PyImage
from PIL import Image, ImageFilter
from display.flexobject_pil import FlexObject

'''
Display Flex Object Class Definition 
'''
class FlexObjectPygame(FlexObject):
    def __init__(self, objectType, objectData, background):
        super().__init__(objectType, objectData, background)
    
    def _init_surface(self):
        ''' pygame surface for output '''
        self.objectSurface = Surface(self.objectData['size'], SRCALPHA, 32)  # Foreground Surface

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
    
        self.objectSurface = PyImage.fromstring(raw_str, size, strFormat)

    def update_object_data(self, updated_objectData=None):
        super().update_object_data(updated_objectData)

        ''' Convert the PIL Canvas to Pygame Surface '''
        self._canvas_to_surface()

        return self.objectSurface 

    def get_object_surface(self):
        return self.objectSurface

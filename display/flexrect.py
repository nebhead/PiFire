class Rect:
    """Simple rectangle class implementation similar to pygame.Rect"""
    def __init__(self, *args):
        if len(args) == 4:
            # Handle four individual arguments
            left, top, width, height = args
        elif len(args) == 2:
            # Handle two tuples: (left, top), (width, height)
            (left, top), (width, height) = args
        elif len(args) == 1 and len(args[0]) == 4:
            # Handle single tuple/list of four values
            left, top, width, height = args[0]
        else:
            raise TypeError("Rect requires either 4 integers, 2 tuples of 2 integers, or 1 tuple/list of 4 integers")

        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.right = left + width
        self.bottom = top + height

    def collidepoint(self, point):
        """Check if a point (x,y) is inside the rectangle"""
        x, y = point
        return (self.left <= x <= self.right and 
                self.top <= y <= self.bottom) 
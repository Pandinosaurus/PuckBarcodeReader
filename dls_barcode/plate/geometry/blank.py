from util.shape import Circle


class BlankGeometry:
    _SERIAL_DELIM = "-"

    TYPE_NAME = "None"
    NUM_SLOTS = 20

    def __init__(self, barcodes):
        self._barcode_bounds = []
        self._set_barcode_bounds(barcodes)

    def _set_barcode_bounds(self, barcodes):
        self._barcode_bounds = []
        for barcode in barcodes:
            self._barcode_bounds.append(barcode.bounds())

    def slot_bounds(self, slot_num):
        return self._barcode_bounds[slot_num - 1]

    ############################
    # Drawing Functions
    ############################
    def draw_plate(self, img, color):
        pass

    def draw_pin_highlight(self, img, color, pin_number):
        """ Draws a highlight circle and slot number for the specified slot on the image. """
        bounds = self._barcode_bounds[pin_number - 1]
        img.draw_circle(bounds, color, thickness=int(bounds.radius() * 0.05))
        #img.draw_text(str(pin_number), bounds.center(), color, centered=True)

    def crop_image(self, img):
        """ Crops the image to the area which contains the puck. """
        tl_x, tl_y = img.width, img.height
        br_x, br_y = 0, 0

        for bounds in self._barcode_bounds:
            x, y, r = bounds.x(), bounds.y(), 3*bounds.radius()
            if x - r < tl_x:
                tl_x = x - r
            if y - r < tl_y:
                tl_y = y - r
            if x + r > br_x:
                br_x = x + r
            if y + r > br_y:
                br_y = y + r

        rectangle = [int(tl_x), int(tl_y), int(br_x), int(br_y)]
        img.crop_image_to_rectangle(rectangle)

    ############################
    # Serialization
    ############################
    @staticmethod
    def deserialize(string):
        circle_strs = string.split(BlankGeometry._SERIAL_DELIM)

        barcode_bounds = []
        for string in circle_strs:
            circle = Circle.deserialize(string)
            barcode_bounds.append(circle)

        geo = BlankGeometry([])
        geo._barcode_bounds = barcode_bounds
        return geo

    def serialize(self):
        circles = []
        for bounds in self._barcode_bounds:
            circles.append(bounds.serialize())
        return self._SERIAL_DELIM.join(circles)

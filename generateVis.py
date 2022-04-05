
####generateVis
####code sources: https://github.com/pavel-perina/gpx_to_png

import sys  
import math 
import logging 
import urllib
import os
import io
import base64
import gpxpy
from PIL import Image as pil_image
from PIL import ImageFilter as pil_filter
from PIL import ImageDraw as pil_draw
from PIL import ImageFont as pil_font
print(os.getcwd())
from PIL.ImageFilter import (
   BLUR, CONTOUR, DETAIL, EDGE_ENHANCE, EDGE_ENHANCE_MORE,
   EMBOSS, FIND_EDGES, SMOOTH, SMOOTH_MORE, SHARPEN
)

def get_black_pixels(im):
    width, height = im.size
    blackPixels = []
    for x in range(width):
        for y in range(height):
            color = im.getpixel((x,y))
            if color < 200: #check for pixels that are not white
                blackPixels.append({"x":x,"y":y})
    return blackPixels
 

##osm functions taken from https://github.com/pavel-perina/gpx_to_png
def osm_lat_lon_to_x_y_tile (lat_deg, lon_deg, zoom):
    """ Gets tile containing given coordinate at given zoom level """
    ## taken from http://wiki.openstreetmap.org/wiki/Slippy_map_tilenames, works for OSM maps and mapy.cz
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    return (xtile, ytile)


def osm_get_auto_zoom_level ( min_lat, max_lat, min_lon, max_lon, max_n_tiles):
    """ Gets zoom level which contains at maximum `max_n_tiles` """
    for z in range (0,17):
        x1, y1 = osm_lat_lon_to_x_y_tile (min_lat, min_lon, z)
        x2, y2 = osm_lat_lon_to_x_y_tile (max_lat, max_lon, z)
        max_tiles = max (abs(x2 - x1), abs(y2 - y1))
        if (max_tiles > max_n_tiles):
            #print ("Max tiles: %d" % max_tiles)
            return z 
    return 17

#given number of activities, return optimal grid dimensions for facets
def get_dimensions(n):
    for x in range(0,100): #100 is maximum amount of rows and columns allowed
        if(n <= (x+1)**2):
            #print("x: " + str(x))
            #print("maxRows: " + str((x+1)**2))
            return(x+1)
    print("failed to get dimensions")
    return(0)


##this class is the canvas that the activities(tracks) will be drawn on.
class ImageCreator:
    def __init__(self, tracks, lineThickness = 5, backgroundColor = (255,255,255), backgroundImage = None, backgroundBlur = 5, foregroundColor = (0,0,0), gridOn = False, gridColor = (255,255,255), gridThickness = 1,  title = "", blackWhiteImage = None, textBackgroundFade = False, infoText = False, totalTime = "", totalDistance = ""):
        
        self.tracks = tracks
        
        ##sizing##
        resolution = 4000
        self.maxTileWidth = resolution/(self.get_max_track_width())
        if blackWhiteImage==None: 
            self.maxRows = get_dimensions(len(tracks))
        else:
            self.maxRows = blackWhiteImage.height
        self.width = resolution #500 * self.maxRows
        self.height = self.width
        self.tile_res = self.maxTileWidth/self.maxRows
        #(resolution/2)*(self.maxTileWidth) #resolution of drawn tracks #6*(self.width/1000)
        self.gridElementSize = self.width / self.maxRows
        print("Max track width: " + str(self.get_max_track_width()))
        print("Max tile width: " + str(self.maxTileWidth))
        
        ##user parameters##
        self.lineThickness = lineThickness 
        self.gridColor = gridColor
        self.foregroundColor = foregroundColor
        self.gridOn = gridOn
        self.gridThickness = gridThickness



        ####background image####

       
        if backgroundImage!=None:
            ##resize and crop image to fit##
            if(backgroundImage.width < resolution or backgroundImage.height < resolution):
                if(backgroundImage.width>backgroundImage.height):
                    backgroundImage = backgroundImage.resize((backgroundImage.width*(math.ceil(resolution/backgroundImage.height)),resolution))
                else:
                    backgroundImage = backgroundImage.resize((resolution,backgroundImage.height*(math.ceil(resolution/backgroundImage.width))))
            backgroundImage = backgroundImage.crop(((backgroundImage.width-resolution)/2,(backgroundImage.height-resolution)/2, (backgroundImage.width+resolution)/2,(backgroundImage.height+resolution)/2))
            backgroundImage = backgroundImage.filter(pil_filter.GaussianBlur(20))
            backgroundImage = backgroundImage.convert("RGBA")
            self.image = backgroundImage
        else:
            self.image = pil_image.new ("RGBA", (self.width, self.height), backgroundColor)

        ###extra image additions####
        if(textBackgroundFade == True):
            fade = pil_image.open("fade.png").resize((resolution,resolution))
            self.image = pil_image.alpha_composite(self.image, fade)

        if (self.gridOn==True): 
            self.draw_grid()

        if (infoText==True):
           self.draw_text("activities",str(self.get_tracks_length())) #str(image_creator.get_tracks_length())
        
          
    def draw_text(self,label="",text=""):
        draw = pil_draw.Draw(self.image)
        textFont = pil_font.truetype('arial.ttf', int(self.width/13)) #300
        labelFont = pil_font.truetype('arial.ttf', int(self.width/30)) #130
        
        # calculate the x,y coordinates of the text
        textwidth, textheight = draw.textsize(text, textFont)
        labelwidth, labelheight = draw.textsize(label, labelFont)
        margin = self.width/40 #self.width is resolution
        
        textx = self.image.width - textwidth - margin
        texty = self.image.height - textheight - margin

        labelx = (textx + textwidth/2)-(labelwidth/2) #+ math.ceil(textwidth*.05)
        labely = texty-(textheight/2)
        
        
        draw.text((textx, texty), text, font=textFont, align='center') #align='center'
        draw.text((labelx, labely), label, font=labelFont)
        
        del draw
    def draw_grid(self):
        step_count = self.maxRows
        # Draw some lines
        draw = pil_draw.Draw (self.image)
        y_start = 0
        y_end = self.image.height
        step_size = int(self.image.width / step_count)
        for x in range(0, self.image.width, step_size):
            line = ((x, y_start), (x, y_end))
            draw.line(line, fill=self.gridColor, width=self.gridThickness)
        x_start = 0
        x_end = self.image.width
        for y in range(0, self.image.height, step_size):
            line = ((x_start, y), (x_end, y))
            draw.line(line, fill=self.gridColor, width=self.gridThickness)
        del draw
    def draw_facets(self):
        row = 0
        column = 0
        gridElementSize = self.width / self.maxRows
        for track in self.tracks:
            if column == self.maxRows:
                row+=1
                column = 0

            #center tracks. set to zero to uncenter
            centerxOffset = (self.gridElementSize/2) - (track.get_width()*self.tile_res)/2
            centeryOffset = (self.gridElementSize/2) -(track.get_height()*self.tile_res)/2

            track.draw_track((self.gridElementSize*column)+centerxOffset,(self.gridElementSize*row) + centeryOffset,self.image, self.tile_res, self.lineThickness, self.foregroundColor)
            column+=1
        self.image = self.image.filter(SMOOTH_MORE)

    def draw_shape(self, blackPxSequence):

        step_count = self.maxRows
        row = 0
        column = 0
        blackPxLength = len(blackPxSequence)
        gridElementSize = self.width / self.maxRows
        y_start = 0
        y_end = self.image.height
        step_size = int(self.image.width / step_count)
        #for i in range(len(self.tracks)):
        j = 0
        for i in range(len(blackPxSequence)):
            if i < blackPxLength: 
                pixel = blackPxSequence[i]
                #print("drawing track " + str(i) + "at x:" + str(self.gridElementSize*pixel["y"]) + " y: " + str(self.gridElementSize*pixel["x"]))
                self.tracks[j].draw_track((self.gridElementSize*pixel["x"]),(self.gridElementSize*pixel["y"]),self.image, self.tile_res, self.lineThickness, self.foregroundColor)
            else:
                break
            j+=1
            if j >= len(self.tracks):
                j = 0
            
    
    def save_image(self, filename = ""):
        if filename != "":
            self.image.save (filename)
            self.image.show()
        # no file name provided, return image as base64-encoded string for displaying without saving on server
        else:
            imgArray = io.BytesIO()
            self.image.save(imgArray, format="PNG")
            return str(base64.b64encode(imgArray.getvalue()), 'utf-8')
        
        
    def get_max_track_width(self):
        maxWidth = 0
        for track in self.tracks:
            width = track.get_width()
            if (width > maxWidth):
                maxWidth = width
        #print("max width of track: " + str(maxWidth))
        return maxWidth
    
    def get_tracks_length(self):
        return(len(self.tracks))
        
        
            

    #activity. only stores GPX data at the moment. eventually should also have data such as activity name, time, distance, etc....          
class Track:
    def __init__(self, activity, min_lat, max_lat, min_lon, max_lon, zoom):
        """ constructor """
        self.activity = activity # list of coordinates
        x1, y1 = osm_lat_lon_to_x_y_tile (min_lat, min_lon, zoom)
        x2, y2 = osm_lat_lon_to_x_y_tile (max_lat, max_lon, zoom)
        self.x1 = min (x1, x2)
        self.x2 = max (x1, x2)
        self.y1 = min (y1, y2)
        self.y2 = max (y1, y2)
        self.width = (self.x2 - self.x1 + 1)
        self.height = (self.y2 - self.y1 + 1)
        self.zoom = zoom

    
        self.x_offset = 0
        self.y_offset = 0

        
    def lat_lon_to_image_xy (self, lat_deg, lon_deg, tile_res):
        """ Internal. Converts lat, lon into dst_img coordinates in pixels """
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** self.zoom
        xtile_frac = (lon_deg + 180.0) / 360.0 * n
        ytile_frac = (1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
        img_x = int( (xtile_frac-self.x1)*tile_res )
        img_y = int( (ytile_frac-self.y1)*tile_res )
        return (img_x + self.x_offset, img_y + self.y_offset) #modified with offsets +300

    def draw_track (self, new_x_offset, new_y_offset, image, tile_res, lineThickness, lineColor):
        
        self.x_offset = new_x_offset #(self.width*tile_res)/2 
        self.y_offset = new_y_offset 
        draw = pil_draw.Draw(image)

        x_from = 0
        y_from = 0
        linePointIdx = 0 #a line requires 2 points to draw. if this is 0, then it sets the first point, if this is 1, then it sets the second point
        
        for coordinate in self.activity:
            #coordinate[0] is latitude. coordinate[1] is longitude
            if (linePointIdx == 0):
                x_from, y_from = self.lat_lon_to_image_xy (coordinate[0], coordinate[1], tile_res) #set first coordinate
            else:    
                x_to, y_to = self.lat_lon_to_image_xy (coordinate[0], coordinate[1], tile_res)
                #draw.line ((x_from,y_from,x_to,y_to), (255,0,trk), 2)
                draw.line ((x_from ,y_from,x_to, y_to), lineColor, lineThickness) #coordinates, color, thickness
                x_from = x_to
                y_from = y_to
               
            linePointIdx +=1
        # (41.14569, -81.34207), (41.14564, -81.34187), (41.14556, -81.34178) 
            
    def get_width(self):
        return(self.width)
    def get_height(self):
        return(self.height)

def get_latlon_bounds(activity):
    min_lat = None
    max_lat = None
    min_lon = None
    max_lon = None

    for coordinate in activity:
        if min_lat is None or coordinate[0] < min_lat:
            min_lat = coordinate[0]
        if max_lat is None or coordinate[0] > max_lat:
            max_lat = coordinate[0]
        if min_lon is None or coordinate[1] < min_lon:
            min_lon = coordinate[1]
        if max_lon is None or coordinate[1] > max_lon:
            max_lon = coordinate[1]

    if min_lat and max_lat and min_lon and max_lon:
        return (min_lat, max_lat, min_lon, max_lon)
    return None

def gpx_to_list(gpx):
    activity = []
    for gpxTrack in gpx.tracks:
        for segment in gpxTrack.segments:
            for point in segment.points:
                activity.append((point.latitude,point.longitude))
    return(activity)
            


def getVis(data, lineThickness = 5, backgroundColor = (255,255,255), backgroundImage = None, backgroundBlur = 5, foregroundColor = (0,0,0), gridOn = False, gridColor = (0,0,0), gridThickness = 1,  title = "", blackWhiteImage = None, textBackgroundFade = False, infoText = False, totalTime = "", totalDistance = ""): 
    """ Program entry point """
    
    
    tracks = []
    countLimit = 2000 #temporary
    count = 0
    
    #####POLYLINE LIST####
    if (type(data[0][0]) is tuple): #very rough way to check if it is a polyline list or a GPX file
        for activity in data:
            try:
                min_lat, max_lat, min_lon, max_lon = get_latlon_bounds(activity)
                #print(get_latlon_bounds(activity))
                zoom = osm_get_auto_zoom_level (min_lat, max_lat, min_lon, max_lon, 1)
                track = Track(activity, min_lat, max_lat, min_lon, max_lon, zoom)
                tracks.append(track)
            except Exception as e:
                logging.exception(e)
                print("Error processing polyline")
                sys.exit(1)
    #####GPX FILE#####
    ##convert GPX file to list
    else:
        print("GPX File")
        gpx_files = glob.glob (r"*.gpx") #get all GPX files in same directory
        
        for gpx_file in gpx_files:
            if count != countLimit:
                count+=1
                try:
                    gpx = gpxpy.parse(open(gpx_file))
                    
                    #start_time, end_time = gpx.get_time_bounds()
                    #min_lat, max_lat, min_lon, max_lon = gpx.get_bounds()
                    
                    activity = gpx_to_list(gpx)
                    min_lat, max_lat, min_lon, max_lon = get_latlon_bounds(activity)
                    zoom = osm_get_auto_zoom_level (min_lat, max_lat, min_lon, max_lon, 1)
                    track = Track(activity, min_lat, max_lat, min_lon, max_lon, zoom)
                    tracks.append(track)

                except Exception as e:

                    logging.exception(e)
                    print('Error processing: %s' % gpx_file)
                    sys.exit(1)
            else:
                break

    blackPixels = []
    maxRows = 0 #set to 0 for imagecreator to automatically set height
    if blackWhiteImage!=None:
         blackPixels = get_black_pixels(blackWhiteImage)
         print("black pixels: " + str(len(blackPixels)))
         
    image_creator = ImageCreator(tracks, lineThickness, backgroundColor, backgroundImage, backgroundBlur, foregroundColor, gridOn, gridColor, gridThickness,  title, blackWhiteImage, textBackgroundFade, infoText, totalTime, totalDistance)
    
    if blackWhiteImage != None:
        image_creator.draw_shape(blackPixels)
    else:
        image_creator.draw_facets()

    return(image_creator.save_image())



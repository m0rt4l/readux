'''
Custom template tags and filter for displaying TEI facsimile content
overlaid on top of a scaled page image.
'''

from django import template
from readux.books.models import TeiZone

register = template.Library()

def percent(a, b):
    # a as percentage of b
    # ensure both are cast to float, divide, then multiply by 100
    return (float(a) / float(b)) * 100

@register.filter
def zone_style(zone, scale):
    ''''Generate an HTMl attribute string for a
    :class:`readux.books.models.TeiZone` element, scaled to match the page
    image size.  Takes an element and a tuple of scale, which is used to
    adjust position information to the needed display size (i.e., the
    scale of the display image size relative to original OCR page image size).'''

    styles = {}
    if isinstance(zone, TeiZone):
        styles['width'] = '%.2f%%' % percent(zone.width, zone.page.width)
        styles['height'] = '%.2f%%' % percent(zone.height, zone.page.height)

        if zone.type in ['textLine', 'line']:
            # text lines are absolutely positioned boxes
            styles['left'] = '%f%%' % percent(zone.ulx, zone.page.width)
            styles['top'] = '%f%%' % percent(zone.uly, zone.page.height)
            # TODO: figure out how to determine this from ocr/teifacsimile
            # rather than assuming
            styles['text-align'] = 'left'
            # TODO: would be better to set font-size by the line, but
            # needs to be generated from word zones, not the line bounding box
        elif zone.type == 'string':
            # word strings are relatively positioned within a line
            if zone.preceding:
                # padding from end of previous word to beginning of the next
                styles['padding-left'] = '%f%%' % percent(zone.ulx - zone.preceding.lrx, zone.parent.width)
            elif zone.parent:
                # padding from beginning of the line to beginning of the first word,
                # if there is a difference
                if zone.ulx != zone.parent.ulx:
                    styles['padding-left'] = '%f%%' % percent(zone.ulx - zone.parent.ulx, zone.parent.width)

        # calculate font size if either:
        # - word zone (alto-based tei)
        # - line with no word zones (abbyy-based tei)
        if zone.type == 'string' or  \
           (zone.type in ['textLine', 'line'] and not zone.word_zones):

            styles['font-size'] = '%.2fpx' % ((zone.lry - zone.uly) * scale)
            # print 'zone height is %s, scale is %s, scaled height is %s' % (zone.lry - zone.uly,
                    # scale, styles['font-size'])
            # NOTE: could *possibly* use viewport percentage sizing for font size,
            # but it would need javascript calculations to adjust when the page image is
            # smaller than the viewport
            # styles['font-size'] = '%fvw' % percent(zone.lry - zone.uly, zone.page.height)
            # FIXME: needs a fallback size for older browsers...

            # may also want to attempt some letter-spacing styles to
            # get text to fill bounding boxes better

    if styles:
        return ';'.join(['%s:%s' % (k, v) for k, v in styles.iteritems()])
    # no styles
    return ''
import os
from datetime import datetime
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.test import TestCase
from mock import patch, Mock, NonCallableMock

from eulxml.xmlmap import load_xmlobject_from_file
from eulfedora.util import RequestFailed

from readux.books import abbyyocr
from readux.books.models import SolrVolume, Volume

class SolrVolumeTest(TestCase):
    # primarily testing BaseVolume logic here

    def test_properties(self):
        ocm = 'ocn460678076'
        vol = 'V.1'
        noid = '1234'
        volume = SolrVolume(label='%s_%s' % (ocm, vol),
                         pid='testpid:%s' % noid)

        self.assertEqual(ocm, volume.control_key)
        self.assertEqual(vol, volume.volume)
        self.assertEqual(noid, volume.noid)

        # don't display volume zero
        vol = 'V.0'
        volume.data['label'] = '%s_%s' % (ocm, vol)
        self.assertEqual('', volume.volume)

        # should also work without volume info
        volume.data['label'] = ocm
        self.assertEqual(ocm, volume.control_key)
        self.assertEqual('', volume.volume)

    def test_fulltext_absolute_url(self):
        volume = SolrVolume(label='ocn460678076_V.1',
                         pid='testpid:1234')

        url = volume.fulltext_absolute_url()
        self.assert_(url.startswith('http://'))
        self.assert_(url.endswith(reverse('books:text', kwargs={'pid': volume.pid})))
        current_site = Site.objects.get_current()
        self.assert_(current_site.domain in url)


class BookViewsTest(TestCase):

    @patch('readux.books.views.Repository')
    @patch('readux.books.views.raw_datastream')
    def test_pdf(self, mockraw_ds, mockrepo):
        mockobj = Mock()
        mockobj.pid = 'vol:1'
        mockobj.label = 'ocm30452349_1908'
        mockrepo.return_value.get_object.return_value = mockobj
        # to support for last modified conditional
        mockobj.pdf.created = datetime.now()

        pdf_url = reverse('books:pdf', kwargs={'pid': mockobj.pid})
        response = self.client.get(pdf_url)

        # only check custom logic implemented here, via mocks
        # (not testing eulfedora.views.raw_datastream logic)
        self.assertEqual(mockraw_ds.return_value.render(), response,
            'result of fedora raw_datastream should be returned')

        # can't check full call args because we can't match request
        args, kwargs = mockraw_ds.call_args

        # second arg should be pid
        self.assertEqual(mockobj.pid, args[1])
        # third arg should be datstream id
        self.assertEqual(Volume.pdf.id, args[2])
        # digital object class should be specified
        self.assertEqual(Volume, kwargs['type'])
        self.assertEqual(mockrepo.return_value, kwargs['repo'])
        self.assertEqual({'Content-Disposition': 'filename="%s.pdf"' % mockobj.label},
            kwargs['headers'])

        # volume with a space in the label
        mockobj.label = 'ocm30452349_1908 V0.1'
        response = self.client.get(pdf_url)
        args, kwargs = mockraw_ds.call_args
        content_disposition = kwargs['headers']['Content-Disposition']
        self.assertEqual('filename="%s.pdf"' % mockobj.label.replace(' ', '-'),
            content_disposition,
            'content disposition filename should not include spaces even if label does')

        # fedora error should 404
        mockresponse = Mock()
        mockresponse.status = 500
        mockresponse.reason = 'server error'
        mockraw_ds.side_effect = RequestFailed(mockresponse, '')
        response = self.client.get(pdf_url)
        expected, got = 404, response.status_code
        self.assertEqual(expected, got,
            'expected %s for %s when there is a fedora error, got %s' % \
            (expected, pdf_url, got))

    @patch('readux.books.views.Paginator', spec=Paginator)
    @patch('readux.books.views.solr_interface')
    def test_search(self, mocksolr_interface, mockpaginator):

        # no search terms - invalid form
        search_url = reverse('books:search')
        response = self.client.get(search_url)
        self.assertContains(response, 'Please enter one or more search terms')

        mocksolr = mocksolr_interface.return_value
        # simulate sunburnt's fluid interface
        mocksolr.query.return_value = mocksolr.query
        for method in ['query', 'facet_by', 'sort_by', 'field_limit',
                       'exclude', 'filter', 'join', 'paginate']:
            getattr(mocksolr.query, method).return_value = mocksolr.query

        # set up mock results for collection query and facet counts
        solr_result = [
            {'pid': 'vol:1', 'title': 'Lecoq, the detective'},
            {'pid': 'vol:2', 'title': 'Mabel Meredith'},
        ]
        mocksolr.query.__iter__.return_value = iter(solr_result)
        mocksolr.count.return_value = 2

        # use a noncallable for the pagination result that is used in the template
        # because passing callables into django templates does weird things
        mockpage = NonCallableMock()
        mockpaginator.return_value.page.return_value = mockpage
        mockpage.object_list = solr_result
        mockpage.has_other_pages = False
        mockpage.paginator.count = 2
        mockpage.paginator.page_range = [1]

        # query with search terms
        response = self.client.get(search_url, {'keyword': 'yellowbacks'})

        mocksolr.query.filter.assert_called_with(content_model=Volume.VOLUME_CONTENT_MODEL)
        mocksolr.query.query.assert_called_with('yellowbacks')
        mocksolr.query.field_limit.assert_called_with(['pid', 'title', 'label'], score=True)

        # check that items are displayed
        for item in solr_result:
            self.assertContains(response, item['title'],
                msg_prefix='title should be displayed')
            self.assertContains(response, reverse('books:pdf', kwargs={'pid': item['pid']}),
                msg_prefix='link to pdf should be included in response')


        # multiple terms and phrase
        response = self.client.get(search_url, {'keyword': 'yellowbacks "lecoq the detective" mystery'})
        mocksolr.query.query.assert_called_with('yellowbacks', 'lecoq the detective', 'mystery')

    @patch('readux.books.views.Repository')
    @patch('readux.books.views.raw_datastream')
    def test_text(self, mockraw_ds, mockrepo):
        mockobj = Mock()
        mockobj.pid = 'vol:1'
        mockobj.label = 'ocm30452349_1908'
        mockrepo.return_value.get_object.return_value = mockobj
        mockobj.get_fulltext.return_value = 'sample text content'
        # to support for last modified conditional
        mockobj.ocr.created = datetime.now()

        text_url = reverse('books:text', kwargs={'pid': mockobj.pid})
        response = self.client.get(text_url)

        self.assertEqual(mockobj.get_fulltext.return_value, response.content,
            'volume full text should be returned as response content')
        self.assertEqual(response['Content-Type'], "text/plain")
        self.assertEqual(response['Content-Disposition'],
            'filename="%s.txt"' % mockobj.label)

        # various 404 conditions
        # - no ocr
        mockobj.ocr.exists = False
        response = self.client.get(text_url)
        self.assertEqual(404, response.status_code,
            'text view should 404 if ocr datastream does not exist')
        # - not a volume
        mockobj.has_requisite_content_models = False
        mockobj.ocr.exists = True
        response = self.client.get(text_url)
        self.assertEqual(404, response.status_code,
            'text view should 404 if object is not a Volume')
        # - object doesn't exist
        mockobj.exists = False
        mockobj.has_requisite_content_models = True
        response = self.client.get(text_url)
        self.assertEqual(404, response.status_code,
            'text view should 404 if object does not exist')


class AbbyyOCRTestCase(TestCase):

    fixture_dir = os.path.join(settings.BASE_DIR, 'readux', 'books', 'fixtures')

    fr6v1_doc = os.path.join(fixture_dir, 'abbyyocr_fr6v1.xml')
    fr8v2_doc = os.path.join(fixture_dir, 'abbyyocr_fr8v2.xml')
    # language code
    eng = 'EnglishUnitedStates'

    def setUp(self):
        self.fr6v1 = load_xmlobject_from_file(self.fr6v1_doc, abbyyocr.Document)
        self.fr8v2 = load_xmlobject_from_file(self.fr8v2_doc, abbyyocr.Document)

    def test_document(self):
        # top-level document properties

        # finereader 6 v1
        self.assertEqual(132, self.fr6v1.page_count)
        self.assertEqual(self.eng, self.fr6v1.language)
        self.assertEqual(self.eng, self.fr6v1.languages)
        self.assert_(self.fr6v1.pages, 'page list should be non-empty')
        self.assertEqual(132, len(self.fr6v1.pages),
                         'number of pages should match page count')
        self.assert_(isinstance(self.fr6v1.pages[0], abbyyocr.Page))

        # finereader 8 v2
        self.assertEqual(186, self.fr8v2.page_count)
        self.assertEqual(self.eng, self.fr8v2.language)
        self.assertEqual(self.eng, self.fr8v2.languages)
        self.assert_(self.fr8v2.pages, 'page list should be non-empty')
        self.assertEqual(186, len(self.fr8v2.pages),
                         'number of pages should match page count')
        self.assert_(isinstance(self.fr8v2.pages[0], abbyyocr.Page))

    def test_page(self):
        # finereader 6 v1
        self.assertEqual(1500, self.fr6v1.pages[0].width)
        self.assertEqual(2174, self.fr6v1.pages[0].height)
        self.assertEqual(300, self.fr6v1.pages[0].resolution)
        # second page has picture block, no text
        self.assertEqual(1, len(self.fr6v1.pages[1].blocks))
        self.assertEqual(1, len(self.fr6v1.pages[1].picture_blocks))
        self.assertEqual(0, len(self.fr6v1.pages[1].text_blocks))
        self.assert_(isinstance(self.fr6v1.pages[1].blocks[0], abbyyocr.Block))
        # fourth page has paragraph text
        self.assert_(self.fr6v1.pages[3].paragraphs)
        self.assert_(isinstance(self.fr6v1.pages[3].paragraphs[0],
                                abbyyocr.Paragraph))

        # finereader 8 v2
        self.assertEqual(2182, self.fr8v2.pages[0].width)
        self.assertEqual(3093, self.fr8v2.pages[0].height)
        self.assertEqual(300, self.fr8v2.pages[0].resolution)
        # first page has multiple text/pic blocks
        self.assert_(self.fr8v2.pages[0].blocks)
        self.assert_(self.fr8v2.pages[0].picture_blocks)
        self.assert_(self.fr8v2.pages[0].text_blocks)
        self.assert_(isinstance(self.fr8v2.pages[0].blocks[0], abbyyocr.Block))
        # first page has paragraph text
        self.assert_(self.fr8v2.pages[0].paragraphs)
        self.assert_(isinstance(self.fr8v2.pages[0].paragraphs[0],
                                abbyyocr.Paragraph))

    def test_block(self):
        # finereader 6 v1
        # - basic block attributes
        b = self.fr6v1.pages[1].blocks[0]
        self.assertEqual('Picture', b.type)
        self.assertEqual(144, b.left)
        self.assertEqual(62, b.top)
        self.assertEqual(1358, b.right)
        self.assertEqual(2114, b.bottom)
        # - block with text
        b = self.fr6v1.pages[3].blocks[0]
        self.assert_(b.paragraphs)
        self.assert_(isinstance(b.paragraphs[0], abbyyocr.Paragraph))

        # finereader 8 v2
        b = self.fr8v2.pages[0].blocks[0]
        self.assertEqual('Text', b.type)
        self.assertEqual(282, b.left)
        self.assertEqual(156, b.top)
        self.assertEqual(384, b.right)
        self.assertEqual(228, b.bottom)
        self.assert_(b.paragraphs)
        self.assert_(isinstance(b.paragraphs[0], abbyyocr.Paragraph))

    def test_paragraph_line(self):
        # finereader 6 v1
        para = self.fr6v1.pages[3].paragraphs[0]
        # untested: align, left/right/start indent
        self.assert_(para.lines)
        self.assert_(isinstance(para.lines[0], abbyyocr.Line))
        line = para.lines[0]
        self.assertEqual(283, line.baseline)
        self.assertEqual(262, line.left)
        self.assertEqual(220, line.top)
        self.assertEqual(1220, line.right)
        self.assertEqual(294, line.bottom)
        # line text available via unicode
        self.assertEqual(u'MABEL MEREDITH;', unicode(line))
        # also mapped as formatted text (could repeat/segment)
        self.assert_(line.formatted_text) # should be non-empty
        self.assert_(isinstance(line.formatted_text[0], abbyyocr.Formatting))
        self.assertEqual(self.eng, line.formatted_text[0].language)
        self.assertEqual(u'MABEL  MEREDITH;', line.formatted_text[0].text) # not normalized

        # finereader 8 v2
        para = self.fr8v2.pages[1].paragraphs[0]
        self.assert_(para.lines)
        self.assert_(isinstance(para.lines[0], abbyyocr.Line))
        line = para.lines[0]
        self.assertEqual(1211, line.baseline)
        self.assertEqual(845, line.left)
        self.assertEqual(1160, line.top)
        self.assertEqual(1382, line.right)
        self.assertEqual(1213, line.bottom)
        self.assertEqual(u'EMORY UNIVERSITY', unicode(line))
        self.assert_(line.formatted_text) # should be non-empty
        self.assert_(isinstance(line.formatted_text[0], abbyyocr.Formatting))
        self.assertEqual(self.eng, line.formatted_text[0].language)
        self.assertEqual(u'EMORY UNIVERSITY', line.formatted_text[0].text)

    def test_frns(self):
        self.assertEqual('fr6v1:par|fr8v2:par', abbyyocr.frns('par'))
        self.assertEqual('fr6v1:text/fr6v1:par|fr8v2:text/fr8v2:par',
                         abbyyocr.frns('text/par'))

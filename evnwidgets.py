import base64
from collections import OrderedDict
import datetime
from itertools import islice

import lxml

from IPython.display import display, HTML
from ipywidgets import widgets
from ipywidgets import VBox, HBox
import traitlets

from sublime_evernote.lib import (markdown2, html2text, pygments)

# https://github.com/CarlLee/ENML_PY
import ENML2HTML
from ENML2HTML import MediaStore

import EvernoteWebUtil as ewu
from settings import authToken

# code for loading notes for a given notebook
# I already have code in my branch of osf.io
# https://github.com/rdhyee/osf.io/blob/ee33dab8a518da1db831d3f2dc531f44766867cb/website/addons/evernote/views.py#L100

class OSFMediaStore(MediaStore):
    def __init__ (self, note_store, note_guid):
        super(OSFMediaStore, self).__init__(note_store, note_guid)

    def save(self, hash_str, mime_type):
        # hash_str is the hash digest string of the resource file
        # mime_type is the mime_type of the resource that is about to be saved
        # you can get the mime type to file extension mapping by accessing the dict MIME_TO_EXTENSION_MAPPING

        # retrieve the binary data
        data = self._get_resource_by_hash(hash_str)
        # some saving operation [ not needed for embedding into data URI]
        
        # return the URL of the resource that has just been saved
        # convert content to data:uri
        # https://gist.github.com/jsocol/1089733
        
        data64 = u''.join(base64.encodestring(data).splitlines())
        return u'data:{};base64,{}'.format(mime_type, data64)


class NotesViewerWidget(object):
    def __init__(self, ewu):
        self.ewu = ewu
        self.notebook_widget = widgets.Dropdown(
            description='Notebook:'
        )
        self.notes_widget = widgets.Select(
            description='Notes:',
            options = [],
            width = '500px'
        )
        self.note_widget = widgets.HTML("<b>note widget</b>",
                        background_color='#F5F5DC', # and also by color code.
                        border_color='red' 
        )
        self.t_widget = widgets.Text()
        
    
        # bind changes in w to display of t
        self.notebook_widget.on_trait_change(self.notebook_changed, 'value')
        self.notes_widget.on_trait_change(self.note_selected, 'value')
        
        self.load_notebooks()
        
    def inv_dict(self, d):
        return dict([(v,k) for (k,v) in d.items()])

    def notes_md_for_notebook(self, notebook_guid):
        return self.ewu.notes_metadata(notebookGuid=notebook_guid, includeTitle=True,) 

    def load_notebooks(self):

        self.notebooks = ewu.all_notebooks(refresh=True)
        self.nbcounts = ewu.notebookcounts()

        _options = OrderedDict([(notebook.name, notebook.guid) for notebook in self.notebooks])
        self.notebook_widget.options=_options

        default_nb_guid = [notebook.guid for notebook in self.notebooks if notebook.defaultNotebook is True][0]
        self.notebook_widget.value = default_nb_guid

    def notebook_changed(self, name, value):
        d = self.inv_dict(self.notebook_widget.options)

        self.t_widget.value = unicode(d.get(value,'') + " ({})".format(self.nbcounts.get(value)) )

        # load notes for notebook
        _options = ([(note_md.title.decode('UTF-8'), note_md.guid) 
                                            for note_md in islice(self.notes_md_for_notebook(value),200)])
        self.notes_widget.options = _options
        
    def note_selected(self, name, value):
        # grab the note
        self.note_widget.value = "<i>Retrieving note...</i>"
        try:
            note = self.ewu.get_note(value, withContent=True, withResourcesData=True)
            mediaStore = OSFMediaStore(self.ewu.noteStore, value)
            _html =  ENML2HTML.ENMLToHTML(note.content, media_store=mediaStore).decode('UTF-8')
            self.note_widget.value = _html
        except Exception as e:
            # how to display message
            # self.note_widget.value = u"{} | {}: {}".format(value, e.errorCode, e.parameter)
            self.note_widget.value = unicode(e)

    def _ipython_display_(self):
        display(self.notebook_widget, 
                self.t_widget, 
                self.notes_widget, 
                self.note_widget)

    def __del__(self):
        for w in [self.notebook_w, self.notes_widget, self.note_widget, self.t_widget]:
            w.close()


class NoteEditWidget(object):
    def __init__(self, ewu, extras=None):
        # start with no note
        self.ewu = ewu
        self.note = None
        # need to track content here because note might hold only a hash of the content
        self.content = None
        if extras is None:
            self.extras =  {
                'footnotes'          : None,
                'cuddled-lists'      : None,
                'metadata'           : None,
                'markdown-in-html'   : None,
                'fenced-code-blocks' : {'noclasses': True, 'cssclass': "", 'style': "default"}
            }
        self.notebook_w = widgets.Dropdown()
        self.title_w = widgets.Text()
        self.body_w = widgets.Textarea()
        self.save_button = widgets.Button(
            description="Save"
        )
        self.new_button = widgets.Button(
          description="New"
        )
        self.status_w = widgets.Text()

        # load list of notebooks into self.notebook_w
        
        self.load_notebooks()
        
        # wire up the event handlers

        self.save_button.on_click(self.handle_save)
        self.new_button.on_click(self.handle_new)
        
        
    def load_notebooks(self):
        
        notebooks = self.ewu.all_notebooks(refresh=True)
        self.notebook_w.options=OrderedDict([(notebook.name, notebook.guid) for notebook in notebooks])
        # to start with use the default notebook
        try:
            default_nb_guid = [notebook.guid for notebook in notebooks if notebook.defaultNotebook is True][0]
            self.notebook_w.value = default_nb_guid
        except:
            pass
        
    def handle_save(self, b):

        if self.note is None:
            # create new note
            if not self.title_w.value:
                self.title_w.value = 'Untitled'
            self.content = self.body_w.value
            body = markdown2.markdown(self.content, extras=self.extras)
            try:
                self.note = self.ewu.create_note(self.title_w.value, body, notebookGuid=self.notebook_w.value)
            except Exception as e:
                self.status_w.value = str(e) # should get this right
        else:
            # figure out new changes
            # pass body if it has changed
            if not self.title_w.value:
                self.title_w.value = 'Untitled'
            if self.body_w.value <> self.content:
                try:
                    self.content = self.body_w.value
                    body = markdown2.markdown(self.content, extras=self.extras)
                    self.note = ewu.update_note(self.note, title=self.title_w.value, 
                                                content=body, notebookGuid=self.notebook_w.value)
                except Exception as e:
                    self.status_w.value = str(e) # should get this right
            else:
                try:
                    self.note = ewu.update_note(self.note, title=self.title_w.value, 
                                                notebookGuid=self.notebook_w.value)
                except Exception as e:
                    self.status_w.value = str(e) # should get this right
                
    
    def handle_new(self, b):
        """
        initialize 
        """
        
        self.note = None
        self.title_w.value = ''
        self.body_w.value = ''
        

    def _ipython_display_(self):
        self.button_line = HBox([self.save_button, self.new_button])
        self.overall_box = VBox([self.notebook_w, 
              self.title_w, 
              self.body_w, 
              self.button_line,
              self.status_w
              ])
        display(self.overall_box)
        
    def __del__(self):
        """
        this doesn't quite work with del s
        """
        for w in [self.notebook_w, self.title_w, self.body_w, self.button_line, self.status_w, self.overall_box]:
            w.close()
       
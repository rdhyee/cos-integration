from ipywidgets import widgets
from ipywidgets import VBox, HBox
import traitlets

from IPython.display import display, HTML
from collections import OrderedDict

from sublime_evernote.lib import (markdown2, html2text, pygments)


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
       
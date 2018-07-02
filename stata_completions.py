# Based on:
# https://github.com/y0ssar1an/CSS3/blob/master/css3_completions.py

# See also:
# http://docs.sublimetext.info/en/latest/reference/api.html

from .completions import util
from .completions import extended_locals

import sublime
import sublime_plugin


class AutocompleteColon(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.run_command("insert_snippet", {"contents": " : "})
        self.view.run_command("auto_complete")


class StataCompletions(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        """Populate the completions menu based on the current cursor location.

        Args:
            view (sublime.View): A Sublime API object that contains the
                match_selector() method for detecting if the current scope has
                completions, and the substr() method for getting text from the
                document.
            prefix (str): The first part of the text that triggered the
                completions menu, e.g. "tex" for "text-decoration".
            locations (list: int): The current integer positions of the cursors.

        Returns:
            [(<label>, <completion), ...], inhibit_flag

            <label> is what will appear in the completions menu. <completion> is
            the snippet that will be inserted. inhibit_flag controls whether
            "word completions" are offered as well. "Word completions" are
            a list of every word in the current file greater than four
            characters long.
        """

        if not view.match_selector(locations[0], "source.stata"):
            return []

        if view.match_selector(locations[0], "comment"):
            return []

        if view.match_selector(locations[0], "source.mata") or True:
            return []

        # If there's multiple cursors, we can't offer completions.
        #     body {
        #         foo: |<- cursor
        #         bar: |<- second cursor
        #     }
        # Which values do we offer? foo's or bar's?
        if len(locations) > 1:
            return [], sublime.INHIBIT_WORD_COMPLETIONS

        # start determines which completions are offered.
        #         |--prefix--|
        # start ->text-decorat|<- current cursor location
        start = locations[0] - len(prefix)

        last_block = view.substr(sublime.Region(start-10, start)).rstrip()

        # Match extended locals ("local x : var label xyz")
        if view.match_selector(start, "meta.local.extended.stata") and last_block.endswith(':'):
            add_space = view.substr(start - 1) == ':'
            #print(last_block, view.substr(start), prefix, sep='|')
            return extended_locals.get_completions(add_space)

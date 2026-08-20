"""Context-aware Stata completions backed by source and filesystem indexes."""

import glob
import os
import traceback

import sublime
import sublime_plugin

from .completions import catalog
from .completions import extended_locals


SETTINGS_FILE = "Stata.sublime-settings"
MAX_OPEN_VIEWS = 24
MAX_OPEN_VIEW_BYTES = 400_000
MAX_OPEN_TOTAL_BYTES = 1_000_000
settings = None
command_snippets = ()

DEFAULT_COMMAND_PRIORITIES = ()


def plugin_loaded():
    global settings, command_snippets
    settings = sublime.load_settings(SETTINGS_FILE)
    command_snippets = _load_command_snippets()


def _load_command_snippets():
    package_name = (__package__ or __name__).split(".", 1)[0]
    prefix = "Packages/{}/snippets/".format(package_name)
    resources = []
    for path in sublime.find_resources("*.sublime-snippet"):
        if not path.startswith(prefix):
            continue
        try:
            resources.append(sublime.load_resource(path))
        except Exception:
            traceback.print_exc()
    try:
        return catalog.snippet_candidates_from_xml(resources)
    except Exception:
        traceback.print_exc()
        return ()


class AutocompleteColonCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.run_command("insert_snippet", {"contents": " : "})
        self.view.run_command("auto_complete")


class StataCompletions(sublime_plugin.EventListener):
    """Offer useful completions without inspecting a running Stata session."""

    def on_query_completions(self, view, prefix, locations):
        if len(locations) != 1:
            return None

        point = locations[0]
        if not view.match_selector(point, "source.stata"):
            return None
        if view.match_selector(
            point, "comment, source.mata, source.python, text.tex.latex"
        ):
            return None

        line = view.line(point)
        line_before_cursor = view.substr(sublime.Region(line.begin(), point))
        context = catalog.detect_context(line_before_cursor)
        if view.match_selector(point, "string") and context.kind not in (
            "path",
            "local",
            "global",
        ):
            return None
        extended_local = view.match_selector(point, "meta.local.extended.stata")

        # Sublime view contents must be captured on the UI thread.  All source
        # parsing and filesystem work below is deferred to an async worker.
        buffer_text = view.substr(sublime.Region(0, view.size()))
        open_texts = self._open_view_texts(view)
        root_candidates = self._project_root_candidates(view)
        configured_ado_paths = self._configured_ado_path_candidates()
        configured_command_priorities = self._configured_command_priorities()
        snippet_snapshot = command_snippets
        request_view_id = view.id()
        request_change_count = view.change_count()
        request_locations = tuple(locations)

        completion_list = sublime.CompletionList()

        def resolve():
            try:
                candidates = self._build_candidates(
                    prefix=prefix,
                    line_before_cursor=line_before_cursor,
                    extended_local=extended_local,
                    buffer_text=buffer_text,
                    open_texts=open_texts,
                    root_candidates=root_candidates,
                    configured_ado_paths=configured_ado_paths,
                    configured_command_priorities=configured_command_priorities,
                    command_snippets=snippet_snapshot,
                )
                items = self._completion_items(candidates)
            except Exception:
                traceback.print_exc()
                items = []

            sublime.set_timeout(
                lambda: self._publish_if_current(
                    completion_list,
                    items,
                    view,
                    request_view_id,
                    request_change_count,
                    request_locations,
                )
            )

        sublime.set_timeout_async(resolve)
        return completion_list

    def _build_candidates(
        self,
        prefix,
        line_before_cursor,
        extended_local,
        buffer_text,
        open_texts,
        root_candidates,
        configured_ado_paths,
        configured_command_priorities,
        command_snippets,
    ):
        if extended_local:
            candidates = [
                catalog.Candidate(
                    trigger,
                    completion,
                    annotation,
                    "snippet",
                    details="Extended local macro function",
                    snippet=True,
                )
                for trigger, annotation, completion in extended_locals.get_completions(
                    add_space=line_before_cursor.endswith(":")
                )
            ]
            return catalog.dedupe_candidates(candidates)

        context = catalog.detect_context(line_before_cursor)
        roots = catalog.normalize_roots(root_candidates)
        ado_roots = catalog.sorted_union(
            roots,
            self._standard_ado_paths(),
            catalog.normalize_roots(configured_ado_paths),
        )
        open_index = catalog.index_sources((buffer_text,) + open_texts)

        if context.kind == "command":
            commands = catalog.sorted_union(
                catalog.load_command_catalog(),
                catalog.discover_ado_commands(ado_roots),
                open_index.programs,
            )
            candidates = catalog.matching_snippet_candidates(
                command_snippets, context.fragment
            )
            candidates += catalog.command_candidates(
                commands,
                context.fragment,
                priorities=configured_command_priorities,
                tiers=catalog.load_command_tiers(),
            )
        elif context.kind == "path":
            candidates = catalog.path_candidates(
                context.fragment,
                roots,
                extensions=catalog.path_extensions(line_before_cursor),
            )
        else:
            project_index = catalog.index_sources(catalog.read_project_sources(roots))
            merged_index = open_index.merged(project_index)
            if context.kind in ("local", "global"):
                candidates = catalog.symbol_candidates(
                    merged_index, context.kind, context.fragment
                )
            else:
                candidates = catalog.symbol_candidates(
                    merged_index, "symbol", context.fragment or prefix
                )

        return catalog.dedupe_candidates(candidates)

    @staticmethod
    def _project_root_candidates(view):
        roots = []
        filename = view.file_name()
        if filename:
            roots.append(os.path.dirname(filename))
        window = view.window()
        if window:
            roots.extend(window.folders())
        return tuple(roots)

    @staticmethod
    def _open_view_texts(view):
        window = view.window()
        if not window:
            return ()

        texts = []
        total_bytes = 0
        for open_view in window.views():
            if len(texts) >= MAX_OPEN_VIEWS:
                break
            if not open_view.is_valid() or open_view.id() == view.id():
                continue
            if not open_view.match_selector(0, "source.stata"):
                continue
            size = open_view.size()
            if size > MAX_OPEN_VIEW_BYTES or total_bytes + size > MAX_OPEN_TOTAL_BYTES:
                continue
            texts.append(open_view.substr(sublime.Region(0, size)))
            total_bytes += size
        return tuple(texts)

    @staticmethod
    def _configured_ado_path_candidates():
        global settings
        if settings is None:
            settings = sublime.load_settings(SETTINGS_FILE)
        value = settings.get("ado_paths", [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return ()
        return tuple(path for path in value if isinstance(path, str))

    @staticmethod
    def _configured_command_priorities():
        global settings
        if settings is None:
            settings = sublime.load_settings(SETTINGS_FILE)
        value = settings.get("command_priorities", [])
        if not isinstance(value, list):
            return DEFAULT_COMMAND_PRIORITIES
        priorities = tuple(command for command in value if isinstance(command, str))
        return priorities

    @staticmethod
    def _standard_ado_paths():
        paths = ["~/ado/personal", "~/ado/plus"]
        for prefix in ("/usr/local", "/opt"):
            paths.extend(glob.glob(os.path.join(prefix, "stata*", "ado", "site")))
        return catalog.normalize_roots(paths)

    @staticmethod
    def _publish_if_current(
        completion_list,
        items,
        view,
        request_view_id,
        request_change_count,
        request_locations,
    ):
        is_current = (
            view.is_valid()
            and view.id() == request_view_id
            and view.change_count() == request_change_count
            and tuple(region.b for region in view.sel()) == request_locations
        )
        completion_list.set_completions(
            items if is_current else [],
            sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_REORDER,
        )

    @staticmethod
    def _completion_items(candidates):
        kind_map = {
            "command": sublime.KIND_FUNCTION,
            "path": sublime.KIND_NAVIGATION,
            "snippet": sublime.KIND_SNIPPET,
            "variable": sublime.KIND_VARIABLE,
        }
        items = []
        for candidate in candidates:
            kwargs = {
                "trigger": candidate.trigger,
                "completion": candidate.completion,
                "annotation": candidate.annotation,
                "kind": kind_map.get(candidate.kind, sublime.KIND_AMBIGUOUS),
                "details": candidate.details,
            }
            if candidate.snippet:
                kwargs["completion_format"] = sublime.COMPLETION_FORMAT_SNIPPET
            items.append(sublime.CompletionItem(**kwargs))
        return items

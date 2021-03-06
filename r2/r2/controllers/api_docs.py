import re
from collections import defaultdict
from itertools import chain
import inspect
from os.path import relpath

from pylons import config
from pylons.i18n import _
from reddit_base import RedditController
from r2.lib.utils import Storage
from r2.lib.pages import BoringPage, ApiHelp

# API sections displayed in the documentation page.
# Each section can have a title and a markdown-formatted description.
section_info = {
    'account': {
        'title': _('account'),
    },
    'flair': {
        'title': _('flair'),
    },
    'links_and_comments': {
        'title': _('links & comments'),
    },
    'messages': {
        'title': _('private messages'),
    },
    'moderation': {
        'title': _('moderation'),
    },
    'misc': {
        'title': _('misc'),
    },
    'listings': {
        'title': _('listings'),
    },
    'search': {
        'title': _('search'),
    },
    'subreddits': {
        'title': _('subreddits'),
    },
    'users': {
        'title': _('users'),
    }
}

api_section = Storage((k, k) for k in section_info)

def api_doc(section, **kwargs):
    """
    Add documentation annotations to the decorated function.

    See ApidocsController.docs_from_controller for a list of annotation fields.
    """
    def add_metadata(api_function):
        doc = api_function._api_doc = getattr(api_function, '_api_doc', {})
        if 'extends' in kwargs:
            kwargs['extends'] = kwargs['extends']._api_doc
        doc.update(kwargs)
        doc['section'] = section
        doc['filepath'] = api_function.func_code.co_filename
        doc['lineno'] = api_function.func_code.co_firstlineno
        return api_function
    return add_metadata

class ApidocsController(RedditController):
    @staticmethod
    def docs_from_controller(controller, url_prefix='/api'):
        """
        Examines a controller for documentation.  A dictionary index of
        sections containing dictionaries of URLs is returned.  For each URL, a
        dictionary of HTTP methods (GET, POST, etc.) is contained.  For each
        URL/method pair, a dictionary containing the following items is
        available:

        - `doc`: Markdown-formatted docstring.
        - `uri`: Manually-specified URI to list the API method as
        - `uri_variants`: Alternate URIs to access the API method from
        - `extensions`: URI extensions the API method supports
        - `parameters`: Dictionary of possible parameter names and descriptions.
        - `extends`: API method from which to inherit documentation
        """

        root_dir = config['pylons.paths']['root']
        api_docs = defaultdict(lambda: defaultdict(dict))
        for name, func in controller.__dict__.iteritems():
            method, sep, action = name.partition('_')
            if not action:
                continue

            api_doc = getattr(func, '_api_doc', None)
            if api_doc and 'section' in api_doc and method in ('GET', 'POST'):
                docs = {}
                docs['doc'] = inspect.getdoc(func)

                if 'extends' in api_doc:
                    docs.update(api_doc['extends'])
                    # parameters are handled separately.
                    docs['parameters'] = {}
                docs.update(api_doc)

                uri = docs.get('uri') or '/'.join((url_prefix, action))
                if 'extensions' in docs:
                    # if only one extension was specified, add it to the URI.
                    if len(docs['extensions']) == 1:
                        uri += '.' + docs['extensions'][0]
                        del docs['extensions']
                docs['uri'] = uri

                # make the file path relative to the module root for use in
                # github source link generation
                if docs['filepath'].startswith(root_dir):
                    docs['relfilepath'] = relpath(docs['filepath'], root_dir)

                # add every variant to the index -- the templates will filter
                # out variants in the long-form documentation
                for variant in chain([uri], docs.get('uri_variants', [])):
                    api_docs[docs['section']][variant][method] = docs

        return api_docs

    def GET_docs(self):
        # controllers to gather docs from.
        from r2.controllers.api import ApiController, ApiminimalController
        from r2.controllers.front import FrontController
        from r2.controllers import listingcontroller

        api_controllers = [
            (ApiController, '/api'),
            (ApiminimalController, '/api'),
            (FrontController, '')
        ]
        for name, value in vars(listingcontroller).iteritems():
            if name.endswith('Controller'):
                api_controllers.append((value, ''))

        # merge documentation info together.
        api_docs = defaultdict(dict)
        for controller, url_prefix in api_controllers:
            for section, contents in self.docs_from_controller(controller, url_prefix).iteritems():
                api_docs[section].update(contents)

        return BoringPage(
            _('api documentation'),
            content=ApiHelp(
                api_docs=api_docs
            ),
            css_class="api-help",
            show_sidebar=False,
            show_firsttext=False
        ).render()

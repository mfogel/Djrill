from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives


class DjrillMessageMixin(object):
    def __init__(self, from_name=None, tags=None, track_opens=True,
            track_clicks=True, **kwargs):
        super(DjrillMessageMixin, self).__init__(**kwargs)
        self.from_name = from_name
        self.tags = self._set_mandrill_tags(tags or [])
        self.track_opens = track_opens
        self.track_clicks = track_clicks

    def _set_mandrill_tags(self, tags):
        """
        Check that all tags are below 50 chars and that they do not start
        with an underscore.

        Raise ImproperlyConfigured if an underscore tag is passed in to
        alert the user. Any tag over 50 chars is left out of the list.
        """
        tag_list = []

        for tag in tags:
            if len(tag) <= 50 and not tag.startswith("_"):
                tag_list.append(tag)
            elif tag.startswith("_"):
                raise ImproperlyConfigured(
                    "Tags starting with an underscore are reserved for "
                    "internal use and will cause errors with Mandill's API")

        return tag_list


class DjrillMessage(DjrillMessageMixin, EmailMultiAlternatives):
    content_subtype = "mandrill"


class DjrillTemplateMessage(DjrillMessageMixin, EmailMessage):
    content_subtype = 'mandrill.template'

    def __init__(self, template_name=None, template_content=None, **kwargs):
        super(DjrillTemplateMessage, self).__init__(**kwargs)
        if not template_name:
            raise RuntimeError("Template name is required")

        self.template_name = template_name
        self.template_content = template_content or []

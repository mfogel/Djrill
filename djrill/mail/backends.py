from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address
from django.utils import simplejson as json

from email.utils import parseaddr
import requests


class DjrillBackendHTTPError(Exception):
    """An exception that will turn into an HTTP error response."""
    def __init__(self, status_code, message):
        super(DjrillBackendHTTPError, self).__init__()
        self.status_code = status_code
        self.message = message

    def __str__(self):
        return u"Remote server {} error: {}".format(
                self.status_code, self.message)


class DjrillBackend(BaseEmailBackend):
    """
    Mandrill API Email Backend
    """

    api_methods = {
        'send': 'messages/send.json',
        'send-template': 'messages/send-template.json',
    }

    def __init__(self, fail_silently=False, **kwargs):
        """
        Set the API key, API url and set the action url.
        """
        super(DjrillBackend, self).__init__(**kwargs)
        self.api_key = getattr(settings, "MANDRILL_API_KEY", None)
        self.api_url = getattr(settings, "MANDRILL_API_URL", None)
        # add trailing slash to url if not present
        if not self.api_url[-1] == '/':
            self.api_url += '/'

        if not self.api_key:
            raise ImproperlyConfigured("You have not set your Mandrill api key "
                "in the settings.py file.")
        if not self.api_url:
            raise ImproperlyConfigured("You have not added the Mandrill api "
                "url to your settings.py")

    def send_messages(self, email_messages):
        if not email_messages:
            return

        num_sent = 0
        for message in email_messages:
            sent = self._send(message)
            if sent:
                num_sent += 1

        return num_sent

    def _send(self, message):
        if not message.recipients():
            return False

        payload = self._build_standard_payload(message)
        if message.content_subtype.startswith('mandrill'):
            self._update_mandrill_payload(payload, message)

        target = self._get_target(message)
        resp = requests.post(target, data=json.dumps(payload))

        if resp.status_code != 200:
            if self.fail_silently:
                return False
            data = json.loads(resp.content)
            raise DjrillBackendHTTPError(
                    resp.status_code, data['message'])
        return True

    def _get_target(self, message):
        method_name = 'send'
        if message.content_subtype == 'mandrill.template':
            method_name = 'send-template'
        return settings.MANDRILL_API_URL + self.api_methods[method_name]

    def _build_standard_payload(self, message):
        """
        Build standard message dict.

        Builds the standard dict that Django's send_mail and send_mass_mail
        use by default. Standard text email messages sent through Django will
        still work through Mandrill.
        """
        recipients_list = [
                sanitize_address(addr, message.encoding)
                for addr in message.recipients()]
        recipients = [
                {"email": e, "name": n}
                for n, e in [parseaddr(r) for r in recipients_list]]

        sender = sanitize_address(message.from_email, message.encoding)
        name, email = parseaddr(sender)

        return {
            'key': self.api_key,
            'message': {
                'text': message.body,
                'subject': message.subject,
                'from_email': email,
                'from_name': getattr(message, 'from_name', name),
                'to': recipients,
            },
        }

    def _update_mandrill_payload(self, payload, message):
        """
        Updates the payload with the mandrill-specific attributes.
        These are attributes that django send_mail() doesn't use,
        but the Mandril email classes do.
        """

        accepted_headers = {}
        if message.extra_headers:
            for k in message.extra_headers.keys():
                if k.startswith('X-') or k == 'Reply-To':
                    accepted_headers[str(k)] = message.extra_headers[k]
            payload['message'].update({'headers': accepted_headers})

        payload['message'].update({
            'tags': message.tags,
            'track_opens': message.track_opens,
            'track_clicks': message.track_clicks,
            'headers': accepted_headers,
        })

        if message.global_merge_vars:
            payload['message']['global_merge_vars'] = [
                {'name': key, 'content': value}
                for key, value in message.global_merge_vars.iteritems()
            ]

        # sending html over to mandrill
        if getattr(message, 'alternatives', None):
            if len(message.alternatives) > 1:
                raise ImproperlyConfigured(
                        "Mandrill only accepts plain text and html emails. "
                        "Please check the alternatives you have attached to "
                        "your message.")
            payload['message']['html'] = message.alternatives[0][0]

        # using a mandrill template message
        if message.content_subtype == 'mandrill.template':
            payload.update({
                'template_name': message.template_name,
                'template_content': message.template_content,
            })

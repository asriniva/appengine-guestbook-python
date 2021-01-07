#!/usr/bin/env python

# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START imports]
import os
import urllib3
from urllib.parse import urlencode, quote
import datetime

from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext.vmruntime import vmstub

import jinja2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [END imports]

DEFAULT_GUESTBOOK_NAME = 'default_guestbook'

import flask
from flask import Flask, request
app = Flask(__name__)

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent. However, the write rate should be limited to
# ~1/second.

def guestbook_key(guestbook_name=DEFAULT_GUESTBOOK_NAME):
    """Constructs a Datastore key for a Guestbook entity.

    We use guestbook_name as the key.
    """
    return ndb.Key('Guestbook', guestbook_name)


# [START greeting]
class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class Greeting(ndb.Model):
    """A main model for representing an individual Guestbook entry."""
    author = ndb.StructuredProperty(Author)
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
# [END greeting]


@app.route('/', methods=['GET'])
def get():
    # Register the VMStub with apiproxy_stub_map, so it will handle transmitting
    # API calls to the wormhole.
    os.environ['APPLICATION_ID'] = os.environ['GAE_APPLICATION']
    os.environ['HTTP_X_APPENGINE_API_TICKET'] = flask.request.headers['X-Appengine-Api-Ticket']
    os.environ['AUTH_DOMAIN'] = flask.request.environ.get('HTTP_X_APPENGINE_AUTH_DOMAIN', 'gmail.com')
    os.environ['USER_ID'] = flask.request.environ.get('HTTP_X_APPENGINE_USER_ID', '')
    os.environ['USER_EMAIL'] = flask.request.environ.get('HTTP_X_APPENGINE_USER_EMAIL', '')
    vmstub.VMStub.SetUseRequestSecurityTicketForThread(True)
    stub = vmstub.VMStub()
    vmstub.Register(stub)

    guestbook_name = flask.request.args.get('guestbook_name',
                                      DEFAULT_GUESTBOOK_NAME)
    greetings_query = Greeting.query(
        ancestor=guestbook_key(guestbook_name)).order(-Greeting.date)
    greetings = greetings_query.fetch(10)

    user = users.get_current_user()
    if user:
        url = users.create_logout_url(flask.request.url)
        url_linktext = 'Logout'
    else:
        url = users.create_login_url(flask.request.url)
        url_linktext = 'Login'

    template_values = {
        'user': user,
        'greetings': greetings,
        'guestbook_name': quote(guestbook_name),
        'url': url,
        'url_linktext': url_linktext,
        'lasttime' : memcache.get('lasttime')
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')
    return template.render(template_values)

@app.route('/sign', methods=['POST'])
def post():
    # Register the VMStub with apiproxy_stub_map, so it will handle transmitting
    # API calls to the wormhole.
    os.environ['APPLICATION_ID'] = os.environ['GAE_APPLICATION']
    os.environ['HTTP_X_APPENGINE_API_TICKET'] = flask.request.headers['X-Appengine-Api-Ticket']
    os.environ['AUTH_DOMAIN'] = flask.request.environ['HTTP_X_APPENGINE_AUTH_DOMAIN']
    os.environ['USER_ID'] = flask.request.environ['HTTP_X_APPENGINE_USER_ID']
    os.environ['USER_EMAIL'] = flask.request.environ['HTTP_X_APPENGINE_USER_EMAIL']
    vmstub.VMStub.SetUseRequestSecurityTicketForThread(True)
    stub = vmstub.VMStub()
    vmstub.Register(stub)

    #  We set the same parent key on the 'Greeting' to ensure each
    # Greeting is in the same entity group. Queries across the
    # single entity group will be consistent. However, the write
    # rate to a single entity group should be limited to
    # ~1/second.
    guestbook_name = flask.request.args.get('guestbook_name',
                                      DEFAULT_GUESTBOOK_NAME)
    greeting = Greeting(parent=guestbook_key(guestbook_name))

    if users.get_current_user():
        greeting.author = Author(
                identity=users.get_current_user().user_id(),
                email=users.get_current_user().email())

    greeting.content = str(urlfetch.fetch(flask.request.form['content']).content[:100])
    greeting.put()
    memcache.set('lasttime', str(datetime.datetime.now()))

    query_params = {'guestbook_name': guestbook_name}
    return flask.redirect('/?' + urlencode(query_params))



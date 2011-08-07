#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
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
#

import os
import datetime
import logging
import httplib2
from xml.dom.minidom import parseString

from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template


WIKI_URL = 'http://sfhomeless.wikia.com/'


class Resource(db.Model):
  """A resource pulled from the sfhomeless.net wiki.
  
  Each resource is based on an organization's page on the sfhomeless.net wiki.
  The WikiSyncTaskHandler cron syncs all the pages from the wiki into the
  datastore as Resources.
  
  Properties:
    name: The resource's name.
    wikiurl: The URL at the wiki which corresponds with this resource.
    summary: A paragraph summary of the resource.
    categories: A list of categories that this resource has been tagged with.
    address: The resource's address.
    geocoded_address: The geocoded address as a lat/long.
    phone: The resource's phone number.
    email: The resource's email address.
    website: The resource's website.
    contacts: A list of contacts (names) at the resource.
    hours: The resource's hours.
    languages: A list of the languages supported at the resource.
    image: The image (either from the wiki or a stored closeup of the map)
      associated with the resource.
    status: The status of this resource in the database.  Possible values are
      Active (if currently visible on the wiki and frontend), Incomplete (if 
      visible on the wiki but we can't pull enough information to show in the
      frontend), or Deleted (if syncs with the wiki no longer return this
      page).
    last_updated: The date and time that this resource was last synced to the
      wiki content.
  """

  name = db.StringProperty()
  wikiurl = db.StringProperty()
  summary = db.TextProperty()
  categories = db.StringListProperty()
  address = db.PostalAddressProperty()
  geocoded_address = db.GeoPtProperty()
  phone = db.PhoneNumberProperty()
  email = db.EmailProperty()
  website = db.LinkProperty()
  contacts = db.StringProperty()
  hours = db.TextProperty()
  languages = db.StringProperty()
  image = db.BlobProperty()
  status = db.StringProperty()
  last_updated = db.DateTimeProperty()


class MainHandler(webapp.RequestHandler):
  """The main site page providing a frontend to browse the resources."""

  def get(self):
    """Retrieves resources and passes them to the frontend."""

    resources = Resource().all().filter('status =', 'Active')

    template_values = {
        'resources': resources
    }
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    self.response.out.write(template.render(path, template_values))


class DirectionsHandler(webapp.RequestHandler):
  """The directions page where a user can find directions to resources."""

  def get(self):
    """Retrieves origin and destination and passes them to the frontend."""

    origin = self.request.get('origin')
    destination = self.request.get('destination')

    template_values = {
      'origin': origin,
      'destination': destination,
    }    
    path = os.path.join(os.path.dirname(__file__), 'directions.html')
    self.response.out.write(template.render(path, template_values))


def getElementValue(semantic_property, element):
  """TODO."""

  special_properties = ['Email', 'Website']
  if semantic_property in special_properties:
    return element.getAttribute('rdf:resource')
  else:
    return element.childNodes[0].nodeValue


def getResourceCategories(resource_xml):
  """TODO."""

  categories = resource_xml.getElementsByTagName('owl:Class')
  category_list = []
  for category in categories:
    text = category.getElementsByTagName('rdfs:label')[0].childNodes[0].data
    category_list.append(text)
  return category_list


def retrieveResourceInfo(resource_page):
  """TODO."""

  url = WIKI_URL + str('/index.php?title=Special:ExportRDF&page=' +
                       resource_page)
  http = httplib2.Http()
  response, content = http.request(url, 'GET')
  response_xml = parseString(content).getElementsByTagName('rdf:RDF')[0]
  
  properties = [
      'Address',
      'Phone_Number',
      'Email',
      'Website',
      'Contact-28s-29',
      'Hours',
      'Language-28s-29',
      'SummaryText'
  ]
  resource_info = {}
  name_node = response_xml.getElementsByTagName('rdfs:label')[0]
  resource_info['Name'] = name_node.childNodes[0].nodeValue
  resource_info['Categories'] = getResourceCategories(response_xml)
  resource_info['Property Success'] = False
  for semantic_property in properties:
    attr_info = response_xml.getElementsByTagName('property:' +
                                                  semantic_property)
    if attr_info:
      resource_info[semantic_property] = getElementValue(semantic_property,
                                                         attr_info[0])
      resource_info['Property Success'] = True
    else:
      resource_info[semantic_property] = None

  return resource_info


class WikiSyncTaskHandler(webapp.RequestHandler):
  """TODO."""

  # TODO(dbow): update to post when turning into a task.
  def get(self):
    """TODO."""

    # TODO(dbow): Maybe use the following maintenance script:
    # http://svn.wikimedia.org/svnroot/mediawiki/trunk/extensions\
    # /SemanticMediaWiki/maintenance/SMW_dumpRDF.php

    # TODO(dbow): Use the python library to query for all pages to
    # get the page names here.
    resource_pages = ['Bristol_Hotel']

    for resource_page in resource_pages:
      resource_info = retrieveResourceInfo(resource_page)
      logging.info(resource_info)
      resource = Resource().all().filter('wikiurl =', resource_page).get()

      if not resource:
        resource = Resource()
        resource.wikiurl = resource_page
      resource.name = resource_info['Name']
    
      if resource_info['Property Success'] == True:
        resource.summary = resource_info['SummaryText']
        resource.categories = resource_info['Categories']
        resource.address = resource_info['Address']
        # geocoded_address = 
        resource.phone = resource_info['Phone_Number']
        resource.email = resource_info['Email']
        resource.website = resource_info['Website']
        resource.contacts = resource_info['Contact-28s-29']
        resource.hours = resource_info['Hours']
        resource.languages = resource_info['Language-28s-29']
        resource.status = 'Active'
      else:
        resource.status = 'Incomplete'
      resource.last_updated = datetime.datetime.now()
      resource.put()


def main():
    application = webapp.WSGIApplication(
        [('/', MainHandler),
         ('/directions', DirectionsHandler),
         ('/task/wikisync', WikiSyncTaskHandler)],
        debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()

#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import webbrowser

from qtpy import QtGui, QtCore, QtWidgets

from carqueries import utils
from carqueries.views import TreeRow, TreeView
from carqueries.auto import AutoMake, AutoMake, AutoRecord, Distance, RecordSort

# ---------------------------------------------------------------------------- #
# -- FUNCTIONS --------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #
# -- CLASSES ----------------------------------------------------------------- #
import os
import time
import math
import urllib2

import json
from bs4 import BeautifulSoup

from carqueries import utils
from carqueries.views import TreeModel
from carqueries.auto import AutoSet, AutoRecord, Distance, RecordSort

class Session(object):
    """
    Manager for loading and saving auto records.
    """
    ZIP_COOKIES = ('ZipCode', 'PersistentZipCode')
    VERSION = 3  # version for save data forward compatability

    def __init__(self):
        """
        Initialization.
        """
        self.directory = utils.CACHE_DIR

        self.query = None
        self.zipcode = None
        self.cookies = None
        self.tree_model = None
        self.progress = dict()

        self.populate_cookies()
        self.auto_set = AutoSet.auto_load(self)

    def populate(self, query):
        """
        Populates records into this session based on the input list of
        makes/models with in the specified distance.
        """
        self.query = query
        self.set_zipcode(query.zipcode)
        self.progress = dict.fromkeys(query.auto_models, 0.0)
        self.tree_model = TreeModel(query.populate(self), self.directory)
        # self.save()
        return self.tree_model

    def populate_cookies(self):
        """
        Populates default cookies... om nom nom nom nom.
        """
        # request = urllib2.Request(DOMAIN + '?zipcode=' + zipcode)
        response = urllib2.urlopen(urllib2.Request(utils.DOMAIN))
        cookies = response.headers.get('Set-Cookie').split('; ')
        inc = lambda c: not any(c.startswith(p + '=') for p in self.ZIP_COOKIES)
        self.cookies = filter(inc, cookies)

    def update_progress(self, auto_model, progress):
        """
        Updates the overall progress loading data.
        """
        self.progress[auto_model] = progress
        overall = float(sum(self.progress.values())) / len(self.progress)
        overall *= 100
        utils.print_line('Progress: {0:.1f}% ({1})'.format(overall, auto_model))

    def set_zipcode(self, zipcode):
        """
        Updates the current session zip code.
        """
        zipcode = str(zipcode)
        if self.zipcode != zipcode:
            # zip code has changed, clear any cached records.
            self.zipcode = zipcode

    def get_page_soup(self, url, sleep=True):
        """
        Gets the soup for the specified auto records listing page.
        """
        response = self.get_page_response(url)
        if response is None:
            return None
        payload = response.read()
        if sleep:
            time.sleep(1.0)  # brief sleep to prevent DOS.
        # BeautifulSoup can handle malformed HTML unlike ElementTree.
        return BeautifulSoup(payload, 'html.parser')

    def get_page_response(self, url):
        """
        Executes a GET request on the specified URL and returns
        the urllb2 response object.
        """
        cookies = list(self.cookies)
        if self.zipcode:
            for cookie in self.ZIP_COOKIES:
                cookies.append(cookie + '=' + str(self.zipcode))
        request = urllib2.Request(url)
        request.add_header('cookie', '; '.join(cookies))
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as err:
            utils.print_line(str(err))
            utils.print_line(str(url))
            return None
        if response.getcode() != 200:
            raise RuntimeError('Request failed for URL: ' + url)
        return response

    def get_unique_values(self, columns):
        """
        Gets the list of unique values for the specified column.
        """
        entries = dict()
        for record in self.records.itervalues():
            if not record.get_is_hidden():
                data = tuple(record.data(c) for c in columns)
                entries.setdefault(data, 0)
                entries[data] += 1
        return entries

    def get_auto_model(self, make_term, model_term):
        """
        Gets the an AutoModel object by make and model tokens.
        """
        return self.auto_set.get(make_term, model_term)

    def serialize(self):
        """
        Python JSON compatible serialization.
        """
        data = dict(vars(self))
        data.pop('root', None)
        data.pop('directory', None)
        data.pop('progress', None)
        make_models = data.pop('make_models', None)
        data['make_models'] = [m.serialize() for m in make_models]
        data['records'] = [r.serialize() for r in self.records.itervalues()]
        data['hidden'] = [r.get_row_path() for r in self.iter_tree() if r.hidden]
        data['columns'] = [r.name for r in self.columns]
        data['groupings'] = [c.name for c in self.groupings]
        data['version'] = self.VERSION
        return data

    def load(self, directory=None):
        """
        Loads all cached records from the specified directory.
        """
        return True

    def save(self, directory=None):
        """
        Saves all loaded records to the specified directory.
        """
        if directory is None:
            directory = self.directory
        else:
            self.directory = directory
        encoder = json.JSONEncoder()
        data_str = encoder.encode(self.serialize())
        path = os.path.join(directory, 'session.dat')
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(path, 'w') as output_fd:
            output_fd.write(data_str)

    def iter_tree(self):
        """
        Iterates over all rows in the tree.
        """
        return self.root.iter_descendants(include_self=False)

    def __getitem__(self, index):
        """
        Overrides Python indexed look up.
        """
        return self.records[index]

    def __len__(self):
        """
        Overrides Python indexed look up.
        """
        return len(self.records)

    def __iter__(self):
        """
        Defines custom Python iteration behavior.
        """
        return iter(self.records)


class AutoQuery(object):
    """
    Manages auto record query parameters.
    """
    NUM_RECORDS = 100

    @classmethod
    def deserialize(cls, data):
        """
        Deserializes data from a JSON representation.
        """
        return cls(**data)

    @classmethod
    def defaults(cls, session):
        """
        Generates default query values for testing and initialization.
        """
        tokens = (# ('nissan', 'altima'),
                  # ('honda', 'civic'),
                   ('toyota', 'camry'),
                   ('ford', 'taurus'))
        auto_models = (session.get_auto_model(*t) for t in tokens)
        return cls(filter(None, auto_models), 75228,
                   year=(2012, 2017),
                   price=(15000, 25000),
                   distance=Distance.M50)

    def __init__(self, auto_models, zipcode,
                 year=None, price=None, distance=None):
        """
        Initialization.
        """
        self.auto_models = auto_models
        self.zipcode = zipcode
        if year:
            year = [int(round(int(y))) for y in year]
        self.year = year
        if price:
            price = [int(round(int(p), -3)) for p in price]
        self.price = price
        if distance is None:
            distance = Distance.M100
        self.distance = distance
        self.records = set()
        self.loadtime = None

    def populate(self, session):
        """
        Populates records using the query information.
        """
        self.records.clear()
        for auto_model in self.auto_models:
            session.update_progress(auto_model, 0.0)
            for records, progress in self._iter_records(session, auto_model):
                self.records.update(records)
                session.update_progress(auto_model, progress)
            # session.update_progress(auto_model, 1.0)
        self.loadtime = time.time()
        records = list(self.records)
        records.sort()
        return records

    def _iter_records(self, session, model):
        """
        Iterates over the parsed auto record page results.
        """
        # parse records from page results.
        num_pages = 1
        page = 1
        while page <= num_pages:
            url = model.get_for_sale_url(page, self)
            soup = session.get_page_soup(url)
            records = dict()
            if soup is not None:
                records = AutoRecord.from_soup(model, soup)
            if page == 1:
                # pares the total number of expected pages.
                num_pages = self._get_num_pages(soup)
            # each iteration yields two values:
            # dictionary of parsed records, fractional progress in total pages
            progress = float(page) / float(num_pages)
            yield records, progress
            if soup is None:
                # no response or unparsable result
                break
            page += 1

    def _get_num_pages(self, soup):
        """
        Gets the number of automotive record pages indicated in the HTML soup.
        """
        if soup is None:
            return 1
        # page the total number of pages of results from HTML soup.
        for span in soup.find_all('span', class_='filter-highlight'):
            span_text = span.text.strip().lower()
            if span_text.endswith(' cars'):
                total = utils.parse_number(span_text)
                return max(1, int(math.ceil(float(total) / self.NUM_RECORDS)))
        return 1

    def get_url_params(self, page=None):
        """
        Gets the list of key/value argument pairs used to
        generate an auto database query URL.
        """
        params = list()
        if self.year:
            params.append(('year', '{0:d}-{1:d}'.format(*self.year)))
        if self.price:
            params.append(('pricerange', '{0:d}-{1:d}'.format(*self.price)))
        params.append(('distance', str(self.distance)))
        if page:
            params.append(('p', str(page)))
        params.append(('nr', self.NUM_RECORDS))
        params.append(('s', RecordSort.NEW_TO_OLD))
        return params

    def serialize(self):
        """
        Retrieves a JSON serializable representation of this object.
        """
        data = dict()
        for key, value in vars(self).iteritems():
            if value is not None:
                data[key] = value
        data['auto_models'] = self.auto_models
        return data


class ViewSettings(object):
    """
    An object that stores the users record view configuration.
    """

#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import os
import datetime

from carqueries import utils


# ---------------------------------------------------------------------------- #
# -- GLOBALS ----------------------------------------------------------------- #

# for determining vehical age
CURRENT_YEAR = datetime.datetime.now().year


# ---------------------------------------------------------------------------- #
# -- ENUMERATORS ------------------------------------------------------------- #

class Distance(object):
    """
    Enumeration of KBB supported distances to filter queries by.
    """
    M25 = 25
    M50 = 50
    M100 = 100


class RecordSort(object):
    """
    Enumeration of KBB supported sort orders for listing queries.
    """
    PRICE_ASC = 'derivedpriceasc'
    PRICE_DESC = 'derivedpricedesc'
    OLD_TO_NEW = 'yearasc'
    NEW_TO_OLD = 'yeardesc'

# ---------------------------------------------------------------------------- #
# -- CLASSES ----------------------------------------------------------------- #

class BaseAuto(object):
    """
    Base class for the AutoMake/AutoModel classes below.
    """
    JSON_KEY = None
    DROPDOWN_ID = None

    @classmethod
    def from_json(cls, parent, data):
        """
        Parses auto information from an XML element.
        """
        return [cls.deserialize(parent, m) for m in data[cls.JSON_KEY]]

    @classmethod
    def from_soup(cls, parent, soup):
        """
        Loads listings from a parsed drop-down input.
        """
        result = list()
        if soup is None:
            return result
        drop_down = soup.find(id=cls.DROPDOWN_ID)
        if drop_down is None:
            return result
        for option in drop_down.find_all('option'):
            token = str(option.get('value', 'none')).lower()
            label = str(option.get_text().strip())
            if token != 'all':
                result.append(cls(parent, token, label))
        return result

    @classmethod
    def deserialize(cls, parent, data):
        """
        Deserializes data from a JSON representation.
        """
        return cls(parent, data['token'], data['label'])

    def __init__(self, parent, token, label):
        """
        Initialization.
        """
        self.parent = parent
        self.token = token
        self.label = label

    def serialize(self):
        """
        Retrieves a JSON serializable representation of this object.
        """
        return dict(token=self.token, label=self.label)

    @property
    def title(self):
        """
        A unique human readable title for this info.
        """
        return self.label

    @property
    def uuid(self):
        """
        A unique identifier for this info.
        """
        return self.token

    def matches(self, value):
        """
        Tests if this object's label or token matches the input string.
        """
        return value in (self.token, self.label, self.uuid)

    def __eq__(self, other):
        """
        Comparison for sorting behavior.
        """
        if isinstance(other, type(self)):
            return self.uuid == other.uuid
        return False

    def __ne__(self, other):
        """
        Comparison for soring behavior.
        """
        return not self.__eq__(other)

    def __cmp__(self, other):
        """
        Comparison for soring behavior.
        """
        if isinstance(other, type(self)):
            return cmp(self.uuid, other.uuid)
        return 1

    def __str__(self):
        """
        Overrides Python string representation.
        """
        return self.title

    def __hash__(self):
        """
        Determines a hash representation.
        """
        return hash(self.uuid)


class AutoMake(BaseAuto):
    """
    Represents an automotive manufacturer (e.g. Ford, Toyota, Aston Martin).
    """
    JSON_KEY = 'makeS'
    DROPDOWN_ID = 'makeDropdown'

    @classmethod
    def deserialize(cls, parent, data):
        """
        Deserializes data from a JSON representation.
        """
        make = super(AutoMake, cls).deserialize(parent, data)
        make.models = AutoModel.from_json(make, data)
        return make

    def __init__(self, parent, token, label):
        """
        Initialization.
        """
        self.models = list()
        super(AutoMake, self).__init__(parent, token, label)

    def serialize(self):
        """
        Retrieves an XML element to represent this kbb auto information.
        """
        data = super(AutoMake, self).serialize()
        # serialzie auto models by this make.
        data[AutoModel.JSON_KEY] = [m.serialize() for m in self.models]
        return data


class AutoModel(BaseAuto):
    """
    Represents a specific model of car (e.g. Ford Model-T).
    """
    JSON_KEY = 'models'
    DROPDOWN_ID = 'modelDropdown'

    @classmethod
    def from_xml(cls, parent, element):
        """
        Parses auto information from an XML element.
        """
        return [cls(parent, e['token'], e.text) for e in element.iter(cls.TAG)]

    @property
    def make(self):
        """
        A meaningful alias for parent. 
        """
        return self.parent

    @property
    def title(self):
        """
        Gets a human readable title '<make> <model>".
        """
        return '{0} {1}'.format(self.make.label, self.label)

    @property
    def uuid(self):
        """
        A unique identifier for this info.
        """
        return '{0}_{1}'.format(self.make.token, self.token)

    def get_url_args(self):
        """
        Gets the URL arguments used to construct a query on this auto model.
        """
        return ('cars-for-sale', 'cars', self.make.token, self.token)

    def get_for_sale_url(self, page, query):
        """
        Determines a url that presents auto records of this
        make and model use the input filters.
        """
        args = self.get_url_args()
        params = query.get_url_params(page)
        return utils.get_url(args, params)


class AutoRecord(BaseAuto):
    """
    Represents a database record for a specific for-sale auto record.
    """
    NUMERIC_KEYS = ('year', 'price', 'mileage', 'distance',
                    'current-index', 'listing-id', 'owner-id')
    LISTING_TYPES = {
                     'js-used-listing':'used',
                     'js-new-listing':'new',
                     'js-certified-listing':'certified'
                     }
    DEFAULTS = dict(
        sale_type='Unknown', title='Unknown', doors='Unknown',
        style='Unknown', engine='Unknown', dealer='Unknown',
        distance='Unknown', interior='Unknown', exterior='Unknown',
        transmission='Unknown', thumb='', image='',
        year=0, mileage=0, price=0, index=0,
        listing_id=0, owner_id=0,
        html_class=list()
        )

    @classmethod
    def from_soup(cls, auto_model, soup):
        """
        Parse auto records from page soup.
        """
        records = set()
        for element in soup.find_all(cls._find_listing):
            records.add(cls.parse_record(auto_model, element))
        return records

    @staticmethod
    def _find_listing(soup):
        """
        Indicates if the input HTML element is an automotive listing.
        """
        if soup is not None and soup.name == 'div' and soup.has_attr('class'):
            return 'listing' in soup.get('class')
        return False

    @classmethod
    def parse_record(cls, auto_model, element):
        """
        Loads a auto record from a BeautifulSoup element.
        """
        html_classes = element['class']
        kwargs = dict(cls=html_classes,
                      thumbnail=None,
                      auto_model=auto_model)
        for html_cls in html_classes:
            if html_cls in cls.LISTING_TYPES:
                kwargs['sale_type'] = cls.LISTING_TYPES[html_cls]
                break
        price = element.find('div', class_='price-info')
        kwargs['price'] = price.span.text.strip() if price else None
        anchor = element.find('a', class_='js-vehicle-name')
        kwargs['title'] = str(anchor.text.strip()) if anchor else None
        anchor = element.find('a', class_='js-vehicle-image')
        if anchor is not None:
            img = anchor.find('img')
            if img is not None and img.get('data-src'):
                kwargs['thumbnail'] = 'http:' + img['data-src']
        # kwargs['thumb'] = 'http:' + anchor.div['data-background-image']
        for key in ('current-index', 'engine', 'listing-id',
                    'listing-type', 'manufacturer', 'owner-id'):
            kwargs[key.replace('-', '_')] = str(element.get('data-' + key))
        for paragraph in element.find_all('p'):
            key, value = cls.parse_data_element(paragraph)
            if key and value:
                kwargs[key] = value
        # parse numeric values from strings
        for key in cls.NUMERIC_KEYS:
            kwargs[key] = utils.parse_number(kwargs.get(key, None))
        if kwargs['title']:
            # parse information from the title of the listing.
            tokens = [t.strip('._ ') for t in kwargs['title'].split(' ')]
            years = [int(t) for t in tokens if t.isdigit()]
            # cars didn't exist before 1980
            years = [t for t in years if t > 1980]
            if years:
                kwargs['year'] = years[0]
            # strip tokens we already know from the title
            strip_tokens = [auto_model.make.label, auto_model.label]
            strip_tokens += ['used', 'new', 'certified']
            strip_tokens += [y for y in years]
            strip_tokens = [str(t).lower() for t in strip_tokens]
            if any(t.lower() == 'certified' for t in tokens):
                kwargs['sale_type'] = 'certified'
            style = [t for t in tokens if t.lower() not in strip_tokens]
            if style:
                # anything left is typically the car body type or trim
                kwargs['style'] = ' '.join(style)
        return cls(**kwargs)

    @classmethod
    def parse_data_element(cls, element):
        """
        Parse a data element.
        """
        html_cls = element.get('class')
        if 'paragraph-two' not in html_cls:
            return None, None
        key = None
        value = element.text.strip()
        for name in ('dealer-name', 'distance'):
            if name in html_cls:
                key = name
                break
        else:
            if ':' in value:
                key, _, value = value.partition(':')
        if not (key and value):
            return None, None
        key = key.strip().lower()
        value = value.strip()
        if key == 'trans.':
            key = 'transmission'
        return str(key), str(value)

    def __init__(self, auto_model, **kwargs):
        """
        Initialization.
        """
        self.auto_model = auto_model
        self.fields = dict(self.DEFAULTS)
        self.fields.update(kwargs)
        token = kwargs['listing_id']
        label = kwargs['title']
        super(AutoRecord, self).__init__(auto_model, token, label)

    def get_url(self):
        """
        Gets the URL to this auto record's page.
        """
        return utils.get_url(('cars-for-sale', self.listing_id))

    def serialize(self):
        """
        JSON safe serialization.
        """
        return dict(self.fields)

    def data(self, column):
        """
        Retrieves the data associated with this record
        for the specified view column.
        """
        return self.fields.get(column.name)

    @property
    def sale_type(self):
        sale_type = self.fields['sale_type'].lower()
        title = self.fields['title'].lower()
        if 'certified' in title or sale_type == 'certified':
            return 'C'
        if sale_type == 'used':
            return 'U'
        if sale_type == 'new':
            return 'N'
        return sale_type

    @property
    def title(self):
        if self.fields['style'] != 'Unknown':
            return self.fields['style']
        return self.fields['title']

    @property
    def thumbnail(self):
        """
        The URL of the thumbnail for this for-sale record.
        """
        return self.fields['thumbnail']

    @property
    def num_records(self):
        return 0 if self.hidden else 1

    @property
    def doors(self):
        return self.fields['doors']

    @property
    def style(self):
        return self.fields['style']

    @property
    def engine(self):
        return self.fields['engine']

    @property
    def dealer(self):
        return self.fields['dealer-name']

    @property
    def distance(self):
        return self.fields['distance']

    @property
    def interior(self):
        return self.fields['interior']

    @property
    def exterior(self):
        return self.fields['exterior']

    @property
    def transmission(self):
        return self.fields['transmission']

    @property
    def year(self):
        return self.fields['year']

    @property
    def mileage(self):
        return self.fields['mileage']

    @property
    def price(self):
        return self.fields['price']

    @property
    def ttl(self):
        """
        Gets the estimated tax title and license fees.
        """
        tax = self.price * 0.0625
        title = 50  # rough estimate
        return tax + title

    @property
    def total(self):
        """
        Gets the estimated out-the-door price for this record.
        """
        return self.price + self.ttl

    @property
    def listing_id(self):
        return self.fields['listing_id']

    @property
    def owner_id(self):
        return self.fields['owner_id']

    @property
    def html_class(self):
        return self.fields['html_class']

    @property
    def age(self):
        return CURRENT_YEAR - self.year

    @property
    def quality(self):
        """
        Retrieves a derived number representing the
        suggested quality of the auto.
        """
        quality = float(self.price) / 500.0
        quality -= float(self.mileage) / 10000.0
        quality -= float(self.age) / 2.0
        return int(round(quality))

    def __hash__(self):
        """
        Handles the hash representation of this auto record.
        """
        return hash(self.listing_id)

    def __eq__(self, other):
        """
        Equalty operator override.
        """
        if isinstance(other, AutoRecord):
            return self.listing_id == other.listing_id
        return False

    def __ne__(self, other):
        """
        Inequalty operator override.
        """
        if isinstance(other, AutoRecord):
            return self.listing_id != other.listing_id
        return True

    def __cmp__(self, other):
        """
        Overrides Python comparison/sorting behavior.
        """
        if not isinstance(other, AutoRecord):
            return 1
        return cmp(self.title, other.title)

    def __str__(self):
        """
        String representation.
        """
        return ' '.join(str(s) for s in (self.style, self.sale_type, self.year))


class AutoSet(object):
    """
    A set of auto make/model records.
    """
    CACHE_NAME = 'make_models.json'
    
    @classmethod
    def auto_load(cls, session, path=None):
        """
        Loads auto make/model information from either a locally cached file
        or from KBB. 
        """
        auto_set = cls(path)
        if os.path.isfile(auto_set.path):
            auto_set.load()
        else:
            auto_set.refresh(session)
            auto_set.save()
        return auto_set
            
    def __init__(self, path=None):
        """
        Initialization.
        """
        if path is None:
            path = os.path.join(utils.RESOURCES, self.CACHE_NAME)
        self.makes = set()
        self.models = set()
        self.makes_by_id = dict()
        self.models_by_id = dict()
        self.path = path
    
    def iter_makes(self):
        """
        Iterates over the automotive makes in the set.
        """
        return iter(sorted(self.makes))

    def iter_models(self):
        """
        Iterates over the automotive models in the set.
        """
        return iter(sorted(self.models))
    
    def get_make(self, make_term):
        """
        Gets the automotive make by a search string.
        """
        for make in self.makes:
            if make.matches(make_term):
                return make
        return None
    
    def get(self, make_term, model_term):
        """
        Gets the automotive model by make and model search strings.
        """
        make = self.get_make(make_term)
        if make is not None:
            for model in make.models:
                if model.matches(model_term):
                    return model
        return None

    def load(self):
        """
        Loads a cached list of auto make/models from the specified JSON file.
        """
        with utils.InputFile(self.path, 'r') as input_fd:
            serialized = input_fd.read_json()
        self.populate([AutoMake.deserialize(None, s) for s in serialized])

    def save(self):
        """
        Saves the auto make/models to the specified JSON file.
        """
        with utils.OutputFile(self.path) as output_fd:
            output_fd.write_json([k.serialize() for k in self.makes])

    def refresh(self, session):
        """
        Refreshes all Auto Make/Model listings from kbb.
        """
        for_sale = (utils.CAR_FOR_SALE,)
        soup = session.get_page_soup(utils.get_url(for_sale))
        makes = AutoMake.from_soup(None, soup)
        for make in makes:
            params = dict(atcmakecode=make.token)
            url = utils.get_url(for_sale, params)
            soup = session.get_page_soup(url, sleep=False)
            make.models = AutoModel.from_soup(make, soup)
        self.populate(makes)

    def populate(self, makes):
        """
        Repopulates the data in this from the input list of auto makes.
        """
        self.makes = set(makes)
        self.makes_by_id = dict((k.uuid, k) for k in self.makes)

        self.models = set(utils.flatten(k.models for k in self.makes))
        self.models_by_id = dict((m.uuid, m) for m in self.models)

    def __getitem__(self, key):
        """
        Provides dictionary like access to the set.
        """
        if key in self.models_by_id:
            return self.models_by_id[key]
        if key in self.makes_by_id:
            return self.makes_by_id[key]
        raise KeyError('Unknown auto token "{0}".'.format(key))

    def __len__(self):
        """
        Retrieves the number of unique automotive models in this set.
        """
        return len(self.models)

    def __iter__(self):
        """
        Iterates over the automtive models in this set.
        """
        return self.iter_models()



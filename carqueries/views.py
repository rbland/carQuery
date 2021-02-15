#!/usr/bin/env python

# ---------------------------------------------------------------------------- #
# -- IMPORTS ----------------------------------------------------------------- #

import math
import webbrowser

from qtpy import QtGui, QtCore, QtWidgets

from carqueries import utils
from carqueries.auto import AutoRecord

# ---------------------------------------------------------------------------- #
# -- CLASSES ----------------------------------------------------------------- #

class TreeView(QtWidgets.QTreeView):
    """
    The main tree displaying all auto records.
    """
    CSS = '''
QHeaderView::section { 
    background-color: #646464 
}

QTreeView::item:hover {
  background-color: #963;
}

QTreeView::item:selected:active{
  background-color: #d83;
}

QTreeView::item:selected:!active{
    background-color: #543;
}
'''

    def __init__(self, parent=None):
        """
        Initialzation.
        """
        self._expanded = None
        QtWidgets.QTreeView.__init__(self, parent)
        self.proxy = ProxyTreeModel()

        # initialize view styling.
        self.setAlternatingRowColors(True)
        self.setStyleSheet(self.CSS)
        header = self.header()
        header.setVisible(True)
        header.setStretchLastSection(False)
        # header.sortIndicatorChanged.connect(self.sort_by_column)
        self.setSortingEnabled(True)
        self.setWordWrap(True)
        self.doubleClicked.connect(self.double_click)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

    def set_model(self, model):
        """
        Rebuilds the tree view from a new model object.
        """
        self.proxy.setSourceModel(model)
        self.setModel(self.proxy)
        self.resize_columns()
        
    def resize_columns(self):
        """
        Resizes the columns of the view to their default sizes.
        """
        header = self.header()
        model = self.model().sourceModel()
        for i, column in enumerate(model.columns):
            if column.width > 0:
                header.setSectionResizeMode(i, QtWidgets.QHeaderView.Fixed)
                header.resizeSection(i, column.width)
            else:
                header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
                
    def double_click(self, index):
        """
        Callback when the tree is double clicked.
        """
        if index and index.isValid():
            index = self.proxy.mapToSource(index)
            row_obj = index.internalPointer()
            if isinstance(row_obj, AutoRecord):
                webbrowser.open_new_tab(row_obj.get_url())

    def get_row_index(self, row):
        """
        Gets the view's model index from the specified row.
        """
        index = getattr(row, 'index', None)
        if index is None:
            return QtCore.QModelIndex()
        return self.proxy.mapFromSource(index)

    def get_selected_rows(self):
        """
        Gets the list of currently selected row objects.
        """
        rows = list()
        for index in self.selectedIndexes():
            if index.isValid():
                index = self.proxy.mapToSource(index)
                if index.isValid():
                    row = index.internalPointer()
                    if isinstance(row, TreeRow) and row not in rows:
                        rows.append(row)
        return rows


class TreeModel(QtCore.QAbstractItemModel):
    """
    The data model of all automtive records displayed in the application's main view.
    """
    def __init__(self, records, directory, **kwargs):
        """
        Initialization.
        """
        self.records = records
        self.directory = directory 
        self.columns = TreeColumns.all()
        self.groupings = [TreeColumns.dealer, TreeColumns.model]
        QtCore.QAbstractItemModel.__init__(self, **kwargs)
        self.root = RootRow()
        self.root.populate(self, None)

    def flags(self, index):
        """
        Retrieves the model flags associated with the specified index.
        """
        if index.isValid():
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        return 0
        
    def index(self, row, col, parent_idx=None):
        """
        Reimplemented from QAbstractItemModel to retrieve
        an index for the specified position.
        """
        parent = self.root
        if parent_idx and parent_idx.isValid():  
            parent = parent_idx.internalPointer()  
        if not QtCore.QAbstractItemModel.hasIndex(self, row, col, parent_idx): 
            # invalid index requested.
            return QtCore.QModelIndex()  
        child = parent[row]
        if not isinstance(child, TreeRow):
            return QtCore.QModelIndex()  
        return QtCore.QAbstractItemModel.createIndex(self, row, col, child)

    def parent(self, index=None):
        """
        Reimplemented from QAbstractItemModel to retrieve
        the parent index of the specified child index.
        """
        if index and index.isValid():  
            row_obj = index.internalPointer()
            parent_row = row_obj.parent
            if type(parent_row) is TreeGroup:  
                return QtCore.QAbstractItemModel.createIndex(self, index.row(),
                                                             0, parent_row)
        return QtCore.QModelIndex()
        
    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        """
        Reimplemented from QAbstractItemModel to retrieve column headers.
        """
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole:
                return self.columns[section].label
            if role == QtCore.Qt.TextAlignmentRole:
                return QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter
        return None
        
    def rowCount(self, index=None):
        """
        Reimplemented from QAbstractItemModel to retrieve the row count.
        """
        row_obj = self.root
        if index and index.isValid():
            if index.column() != 0:
                return 0
            row_obj = index.internalPointer()
        return len(row_obj)

    def columnCount(self, parent=None):
        """
        Reimplemented from QAbstractItemModel to retrieve the column count.
        """
        return len(self.columns)
        
    def data(self, index, role=None):
        """
        Reimplemented from QAbstractItemModel to retrieve
        data for the specified index.
        """
        if not index.isValid():  
            return None  
        row_obj = index.internalPointer()  
        if not isinstance(row_obj, TreeRow):
            return None
        col = self.columns[index.column()]
        if role == QtCore.Qt.DisplayRole:  
            return row_obj.label(col)
        if role == QtCore.Qt.DecorationRole:
            return row_obj.decoration(col)
        if role == QtCore.Qt.SizeHintRole:
            return row_obj.size(col)
        if role == QtCore.Qt.TextAlignmentRole:
            return QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter
        if role == QtCore.Qt.ForegroundRole:
            if row_obj.hidden:
                return QtGui.QBrush(QtGui.QColor(120, 120, 120))
            else:
                return QtGui.QBrush(QtGui.QColor(230, 230, 230))
        return None

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
            
    def iter_tree(self):
        """
        Iterates over all rows in the tree.
        """
        return self.root.iter_descendants(include_self=False)


class ProxyTreeModel(QtCore.QSortFilterProxyModel):
    """
    The proxy model that wraps the main auto model to sort and filter records.
    """
    def __init__(self):
        """
        Initialization.
        """
        self.show_hidden = False
        QtCore.QSortFilterProxyModel .__init__(self)

    def lessThan(self, left_idx, right_idx):
        """
        The less than operation handles proxy model sorting.
        """
        left_data = None
        right_data = None
        model = self.sourceModel()
        if left_idx.isValid():
            left_row = left_idx.internalPointer()
            col = model.columns[left_idx.column()]
            left_data = left_row.data(col)
        if right_idx.isValid():
            right_row = right_idx.internalPointer()
            col = model.columns[right_idx.column()]
            right_data = right_row.data(col)
        return cmp(left_data, right_data) < 0

    def filterAcceptsRow(self, row, parent):
        """
        Overridden to control filtering of hidden rows.
        """
        if self.show_hidden:
            return True
        parent_row = parent.internalPointer()
        if parent_row is None:
            parent_row = self.sourceModel().root
        return not parent_row[row].hidden
    

class TreeColumn(object):
    """
    A column in the main auto records tree view.
    """
    # index to recognize column declaration order.
    INDEX = 0

    def __init__(self, label, data_type, width=50,
                 format_str=None, hidden=False):
        """
        Initialization.
        """
        self.name = None
        self.label = label
        self.data_type = data_type
        self.number = issubclass(data_type, (float, int))
        self.width = width
        self.format_str = format_str
        self.hidden = hidden
        self.index = self.INDEX
        type(self).INDEX += 1
    
    def get_header(self, padded=False):
        """
        Gets a printable header label.
        """
        if padded:
            return self.label.ljust(self.width)
        return self.label

    def get_average(self, values):
        """
        Gets the average of the input values for this column.
        """
        if self.number:
            if not values:
                return 0
            return float(sum(values)) / float(len(values))
        if len(set(values)) == 1:
            # a single common value.
            return values[0]
        return '---'

    def data_to_label(self, data, padded=None):
        """
        Retrieves a human readable label for the specified string.
        """
        if data is None:
            return ''
        try:
            data = self.data_type(data)
        except (ValueError, TypeError):
            data_str = ''
        else:
            if self.format_str:
                data_str = self.format_str.format(data)
            else:
                data_str = str(data)
        if padded:
            data_str = data_str.ljust(padded)
        return data_str
        
    def __cmp__(self, other):
        """
        Python comparison for sorting.
        """
        if isinstance(other, TreeColumn):
            return cmp(self.index, other.index)
        return 1
        

class TreeColumns(object):
    """
    Enumeration of table columns.
    """
    title = TreeColumn('Title', str, -1)
    year = TreeColumn('Year', int, 50)
    # num_records = TreeColumn('Num Records', int, 80)
    make = TreeColumn('Make', str, 100, hidden=True)
    model = TreeColumn('Model', str, 100, hidden=True)
    image = TreeColumn('Image/Count', int, 152, '{0} Vehicles')
    sale_type = TreeColumn('Type', str, 40)
    dealer = TreeColumn('Dealer', str, 120)
    distance = TreeColumn('Distance', int, 80, format_str='{0} mi')
    mileage = TreeColumn('Mileage', int, 80, format_str='{0:,d} mi')
    quality = TreeColumn('Quality', float, 60, format_str='{0:.1f}')
    price = TreeColumn('Price', int, 60, format_str='${0:,d}')
    ttl = TreeColumn('TTL', int, 60, format_str='${0:,d}')
    total = TreeColumn('Total', int, 60, format_str='${0:,d}')

    @classmethod
    def all(cls):
        """
        Gets the ordered list of table columns.
        """
        columns = list()
        for key, value in vars(cls).iteritems():
            if isinstance(value, TreeColumn):
                value.name = key.lower()
                if not value.hidden:
                    columns.append(value)
        columns.sort()
        return columns

    @classmethod
    def get(cls, name):
        """
        Gets a column object by name.
        """
        return getattr(cls, name.upper(), None)


class TreeRow(object):
    """
    Abstract base class for a auto model row.
    """
    def __init__(self, row_id):
        """
        Initialization.
        """
        self.hidden = False
        self.row_id = str(row_id).lower()
        # the root data model object.
        self.model = None
        # The QModelIndex associated with this row.
        self.index = None
        # the parent row object to be populated later.
        self.parent = None
        # the child rows of this row to be populated later.
        self.children = list()
        # the auto records included in row to be populated later.
        self.records = list()

    def get_row_id(self):
        """
        Retrieves a persistent ID that identifies this tree row.
        """
        return self.row_id

    def get_row_path(self):
        """
        Gets a unique row path that identifies this row in the tree.
        """
        row_ids = [r.row_id for r in self.iter_ancestors(include_self=True)]
        return '/'.join(str(i) for i in reversed(row_ids))

    def set_hidden(self, hidden):
        """
        Assigns the hidden state of this row.
        """
        self.hidden = hidden

    def get_is_hidden(self):
        """
        Determines if this row is hidden or if any ancestor is hidden.
        """
        for row in self.iter_ancestors(include_self=True):
            if row.hidden:
                return True
        return False

    def populate(self, model, parent):
        """
        Abstract method to populate the list of child rows.
        """
        raise NotImplemented

    def populate_index(self, row, parent_index):
        """
        Pouplates an index for all rows in the tree.
        """
        self.index = self.model.index(row, 0, parent_index)
        for row, child in enumerate(self.children):
            child.populate_index(row, self.index)

    def clear(self):
        """
        Clears all cached records.
        """
        for child in self.children:
            child.clear()
        self.records[:] = list()
        self.children[:] = list()

    def label(self, column):
        """
        Retrieves the label from this row for the specified column.
        """
        data = self.data(column)
        return column.data_to_label(data)

    def data(self, column):
        """
        Retrieves model data for this make/model.
        """
        if hasattr(self, column.name):
            return getattr(self, column.name)
        return self.get_average(column)

    def decoration(self, column):
        """
        Virtual method to get custom cell decoration for this row.
        """
        return None

    def size(self, column):
        """
        Virtual method to get the size hint for the specified column of this row.
        """
        return QtCore.QSize(column.width, self.get_row_height())

    def print_tree(self, depth=0):
        """
        Debugging method that prints all tree rows.
        """
        utils.print_line('  ' * depth + self.title)
        for child in self.children:
            child.print_tree(depth + 1)

    def iter_ancestors(self, include_self=False):
        """
        Iterates over the ancestors of this row.
        """
        parent = self if include_self else self.parent
        while isinstance(parent, TreeRow):
            yield parent
            parent = getattr(parent, 'parent', None)

    def iter_descendants(self, include_self=False):
        """
        Iterates over the ancestors of this row.
        """
        if include_self:
            yield self
        for child in self.children:
            for descendant in child.iter_descendants(True):
                yield descendant

    def get_row_height(self):
        """
        Virtual method to retreive the height hint for this row.
        """
        return 40

    def get_average(self, column):
        """
        Gets the average value for all records in the hierarchy
        below this row for the specified column.
        """
        values = self.get_values(column)
        return column.get_average(values)

    def get_values(self, column):
        """
        Gets the list of values from the child records for the specified column.
        """
        values = [r.data(column) for r in self.records]
        return [v for v in values if v is not None]
        
    def get_parent_records(self):
        """
        Gets the list of records from the parent row.
        """
        return list(self.parent.records)
         
    def get_is_leaf(self):
        """
        Indicates if this row is a leaf level node.
        """
        return False

    def get_stats(self, column):
        """
        Gets a dictionary stats about the specified column.
        """
        values = self.get_values(column)
        if not values:
            dict(mean=0, minimum=0, maximum=0, stddev=0, count=0)
        num_items = len(values)
        mean = sum(values) / num_items
        diffs = [x - mean for x in values]
        sq_diffs = [d ** 2 for d in diffs]
        stats = dict()
        stats['stddev'] = math.sqrt(sum(sq_diffs) / num_items)
        stats['mean'] = mean
        stats['count'] = num_items
        stats['minimum'] = min(values)
        stats['maximum'] = max(values)
        stats['range'] = stats['maximum'] - stats['minimum']
        stats['median'] = (float(stats['range']) / 2.0) + stats['minimum']
        return stats

    @property
    def num_records(self):
        if self.hidden or not self.children:
            return 0
        return sum(c.num_records for c in self.children)

    @property
    def image(self):
        return self.num_records

    def __getitem__(self, index):
        """
        Overrides Python indexed look up.
        """
        return self.children[index]

    def __len__(self):
        """
        Gets the number of child rows for this tree row.
        """
        if self.get_is_leaf():
            return 0
        return len(self.children)


class TreeGroup(TreeRow):
    """
    A row in the auto record tree that groups instances with a common field.
    """
    def __init__(self, column, matcher, depth, row_id=None):
        """
        Initialization.
        """
        self.column = column
        self.matcher = matcher
        self.depth = depth
        self.title = str(matcher)
        if row_id is None:
            row_id = '{0}_{1}'.format(column.name, matcher)
        super(TreeGroup, self).__init__(row_id)

    def populate(self, model, parent):
        """
        Populate child information into this tree row.
        """
        self.model = model
        self.parent = parent
        self.records = [r for r in self.get_parent_records()
                        if self._is_included(r)]
        self.children = self.create_children()
        for child in self.children:
            child.populate(model, self)

    def create_children(self):
        if self.depth == len(self.model.groupings):
            # reached leaf level rows.
            return [AutoRow(r) for r in self.records]
        column = self.model.groupings[self.depth]
        values = self.get_unique_values(column)
        depth = self.depth + 1
        return [TreeGroup(column, value, depth) for value in values]

    def get_unique_values(self, column=None):
        """
        """
        return set(r.data(column) for r in self.records)

    def _is_included(self, record):
        """
        Internal method to determine if the specified record is included in this group.
        """
        return record.data(self.column) == self.matcher


class RootRow(TreeGroup):
    """
    A virtual row in the tree which populates top level items.
    """
    def __init__(self):
        """
        Initialization.
        """
        super(RootRow, self).__init__('', '', 0, row_id='root')

    def populate_index(self):
        """
        Pouplates an index for all rows in the tree.
        """
        self.index = QtCore.QModelIndex()
        for row, child in enumerate(self.children):
            child.populate_index(row, self.index)

    def _is_included(self, record):
        """
        Internal method to determine if the specified
        record is included in this group.
        """
        return True

    def get_parent_records(self):
        """
        Gets the list of records from the parent row.
        """
        return self.model.records


class AutoRow(TreeRow):
    """
    Represents a leaf level tree row for an actual car for sale.
    """
    def __init__(self, record):
        """
        Initialization.
        """
        self.record = record
        super(AutoRow, self).__init__(record.token)

    def populate(self, model, parent):
        """
        Leaf level data population.
        """
        self.model = model
        self.parent = parent
        self.records = [self]
        self.children = list()
        url = self.record.thumbnail
        if url is not None:
            self.thumbnail = utils.WebImage.instance(model.directory, url)

    def get_row_height(self):
        """
        Default row height based on standard thumbnail size.
        """
        return 114

    def clear(self):
        """
        Abstract method override, no effect on the leaf level.
        """
        return

    def get_is_leaf(self):
        """
        Indicates if this row is a leaf level node.
        """
        return True

    def data(self, column):
        """
        Retrieves model data for this make/model.
        """
        if column is TreeColumns.image:
            return None
        field = column.name
        if hasattr(self, field):
            return getattr(self, field)
        return self.fields.get(field, None)

    def decoration(self, column):
        """
        Virtual method to get custom cell decoration for this row.
        """
        if column is TreeColumns.image:
            return self.thumbnail.pixmap
        return None

    def __str__(self):
        """
        String representation.
        """
        return str(self.record)


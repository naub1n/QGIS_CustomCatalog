# -*- coding: utf-8 -*-
"""
/****************************************************************************
 CustomCatalogEditCatalog
                                 A QGIS plugin
 Create your own catalog based on various sources and versions
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2021-11-02
        git sha              : $Format:%H$
        copyright            : (C) 2021 by Nicolas AUBIN
        email                : aubinnic@gmail.com
 ****************************************************************************/

/****************************************************************************
 *                                                                          *
 *   This program is free software: you can redistribute it and/or modify   *
 *   it under the terms of the GNU General Public License as published by   *
 *   the Free Software Foundation, either version 3 of the License, or      *
 *   (at your option) any later version.                                    *
 *                                                                          *
 *   This program is distributed in the hope that it will be useful,        *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of         *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          *
 *   GNU General Public License for more details.                           *
 *                                                                          *
 *   You should have received a copy of the GNU General Public License      *
 *   along with this program.  If not, see <https://www.gnu.org/licenses/>. *
 *                                                                          *
 ****************************************************************************/
"""

import json
import os

from PyQt5.QtGui import QColor
from qgis.PyQt import QtWidgets, uic, QtCore, QtGui
from qgis.core import Qgis, QgsApplication, QgsProviderRegistry, QgsDataSourceUri
from .globals import log, read_catalogs, CustomCatalogTreeWidgetItem, \
    get_icon, layer_format_values, layer_geom_values, catalog_item_type_values, check_keys, load_layer
from .db_connection import CustomCatalogAddConnexionDialog
from osgeo import ogr
from owslib import wfs, wms, wmts
from urllib.parse import parse_qs, urlparse

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '../ui/custom_catalog_edit_catalog.ui'))


class CustomCatalogEditCatalog(QtWidgets.QDialog, FORM_CLASS):

    catalogSaved = QtCore.pyqtSignal()
    catalogClosed = QtCore.pyqtSignal()

    def __init__(self, parent=None, setting_name=None, catalog_path=None, catalog_type=None, authid=None):
        # Init QDialog
        QtWidgets.QDialog.__init__(self, parent)
        # Use UI design file
        self.setupUi(self)
        # Init variables
        self.copied_item = None
        # Define columns ID
        self.name_col_id = 0
        self.type_col_id = 1
        self.geom_col_id = 2
        self.version_col_id = 3
        self.format_col_id = 4
        self.link_col_id = 5
        self.browse_col_id = 6
        self.auth_col_id = 7
        # Add Maximize flag
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowMaximizeButtonHint)
        # Define Tree Widget
        self.tree = self.treeCatalogContent
        # Define setting info
        self.setting_name = setting_name
        # Define catalog info
        self.catalog_name = None
        self.catalog_path = self.__check_catalog_path(catalog_path)
        self.catalog_type = catalog_type
        # Read catalog
        self.catalog = read_catalogs(catalog_type, catalog_path, authid)
        if self.catalog is None:
            log(self.tr("Unable to read setting") + " " + self.setting_name, Qgis.Critical)
        else:
            # Build catalog
            #self.build_catalog()
            self.read_levels(self.catalog)
            self.tree.expandAll()
            # switch off "default" editing behaviour
            self.tree.setEditTriggers(self.tree.NoEditTriggers)
            self.tree.itemDoubleClicked.connect(lambda item, col_id: self.__edit_item(item, col_id))
            self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.tree.customContextMenuRequested.connect(lambda point: self.__on_right_clicked(point))
            # call method when item is modified
            self.tree.itemChanged.connect(self.__on_item_changed)
            # call method when save button clicked
            self.btnSave.clicked.connect(self.__on_btn_save_clicked)
            # Cal method when check button clicked
            self.btnCheck.clicked.connect(self.__on_btn_check_clicked)
            # Resize all columns
            self.resize_columns()

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        return QtCore.QCoreApplication.translate('CustomCatalogEditCatalog', message)

    def __check_catalog_path(self, path):
        if path is None or path == "":
            dir_path = os.path.dirname(__file__)
            path = os.path.join(dir_path, '../catalog/default_catalog.json')
        return path

    def __on_btn_save_clicked(self, check_only=False):
        data_json = []
        for top_index in range(self.tree.topLevelItemCount()):
            data_json.append(self.tree.topLevelItem(top_index).readData())
        if data_json == self.catalog:
            if check_only:
                return False
            else:
                log(self.tr("no change found in catalog"), Qgis.Info)
        else:
            if check_only:
                return True
            else:
                try:
                    if self.catalog_type == "json":
                        with open(self.catalog_path, 'w') as outfile:
                            json.dump(data_json, outfile, indent=2)
                    elif self.catalog_type == "PostgreSQL":
                        provider = QgsProviderRegistry.instance().providerMetadata('postgres')
                        uri = QgsDataSourceUri(self.catalog_path)
                        conn = provider.createConnection(uri.uri(), {})
                        schema = uri.schema()
                        table = uri.table()
                        sql = uri.sql()
                        new_data = json.dumps(data_json)
                        conn.executeSql('UPDATE "' + schema + '"."' + table + '" set catalog_data = ' + "'" + new_data + "' WHERE " + sql)
                    else:
                        return
                    self.catalog = data_json
                    log(self.tr("Catalog modified"), Qgis.Info)
                    self.catalogSaved.emit()
                except Exception as exc:
                    log(str(exc), Qgis.Warning)

    def iterate_tree(self):
        item_list = []
        for top_index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(top_index)
            item_list.append(item)
            children = None
            for index_child in range(item.childCount()):
                children = self.iterate_child(item.child(index_child))
                item_list.extend(children)
        return item_list

    def iterate_child(self, item):
        child_list = []
        child_list.append(item)
        children = None
        for index_child in range(item.childCount()):
            children = self.iterate_child(item.child(index_child))
            child_list.extend(children)
        return child_list

    def __on_btn_check_clicked(self):
        for item in self.iterate_tree():
            if item.catalog_type == 'format':
                layer_format = self.tree.itemWidget(item, self.format_col_id).currentText()
                layer_name = item.text(self.name_col_id)
                layer_link = item.text(self.link_col_id)
                layer_auth = self.tree.itemWidget(item, self.auth_col_id).currentText()
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
                check_layer = load_layer(layer_name, layer_format, layer_link, layer_auth, check_only=True)
                QtWidgets.QApplication.restoreOverrideCursor()
                if check_layer:
                    item.setForeground(self.name_col_id, QColor('green'))
                else:
                    item.setForeground(self.name_col_id, QColor('red'))

    def __edit_item(self, item, col_id):
        if hasattr(item, 'editable_cols'):
            if col_id in item.editable_cols:
                self.tree.editItem(item, col_id)

    def __on_item_changed(self, item, col):
        if item.catalog_type == 'version' and col == self.version_col_id:
            item.setText(self.name_col_id, self.tr('version') + '_' + item.text(self.version_col_id))
        if item.catalog_type == 'format' and col == self.format_col_id:
            item.setText(self.name_col_id, self.tr('format') + '_' + item.text(self.format_col_id))
        self.updateItemData(item)

    def __on_right_clicked(self, point):
        item = self.tree.itemAt(point)
        menu = QtWidgets.QMenu()
        type = item.catalog_type

        if type == 'format':
            deleteItem_action = self.__action_delete_item(item, self.tr("Delete this format"))
            menu.addAction(deleteItem_action)
        elif type == 'version':
            addItem_action = self.__action_add_item(item, self.tr("Add format"), child_type='format')
            menu.addAction(addItem_action)
            deleteItem_action = self.__action_delete_item(item, self.tr("Delete this version"))
            menu.addAction(deleteItem_action)
        elif type == 'layer':
            self.__add_sort_actions(menu, item)
            addItem_action = self.__action_add_item(item, self.tr("Add version"), child_type='version')
            menu.addAction(addItem_action)
            deleteItem_action = self.__action_delete_item(item, self.tr("Delete this layer"))
            menu.addAction(deleteItem_action)
        elif type == 'node':
            self.__add_sort_actions(menu, item)
            addItem_action = self.__action_add_item(item, self.tr("Add layer"), child_type='layer')
            menu.addAction(addItem_action)
            addItem_action = self.__action_add_item(item, self.tr("Add node"), child_type='node')
            menu.addAction(addItem_action)
            deleteItem_action = self.__action_delete_item(item, self.tr("Delete this node"))
            menu.addAction(deleteItem_action)
        elif type == 'catalog':
            self.__add_sort_actions(menu, item)
            addItem_action = self.__action_add_item(item, self.tr("Add layer"), child_type='layer')
            menu.addAction(addItem_action)
            addItem_action = self.__action_add_item(item, self.tr("Add node"), child_type='node')
            menu.addAction(addItem_action)

        menu.exec_(self.tree.mapToGlobal(point))

    def __add_sort_actions(self, menu, item):
        addItem_action = self.__action_sort_item(item, QtCore.Qt.AscendingOrder)
        menu.addAction(addItem_action)
        addItem_action = self.__action_sort_item(item, QtCore.Qt.DescendingOrder)
        menu.addAction(addItem_action)

    def __action_sort_item(self, item, sort_order):
        if sort_order == QtCore.Qt.AscendingOrder:
            title = self.tr("Sort Asc")
            ico = QtGui.QIcon(QgsApplication.iconPath("sort.svg"))
        elif sort_order == QtCore.Qt.DescendingOrder:
            title = self.tr("Sort Desc")
            ico = QtGui.QIcon(QgsApplication.iconPath("sort-reverse.svg"))
        else:
            return

        addItem_action = QtWidgets.QAction(ico, title, self.tree)
        addItem_action.triggered.connect(lambda: self.__sort_item(item, sort_order))
        return addItem_action

    def __sort_item(self, item, sort_order):
        if isinstance(item, QtWidgets.QTreeWidgetItem):
            item.sortChildren(self.name_col_id, sort_order)

    def __action_add_item(self, item, title, child_type):
        addItem_action = QtWidgets.QAction(QtGui.QIcon(QgsApplication.iconPath("mActionAdd.svg")),
                                           title, self.tree)
        addItem_action.triggered.connect(lambda: self.__add_item(item, child_type))
        return addItem_action

    def __add_item(self, item, child_type):
        if isinstance(item, QtWidgets.QTreeWidgetItem):
            new_item = CustomCatalogTreeWidgetItem(item, child_type, self.__get_editable_cols(child_type),
                                                   editable=True)
            if child_type == 'format':
                self.tree.setItemWidget(new_item, self.format_col_id,
                                        self.__cbx_defaults_layers_formats(None, True, new_item))
                self.tree.setItemWidget(new_item, self.auth_col_id, self.__cbx_defaults_authid())
                self.tree.setItemWidget(new_item, self.browse_col_id, self.__create_btn_browse(new_item))
                self.__on_cbx_format_changed(new_item)
            elif child_type == 'version':
                new_item.setText(self.version_col_id, self.tr("New version"))
                self.__add_item(new_item, 'format')
            elif child_type == 'node':
                new_item.setText(self.name_col_id, self.tr("New node"))
                self.tree.setItemWidget(new_item, self.type_col_id,
                                        self.__cbx_defaults_types_nodes(child_type, enabled=False))
                new_item.setIcon(0, get_icon(child_type))
            elif child_type == 'layer':
                new_item.setText(self.name_col_id, self.tr("New layer"))
                self.tree.setItemWidget(new_item, self.geom_col_id, self.__cbx_defaults_layers_geom())
                self.__add_item(new_item, 'version')

            self.updateItemData(new_item)
            new_item.setExpanded(True)
            self.resize_columns()

    def __action_delete_item(self, item, title):
        deleteItem_action = QtWidgets.QAction(QtGui.QIcon(QgsApplication.iconPath("mActionDeleteSelected.svg")),
                                              title, self.tree)
        deleteItem_action.triggered.connect(lambda: self.__delete_item(item))
        return deleteItem_action

    def __delete_item(self, item):
        if isinstance(item, CustomCatalogTreeWidgetItem):
            parent = item.parent
            parent.removeChild(item)
            self.resize_columns()

    def __get_editable_cols(self, item_type):
        editable_cols = []
        if item_type == 'node':
            editable_cols.append(self.name_col_id)
        elif item_type == 'layer':
            editable_cols.append(self.name_col_id)
            editable_cols.append(self.geom_col_id)
        elif item_type == 'version':
            editable_cols.append(self.version_col_id)
        elif item_type == 'format':
            editable_cols.append(self.link_col_id)
        return editable_cols

    def resize_columns(self):
        col_count = self.tree.columnCount()
        for i in range(col_count - 1):
            self.tree.resizeColumnToContents(i)

    def __cbx_defaults_layers_formats(self, selected_value=None, change_name_item=False, item=None):
        cbx_format = QtWidgets.QComboBox()
        defaults_values = layer_format_values()
        for value in defaults_values:
            cbx_format.addItem(value)
        if selected_value is not None and selected_value in defaults_values:
            cbx_format.setCurrentText(selected_value)
        if change_name_item:
            cbx_format.currentTextChanged.connect(lambda: self.__on_cbx_format_changed(item))
        return cbx_format

    def __cbx_defaults_types_nodes(self, selected_value=None, enabled=True, item=None):
        cbx_type = QtWidgets.QComboBox()
        defaults_values = catalog_item_type_values()
        for value in defaults_values:
            cbx_type.addItem(value)
        if selected_value is not None and selected_value in defaults_values:
            cbx_type.setCurrentText(selected_value)
        cbx_type.currentTextChanged.connect(lambda: self.updateItemData(item))
        cbx_type.setEnabled(enabled)
        return cbx_type

    def __cbx_defaults_layers_geom(self, selected_value=None, item=None):
        cbx_geom = QtWidgets.QComboBox()
        defaults_values = layer_geom_values()
        for value in defaults_values:
            cbx_geom.addItem(value)
        if selected_value is not None and selected_value in defaults_values:
            cbx_geom.setCurrentText(selected_value)
        cbx_geom.currentTextChanged.connect(lambda: self.updateItemData(item))
        return cbx_geom

    def __cbx_defaults_authid(self, selected_value=None, item=None):
        cbx_auth = QtWidgets.QComboBox()
        values = ['']
        values.extend(QgsApplication.authManager().configIds())
        cbx_auth.addItems(values)
        if selected_value is not None and selected_value in values:
            cbx_auth.setCurrentText(selected_value)
        cbx_auth.currentTextChanged.connect(lambda: self.updateItemData(item))
        return cbx_auth

    def __on_cbx_format_changed(self, item):
        item.setText(self.name_col_id, self.tr('format') + '_' + self.tree.itemWidget(item, self.format_col_id).currentText())
        self.updateItemData(item)

    def setEditable(self, item, editable):
        if editable:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
        else:
            item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)

    def read_levels(self, children_dict, parent=None):
        for item in children_dict:
            if check_keys(item, self.setting_name):
                if item['type'] == "catalog":
                    self.catalog_name = item['name']
                    catalog_root_item = CustomCatalogTreeWidgetItem(None, item['type'])
                    catalog_root_item.setText(self.name_col_id, item['name'])
                    catalog_root_item.setIcon(self.name_col_id, get_icon("catalog"))
                    self.tree.addTopLevelItem(catalog_root_item)
                    self.tree.setItemWidget(catalog_root_item, self.type_col_id,
                                            self.__cbx_defaults_types_nodes(item['type'], False, catalog_root_item))
                    self.updateItemData(catalog_root_item)
                    self.read_levels(item['children'], catalog_root_item)
                else:
                    widget_item = CustomCatalogTreeWidgetItem(parent, item['type'])
                    widget_item.setText(self.name_col_id, item['name'])
                    if widget_item.catalog_type == "node":
                        widget_item.setIcon(0, get_icon(item['type']))
                        self.tree.setItemWidget(widget_item, self.type_col_id,
                                                self.__cbx_defaults_types_nodes(item['type'], False, widget_item))
                        widget_item.editable_cols = [self.name_col_id]
                        widget_item.setEditable(True)
                        self.updateItemData(widget_item)
                        if 'children' in item and len(item['children']) != 0:
                            self.read_levels(item['children'], widget_item)

                    elif widget_item.catalog_type == "layer":
                        self.tree.setItemWidget(widget_item, self.geom_col_id,
                                                self.__cbx_defaults_layers_geom(item['geomtype'], widget_item))
                        widget_item.editable_cols = [self.name_col_id, self.geom_col_id]
                        widget_item.setEditable(True)
                        self.updateItemData(widget_item)
                        for version in item['versions']:
                            version_widget_item = CustomCatalogTreeWidgetItem(widget_item, 'version', [self.version_col_id],
                                                                              editable=True)
                            version_widget_item.setText(self.name_col_id, self.tr('version') + '_' + version['version'])
                            version_widget_item.setText(self.version_col_id, version['version'])
                            self.updateItemData(version_widget_item)
                            for format in version['formats']:
                                format_widget_item = CustomCatalogTreeWidgetItem(version_widget_item,
                                                                                 'format',
                                                                                 [self.link_col_id],
                                                                                 editable=True)
                                format_widget_item.setText(self.name_col_id, self.tr('format') + '_' + format['format'])
                                self.tree.setItemWidget(format_widget_item, self.format_col_id,
                                                        self.__cbx_defaults_layers_formats(format['format'],
                                                                                           True,
                                                                                           format_widget_item))
                                format_widget_item.setText(self.link_col_id, format['link'])
                                self.tree.setItemWidget(format_widget_item, self.browse_col_id,
                                                        self.__create_btn_browse(format_widget_item))
                                if "qgisauthconfigid" in format:
                                    authid = format['qgisauthconfigid']
                                else:
                                    authid = ""
                                self.tree.setItemWidget(format_widget_item, self.auth_col_id,
                                                        self.__cbx_defaults_authid(authid, format_widget_item))
                                self.updateItemData(format_widget_item)

    def __create_btn_browse(self, item):
        btn = QtWidgets.QPushButton('...')
        btn.setMaximumWidth(55)
        btn.clicked.connect(lambda: self.__on_btn_browse_clicked(item))
        return btn

    def __on_btn_browse_clicked(self, tree_item):
        if isinstance(tree_item, CustomCatalogTreeWidgetItem):
            current_path = tree_item.text(self.link_col_id)
            if tree_item.catalog_type == 'format':
                layer_format = self.tree.itemWidget(tree_item, self.format_col_id).currentText()
                if layer_format == 'SHP':
                    filter = "ESRI Shapefile (*.shp)"
                    new_path = self.browse_layer_file(filter, current_path)
                    if new_path:
                        tree_item.setText(self.link_col_id, new_path)
                elif layer_format == "GPKG":
                    current_path = current_path.split("|")[0]
                    filter = "GeoPackage (*.gpkg)"
                    new_path = self.browse_layer_file(filter, current_path)
                    if new_path:
                        input_dialog = QtWidgets.QInputDialog()
                        gpkg_layers = [l.GetName() for l in ogr.Open(new_path)]
                        selected_layer = input_dialog.getItem(self, self.tr("Select a layer"),
                                                              self.tr("Layer :"), gpkg_layers)
                        tree_item.setText(self.link_col_id, new_path + '|layername=' + selected_layer[0])
                elif layer_format == 'QLR':
                    filter = "QGIS Layer Definition (*.qlr)"
                    new_path = self.browse_layer_file(filter, current_path)
                    if new_path:
                        tree_item.setText(self.link_col_id, new_path)
                elif layer_format == "PostGIS":
                    self.open_cnx_dialog(tree_item, current_uri=current_path, edit_catalog=True, db_type="PostgreSQL")
                elif layer_format == "Oracle":
                    # Check QGIS version to use Oracle provider method 'createConnection'. 3.18 required
                    qgisVersionMajor = int(Qgis.QGIS_VERSION.split(".")[0])
                    qgisVersionMinor = int(Qgis.QGIS_VERSION.split(".")[1])
                    if qgisVersionMajor >= 3 and qgisVersionMinor >= 18:
                        self.open_cnx_dialog(tree_item, current_uri=current_path, edit_catalog=True, db_type="Oracle")
                    else:
                        log(self.tr("Qgis minimum version required is 3.18 to use Oracle provider"), Qgis.Warning)
                elif layer_format == "SpatiaLite":
                    self.open_cnx_dialog(tree_item, current_uri=current_path, edit_catalog=True, db_type="SQLite")
                    """self.cnx_dialog = CustomCatalogAddConnexionDialog(current_uri=current_path, edit_catalog=True, 
                                                                      db_type="PostgreSQL")
                    self.cnx_dialog.connectionDefined.connect(lambda new_path: tree_item.setText(self.link_col_id, new_path))
                    self.cnx_dialog.dialogClosed.connect(self.__on_connexiondialog_closed)
                    self.cnx_dialog.exec_()"""
                elif layer_format == "WFS" or layer_format == "WMS" or layer_format == "WMTS":
                    if current_path:
                        layer_url = self.get_ows_layer(layer_format, current_path)
                        if layer_url:
                            tree_item.setText(self.link_col_id, layer_url)

    def open_cnx_dialog(self, item, current_uri=None, edit_catalog=False, db_type=None):
        self.cnx_dialog = CustomCatalogAddConnexionDialog(current_uri=current_uri, edit_catalog=edit_catalog,
                                                          db_type=db_type)
        self.cnx_dialog.connectionDefined.connect(lambda new_path: item.setText(self.link_col_id, new_path))
        self.cnx_dialog.dialogClosed.connect(self.__on_connexiondialog_closed)
        self.cnx_dialog.exec_()

    def get_ows_layer(self, layer_format, url):
        try:
            if layer_format == 'WFS':
                base_url = url.split("?")[0]
                parsed_url = urlparse(url)
                args = parse_qs(parsed_url.query.lower())
                version = None
                if args:
                    if 'version' in args:
                        version = parse_qs(parsed_url.query.lower())['version'][0]
                if not version:
                    log("WFS version not specified, v1.0.0 is used", Qgis.Info)
                    version = '1.0.0'
                ows = wfs.WebFeatureService(url=base_url, version=version)
                layers = list(ows.contents)
                layers.sort()
                input_dialog = QtWidgets.QInputDialog()
                selected_layer, ok = input_dialog.getItem(self, self.tr("Select a layer"),
                                                      self.tr("Layer :"), layers, 0, False)
                if not ok or not selected_layer:
                    return
                full_url = base_url + '?service=WFS&request=GetFeature&version=' + version + '&typename=' + selected_layer

            elif layer_format == 'WMS':
                if not "url=" in url:
                    log("WMS link should be similar to url=httpx://xxxxxx", Qgis.Warning)
                    log("Trying to read URL adding 'url='", Qgis.Info)
                    return self.get_ows_layer(layer_format, "url=" + url)
                try:
                    params = dict(arg.split('=') for arg in url.split('&'))
                except Exception as exc:
                    log("WMS link should be similar to key1=value1&key2=value2", Qgis.Warning, str(exc))
                    if "?" in url:
                        log("Trying to read URL replacing '?' by '&'", Qgis.Info)
                        return self.get_ows_layer(layer_format, url.replace("?", "&"))
                    return
                base_url = params['url']
                if "version" in params:
                    version = params["version"]
                else:
                    log("WMS version not specified, v1.1.1 is used", Qgis.Info)
                    version = '1.1.1'
                ows = wms.WebMapService(url=base_url, version=version)
                format_options = ows.getOperationByName('GetMap').formatOptions
                if "image/png" in format_options:
                    format_option = "image/png"
                elif "image/jpeg" in format_options:
                    format_option = "image/jpeg"
                else:
                    format_option = format_options[0]
                layers = list(ows.contents)
                layers.sort()
                input_dialog = QtWidgets.QInputDialog()
                selected_layer, ok = input_dialog.getItem(self, self.tr("Select a layer"),
                                                      self.tr("Layer :"), layers, 0, False)
                if not ok or not selected_layer:
                    return

                full_url = 'url=' + base_url + '&format=' + format_option + '&styles=&version=' + version + '&layers=' + selected_layer

            elif layer_format == 'WMTS':
                if not "url=" in url:
                    log("WMS link should be similar to url=httpx://xxxxxx", Qgis.Warning)
                    log("Trying to read URL adding 'url='", Qgis.Info)
                    return self.get_ows_layer(layer_format, "url=" + url)
                try:
                    params = dict(arg.split('=') for arg in url.split("?")[0].split('&'))
                except Exception as exc:
                    log("WMTS link should be similar to key1=value1&key2=value2", Qgis.Warning, str(exc))
                    return
                base_url = params['url']
                if "version" in params:
                    version = params["version"]
                else:
                    log("WMTS version not specified, v1.0.0 is used", Qgis.Info)
                    version = '1.0.0'
                ows = wmts.WebMapTileService(url=base_url, version=version)

                layers = list(ows.contents)
                layers.sort()
                input_dialog_layer = QtWidgets.QInputDialog()
                selected_layer, ok = input_dialog_layer.getItem(self, self.tr("Select a layer"), self.tr("Layer :"), layers, 0, False)
                if not ok or not selected_layer:
                    return

                formats = ows[selected_layer].formats
                if len(formats) == 1:
                    selected_format = formats[0]
                else:
                    input_dialog_format = QtWidgets.QInputDialog()
                    selected_format, ok = input_dialog_format.getItem(self, self.tr("Select a format"), self.tr("Format :"),
                                                                  formats)
                    if not ok or not selected_format:
                        return

                tile_matrix = sorted(ows[selected_layer].tilematrixsetlinks.keys())
                if len(tile_matrix) == 1:
                    selected_tile_matrix = tile_matrix[0]
                else:
                    input_dialog_tilematrix = QtWidgets.QInputDialog()
                    selected_tile_matrix, ok = input_dialog_tilematrix.getItem(self, self.tr("Select a tile matrix"), self.tr("Tile matrix :"), tile_matrix)
                    if not ok or not selected_tile_matrix:
                        return

                styles = sorted(ows.contents[selected_layer].styles.keys())
                if len(styles) == 1:
                    selected_style = styles[0]
                else:
                    input_dialog_style = QtWidgets.QInputDialog()
                    selected_style, ok = input_dialog_style.getItem(self, self.tr("Select a style"), self.tr("Style :"), styles)
                    if not ok or not selected_style:
                        return
                crs = ows.tilematrixsets[selected_tile_matrix].crs

                full_url = 'url=' + base_url + '?SERVICE%3DWMTS%26REQUEST%3DGetCapabilities' + \
                           '&format=' + selected_format + '&styles=' + selected_style + '&version=' + version + '&crs=' + crs + \
                           '&tileMatrixSet=' + selected_tile_matrix + '&layers=' + selected_layer
            else:
                return
        except Exception as exc:
            log(self.tr("Invalid {} url").format(layer_format), Qgis.Warning,
                self.tr("URL") + " : " + base_url + " ;" + self.tr("Version") + " : " + version +
                "\n" + "Error" + " : " + str(exc))
            return
        return full_url

    def updateItemData(self, item):
        if isinstance(item, CustomCatalogTreeWidgetItem):
            try:
                if item.catalog_type == "node" or item.catalog_type == "catalog":
                    item.itemName = item.text(self.name_col_id)
                    item.itemType = self.tree.itemWidget(item, self.type_col_id).currentText()
                if item.catalog_type == "layer":
                    item.itemName = item.text(self.name_col_id)
                    item.itemGeom = self.tree.itemWidget(item, self.geom_col_id).currentText()
                if item.catalog_type == "version":
                    item.itemVersion = item.text(self.version_col_id)
                if item.catalog_type == "format":
                    item.itemFormat = self.tree.itemWidget(item, self.format_col_id).currentText()
                    item.itemLink = item.text(self.link_col_id)
                    item.itemAuth = self.tree.itemWidget(item, self.auth_col_id).currentText()
                self.resize_columns()
            except Exception as exc:
                # when an item is created, an error occur because itemWidgets do not exist
                pass

    def __on_connexiondialog_closed(self):
        self.cnx_dialog.connectionDefined.disconnect()
        self.cnx_dialog.dialogClosed.disconnect()

    def browse_layer_file(self, filter, current_file_path=None):
        if os.path.exists(current_file_path):
            current_dir = os.path.dirname(current_file_path)
        else:
            current_dir = None
        dlg = QtWidgets.QFileDialog()
        new_file_path = dlg.getOpenFileName(None, self.tr("Select layer file"), current_dir, filter)[0]
        return new_file_path

    # TODO
    def change_parent(self, item, new_parent):
        if isinstance(item, QtWidgets.QTreeWidgetItem):
            old_parent = item.parent()
            ix = old_parent.indexOfChild(item)
            item_without_parent = old_parent.takeChild(ix)
            new_parent.addChild(item_without_parent)

    def closeEvent(self, event):
        if self.__on_btn_save_clicked(check_only=True):
            edit_close_dialog = QtWidgets.QMessageBox()
            edit_close_dialog.setIcon(QtWidgets.QMessageBox.Warning)
            edit_close_dialog.setText(self.tr("Changes detected, are you sure to close catalog editing ?"))
            edit_close_dialog.setWindowTitle(self.tr("Changes detected"))
            edit_close_dialog.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

            close_settings = edit_close_dialog.exec()
            if close_settings == QtWidgets.QMessageBox.Yes:
                self.catalogClosed.emit()
                event.accept()
            else:
                event.ignore()
        else:
            self.catalogClosed.emit()
            event.accept()

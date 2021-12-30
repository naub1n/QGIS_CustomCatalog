# -*- coding: utf-8 -*-
"""
/****************************************************************************
 CustomCatalogAddConnexionDialog
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

import os

from PyQt5.QtCore import QSettings
from qgis.PyQt import QtWidgets, uic, QtCore
from qgis.core import Qgis, QgsDataSourceUri, QgsProviderRegistry, QgsAbstractProviderConnection
from .globals import log, init_catalog_data

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), '../ui/custom_catalog_set_database_connection.ui'))


class CustomCatalogAddConnexionDialog(QtWidgets.QDialog, FORM_CLASS):

    connectionDefined = QtCore.pyqtSignal(str)
    dialogClosed = QtCore.pyqtSignal()

    def __init__(self, parent=None, catalog_name=None, current_uri=None, edit_catalog=False):
        QtWidgets.QDialog.__init__(self, parent)
        self.setupUi(self)
        self.settings = QSettings()
        # Init variables
        self.provider = None
        self.catalog = catalog_name
        self.current_uri = current_uri
        self.edit_catalog = edit_catalog
        # Default state geom widgets
        self.cbxGeom.setEnabled(False)
        self.txbxGeom.setEnabled(False)
        self.lblCbxGeom.setEnabled(False)
        self.lblTxbxGeom.setEnabled(False)
        # Define supported database
        db_types = ["PostgreSQL"]
        self.cbxDbType.addItems(db_types)
        self.get_connections()
        self.set_provider()
        # call method when connexion type is modified
        self.cbxDbType.currentIndexChanged.connect(self.__on_cbxdbtype_changed)
        # Update groupbox state and call method when connexion name is modified
        self.rbExistingCnx.setChecked(True)
        self.__on_radiobtn_changed(True)
        self.rbExistingCnx.toggled.connect(self.__on_radiobtn_changed)
        # Init button OK
        self.btn_ok = self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.__on_ok_clicked)
        self.buttonBox.rejected.connect(self.__on_cancel_clicked)
        # call method when connexion name is modified
        self.cbxCnx.currentIndexChanged.connect(self.__on_cbxcnx_changed)
        # call method when schema is modified
        self.cbxSchema.currentIndexChanged.connect(self.__on_cbxschema_changed)
        # call method when table is modified
        self.cbxTable.currentIndexChanged.connect(self.__on_cbxtable_changed)
        # check if current_uri is set
        if self.current_uri:
            self.read_current_uri()
        # Check if idt_catalog mod
        if self.edit_catalog:
            self.cbxGeom.setEnabled(True)
            self.txbxGeom.setEnabled(True)
            self.lblCbxGeom.setEnabled(True)
            self.lblTxbxGeom.setEnabled(True)

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        return QtCore.QCoreApplication.translate('CustomCatalogAddConnexionDialog', message)

    def read_current_uri(self):
        uri = QgsDataSourceUri(self.current_uri)
        self.rbNewCnx.setChecked(True)
        self.txbxHost.setText(uri.host())
        self.txbxPort.setText(uri.port())
        self.txbxDb.setText(uri.database())
        self.txbxSchema.setText(uri.schema())
        self.txbxTable.setText(uri.table())

    def __on_cbxtable_changed(self):
        if self.edit_catalog:
            uri = self.set_uri()
            self.cbxGeom.clear()
            conn = self.provider.createConnection(uri.uri(), {})
            try:
                if self.rbExistingCnx.isChecked():
                    schema = self.cbxSchema.currentText()
                    table = self.cbxTable.currentText()
                else:
                    schema = self.txbxSchema.text()
                    table = self.txbxTable.text()
                fields = conn.fields(schema, table).names()
                self.cbxGeom.addItems(fields)
                if "geom" in fields:
                    self.cbxGeom.setCurrentText("geom")

            except Exception:
                pass



    def __on_cbxschema_changed(self):
        uri = self.set_uri()
        self.cbxTable.clear()
        conn = self.provider.createConnection(uri.uri(), {})
        try:
            self.cbxTable.addItem("NEW TABLE")
            tables = conn.tables(self.cbxSchema.currentText())
            for table in tables:
                self.cbxTable.addItem(table.tableName())
        except Exception:
            pass

    def __on_cbxdbtype_changed(self):
        self.get_connections()
        self.set_provider()

    def get_connections(self):
        if self.cbxDbType.currentText() != "" and self.cbxDbType.currentText() is not None:
            self.cbxCnx.clear()
            db_type = self.cbxDbType.currentText()
            self.settings.beginGroup(db_type + "/connections")
            self.cbxCnx.addItems(self.settings.childGroups())
            #self.cbxCnx.addItems(self.settings.allKeys())
            self.settings.endGroup()

    def set_provider(self):
        if self.cbxDbType.currentText() == "PostgreSQL":
            self.provider = QgsProviderRegistry.instance().providerMetadata('postgres')

    def __on_radiobtn_changed(self, checked):
        if checked:
            self.gbxCustomCnx.setEnabled(True)
            self.gbxExistCnx.setEnabled(False)
        else:
            self.gbxCustomCnx.setEnabled(False)
            self.gbxExistCnx.setEnabled(True)

    def __on_cbxcnx_changed(self):
        uri = self.set_uri()
        self.cbxSchema.clear()
        if self.cbxDbType.currentText() == "PostgreSQL":
            conn = self.provider.createConnection(uri.uri(), {})
        try:
            self.cbxSchema.addItems(conn.schemas())
        except Exception:
            pass

    def set_uri(self):
        uri = QgsDataSourceUri()
        if self.rbExistingCnx.isChecked():
            cnx_info = self.cbxDbType.currentText() + "/connections/" + self.cbxCnx.currentText() + "/"
            service = self.settings.value(cnx_info + "service")
            auth_id = self.settings.value(cnx_info + "authcfg")
            if service:
                uri.setConnection(service, None, None, None, authConfigId=auth_id)
            else:
                host = self.settings.value(cnx_info + "host")
                port = self.settings.value(cnx_info + "port")
                database = self.settings.value(cnx_info + "database")
                username = self.settings.value(cnx_info + "username")
                password = self.settings.value(cnx_info + "password")
                uri.setConnection(host, port, database, username, password)
        else:
            host = self.txbxHost.text()
            port = self.txbxPort.text()
            database = self.txbxDb.text()
            username = self.txbxUser.text()
            password = self.txbxPass.text()
            uri.setConnection(host, port, database, username, password)
        return uri

    def __on_ok_clicked(self):
        uri = self.set_uri()
        try:
            if self.rbExistingCnx.isChecked():
                schema = self.cbxSchema.currentText()
                table = self.cbxTable.currentText()
                geom = self.cbxGeom.currentText()
            else:
                schema = self.txbxSchema.text()
                table = self.txbxTable.text()
                geom = self.txbxGeom.text()

            if self.edit_catalog:
                uri.setSchema(schema)
                uri.setTable(table)
                uri.setGeometryColumn(geom)
            else:
                default_catalog_data = init_catalog_data(self.catalog)
                conn = self.provider.createConnection(uri.uri(), {})
                sql_insert = "INSERT INTO {}.{} (id, catalog_data) VALUES ('{}','{}');"
                sql_check_catalog = "SELECT count(id) as nb_catalogs FROM {}.{} WHERE id='{}';".format(schema, table, self.catalog)
                sql_create = "CREATE TABLE {}.{}(id character varying(30) NOT NULL, catalog_data json, PRIMARY KEY (id));"
                uri.setDataSource(aSchema=schema, aTable=table, aGeometryColumn=None, aSql="id = '{}'".format(self.catalog))
                if table == "NEW TABLE" or table is None or table == "":
                    # Init messagebox
                    dialog = self.create_table_dialog()
                    # Create table and insert data if user press yes
                    create_table_response = dialog.exec()
                    if create_table_response == QtWidgets.QMessageBox.Yes:
                        table = "catalogs"
                        conn.executeSql(sql_create.format(schema, table))
                        conn.executeSql(sql_insert.format(schema, table, self.catalog, default_catalog_data))
                        uri.setTable(table)
                else:
                    tables = []
                    for t in conn.tables(schema):
                        tables.append(t.tableName())
                    # check if table exists in database
                    if table not in tables:
                        dialog = self.create_table_dialog()
                        create_table_response = dialog.exec()
                        if create_table_response == QtWidgets.QMessageBox.Yes:
                            conn.executeSql(sql_create.format(schema, table))
                            conn.executeSql(sql_insert.format(schema, table, self.catalog, default_catalog_data))
                    # check if catalog exists in table
                    check = conn.executeSql(sql_check_catalog)
                    if check == [[0]]:
                        # Init messagebox
                        insert_catalog_dialog = QtWidgets.QMessageBox()
                        insert_catalog_dialog.setIcon(QtWidgets.QMessageBox.Warning)
                        insert_catalog_dialog.setText(self.tr("Catalog doesn't exist, do you want to create it ?"))
                        insert_catalog_dialog.setWindowTitle(self.tr("Create new entry in table"))
                        insert_catalog_dialog.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                        # Insert data if user press yes
                        create_table_response = insert_catalog_dialog.exec()
                        if create_table_response == QtWidgets.QMessageBox.Yes:
                            conn.executeSql(sql_insert.format(schema, table, self.catalog, default_catalog_data))

            uri.setAuthConfigId(None)
            self.connectionDefined.emit(uri.uri(expandAuthConfig=False))
            self.close()
        except Exception as exc:
            log(str(exc), Qgis.Warning)


    def create_table_dialog(self):
        dialog = QtWidgets.QMessageBox()
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setText(self.tr("Table not defined or doesn't exist, do you want to create it ?"))
        dialog.setWindowTitle(self.tr("Create new table in database"))
        dialog.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        return dialog

    def __on_cancel_clicked(self):
        self.close()

    def closeEvent(self, event):
        self.dialogClosed.emit()
        event.accept()



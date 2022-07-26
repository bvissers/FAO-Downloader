# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WaporDataToolDialog
                                 A QGIS plugin
 This plugin downloads and analyses WaPOR data for a selected region
                             -------------------
        begin                : 2022-07-26
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Brenden & Celray James
        email                : celray@chawanda.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import datetime
import os

import requests
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from qgis.PyQt import QtWidgets, uic

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'waport_data_dialog_base.ui'))


class WaporDataToolDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(WaporDataToolDialog, self).__init__(parent)
        self.setupUi(self)

        # set constants
        self.path_catalog=r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/'
        self.path_download=r'https://io.apps.fao.org/gismgr/api/v1/download/'
        self.path_jobs=r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR/jobs/'
        self.path_query=r'https://io.apps.fao.org/gismgr/api/v1/query/'
        self.path_sign_in=r'https://io.apps.fao.org/gismgr/api/v1/iam/sign-in/'
        self.workspaces='WAPOR_2'

        self.token_is_valid = False

        self.AccessToken = None
        self.time_expire = None
        self.time_start = None

        self.current_download_location = None

        # set initial states
        self.initialise_defaults()

        # connect click functions
        self.btn_retrieve_catalog.clicked.connect(self.load_catalog)
        self.btn_update_token.clicked.connect(self.update_token)
        self.btn_check_token.clicked.connect(self.validate_token)
        self.btn_browse_default_download_dir.clicked.connect(self.browse_default_directory)
        self.btn_set_download_location.clicked.connect(self.browse_download_directory)



    def initialise_defaults(self):

        # get current date and time and set default time range
        date_time_now = datetime.datetime.now()
        self.date_from.setDate(QDate(2009, 1, 1))
        self.date_to.setDate(QDate(date_time_now.year - 1, 12, 12))

        # set default control state
        self.chb_clip_to_cutline.setCheckState(2)  # it is checked
        
        # set hints
        self.lbl_token_status.setText("")
        self.wapor_tokenbox.setPlaceholderText("Paste your new token here")

        # set default variable states
        self.validate_token()
        self.check_default_download_dir()

        if self.token_is_valid:
            self.tab_pages.setCurrentIndex(0)
        else:
            self.tab_pages.setCurrentIndex(2)

        default_dir_fn = os.path.join(os.path.dirname(__file__), 'defdir.dll')
        if self.exists(default_dir_fn):
            dld_location = self.read_from(default_dir_fn)[0]
            self.txt_default_dir_path.setPlainText(dld_location)
            self.txb_download_location.setPlainText(dld_location)
            self.current_download_location = dld_location
        else:
            self.txt_default_dir_path.setPlainText("")
            self.txb_download_location.setPlainText("")
            self.current_download_location = None

        self.treeWidget.clear()
        self.treeWidget.headerItem().setText(0, '')



    def load_catalog(self):
        print('loading catalog...')

        try:
            #Cubes: provides operations pertaining to Cube resources
            #returns a list of available Cube resource type items
            #example:https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1'
            L1 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1'.format(self.path_catalog,self.workspaces)).json()).get('response'))
            L2 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L2'.format(self.path_catalog,self.workspaces)).json()).get('response'))
            L3 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L3'.format(self.path_catalog,self.workspaces)).json()).get('response'))            
            self.MasterList = L1 + L2 + L3
            
            #sorts by type of information
            L1 = sorted(L1, key=lambda d: d.get('caption'))
            L2 = sorted(L2, key=lambda d: d.get('caption'))
            
            #Sorts first country location, then by type of information
            L3 = sorted(L3, key=lambda d: [d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[2],d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[1] ,d.get('code') ])
            
            #creates the treewidget to select data from
            self.treeWidget.clear()
            self.treeWidget.headerItem().setText(0, self.workspaces)
            self.TreeAddBasic(L1, "Level 1")
            self.TreeAddBasic(L2, "Level 2")
            self.TreeAddLvl3(L3, "Level 3")

        except: pass
            # self.Mbox( 'Error' ,'Error Loading data from the WaPOR Server',0)

    def TreeAddBasic(self, L, name):    
        parent = QTreeWidgetItem(self.treeWidget)

        parent.setText(0, name)        
        parent.setFlags(parent.flags()   | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
        
        for x in L:
            child = QTreeWidgetItem(parent)
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setText(0, x.get('caption'))
            child.setText(1, str(x.get('code')))
            child.setCheckState(0, Qt.CheckState.Unchecked)
            














    def update_token(self):
        print('updating token...')
        token_fn = os.path.join(os.path.dirname(__file__), 'token.dll')
        
        token_text = self.wapor_tokenbox.toPlainText()

        self.write_to(token_fn, token_text)


    def read_token(self):
        print('reading token...')
        token_fn = os.path.join(os.path.dirname(__file__), 'token.dll')
        
        if self.exists(token_fn): return self.read_from(token_fn)[0]
        else: return ''

    def browse_default_directory(self):
        print('select default directory...')

        startingDir = "/"
        destDir = QFileDialog.getExistingDirectory(None, 
                                                    'Select Default Download Directory', 
                                                    startingDir, 
                                                    QFileDialog.ShowDirsOnly)

        if len(destDir) > 0:
            default_dir_fn = os.path.join(os.path.dirname(__file__), 'defdir.dll')
            self.write_to(default_dir_fn, destDir)
            self.check_default_download_dir()
        
    def browse_download_directory(self):
        print('select download directory...')

        startingDir = "/"
        destDir = QFileDialog.getExistingDirectory(None, 
                                                    'Select Download Directory', 
                                                    startingDir, 
                                                    QFileDialog.ShowDirsOnly)

        if len(destDir) > 0:
            self.txb_download_location.setPlainText(destDir)
            self.current_download_location = destDir

        
    def check_default_download_dir(self):
        default_dir_fn = os.path.join(os.path.dirname(__file__), 'defdir.dll')
        if self.exists(default_dir_fn):
            self.txt_default_dir_path.setPlainText(self.read_from(default_dir_fn)[0])
        else:
            self.txt_default_dir_path.setPlainText("")













    def validate_token(self):
        resp_vp=requests.post(self.path_sign_in,headers={'X-GISMGR-API-KEY':self.read_token()})
        resp_vp = resp_vp.json()
        print(resp_vp)
        try:
            if resp_vp['message'] == "OK":
                self.token_is_valid = True
                self.lbl_token_status.setText("Current Token is OK")

                self.AccessToken = resp_vp['response']['accessToken']
                self.time_expire = resp_vp['response']['expiresIn']
                self.time_start = datetime.datetime.now().timestamp()

        except:
            self.lbl_token_status.setText("Can't Validate Token")
            print( 'Error','Could not connect to server.',0)  
    

        
    def write_to(self, filename, text_to_write):
        '''
        a function to write to file
        '''
        if not os.path.isdir(os.path.dirname(filename)): os.makedirs(os.path.dirname(filename))
        g = open(filename, 'w', encoding="utf-8")
        g.write(text_to_write)
        g.close()


    def exists(self, path_):
        if os.path.isdir(path_): return True
        if os.path.isfile(path_): return True
        return False



    def read_from(self, filename):
        '''
        a function to read ascii files
        '''
        g = open(filename, 'r')
        file_text = g.readlines()
        g.close
        return file_text



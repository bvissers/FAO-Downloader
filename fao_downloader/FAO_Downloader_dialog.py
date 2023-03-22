# -*- coding: utf-8 -*-
"""
/***************************************************************************
 WaporDataToolDialog
                                 A QGIS plugin
 This plugin downloads and analyses FAO data for a selected region
                             -------------------
        begin                : 2022-07-26
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Brenden & Celray James
        email                : bvissers929@gmail.com
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

import ctypes
import datetime
import numpy as np
import os
from osgeo import gdal, osr
import pandas as pd
import PyQt5.QtCore as QTC
import PyQt5.QtWidgets as QTW 
import qgis.core 
from qgis.PyQt import QtWidgets, uic
import requests
import time









# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
     os.path.dirname(__file__), 'FAO_Downloader_dialog_base.ui'))



class FAODownloaderDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(FAODownloaderDialog, self).__init__(parent)
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
        self.treeWidget.itemDoubleClicked.connect(self.LaunchPopup) 
        self.cbx_workspace.currentTextChanged.connect(self.load_catalog)
        self.btn_update_token.clicked.connect(self.update_token)
        self.btn_check_token.clicked.connect(self.validate_token)
        self.btn_browse_default_download_dir.clicked.connect(self.browse_default_directory)
        self.btn_set_download_location.clicked.connect(self.browse_download_directory)
        self.btn_download.clicked.connect(self.LaunchDownload)

        
        # set sizes of items
        self.btn_download.setFixedSize(141, 142)
        self.pbar_primary.setFixedSize(0, 0)
        self.pbar_secondary.setFixedSize(0, 0)

        # attributes for report creation
        self.layout = None
        self.manager = None
        self.project = None

        
    # to store swat constants
    class swat_analysis_var_constants:
        def __init__(self, variable, file_prefix, column_index):
            self.variable = variable
            self.file_prefix = file_prefix
            self.column_index = column_index
    

    def initialise_defaults(self):

        self.pop_workspace()

        self.txt_default_dir_path.setReadOnly(True)
        self.txb_download_location.setReadOnly(True) 
        # get current date and time and set default time range
        date_time_now = datetime.datetime.now()
        self.date_from.setDate(QTC.QDate(2009, 1, 1))
        self.date_to.setDate(QTC.QDate(date_time_now))
        
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
            self.txt_default_dir_path.setText(dld_location)
            self.txb_download_location.setText(dld_location)
            self.current_download_location = dld_location
        else:
            self.txt_default_dir_path.setText("")
            self.txb_download_location.setText("")
            self.current_download_location = None

        self.treeWidget.clear()
        self.treeWidget.headerItem().setText(0, '')
       
        # load catalog to treewidgit
        self.load_catalog()
        

    def pop_workspace(self):
        workspaces = requests.get("https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces?overview=true&paged=false").json().get('response')
        for workspace in workspaces:
            self.cbx_workspace.addItem(workspace['code'])
        self.cbx_workspace.setCurrentText("WAPOR_2")    
        

    def load_catalog(self):
        print('loading catalog...')
        
        
        if self.cbx_workspace.currentText() == 'WAPOR_2':
            try:
                #Cubes: provides operations pertaining to Cube resources
                #returns a list of available Cube resource type items
                #example:https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1'
                L1 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1'.format(self.path_catalog,self.workspaces)).json()).get('response'))
                L2 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L2'.format(self.path_catalog,self.workspaces)).json()).get('response'))
                L3 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L3'.format(self.path_catalog,self.workspaces)).json()).get('response'))            
                
                
                #sorts by type of information
                L1 = sorted(L1, key=lambda d: d.get('caption'))
                L2 = sorted(L2, key=lambda d: d.get('caption'))
                
                #Sorts first country location, then by type of information
                L3 = sorted(L3, key=lambda d: [d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[2],d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[1] ,d.get('code') ])
                
                self.MasterList = L1 + L2 + L3
                level_list = [L1, L2, L3] 
                #creates the treewidget to select data from
                self.treeWidget.clear()
                self.treeWidget.headerItem().setText(0, self.workspaces)
                self.TreeWaPOR(level_list, "WAPOR_2")
                
                self.combo_dekadal.show()
                self.label_dekadal.show()
                
                
            except: pass
        
        else:
            try:
                L = ((requests.get('{0}{1}/cubes?overview=false&paged=false'.format(self.path_catalog,self.cbx_workspace.currentText())).json()).get('response'))
                L = sorted(L, key=lambda d: d.get('caption'))
                self.MasterList = L
                self.treeWidget.clear()
                self.treeWidget.headerItem().setText(0, self.cbx_workspace.currentText())
                self.TreeAddBasic(L, self.cbx_workspace.currentText())    
                
                self.combo_dekadal.hide()
                self.label_dekadal.hide()
            except: pass
            # self.Mbox( 'Error' ,'Error Loading data from the WaPOR Server',0)


    def TreeAddBasic(self, L, name):    
        parent = QTW.QTreeWidgetItem(self.treeWidget)

        parent.setText(0, name)        
        parent.setFlags(parent.flags()   | QTC.Qt.ItemFlag.ItemIsUserCheckable | QTC.Qt.ItemFlag.ItemIsAutoTristate)
        
        for x in L:
            child = QTW.QTreeWidgetItem(parent)
            child.setFlags(child.flags() | QTC.Qt.ItemFlag.ItemIsUserCheckable)
            child.setText(0, x.get('caption'))
            child.setText(1, str(x.get('code')))
            child.setCheckState(0, QTC.Qt.CheckState.Unchecked)
            
            
    def TreeWaPOR(self, level_list, name):    
        parent = QTW.QTreeWidgetItem(self.treeWidget)
        parent.setText(0, name)
        parent.setFlags(parent.flags() |  QTC.Qt.ItemFlag.ItemIsUserCheckable | QTC.Qt.ItemFlag.ItemIsAutoTristate)
        Levels = ['Level 1 (250m)', 'Level 2 (100m)', 'Level 3 (30m)']
        locations = []
        index = 0
        for L in level_list:        
            level = QTW.QTreeWidgetItem(parent)
            level.setFlags(level.flags() | QTC.Qt.ItemFlag.ItemIsUserCheckable| QTC.Qt.ItemFlag.ItemIsAutoTristate)
            level.setText(0, Levels[index])
            level.setCheckState(0, QTC.Qt.CheckState.Unchecked)
                       
            
            
            if L != level_list[2]:
                for x in L:
                    child = QTW.QTreeWidgetItem(level)
                    child.setFlags(child.flags() | QTC.Qt.ItemFlag.ItemIsUserCheckable)
                    child.setText(0, x.get('caption'))
                    child.setText(1, str(x.get('code')))
                    child.setCheckState(0, QTC.Qt.CheckState.Unchecked)
   
            if L == level_list[2]:
                for x in L:
                    if (x.get('additionalInfo').get('spatialExtent')) not in locations:
                        locations.append(x.get('additionalInfo').get('spatialExtent'))
                        country = QTW.QTreeWidgetItem(level)
                        country.setFlags(country.flags() | QTC.Qt.ItemFlag.ItemIsUserCheckable| QTC.Qt.ItemFlag.ItemIsAutoTristate)
                        country.setText(0, locations[-1])
                        country.setCheckState(0, QTC.Qt.CheckState.Unchecked)        
        
                    child2 = QTW.QTreeWidgetItem(country)
                    child2.setFlags(child2.flags() | QTC.Qt.ItemFlag.ItemIsUserCheckable)
                    child2.setText(0, x.get('caption'))
                    child2.setCheckState(0, QTC.Qt.CheckState.Unchecked)     
                    child2.setText(1, str(x.get('code')))              
            index += 1

            
    def get_bbox(self):
        vector_layer = self.mMapLayerComboBox.currentLayer()
        bounding=vector_layer.extent()   
        if vector_layer.crs() != qgis.core.QgsCoordinateReferenceSystem("EPSG:4326"):
            crsSrc = vector_layer.crs()    # WGS 84
            crsDest = qgis.core.QgsCoordinateReferenceSystem("EPSG:4326")# WGS 84 / UTM zone 33N
            transformContext = qgis.core.QgsProject.instance().transformContext()
            xform = qgis.core.QgsCoordinateTransform(crsSrc, crsDest, transformContext)
            bounding_t = xform.transformBoundingBox(bounding)
            bounding = bounding_t
        buffer = 0.05
        bbox = [bounding.xMinimum()- buffer,bounding.yMinimum() - buffer,bounding.xMaximum() + buffer, bounding.yMaximum() + buffer]
        return bbox


    def LaunchDownload(self):
        start_date = self.date_from.date().toPyDate().strftime("%Y-%m-%d")
        end_date = self.date_to.date().toPyDate().strftime("%Y-%m-%d")
        polygon_name = self.mMapLayerComboBox.currentLayer()
        vector_location = polygon_name.dataProvider().dataSourceUri()
        bbox = self.get_bbox()
        token = self.read_token()
        
        self.worker = WorkerThread(token, bbox, 
                                   self.current_download_location, self.chb_clip_to_cutline.isChecked(), self.combo_dekadal.currentText(),
                                   self.treeWidget, start_date, end_date, self.MasterList, vector_location, self.cbx_workspace.currentText())
        self.worker.start()
        self.worker.UpdateStatus.connect(self.evt_UpdateStatusUI)
        self.worker.UpdateProgress.connect(self.UpdateProgressUI)
        
        # if download is in progress, let us cancel
        # if not let us launch and we will change text in any case
        if self.btn_download.text() == "Retrieve Data":
            self.btn_download.setText("Cancel Download")
            self.btn_download.clicked.disconnect(self.LaunchDownload)
            self.btn_download.clicked.connect(self.StopDownload)

            self.btn_download.setFixedSize(141, 101)
            
            self.pbar_primary.setFixedSize(141, 9)
            self.pbar_secondary.setFixedSize(141, 21)

            self.pbar_primary.setValue(0)
            self.pbar_secondary.setValue(0)
            
        
    def evt_UpdateStatusUI(self, text):
        if text == "Status: Download Completed":
            if self.btn_download.text() == "Cancel Download":
                self.btn_download.setFixedSize(141, 142)

                self.pbar_primary.setFixedSize(0, 0)
                self.pbar_secondary.setFixedSize(0, 0)

                self.btn_download.setText("Retrieve Data")
                self.btn_download.clicked.disconnect(self.StopDownload)
                self.btn_download.clicked.connect(self.LaunchDownload)

        self.labelStatus.setText(text)
    
    
    def UpdateProgressUI(self, text):

        if len(text.split("\n")) == 3:
            try:
                # update progress bar
                base_parts = text.split("\n"); cpp = base_parts[1].split(' '); spp = base_parts[2].split(' ')

                current_primary_progress = [int(cpp[2]), int(cpp[4])]
                current_secondary_progress = [int(spp[2]), int(spp[4])]


                self.pbar_primary.setMaximum(current_primary_progress[1])
                self.pbar_primary.setValue(current_primary_progress[0])

                self.pbar_secondary.setMaximum(current_secondary_progress[1])
                self.pbar_secondary.setValue(current_secondary_progress[0])

            except: pass
        
        self.labelProgress.setText(text)
        
        
    def StopDownload(self):
        self.worker.requestInterruption()
        self.labelStatus.setText("Status: Canceling Download")  
        
        if self.btn_download.text() == "Cancel Download":
            self.btn_download.setFixedSize(141, 142)

            self.pbar_primary.setFixedSize(0, 0)
            self.pbar_secondary.setFixedSize(0, 0)

            self.btn_download.setText("Retrieve Data")
            self.btn_download.clicked.disconnect(self.StopDownload)
            self.btn_download.clicked.connect(self.LaunchDownload)
        
        
    def update_token(self):
        print('updating token...')
        token_fn = os.path.join(os.path.dirname(__file__), 'token.dll')
        token_text = self.wapor_tokenbox.toPlainText()
        self.write_to(token_fn, token_text)


    def read_token(self):
        token_fn = os.path.join(os.path.dirname(__file__), 'token.dll')
        if self.exists(token_fn): return self.read_from(token_fn)[0]
        else: return ''


    def validate_token(self):
        resp_vp=requests.post(self.path_sign_in,headers={'X-GISMGR-API-KEY':self.read_token()})
        resp_vp = resp_vp.json()
        print("validate_token")
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


    def browse_default_directory(self):
        startingDir = "/"
        destDir = QTW.QFileDialog.getExistingDirectory(None, 
                                                    'Select Default Download Directory', 
                                                    startingDir, 
                                                    QTW.QFileDialog.ShowDirsOnly)

        if len(destDir) > 0:
            default_dir_fn = os.path.join(os.path.dirname(__file__), 'defdir.dll')
            self.write_to(default_dir_fn, destDir)
            self.check_default_download_dir()
        
        
    def browse_download_directory(self):
        print('select download directory...')

        startingDir = "/"
        destDir = QTW.QFileDialog.getExistingDirectory(None, 
                                                    'Select Download Directory', 
                                                    startingDir, 
                                                    QTW.QFileDialog.ShowDirsOnly)

        if len(destDir) > 0:
            self.txb_download_location.setText(destDir)
            self.current_download_location = destDir
        
        
    def check_default_download_dir(self):
        default_dir_fn = os.path.join(os.path.dirname(__file__), 'defdir.dll')
        if self.exists(default_dir_fn):
            self.txt_default_dir_path.setText(self.read_from(default_dir_fn)[0])
        else:
            self.txt_default_dir_path.setText("")


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
        with open(filename, 'r') as g:
            file_text = g.readlines()
        return file_text
    

    def LaunchPopup(self, item):
        if item.childCount()  == 0 or item.parent() == None:
            if item.childCount()  == 0 and item.parent() != None:
                self.pop = InfoPopup(item.text(1), 0, self.MasterList)
            if item.parent() == None:
                self.pop = InfoPopup(item.text(0),1)
            self.pop.setWindowTitle(item.text(0))
            self.pop.show()


class InfoPopup(QTW.QWidget):
        def __init__(self, code, index, MasterList = None):
            super().__init__()
            layout = QTW.QGridLayout()
            if index == 0:
                for x in MasterList:
                    if str(x.get('code'))  == code:                 
                      keylist = ['caption', 'code', 'description']+list(x.get('additionalInfo').keys())
                      valuelist = [x.get('caption'), x.get('code'), x.get('description')]+list(x.get('additionalInfo').values())
                      
                      keyitems = len(keylist)-1
                      keyposition = 0
                      while keyposition <= keyitems:
                              y = QTW.QLabel(str(keylist[keyposition]))
                              y.setWordWrap(True)
                              y.setStyleSheet("border: 1px solid black;")
                              y.setTextInteractionFlags(QTC.Qt.TextInteractionFlag.TextSelectableByMouse)
                              layout.addWidget(y,keyposition,0)
                                
                              y = QTW.QLabel(str(valuelist[keyposition]))
                              y.setWordWrap(True)
                              y.setStyleSheet("border: 1px solid black;")
                              y.setTextInteractionFlags(QTC.Qt.TextInteractionFlag.TextSelectableByMouse)
                              layout.addWidget(y,keyposition,1)
                              
                              keyposition += 1
                      break         
            if index == 1:
                      responce = ((requests.get(r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/{0}'.format(code)).json()).get('response'))
                      print(responce)
                      keylist = []
                      valuelist = []
                      try:
                          valuelist.append(responce['description'])
                          keylist.append(responce['caption'])
                      except:
                          pass
                      try:
                          valuelist.append(responce['additionalInfo']['created'])
                          keylist.append('Created')
                      except:
                          pass
                      try:
                          valuelist.append(responce['additionalInfo']['site'])
                          keylist.append('Site')
                      except:
                          pass
                        
                      
                      keyitems = len(keylist)-1
                      keyposition = 0
                      while keyposition <= keyitems:
                              y = QTW.QLabel(str(keylist[keyposition]))
                              y.setWordWrap(True)
                              y.setStyleSheet("border: 1px solid black;")
                              y.setTextInteractionFlags(QTC.Qt.TextInteractionFlag.TextSelectableByMouse)
                              layout.addWidget(y,keyposition,0)
                                
                              y = QTW.QLabel(str(valuelist[keyposition]))
                              y.setWordWrap(True)
                              y.setStyleSheet("border: 1px solid black;")
                              y.setTextInteractionFlags(QTC.Qt.TextInteractionFlag.TextSelectableByMouse)
                              layout.addWidget(y,keyposition,1)
                              
                              keyposition += 1
            
            self.setLayout(layout)
            
            
class WorkerThread(QTC.QThread):
    UpdateStatus = QTC.pyqtSignal(str)
    UpdateProgress = QTC.pyqtSignal(str)
    
    def __init__(self, wapor_api_token, bbox, FolderLocation, CropChecked, Combo, SelectWidget, Startdate, Enddate, MasterList, vector_location, workspace):
        super().__init__()
        self.wapor_api_token = wapor_api_token 
        self.bbox = bbox 
        self.FolderLocation = FolderLocation
        self.CropChecked = CropChecked
        self.Combo = Combo
        self.SelectWidget = SelectWidget 
        self.Startdate = Startdate 
        self.Enddate = Enddate
        self.MasterList = MasterList
        self.vector_location = vector_location
        
        self.path_catalog = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/'
        self.path_download = r'https://io.apps.fao.org/gismgr/api/v1/download/'
        self.path_jobs = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR/jobs/'
        self.path_query = r'https://io.apps.fao.org/gismgr/api/v1/query/'
        self.path_sign_in = r'https://io.apps.fao.org/gismgr/api/v1/iam/sign-in/'
        self.workspaces = workspace
    
    
    def Mbox(self, title, text, style):
        return ctypes.windll.user32.MessageBoxW(0, text, title, style) 
    
    
    def run(self):
        x = 0
        self.UpdateStatus.emit("Status: Checking Inputs")
        #try to make new base folder
        try:
            self.base_save_folder = os.path.join(self.FolderLocation,self.workspaces + " " + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
            print(self.base_save_folder)
            os.makedirs(self.base_save_folder)
        except:
            self.Mbox('Error', 'Unable to create new folder for download in the selected folder.', 0)
            x += 1    
        #check start date is less that end date
        if self.Enddate < self.Startdate:
            self.Mbox('Error', 'End date is earlier than the Start date.', 0)
            x += 1
        #Creats self.SelectedCubeCodes (a list of checked boxes for FAO request), and self.cubedict (contains info for each checked box)
        self.Selected()
        
        #Check that at least one box is checked
        if self.SelectedCubeCodes  == []:
            self.Mbox('Error', 'Must have one item checked for FAO request.', 0)
            x += 1

        #User inputs have been checked in the above sections so now the data requests to the FAO server can be started    
        if x  == 0:
            self.DownloadRequest()  
        else:
            self.UpdateStatus.emit("Status:")            
            pass

  
    def query_accessToken(self):
            resp_vp = requests.post(self.path_sign_in,headers = {'X-GISMGR-API-KEY':self.wapor_api_token})
            resp_vp = resp_vp.json()
            print("query_accessToken")
            print(resp_vp)
            try:
                self.AccessToken = resp_vp['response']['accessToken']               
                self.time_expire = resp_vp['response']['expiresIn']-600 #set expire time 2 minutes earlier
                self.time_start = datetime.datetime.now().timestamp()
            except:

                self.Mbox( 'Error:', resp_vp['message'],0)    
    
    
    def CheckAccessToken(self):     
            time_now = datetime.datetime.now().timestamp()
            if time_now-self.time_start > self.time_expire:
                self.query_accessToken()       


    def LCC_Legend(self, cube_code, savefolder):
        LCCBody = pd.DataFrame.from_dict(self.cubedict[cube_code]['cubemeasure']['classes']).T
        LCCTitle = pd.DataFrame.from_dict({self.cubedict[cube_code]['cubemeasure']['code']: {'caption': self.cubedict[cube_code]['cubemeasure']['caption'], 'description': self.cubedict[cube_code]['cubemeasure']['description']} }).T
        LCCList = pd.concat([LCCTitle, LCCBody])
        LCCList.to_csv(os.path.join(savefolder,'{0} Legend.csv'.format(cube_code)) ,encoding = 'utf-8', sep = ',')
      
        
    def Selected(self):
        self.SelectedCubeCodes = []
        iterator = QTW.QTreeWidgetItemIterator(self.SelectWidget,  QTW.QTreeWidgetItemIterator.IteratorFlag(0x00001000) )
        while iterator.value():
            CurrentItem = iterator.value()
            if CurrentItem.childCount()  == 0:
                self.SelectedCubeCodes.append(CurrentItem.text(1))
            iterator += 1
        self.AddCubeData()
        
        
    def AddCubeData(self):
        self.cubedict = dict()

        for cubecode in self.SelectedCubeCodes:
                    for x in self.MasterList:
                        if x.get('code')  == cubecode:
                            self.cubedict[cubecode] = x
                            break
                    
                    #Measures
                    #provides operations pertaining to Measure resources
                    #returns a list (paged or not) of available Measure resource type items
                    #example: https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes/L1_E_A/measures?overview=false&paged=false
                    request_json = (requests.get(r'{0}{1}/cubes/{2}/measures?overview=false&paged=false'.format(self.path_catalog,self.workspaces, cubecode)).json())
                    if request_json['status']  == 200:
                        self.cubedict[cubecode].update({'cubemeasure':(request_json['response'][0])})
                    else:
                        self.Mbox( 'Error' ,str(request_json['message']),0)

                    #Cube Dimensions: provides operations pertaining to CubeDimension resources
                    #get the CubeDimensions list
                    #example:https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes/L1_AETI_M/dimensions?overview=false&paged=false
                    request_json = (requests.get(r'{0}{1}/cubes/{2}/dimensions?overview=false&paged=false'.format(self.path_catalog,self.workspaces,cubecode)).json())
                    if request_json['status']  == 200:
                        self.cubedict[cubecode].update({'cubedimensions':(request_json['response'])})
                    else:
                        self.Mbox( 'Error' ,str(request_json['message']),0)
        

    def DownloadRequest(self):        
            #Sets off main request code chunk
            self.UpdateStatus.emit("Status: Preparing Download")
            m = 0
            self.query_accessToken()
            for  cube_code in self.SelectedCubeCodes:
                if self.isInterruptionRequested()  == False:
                    m+= 1
                    self.UpdateProgress.emit("Progress: Starting download for FAO data {0}.\n Item number {1} of {2}".format(cube_code, m,  str(len(self.SelectedCubeCodes))))
                    self.UpdateStatus.emit("Status: Creating Data list")
                    df_avail = self.Get_df(cube_code, self.Startdate, self.Enddate) 
                    
                    multiplier = self.cubedict[cube_code]['cubemeasure']['multiplier']
                    savefolder = os.path.join(self.base_save_folder, cube_code)
                    os.makedirs(savefolder)
                    df_avail.to_csv(os.path.join(self.base_save_folder,cube_code +' list.csv'))
                    
                   #self.ui.labelStatus.setText("Status: Constructing FAO Request")
                    if 'lcc' in cube_code.lower() and self.workspaces == 'WAPOR_2':
                        self.LCC_Legend(cube_code, savefolder)
                        pass
                    
                    n = 0
                    for index, row in df_avail.iterrows():
                        if self.isInterruptionRequested()  == False:
                            n+= 1            
                            self.UpdateProgress.emit("Progress: Starting download for FAO data {0}. \nItem number {1} of {2} \nDownloading raster {3} of {4}".format(cube_code, m,  str(len(self.SelectedCubeCodes)), n,str(len(df_avail))))
                            self.UpdateStatus.emit("Status: Requesting download URL from FAO")
                            self.download_url = self.getCropRasterURL(cube_code, row) 
                            
                            self.UpdateStatus.emit("Status: Downloading")
                            resp = requests.get(self.download_url)
                            self.UpdateStatus.emit("Status: Correcting raster")
                            self.Tiff_Edit_Save(cube_code,  multiplier, row, savefolder, resp)
                            
            if self.isInterruptionRequested()  == False:
                self.UpdateStatus.emit("Status: Download Completed")
                self.UpdateProgress.emit("")
            else:
                self.UpdateStatus.emit("Status: Download Canceled")
                self.UpdateProgress.emit("")
                
    def Get_df(self, cube_code, Startdate, Enddate):
        time_range = '{0},{1}'.format(Startdate,Enddate)
        try:
            df_avail = self.getAvailData(cube_code,time_range)
            return df_avail
        except:
            self.Mbox( 'Error' ,'Cannot get list of available requested data',0)
            return
        
                
    def Tiff_Edit_Save(self, cube_code,  multiplier, row, savefolder, resp):                  
      #check this works for seasonal and non seasonal
              try:   
                  cube_dimensions = self.cubedict[cube_code]['cubedimensions']
                  rasterID_index = (len(row) - 2)
                  rasterID = row[rasterID_index]
            
                  time_code = ''
                  if any('TIME' in d.values() for d in cube_dimensions):
                      time_code_index = int(((len(row) - 2)/3))
                      time_code = row[time_code_index]
     
                  filename = '{0}{1}.tif'.format(rasterID, time_code)
                  outfilename = os.path.join(savefolder,filename)       
                  download_file = os.path.join(savefolder,'raw_{0}.tif'.format(rasterID))
                  ndays = 1
                  #By defualt dekadal data from WaPOR is an average. This allows it to give the cumulative value.
                  if any(d['code'] == 'DEKAD' for d in self.cubedict[cube_code]['cubedimensions']) and self.Combo  == 'Cumulative' and self.workspaces == 'WAPOR_2':
                      timestr = time_code
                      startdate = datetime.datetime.strptime(timestr[1:11],'%Y-%m-%d')
                      enddate = datetime.datetime.strptime(timestr[12:22],'%Y-%m-%d')
                      ndays = (enddate.timestamp()-startdate.timestamp())/86400
                  open(download_file,'wb').write(resp.content)
                  driver, NDV, xsize, ysize, GeoT, Projection = self.GetGeoInfo(download_file)
                  Array = self.OpenAsArray(download_file,nan_values = True)
                  correction = multiplier * ndays
                  
                  if(self.workspaces == 'ASIS' and cube_code != 'PHE'):
                      CorrectedArray = np.multiply(Array, correction, out = Array, where = Array < 251)
                  else:
                      CorrectedArray = np.multiply(Array, correction, where = Array!=NDV)
                      
                  self.CreateGeoTiff(outfilename,CorrectedArray,
                                    driver, NDV, xsize, ysize, GeoT, Projection)

                  os.remove(download_file)          
                  if self.CropChecked:
                      gdal.Warp(os.path.join(savefolder,('Clip' + filename)), outfilename,cutlineDSName = self.vector_location, cropToCutline = (True), warpOptions = [ 'CUTLINE_ALL_TOUCHED=TRUE' ])#
                      os.remove(outfilename)
                      os.rename(os.path.join(savefolder,('Clip' + filename)), outfilename)
              except:
                  pass


    def getAvailData(self,cube_code,time_range):
        try:
            measure_code = self.cubedict[cube_code]['cubemeasure']['code']
            dimensions = self.cubedict[cube_code]['cubedimensions']

        except:
            self.Mbox( 'Error' ,'Cannot get cube info',0)
           
        df_dims_ls = []
        dims_ls = []
        columns_codes = ['MEASURES']
        rows_codes = []
        try:

            for item in dimensions:
                if item['type']  == 'TIME': #get time dims
                    time_dims_code = item['code']
                    df_time, avalible_data = self._query_dimensionsMembers(cube_code,time_dims_code)
                    df_dims_ls = df_dims_ls + avalible_data
                    time_dims = {
                        "code": time_dims_code,
                        "range": '[{0})'.format(time_range)
                        }
                    dims_ls.append(time_dims)
                    rows_codes.append(time_dims_code)  
                if item['type']  == 'WHAT':
                    dims_code = item['code']
                    df_dims , avalible_data = self._query_dimensionsMembers(cube_code,dims_code)
                    df_dims_ls = df_dims_ls + avalible_data
                    members_ls = df_dims['code'].tolist()
                    what_dims = {
                            "code":item['code'],
                            "values":members_ls
                            }
                    dims_ls.append(what_dims)
  
                    rows_codes.append(item['code']) 

            df = self._query_availData(cube_code,measure_code,
                             dims_ls,columns_codes,rows_codes)
        except:
            self.Mbox( 'Error' ,'Failed request cannot get list of available data',0)
            return None
        
        keys = []
        for item in rows_codes:
            keys.append(item)
            keys.append(item + '-code')
            keys.append(item + '-description')
       
   
        keys = keys + ['raster_id','bbox']
        df_dict = { i : [] for i in keys }
        for irow,row in df.iterrows():
            header_count = 0
            cell_count = 0
            for i in range(len(row)): 
                if row[i] == None:
                    break
                if row[i]['type']  == 'ROW_HEADER':
                    key_info = row[i]['value']
                    header_number = int(header_count * 3)
                    df_dict[keys[header_number]].append(key_info)
                    #df_dims_ls can get quite long
                    #potentialy could be a quicker way to iterate through.
                    for j in df_dims_ls:
                        if j['caption'] ==  key_info:
                            key= keys[header_number] + '-code'
                            df_dict[key].append(j['code'])
                            key= keys[header_number] + '-description'
                            #Not all items have a description
                            try:
                                df_dict[key].append(j['description'])
                            except:
                                df_dict[key].append('NA')
                            header_count += 1
                            break

                if row[i]['type']=='DATA_CELL':
                    if cell_count != 0:
                        k=0
                        while k < len(df_dict)-2:
                            key = keys[k]
                            df_dict[key].append(df_dict[key][-1])
                            k += 1
                        
                    raster_info=row[i]['metadata']['raster']    
                    df_dict['raster_id'].append(raster_info['id'])
                    df_dict['bbox'].append(raster_info['bbox'])
                    cell_count += 1

        df_sorted=pd.DataFrame.from_dict(df_dict)
        return df_sorted            
    
    
    def _query_dimensionsMembers(self,cube_code,dims_code):
        base_url = '{0}{1}/cubes/{2}/dimensions/{3}/members?overview=false&paged=false'       
        request_url = base_url.format(self.path_catalog,
                                    self.workspaces,
                                    cube_code,
                                    dims_code
                                    )
        resp = requests.get(request_url)
        resp_vp = resp.json()
        try:
            avail_items = resp_vp['response']
            df = pd.DataFrame.from_dict(avail_items, orient = 'columns')
        except:
            self.Mbox( 'Error' ,'Cannot get dimensions Members.'+str(resp_vp['message']),0)
        return df , avail_items


    def _query_availData(self,cube_code,measure_code,
                         dims_ls,columns_codes,rows_codes):                
        query_load = {
          "type": "MDAQuery_Table",              
          "params": {
            "properties": {                     
              "metadata": True,                     
              "paged": False,                 
            },
            "cube": {                            
              "workspaceCode": self.workspaces,            
              "code": cube_code,                       
              "language": "en"                      
            },
            "dimensions": dims_ls,
            "measures": [measure_code],
            "projection": {                      
              "columns": columns_codes,                               
              "rows": rows_codes
            }
          }
        }

        resp = requests.post(self.path_query, json = query_load)
        resp_vp = resp.json()
        print("_query_availData")
        print(resp_vp)
        try:
            results = resp_vp['response']['items']
            #Some of the responces have duplicate items in them which need to be removed 
            #the following section removes these duplicates.
            #exception writen in for where the duplicates are intentional
            if cube_code != 'EMS' and self.workspaces != 'GLEAM3':
                for item in results:
                    y = len(item)-1    
                    while y > 0:
                        if item[y] in item[:y]:
                            item.remove(item[y])
                            if y > len(item)-1:
                                y -= 1
                        else:
                            y -= 1
                            
            return pd.DataFrame(results)
        
        except:
            self.Mbox( 'Error' ,'Cannot get list of available data.'+str(resp_vp['message']),0)
        
            
    def getCropRasterURL(self,cube_code,
                          row):
        #Create Polygon        
        xmin,ymin,xmax,ymax = self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3]
        Polygon = [
                  [xmin,ymin],
                  [xmin,ymax],
                  [xmax,ymax],
                  [xmax,ymin],
                  [xmin,ymin]
                ]
        cube_measure_code = self.cubedict[cube_code]['cubemeasure']['code']
        dimension_params = []
        rasterID_index = (len(row) - 2)
        rasterID = row[rasterID_index]
        x=0
        while x < (len(row)-2):
            i_code = int(x+1)                         
            dimension_params.append({
            "code": row.index[x],
            "values": [row[i_code]]
            })
            x += 3
 
        #Query payload
        query_crop_raster = {
          "type": "CropRaster",
          "params": {
            "properties": {
              "outputFileName": "{0}.tif".format(rasterID),
              "cutline": True,
              "tiled": True,
              "compressed": True,
              "overviews": True
            },
            "cube": {
              "code": cube_code,
              "workspaceCode": self.workspaces,
              "language": "en"
            },
            "dimensions": dimension_params,
            "measures": [
              cube_measure_code
            ],
            "shape": {
              "type": "Polygon",
              "properties": {
                      "name": "epsg:4326" #latlon projection
                              },
              "coordinates": [
                Polygon
              ]
            }
          }
        }
        
        self.CheckAccessToken()
        resp_vp = requests.post(self.path_query,
                              headers = {'Authorization':'Bearer {0}'.format(self.AccessToken)},
                                                        json = query_crop_raster)
        resp_vp = resp_vp.json()
        print("getCropRasterURL")
        print(resp_vp)
        try:
            job_url = resp_vp['response']['links'][0]['href']
            download_url = self._query_jobOutput(job_url)
            return download_url     
        except:
            self.Mbox( 'Error' ,'Cannot get cropped raster URL',0)
  
    
    def _query_jobOutput(self,job_url):
     #This method queries the FAO sever until the download is ready which it then returns.
     contiue = True        
     while contiue:        
         resp = requests.get(job_url)
         resp = resp.json()
         jobType = resp['response']['type'] 
                
         if resp['response']['status']  == 'COMPLETED':
             contiue = False
             if jobType  == 'CROP RASTER':
                 output = resp['response']['output']['downloadUrl']                
             elif jobType  == 'AREA STATS':
                 results = resp['response']['output']
                 output = pd.DataFrame(results['items'], columns = results['header'])
             else:
                 pass                
             return output
         if resp['response']['status']  == 'COMPLETED WITH ERRORS':
             contiue = False    
         #Method keeps pinging the sever till the request is done. Short delay to minimize the number of requests.       
         time.sleep(2)

    
    def GetGeoInfo(self, fh, subdataset = 0):

        SourceDS = gdal.Open(fh, gdal.GA_Update)
        Type = SourceDS.GetDriver().ShortName
        if Type  == 'HDF4' or Type  == 'netCDF':
            SourceDS = gdal.Open(SourceDS.GetSubDatasets()[subdataset][0])
        NDV = SourceDS.GetRasterBand(1).GetNoDataValue()
        xsize = SourceDS.RasterXSize
        ysize = SourceDS.RasterYSize
        GeoT = SourceDS.GetGeoTransform()
        Projection = osr.SpatialReference()
        Projection.ImportFromWkt(SourceDS.GetProjectionRef())
        driver = gdal.GetDriverByName(Type)
        return driver, NDV, xsize, ysize, GeoT, Projection    
    

    def OpenAsArray(self, fh, bandnumber = 1, dtype = 'float32', nan_values = False):

        datatypes = {"uint8": np.uint8, "int8": np.int8, "uint16": np.uint16, "int16":  np.int16, "Int16":  np.int16, "uint32": np.uint32,
        "int32": np.int32, "float32": np.float32, "float64": np.float64, "complex64": np.complex64, "complex128": np.complex128,
        "Int32": np.int32, "Float32": np.float32, "Float64": np.float64, "Complex64": np.complex64, "Complex128": np.complex128,}
        DataSet = gdal.Open(fh, gdal.GA_Update)
        Type = DataSet.GetDriver().ShortName
        if Type  == 'HDF4':
            Subdataset = gdal.Open(DataSet.GetSubDatasets()[bandnumber][0])
            NDV = int(Subdataset.GetMetadata()['_FillValue'])
        else:
            Subdataset = DataSet.GetRasterBand(bandnumber)
            NDV = Subdataset.GetNoDataValue()
        Array = Subdataset.ReadAsArray().astype(datatypes[dtype])
        if nan_values:
            Array[Array  == NDV] = np.nan
        return Array
   
    
    def CreateGeoTiff(self, fh, Array, driver, NDV, xsize, ysize, GeoT, Projection, explicit = True, compress = None):
        
        datatypes = {"uint8": 1, "int8": 1, "uint16": 2, "int16": 3, "Int16": 3, "uint32": 4,
        "int32": 5, "float32": 6, "float64": 7, "complex64": 10, "complex128": 11,
        "Int32": 5, "Float32": 6, "Float64": 7, "Complex64": 10, "Complex128": 11,}
        if compress != None:
            DataSet2 = driver.Create(fh,xsize,ysize,1,datatypes[Array.dtype.name], ['COMPRESS={0}'.format(compress)])
        else:
            DataSet2 = driver.Create(fh,xsize,ysize,1,datatypes[Array.dtype.name])
        if NDV is None:
            NDV = -9999
        if explicit:
            Array[np.isnan(Array)] = NDV
        DataSet2.GetRasterBand(1).SetNoDataValue(NDV)
        DataSet2.SetGeoTransform(GeoT)
        DataSet2.SetProjection(Projection.ExportToWkt())
        DataSet2.GetRasterBand(1).WriteArray(Array)
        DataSet2 = None
        if "nt" not in Array.dtype.name:
            Array[Array  == NDV] = np.nan 
            

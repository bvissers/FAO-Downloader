# -*- coding: utf-8 -*-
"""


author: Brenden Vissers

Contributions from:
         Bich Tran
         IHE Delft 2019

Authors: Tim Hessels and Bert Coerver
UNESCO-IHE 2017
"""

import os
from PyUI import Ui_Widget
from PyQt6 import QtWidgets as qtw
from PyQt6 import QtCore as qtc
from PyQt6.QtCore import QThreadPool
import pickle
import easygui
import ctypes
import requests
import threading

import datetime
import pandas as pd

import geopandas as gpd
from osgeo import gdal
from osgeo import osr
import numpy as np
import time
from pathlib import Path




class WaPORwidget(qtw.QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_catalog = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/'
        self.path_download = r'https://io.apps.fao.org/gismgr/api/v1/download/'
        self.path_jobs = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR/jobs/'
        self.path_query = r'https://io.apps.fao.org/gismgr/api/v1/query/'
        self.path_sign_in = r'https://io.apps.fao.org/gismgr/api/v1/iam/sign-in/'
        self.workspaces = 'WAPOR_2'
        
        self.setFixedSize(828, 600)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)
        try:
            self.ui.plainTextEditExport.setPlainText(str(os.path.join(Path.home(), "Downloads")))
        except:
            pass
        
        self.ui.tabWidget.setTabEnabled(1, False)
        self.LoadAPI()
        self.ui.dateEnd.setDate(qtc.QDate.currentDate())
        self.ui.dateEnd.setMaximumDate((qtc.QDate.currentDate()))
        self.thread_manager = QThreadPool()
        self.CancelDownload = False
        


        #Set buttons
        self.ui.treeWidget.itemDoubleClicked.connect(self.LaunchPopup)        
        self.ui.ButtonSave.clicked.connect(self.SaveAPI)        
        self.ui.ButtonShape.clicked.connect(self.FileLocation)
        self.ui.ButtonFolder.clicked.connect(self.FolderLocation)
        self.ui.ButtonCancel.clicked.connect(self.StopDownload)
        self.ui.ButtonDownload.clicked.connect(lambda: self.LaunchDownload())
 


#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX                 XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX     Methods     XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX                 XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    def closeEvent(self, event):
        self.worker.requestInterruption()
   
    
    
        
    def LoadAPI(self):
        api_token_pickle = os.path.join(os.path.dirname(__file__),
                                      'wapor_api_token.pickle')
        try: 
            with open(api_token_pickle, 'rb') as handle:
                self.wapor_api_token = pickle.load(handle)
                ResponceStatus, ResponceMessage = self.ValidAccessToken()
                if ResponceStatus  == 200: 
                    self.ui.tabWidget.setTabEnabled(1, True)
                    self.PackageList()
                    self.ui.LableLoad.setText("Token Loaded")
                else:
                    self.ui.LableLoad.setText("Failed to Load Token")
                   
        except:
            pass
        
    def SaveAPI(self):    
        api_token_pickle = os.path.join(os.path.dirname(__file__),
                                      'wapor_api_token.pickle')
        
        self.wapor_api_token = self.ui.plainTextEditAPI.toPlainText()
        if len(self.wapor_api_token)>0:
            try:   
                ResponceStatus,ResponceMessage = self.ValidAccessToken()
                if ResponceStatus  == 200: 
                    self.ui.tabWidget.setTabEnabled(1, True)
                    with open(api_token_pickle, 'wb') as handle:
                        pickle.dump(self.wapor_api_token, handle, protocol = pickle.HIGHEST_PROTOCOL)
                        self.PackageList()
                        self.ui.tabWidget.setTabEnabled(1, True)
                        self.ui.LableLoad.setText("Saved Token")
                else:
                    self.Mbox( 'Error' ,str(ResponceMessage),0)
                    self.ui.LableLoad.setText("No Token Saved")
            except:
                self.Mbox( 'Error','Personal API Key is not valid and/or is not enabled.',0)
                
            
    def ValidAccessToken(self):
        resp_vp = requests.post(self.path_sign_in,headers = {'X-GISMGR-API-KEY':self.wapor_api_token})
        resp_vp = resp_vp.json()
        try:
            return resp_vp['status'], resp_vp['message']
        except:
            self.Mbox( 'Error','Could not connect to server.',0)
            

           
    def FolderLocation(self):
        self.ui.plainTextEditExport.setPlainText('')
        FolderLocation = easygui.diropenbox(msg = 'Choose export folder location.')
        try:
            self.ui.plainTextEditExport.setPlainText(FolderLocation)
        except:
            pass            
            
    def FileLocation(self):
        self.ui.LableVectorLocation.setText("")
        self.FileName = easygui.fileopenbox(msg = "Select a file with the .shp extention",filetypes = ["*.shp","shape files"])
        self.ui.LableVectorLocation.setText(self.FileName)
        self.FileName = self.ui.LableVectorLocation.text()    
    
    def Mbox(self, title, text, style):
        return ctypes.windll.user32.MessageBoxW(0, text, title, style)  
  
    def PackageList(self):
        try:
            #Cubes: provides operations pertaining to Cube resources
            #returns a list of available Cube resource type items
            #example:https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview = false&paged = false&sort = sort%20%3D%20code&tags = L1'
            L1 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1'.format(self.path_catalog,self.workspaces)).json()).get('response'))
            L2 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L2'.format(self.path_catalog,self.workspaces)).json()).get('response'))
            L3 = ((requests.get('{0}{1}/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L3'.format(self.path_catalog,self.workspaces)).json()).get('response'))            
            self.MasterList = L1 + L2 + L3
            #sorts by type of information
            L1 = sorted(L1, key = lambda d: d.get('caption'))
            L2 = sorted(L2, key = lambda d: d.get('caption'))
            #Sorts first country location, then by type of information
            L3 = sorted(L3, key = lambda d: [d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[2],d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[1] ,d.get('code') ])
            #creates the treewidget to select data from
            self.ui.treeWidget.clear()
            self.ui.treeWidget.headerItem().setText(0, self.workspaces)
            self.TreeAddBasic(L1, "Level 1")
            self.TreeAddBasic(L2, "Level 2")
            self.TreeAddLvl3(L3, "Level 3")
        except:
            self.Mbox( 'Error' ,'Error Loading data from the WaPOR Server',0)

    def TreeAddBasic(self, L, name):    
           
            parent = qtw.QTreeWidgetItem(self.ui.treeWidget)

            parent.setText(0, name)        
            parent.setFlags(parent.flags()   | qtc.Qt.ItemFlag.ItemIsUserCheckable | qtc.Qt.ItemFlag.ItemIsAutoTristate)
            
            for x in L:
                child = qtw.QTreeWidgetItem(parent)
                child.setFlags(child.flags() | qtc.Qt.ItemFlag.ItemIsUserCheckable)
                child.setText(0, x.get('caption'))
                child.setText(1, str(x.get('code')))
                child.setCheckState(0, qtc.Qt.CheckState.Unchecked)
                
        
    def TreeAddLvl3(self, L, name):    
           
            parent = qtw.QTreeWidgetItem(self.ui.treeWidget)
            
            parent.setText(0, name)        
            parent.setFlags(parent.flags()   | qtc.Qt.ItemFlag.ItemIsUserCheckable | qtc.Qt.ItemFlag.ItemIsAutoTristate)
            locations = []
            
            for x in L:
                if (x.get('additionalInfo').get('spatialExtent')) not in locations:
                    locations.append(x.get('additionalInfo').get('spatialExtent'))
                    country = qtw.QTreeWidgetItem(parent)
                    country.setFlags(country.flags() | qtc.Qt.ItemFlag.ItemIsUserCheckable| qtc.Qt.ItemFlag.ItemIsAutoTristate)
                    country.setText(0, locations[-1])
                    country.setCheckState(0, qtc.Qt.CheckState.Unchecked)        

                child2 = qtw.QTreeWidgetItem(country)
                child2.setFlags(child2.flags() | qtc.Qt.ItemFlag.ItemIsUserCheckable)
                child2.setText(0, x.get('caption'))
                child2.setCheckState(0, qtc.Qt.CheckState.Unchecked)     
                child2.setText(1, str(x.get('code')))  

    def LaunchPopup(self, item):
        if item.childCount()  == 0:
            self.pop = InfoPopup(item.text(1), self.MasterList)
            self.pop.show()
            

        
    def LaunchDownload(self):
        x=0
        
        StartDateEdit = self.ui.dateStart.date().toPyDate().strftime("%Y-%m-%d")
        EndDateEdit = self.ui.dateEnd.date().toPyDate().strftime("%Y-%m-%d")
        #check folder is valid folder
        
        
        if os.path.isdir(self.ui.plainTextEditExport.toPlainText())  == False:
            self.Mbox('Error', 'Invalid folder Location.', 0)
            x += 1
        if hasattr(self, 'FileName') == False:
            self.Mbox('Error', 'No Vector File inputed.', 0)
            x  == 1        
        
        if x == 0:
            self.worker = WorkerThread(self.wapor_api_token, self.FileName, self.ui.plainTextEditExport.toPlainText(), self.ui.checkBoxClip.isChecked(), self.ui.comboDekadal.currentText(),self.ui.treeWidget, StartDateEdit, EndDateEdit, self.MasterList)
            self.worker.start()
            self.worker.UpdateStatus.connect(self.evt_UpdateStatusUI)
            self.worker.UpdateProgress.connect(self.UpdateProgressUI)
        
    def evt_UpdateStatusUI(self, text):
        self.ui.labelStatus.setText(text)
        
    def UpdateProgressUI(self, text):
            self.ui.labelProgress.setText(text)
            
    def StopDownload(self):
        print(1)
        self.worker.requestInterruption()
        print(1)
        self.ui.labelStatus.setText("Status: Canceling Download")    
            
            
class WorkerThread(qtc.QThread):
    UpdateStatus = qtc.pyqtSignal(str)
    UpdateProgress = qtc.pyqtSignal(str)
    
    def __init__(self, wapor_api_token, VFileLocation, FolderLocation, CropChecked, Combo, SelectWidget, Startdate, Enddate, MasterList):
        super().__init__()
        self.wapor_api_token = wapor_api_token 
        self.VFileLocation = VFileLocation 
        self.FolderLocation = FolderLocation
        self.CropChecked = CropChecked
        self.Combo = Combo
        self.SelectWidget = SelectWidget 
        self.Startdate = Startdate 
        self.Enddate = Enddate
        self.MasterList = MasterList
        
        self.path_catalog = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/'
        self.path_download = r'https://io.apps.fao.org/gismgr/api/v1/download/'
        self.path_jobs = r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR/jobs/'
        self.path_query = r'https://io.apps.fao.org/gismgr/api/v1/query/'
        self.path_sign_in = r'https://io.apps.fao.org/gismgr/api/v1/iam/sign-in/'
        self.workspaces = 'WAPOR_2'

    
    
    def Mbox(self, title, text, style):
        return ctypes.windll.user32.MessageBoxW(0, text, title, style) 
    
    
    
    
    
    def run(self):
        x = 0
        self.UpdateProgress.emit("Status: Checking Inputs")
        #try to make new base folder
        try:
            self.base_save_folder = os.path.join(self.FolderLocation,"WaPOR Download " + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"))
            os.makedirs(self.base_save_folder)
        except:
            self.Mbox('Error', 'Unable to create new folder for WaPOR download in the selected folder.', 0)
            x += 1    
        #check start date is less that end date
        if self.Enddate < self.Startdate:
            self.Mbox('Error', 'End date is earlier than the Start date.', 0)
            x += 1
        #Creats self.SelectedCubeCodes (a list of checked boxes for WaPOR request), and self.cubedict (contains info for each checked box)
        self.Selected()
        #Check that at least one box is checked
        if self.SelectedCubeCodes  == []:
            self.Mbox('Error', 'Must have one item checked for WaPOR request.', 0)
            x += 1

        #get the boundaries of the shape file
        try: 
            data = gpd.read_file(self.VFileLocation, SHAPE_RESTORE_SHX = True)
            #Checks if the shape file needs to be reprojected
            if data.crs['init'] != 'epsg:4326':
                # change CRS to epsg 4326
                data = data.to_crs(epsg = 4326)
            minx, miny, maxx, maxy = data.total_bounds
            latlim = [miny, maxy]
            lonlim = [minx, maxx]
            
        except:
            self.Mbox('Error', 'Unable to read the boundaries of the vector file.', 0)
            x+= 1
            
        
        #User inputs have been checked in the above sections so now the data requests to the WaPOR server can be started    
        if x  == 0:
            self.DownloadRequest(latlim, lonlim)  
        else:
            self.Mbox( 'Error:', 'Error found in inputs, canceling WaPOR request.',0)




  
    def query_accessToken(self):
            resp_vp = requests.post(self.path_sign_in,headers = {'X-GISMGR-API-KEY':self.wapor_api_token})
            resp_vp = resp_vp.json()
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
        iterator = qtw.QTreeWidgetItemIterator(self.SelectWidget,  qtw.QTreeWidgetItemIterator.IteratorFlag(0x00001000) )
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
                    request_json = (requests.get(r'{0}{1}/cubes/{2}/measures?overview=false&paged=false'.format(self.path_catalog,self.workspaces, cubecode)).json())
                    if request_json['status']  == 200:
                        self.cubedict[cubecode].update({'cubemeasure':(request_json['response'][0])})
                    else:
                        self.Mbox( 'Error' ,str(request_json['message']),0)

                    #Cube Dimensions: provides operations pertaining to CubeDimension resources
                    #get the CubeDimensions list
                    #example:https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes/L1_AETI_M/dimensions?overview = false&paged = false
                    request_json = (requests.get(r'{0}{1}/cubes/{2}/dimensions?overview=false&paged=false'.format(self.path_catalog,self.workspaces,cubecode)).json())
                    if request_json['status']  == 200:
                        self.cubedict[cubecode].update({'cubedimensions':(request_json['response'][0])})
                    else:
                        self.Mbox( 'Error' ,str(request_json['message']),0)
        

    def DownloadRequest(self,latlim, lonlim):        
            #Sets off main request code chunk
            self.UpdateStatus.emit("Status: Preparing Download")
            m = 0
            self.query_accessToken()
            for  cube_code in self.SelectedCubeCodes:
           
                if self.isInterruptionRequested()  == False:
                    m+= 1
                    self.UpdateProgress.emit("Progress: Starting download for Wapor data {0}.\n Item number {1} of {2}".format(cube_code, m,  str(len(self.SelectedCubeCodes))))
                    self.UpdateStatus.emit("Status: Creating Data list")
                    df_avail = self.Get_df(cube_code, self.Startdate, self.Enddate) 
                    
                    bbox = [lonlim[0],latlim[0],lonlim[1],latlim[1]]
                    multiplier = self.cubedict[cube_code]['cubemeasure']['multiplier']
                    savefolder = os.path.join(self.base_save_folder, cube_code)
                    os.makedirs(savefolder)
                   #self.ui.labelStatus.setText("Status: Constructing WaPOR Request")
                    if 'lcc' in cube_code.lower():
                        self.LCC_Legend(cube_code, savefolder)
                        pass
                    n = 0
                    for index, row in df_avail.iterrows():
                        if self.isInterruptionRequested()  == False:
                            n+= 1            
                            self.UpdateProgress.emit("Progress: Starting download for Wapor data {0}. \nItem number {1} of {2} \nDownloading raster {3} of {4}".format(cube_code, m,  str(len(self.SelectedCubeCodes)), n,str(len(df_avail))))
                            self.UpdateStatus.emit("Status: Requesting download URL from WaPOR")
                            self.WaporRequest(cube_code, bbox, row)
                            
                            self.UpdateStatus.emit("Status: Downloading")
                            resp = requests.get(self.download_url)
                            self.UpdateStatus.emit("Status: Correcting raster")
                            self.Tiff_Edit_Save(cube_code,  multiplier, row, savefolder, resp)
                            
            if self.isInterruptionRequested()  == False:
                self.UpdateStatus.emit("Status: Download Completed")
                self.UpdateProgress.emit("Progress:")
            else:
                self.UpdateStatus.emit("Status: Download Canceled")
                self.UpdateProgress.emit("Progress:")
                
    def Get_df(self, cube_code, Startdate, Enddate):
        time_range = '{0},{1}'.format(Startdate,Enddate)
        try:
            df_avail = self.getAvailData(cube_code,time_range)
            return df_avail
        except:
            self.Mbox( 'Error' ,'Cannot get list of available requested data',0)
            return

        
        
    def WaporRequest(self, cube_code, bbox, row):
       
              try:
                  if self.cubedict[cube_code]['additionalInfo']['temporalExtent']  == 'Seasonal':
                      season_val = {'Season 1':'S1','Season 2':'S2'}
                      if 'PHE' in cube_code:
                          stage_val = {'End':'EOS','Maximum':'MOS','Start':'SOS'}
                          raster_stage = stage_val[row['STAGE']]
                      else:
                          raster_stage = None
                          
                      self.download_url = self.getCropRasterURL(bbox,cube_code,
                                                         row['time_code'],
                                                         row['raster_id'],
                                                         season = season_val[row['SEASON']],
                                                         stage = raster_stage)  
      
                  else:
                      self.download_url = self.getCropRasterURL(bbox,cube_code,
                                                   row['time_code'],
                                                   row['raster_id'])
              except:
                  pass
              
    def Tiff_Edit_Save(self, cube_code,  multiplier, row, savefolder, resp):                  
      #check this works for seasonal and non seasonal
              try:   
                  filename = '{0}{1}.tif'.format(row['raster_id'],row['time_code'])
                  outfilename = os.path.join(savefolder,filename)       
                  download_file = os.path.join(savefolder,'raw_{0}.tif'.format(row['raster_id']))
                  ndays = 1
                  
                  #By defualt dekadal data from WaPOR is an average. This allows it to give the cumulative value.
                  if self.cubedict[cube_code]['cubedimensions']['code']  == 'DEKAD' and self.Combo  == 'Cumulative' :
                      timestr = row['time_code']
                      startdate = datetime.datetime.strptime(timestr[1:11],'%Y-%m-%d')
                      enddate = datetime.datetime.strptime(timestr[12:22],'%Y-%m-%d')
                      ndays = (enddate.timestamp()-startdate.timestamp())/86400
                 
                  open(download_file,'wb').write(resp.content)
                  driver, NDV, xsize, ysize, GeoT, Projection = self.GetGeoInfo(download_file)
                  Array = self.OpenAsArray(download_file,nan_values = True)
                  CorrectedArray = Array*multiplier*ndays
                  
                  self.CreateGeoTiff(outfilename,CorrectedArray,
                                    driver, NDV, xsize, ysize, GeoT, Projection)
                  os.remove(download_file)
                  if self.CropChecked:

                      gdal.Warp(os.path.join(savefolder,('Clip' + filename)), outfilename,cutlineDSName = self.VFileLocation, cropToCutline = (True), warpOptions = [ 'CUTLINE_ALL_TOUCHED = TRUE' ] )#
                      os.remove(outfilename)
                      os.rename(os.path.join(savefolder,('Clip' + filename)), outfilename)
              except:
                  pass



    def getAvailData(self,cube_code,time_range,
                     location = [],season = [],stage = []):
        
        try:
            measure_code = self.cubedict[cube_code]['cubemeasure']['code']
            dimensions = self.cubedict[cube_code]['cubedimensions']
        except:
            self.Mbox( 'Error' ,'Cannot get cube info',0)
           
       
        dims_ls = []
        columns_codes = ['MEASURES']
        rows_codes = []
        try:
            
            if dimensions['type']  == 'TIME': #get time dims
                time_dims_code = dimensions['code']
                df_time = self._query_dimensionsMembers(cube_code,time_dims_code)
                time_dims = {
                    "code": time_dims_code,
                    "range": '[{0})'.format(time_range)
                    }
                dims_ls.append(time_dims)
                rows_codes.append(time_dims_code)
            if dimensions['type']  == 'WHAT':
                dims_code = dimensions['code']
                print(dims_code)
                df_dims = self._query_dimensionsMembers(cube_code,dims_code) 
                members_ls = [row['code'] for i,row in df_dims.iterrows()]
                if (dims_code  == 'COUNTRY' or dims_code  == 'BASIN'):
                    if location:
                        members_ls = location
                if (dims_code  == 'SEASON'):
                    if season:
                        members_ls = season
                if (dims_code  == 'STAGE'):
                    if stage:
                        members_ls = stage    
                     
                what_dims = {
                        "code":dimensions['code'],
                        "values":members_ls
                        }
                dims_ls.append(what_dims)
                rows_codes.append(dimensions['code']) 
                
            df = self._query_availData(cube_code,measure_code,
                             dims_ls,columns_codes,rows_codes)
        except:
            self.Mbox( 'Error' ,'Failed request cannot get list of available data',0)
            return None
        
        keys = rows_codes + ['raster_id','bbox','time_code']
        df_dict = { i : [] for i in keys }
        for irow,row in df.iterrows():
            for i in range(len(row)):
                if row[i]['type']  == 'ROW_HEADER':
                    key_info = row[i]['value']
                    df_dict[keys[i]].append(key_info)
                    if keys[i]  == time_dims_code:
                        time_info = df_time.loc[df_time['caption'] == key_info].to_dict(orient = 'records')
                        df_dict['time_code'].append(time_info[0]['code'])
                if row[i]['type']=='DATA_CELL':
                    raster_info=row[i]['metadata']['raster']
            df_dict['raster_id'].append(raster_info['id'])
            df_dict['bbox'].append(raster_info['bbox'])
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
        return df


    
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
        try:
            results = resp_vp['response']['items']
            return pd.DataFrame(results)
        except:
            self.Mbox( 'Error' ,'Cannot get list of available data.'+str(resp_vp['message']),0)
        
  
            
    def getCropRasterURL(self,bbox,cube_code,
                          time_code,rasterId,season = None,stage = None):
        #Create Polygon        
        xmin,ymin,xmax,ymax = bbox[0],bbox[1],bbox[2],bbox[3]
        Polygon = [
                  [xmin,ymin],
                  [xmin,ymax],
                  [xmax,ymax],
                  [xmax,ymin],
                  [xmin,ymin]
                ]
        
        cube_measure_code = self.cubedict[cube_code]['cubemeasure']['code']
        cube_dimensions = self.cubedict[cube_code]['cubedimensions']
        
        dimension_params = []
        

        if cube_dimensions['type']  == 'TIME':
            cube_dimension_code = cube_dimensions['code']
            dimension_params.append({
            "code": cube_dimension_code,
            "values": [
            time_code
            ]
            })
        if cube_dimensions['code']  == 'SEASON':                
            dimension_params.append({
            "code": 'SEASON',
            "values": [
            season
            ]
            })
        if cube_dimensions['code']  == 'STAGE':                
            dimension_params.append({
            "code": 'STAGE',
            "values": [
            stage
            ]
            })                
 
        #Query payload
        query_crop_raster = {
          "type": "CropRaster",
          "params": {
            "properties": {
              "outputFileName": "{0}.tif".format(rasterId),
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
        try:
            job_url = resp_vp['response']['links'][0]['href']
            download_url = self._query_jobOutput(job_url)
            return download_url     
        except:
            self.Mbox( 'Error' ,'Cannot get cropped raster URL',0)
   
  
    
    def _query_jobOutput(self,job_url):
     #This method queries the WaPOR sever until the download is ready which it then returns.
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
                 print('ERROR: Invalid jobType')                
             return output
         if resp['response']['status']  == 'COMPLETED WITH ERRORS':
             contiue = False
             print(resp['response'])
             print(resp['response']['log'])     
         #Method keeps pinging the sever till the request is done. Short delay to minimize the number of requests.       
         time.sleep(5)

    
    def GetGeoInfo(self, fh, subdataset = 0):
        """
        Subtract metadata from a geotiff, HDF4 or netCDF file.
        
        Parameters
        ----------
        fh : str
            Filehandle to file to be scrutinized.
        subdataset : int, optional
            Layer to be used in case of HDF4 or netCDF format, default is 0.
            
        Returns
        -------
        driver : str
            Driver of the fh.
        NDV : float
            No-data-value of the fh.
        xsize : int
            Amount of pixels in x direction.
        ysize : int
            Amount of pixels in y direction.
        GeoT : list
            List with geotransform values.
        Projection : str
            Projection of fh.
        """
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
        """
        Open a map as an numpy array. 
        
        Parameters
        ----------
        fh: str
            Filehandle to map to open.
        bandnumber : int, optional 
            Band or layer to open as array, default is 1.
        dtype : str, optional
            Datatype of output array, default is 'float32'.
        nan_values : boolean, optional
            Convert he no-data-values into np.nan values, note that dtype needs to
            be a float if True. Default is False.
            
        Returns
        -------
        Array : ndarray
            Array with the pixel values.
        """
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
        """
        Creates a geotiff from a numpy array.
        
        Parameters
        ----------
        fh : str
            Filehandle for output.
        Array: ndarray
            Array to convert to geotiff.
        driver : str
            Driver of the fh.
        NDV : float
            No-data-value of the fh.
        xsize : int
            Amount of pixels in x direction.
        ysize : int
            Amount of pixels in y direction.
        GeoT : list
            List with geotransform values.
        Projection : str
            Projection of fh.    
        """

        
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
    

        
class InfoPopup(qtw.QWidget):
        def __init__(self, cube_code, MasterList):
            super().__init__()
            layout = qtw.QGridLayout()
            for x in MasterList:
               if str(x.get('code'))  == cube_code:                 
                  keylist = ['caption', 'code', 'description']+list(x.get('additionalInfo').keys())
                  valuelist = [x.get('caption'), x.get('code'), x.get('description')]+list(x.get('additionalInfo').values())
                  
                  keyitems = len(keylist)-1
                  keyposition = 0
                  while keyposition <= keyitems:
                          y = qtw.QLabel(str(keylist[keyposition]))
                          y.setWordWrap(True)
                          y.setStyleSheet("border: 1px solid black;")
                          y.setTextInteractionFlags(qtc.Qt.TextInteractionFlag.TextSelectableByMouse)
                          layout.addWidget(y,keyposition,0)
                            
                          y = qtw.QLabel(str(valuelist[keyposition]))
                          y.setWordWrap(True)
                          y.setStyleSheet("border: 1px solid black;")
                          y.setTextInteractionFlags(qtc.Qt.TextInteractionFlag.TextSelectableByMouse)
                          layout.addWidget(y,keyposition,1)
                          
                          keyposition += 1
                  break         
            self.setLayout(layout)
            
        


        
if __name__  == '__main__':
    app = qtw.QApplication([]) 
    
    widget = WaPORwidget()
    widget.show()
    
    app.exec()
# -*- coding: utf-8 -*-
"""
Created on Sat Apr 30 13:48:12 2022

@author: brend
"""

import os
import sys
sys.path.append(os.getcwd())
sys.path.append(os.getcwd()+"\WaPOR")
from PyUI import Ui_Widget
from PyQt6 import QtWidgets as qtw
from PyQt6 import QtCore as qtc
import pickle
import easygui
import ctypes
import requests

import datetime
import pandas as pd

import geopandas as gpd
import gdal
import osr
import numpy as np






class WaPORwidgiet(qtw.QWidget):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui=Ui_Widget()
        self.ui.setupUi(self)
        self.ui.tabWidget.setTabEnabled(1, False)
        self.ui.textStatus.setReadOnly(True)
        self.ui.dateEnd.setDate(qtc.QDate.currentDate())
        self.ui.dateEnd.setMaximumDate((qtc.QDate.currentDate()))
        self.path_sign_in=r'https://io.apps.fao.org/gismgr/api/v1/iam/sign-in/'

        
        self.LoadAPI()


        #Set buttons
        self.ui.treeWidget.itemDoubleClicked.connect(self.LaunchPopup)        
        self.ui.ButtonSave.clicked.connect(self.SaveAPI)        
        self.ui.ButtonShape.clicked.connect(self.FileLocation)
        self.ui.ButtonFolder.clicked.connect(self.FolderLocation)
        
       

        self.path_catalog=r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/'
        self.workspaces={2: 'WAPOR_2'}
        self.version=2 
        self.print_job=False
        self.path_query=r'https://io.apps.fao.org/gismgr/api/v1/query/'
        self.ui.ButtonRefresh.clicked.connect(lambda: self.CheckInputs())
          


#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX                 XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX     Methods     XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXX                 XXXXXXXXXXXXXXXXXXXXXXXXXXXXX
#XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    def LoadAPI(self):
        api_token_pickle=os.path.join(os.path.dirname(__file__),
                                      'WaPOR/wapor_api_token.pickle')
        
      #attempts to load API toekn on start up
        try:
            self.PrintStatus("Attempting to Load API Token") 
            
            with open(api_token_pickle, 'rb') as handle:
                self.wapor_api_token=pickle.load(handle)
                self.PrintStatus("Obtained saved API Token")
                ResponceStatus, ResponceMessage = self.CheckAccessToken()
                if ResponceStatus == 200: 
                    self.ui.tabWidget.setTabEnabled(1, True)
                    self.PrepTab()
                    self.ui.LableLoad.setText("Token Loaded")
                else:
                    self.Mbox( 'Error' ,str(ResponceMessage),0)
                   
        except:
            self.PrintStatus("Failed to Load API Token")
        pass
        
    def SaveAPI(self):    
            
        api_token_pickle=os.path.join(os.path.dirname(__file__),
                                      'WaPOR/wapor_api_token.pickle')
        
        self.wapor_api_token=self.ui.plainTextEditAPI.toPlainText()
        if len(self.wapor_api_token)>0:
            try:   
                ResponceStatus,ResponceMessage = self.CheckAccessToken()
                if ResponceStatus == 200: 
                    self.ui.tabWidget.setTabEnabled(1, True)
                    with open(api_token_pickle, 'wb') as handle:
                        pickle.dump(self.wapor_api_token, handle, protocol=pickle.HIGHEST_PROTOCOL)
                        self.PrintStatus("Saved API Token to "+ str(api_token_pickle))
                        self.PrepTab()
                        self.ui.tabWidget.setTabEnabled(1, True)
                else:
                    self.Mbox( 'Error' ,str(ResponceMessage),0)
            
            except:
                self.Mbox( 'Error','Personal API Key is not valid and/or is not enabled.',0)
                pass
    
    
    
    

    
    def FolderLocation(self):
        self.ui.plainTextEditExport.setPlainText('')
        FolderLocation = easygui.diropenbox(msg = 'Choose export folder location.')
        try:
            self.ui.plainTextEditExport.setPlainText(FolderLocation)
        except:
            pass
    
    def FileLocation(self):
        self.ui.plainTextEditShape.setPlainText("")
        self.FileName = easygui.fileopenbox(msg="Select a file with the .shp extention",filetypes=["*.shp","shape files"])
        self.ui.plainTextEditShape.setPlainText(self.FileName)
        try:
            if self.FileName[-3:] != 'shp':
                self.Mbox( 'Warning','File must be a .shp file.',0)
        except:
            pass
    
    def Mbox(self, title, text, style):
        return ctypes.windll.user32.MessageBoxW(0, text, title, style)
    
    def PrepTab(self):
        try:
            L1 = ((requests.get('https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L1')).json()).get('response')
            L2 = ((requests.get('https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L2')).json()).get('response')
            L3 = ((requests.get('https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes?overview=false&paged=false&sort=sort%20%3D%20code&tags=L3')).json()).get('response')

            
            self.MasterList = L1 + L2 + L3
            #sorts by type of information
            L1 = sorted(L1, key=lambda d: d.get('caption'))
            L2 = sorted(L2, key=lambda d: d.get('caption'))
            #Sorts first country location, then by type of information
            L3 = sorted(L3, key=lambda d: [d.get('additionalInfo', {}).get('spatialExtent').partition(", ")[2] ,d.get('caption') ])
            self.ui.treeWidget.headerItem().setText(0, "WaPOR")
            self.TreeAddBasic(L1, "Level 1")
            self.TreeAddBasic(L2, "Level 2")
            self.TreeAddLvl3(L3, "Level 3")
            self.PrintStatus("Loaded Data Catalog from the WaPOR Server")
        except:
            self.PrintStatus("Error Loading data from the WaPOR Server")
            




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
        
      
    def Selected(self):
        self.SelectedCubeCodes = []
        iterator = qtw.QTreeWidgetItemIterator(self.ui.treeWidget,  qtw.QTreeWidgetItemIterator.IteratorFlag(0x00001000) )
        while iterator.value():
            CurrentItem = iterator.value()
            if CurrentItem.childCount() == 0:
                self.SelectedCubeCodes.append(CurrentItem.text(1))
            iterator += 1
        self.AddCubeData()

        
    def AddCubeData(self):
        self.cubedict= dict()

        for cubecode in self.SelectedCubeCodes:
                    for x in self.MasterList:
                        if x.get('code') == cubecode:
                            self.cubedict[cubecode]=x
                            break
                    
                    request_json = (requests.get(r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes/{0}/measures?overview=false&paged=false'.format(cubecode)).json())
                    if request_json['status'] == 200:
                        self.cubedict[cubecode].update({'cubemeasure':(request_json['response'][0])})
                    else:
                        print('\n ERROR:',request_json['message'])    


                    request_json = (requests.get(r'https://io.apps.fao.org/gismgr/api/v1/catalog/workspaces/WAPOR_2/cubes/{0}/dimensions?overview=false&paged=false'.format(cubecode)).json())
                    if request_json['status'] == 200:
                     self.cubedict[cubecode].update({'cubedimensions':(request_json['response'][0])})
                    else:
                     print('\n ERROR:',request_json['message']) 
        


       
    def LaunchPopup(self, item):
        if item.childCount() == 0:
            self.pop = Popup(item.text(1), self.MasterList)
            self.pop.show()


    def PrintStatus(self, text):
        self.ui.textStatus.append(text)
        pass



    def CheckAccessToken(self):
        resp_vp=requests.post(self.path_sign_in,headers={'X-GISMGR-API-KEY':self.wapor_api_token})
        resp_vp = resp_vp.json()
        try:
            return resp_vp['status'], resp_vp['message']
        except:
            self.Mbox( 'ERROR: Could not connect to server.',0)               
            
    def GetTime(self):
        self.StartDateEdit = self.ui.dateStart.date().toPyDate().strftime("%Y-%m-%d")
        self.EndDateEdit = self.ui.dateEnd.date().toPyDate().strftime("%Y-%m-%d")
        
    def CheckInputs(self):
        self.PrintStatus("Checking user inputs.")
        x = 0
        
        #check folder is valid folder
        if os.path.isdir(self.ui.plainTextEditExport.toPlainText()) == False:
            self.Mbox('Error', 'Invalid folder Location.', 0)
            x += 1
        #try to make new base folder
        try:
            self.base_save_folder = os.path.join(self.ui.plainTextEditExport.toPlainText(),"WaPOR Download " + datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"))
            os.makedirs(self.base_save_folder)
        except:
            self.Mbox('Error', 'Unable to create new folder for WaPOR download in the selected folder.', 0)
            x+=1    
        #Cant figure out out to get the writen text from the input without springing an error thus we'll just pull self.filename when loading the shape file later
        #bug needs to be fixed in the future, or make them not except straight user text.
        #check file is valid file
        print(self.ui.plainTextEditShape.toPlainText())
        if os.path.isfile(self.ui.plainTextEditShape.toPlainText().encode('unicode_escape').decode()) == False:
            self.Mbox('Error', 'Invalid shape File, or pathway  Ensure that file extension is ".shp".', 0)
            x += 1
        self.GetTime()
        #check start date is less that end date
        if self.ui.dateEnd.date() < self.ui.dateStart.date():
            self.Mbox('Error', 'End date is earlier than the Start date.', 0)
            x += 1
        #Creats self.SelectedCubeCodes (a list of checked boxes for WaPOR request), and self.cubedict (contains info for each checked box)
        self.Selected()
        #Check that at least one box is checked
        if self.SelectedCubeCodes == []:
            self.Mbox('Error', 'Must have one item checked for WaPOR request.', 0)
            x += 1

        #get the boundaries of the shape file
        try: 
            data = gpd.read_file(self.FileName, SHAPE_RESTORE_SHX = True)
            #Checks if the shape file needs to be reprojected
            if data.crs['init'] != 'epsg:4326':
                # change CRS to epsg 4326
                data = data.to_crs(epsg=4326)
            minx, miny, maxx, maxy = data.total_bounds
            
        except:
            self.Mbox('Error', 'Error reading .shp file. Ensure all components of the shape file are saved in the same folder.', 0)
            x+=1
            
        
        #User inputs have been checked in the above sections so now the data requests to the WaPOR server can be started    
        if x == 0:
            #Refresh accessscode
            #Sets off main request code chunk
            for n, cube_code in enumerate(self.SelectedCubeCodes, start=1):
                self.PrintStatus("Starting download for  Wapor data {0}. Item number {1} of {2}".format(cube_code, n,  str(len(self.SelectedCubeCodes))))
                self.WaporRequest(cube_code, self.StartDateEdit, self.EndDateEdit,[miny, maxy], [minx, maxx] )

        else:
            self.PrintStatus("Error found in inputs, canceling WaPOR request.")
            
            #NEED TO TEST THESE CONSTRAINS AND WRITE IN AN EXEPTION IF MANDITORY
      #  latlim -- [ymin, ymax] (values must be between -40.05 and 40.05)
      #  lonlim -- [xmin, xmax] (values must be between -30.05 and 65.05)

#######################
#CODE TAKEN
#######################
    
    def query_accessToken(self):
            
            resp_vp=requests.post(self.path_sign_in,headers={'X-GISMGR-API-KEY':self.wapor_api_token})
            resp_vp = resp_vp.json()
       
            try:
                self.AccessToken=resp_vp['response']['accessToken']
                self.RefreshToken=resp_vp['response']['refreshToken']        
                self.time_expire=resp_vp['response']['expiresIn']-600 #set expire time 2 minutes earlier
                self.time_start=datetime.datetime.now().timestamp()
            except:
                
                self.Mbox( 'ERROR:', resp_vp['message'],0)
                print()                      
            return self.AccessToken



#######################
#CODE TAKEN END
#######################
    def WaporRequest(self, cube_code, Startdate, Enddate, 
             latlim, lonlim):
       
      
        """
        This function downloads seasonal WAPOR LCC data
    
        Keyword arguments:
        cube_code -- cube code for the given data package
        str ex. 'L2_CTY_PHE_S'
        Startdate -- 'yyyy-mm-dd'
        Enddate -- 'yyyy-mm-dd'
        latlim -- [ymin, ymax] (values must be between -40.05 and 40.05)
        lonlim -- [xmin, xmax] (values must be between -30.05 and 65.05)
        """
        
        # Download data
        bbox=[lonlim[0],latlim[0],lonlim[1],latlim[1]]
        self.APIToken=self.query_accessToken()
        
        #for applying to the downloaded tiff
        multiplier=self.cubedict[cube_code]['cubemeasure']['multiplier']
        time_range='{0},{1}'.format(Startdate,Enddate)
        try:
            df_avail=self.getAvailData(cube_code,time_range)
        except:
            print('ERROR: cannot get list of available data')
            return None
        #Need to figure out how to save this!!!!!!!!!!!!!!!!!!!XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        savefolder = os.path.join(self.base_save_folder, cube_code)
        os.makedirs(savefolder)
            
            
        for index,row in df_avail.iterrows():   
            if self.cubedict[cube_code]['additionalInfo']['temporalExtent'] == 'Seasonal':
                season_val={'Season 1':'S1','Season 2':'S2'}
                if 'PHE' in cube_code:
                    stage_val={'End':'EOS','Maximum':'MOS','Start':'SOS'}
                    raster_stage=stage_val[row['STAGE']]
                else:
                    raster_stage=None
                    
                download_url=self.getCropRasterURL(bbox,cube_code,
                                                   row['time_code'],
                                                   row['raster_id'],
                                                   self.APIToken,
                                                   season=season_val[row['SEASON']],
                                                   stage=raster_stage)  

            else:
                download_url=self.getCropRasterURL(bbox,cube_code,
                                             row['time_code'],
                                             row['raster_id'],
                                             self.APIToken)

#check this works for seasonal and non seasonal
            filename='{0}.tif'.format(row['raster_id'])
            outfilename=os.path.join(savefolder,filename)       
            download_file=os.path.join(savefolder,'raw_{0}.tif'.format(row['raster_id']))
        
            
            #Download raster file
            resp=requests.get(download_url) 
            open(download_file,'wb').write(resp.content) 
            driver, NDV, xsize, ysize, GeoT, Projection= self.GetGeoInfo(download_file)
            print(driver)
            print(NDV)
            Array = self.OpenAsArray(download_file,nan_values=True)
            CorrectedArray=Array*multiplier
            self.CreateGeoTiff(outfilename,CorrectedArray,
                              driver, NDV, xsize, ysize, GeoT, Projection)
            os.remove(download_file)        
            
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
        print('type')
        print(Type)
        if Type == 'HDF4' or Type == 'netCDF':
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
        if Type == 'HDF4':
            Subdataset = gdal.Open(DataSet.GetSubDatasets()[bandnumber][0])
            NDV = int(Subdataset.GetMetadata()['_FillValue'])
        else:
            Subdataset = DataSet.GetRasterBand(bandnumber)
            NDV = Subdataset.GetNoDataValue()
        Array = Subdataset.ReadAsArray().astype(datatypes[dtype])
        if nan_values:
            Array[Array == NDV] = np.nan
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
            Array[Array == NDV] = np.nan























    def getAvailData(self,cube_code,time_range,
                     location=[],season=[],stage=[]):
        '''

        time_range: str
            ex. '2009-01-01,2018-12-31'
        location: list of strings
            default: empty list, return all available locations
            ex. ['ETH']
        season: list of string
            default: empty list, return all available seasons
            ex. ['S1']
        stage: list of strings
            default: empty list, return all available stages
            ex. ['EOS','SOS']
        '''
        try:
            measure_code=self.cubedict[cube_code]['cubemeasure']['code']
            dimensions=self.cubedict[cube_code]['cubedimensions']
            print(dimensions)
        except:
            print('ERROR: Cannot get cube info')
        print('cube request setup')    
        dims_ls=[]
        columns_codes=['MEASURES']
        rows_codes=[]
        try:
            
            if dimensions['type']=='TIME': #get time dims
                time_dims_code=dimensions['code']
                df_time=self._query_dimensionsMembers(cube_code,time_dims_code)
                time_dims= {
                    "code": time_dims_code,
                    "range": '[{0})'.format(time_range)
                    }
                dims_ls.append(time_dims)
                rows_codes.append(time_dims_code)
            if dimensions['type']=='WHAT':
                dims_code=dimensions['code']
                df_dims=self._query_dimensionsMembers(cube_code,dims_code) 
                members_ls=[row['code'] for i,row in df_dims.iterrows()]
                if (dims_code=='COUNTRY' or dims_code=='BASIN'):
                    if location:
                        members_ls=location
                if (dims_code=='SEASON'):
                    if season:
                        members_ls=season
                if (dims_code=='STAGE'):
                    if stage:
                        members_ls=stage    
                     
                what_dims={
                        "code":dimensions['code'],
                        "values":members_ls
                        }
                dims_ls.append(what_dims)
                rows_codes.append(dimensions['code']) 
                
            print('try request for cube')  
            df=self._query_availData(cube_code,measure_code,
                             dims_ls,columns_codes,rows_codes)
        except:
            print('ERROR:failed request Cannot get list of available data')
            return None
        
        keys=rows_codes+ ['raster_id','bbox','time_code']
        df_dict = { i : [] for i in keys }
        for irow,row in df.iterrows():
            for i in range(len(row)):
                print(666)
                if row[i]['type']=='ROW_HEADER':
                    key_info=row[i]['value']
                    df_dict[keys[i]].append(key_info)
                    if keys[i]==time_dims_code:
                        time_info=df_time.loc[df_time['caption']==key_info].to_dict(orient='records')
                        df_dict['time_code'].append(time_info[0]['code'])
                if row[i]['type']=='DATA_CELL':
                    raster_info=row[i]['metadata']['raster']
            df_dict['raster_id'].append(raster_info['id'])
            df_dict['bbox'].append(raster_info['bbox'])
            print(777)                    
        df_sorted=pd.DataFrame.from_dict(df_dict)
        return df_sorted            

    

    #NEEDED
    def _query_dimensionsMembers(self,cube_code,dims_code):
        base_url='{0}{1}/cubes/{2}/dimensions/{3}/members?overview=false&paged=false'       
        request_url=base_url.format(self.path_catalog,
                                    self.workspaces[self.version],
                                    cube_code,
                                    dims_code
                                    )
        resp = requests.get(request_url)
        resp_vp = resp.json()
        try:
            avail_items=resp_vp['response']
            df=pd.DataFrame.from_dict(avail_items, orient='columns')            
        except:
            print('\n ERROR: Cannot get dimensions Members. ',resp_vp['message'])
        return df


    #NEEDED
    def _query_availData(self,cube_code,measure_code,
                         dims_ls,columns_codes,rows_codes):                

        query_load={
          "type": "MDAQuery_Table",              
          "params": {
            "properties": {                     
              "metadata": True,                     
              "paged": False,                   
            },
            "cube": {                            
              "workspaceCode": 'WAPOR_2',            
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
            
        resp = requests.post(self.path_query, json=query_load)
        resp_vp = resp.json()
        try:
            results=resp_vp['response']['items']         
        except:
            print('\n ERROR: Cannot get list of available data. ', resp_vp['message'])
        return pd.DataFrame(results)
  
            
    def getCropRasterURL(self,bbox,cube_code,
                          time_code,rasterId,APIToken,season=None,stage=None):
        '''
        bbox: str
            latitude and longitude
            [xmin,ymin,xmax,ymax]
        '''
        print('getcroprasterURL')
        #Get AccessToken        
        AccessToken=self.AccessToken        
        self.time_now=datetime.datetime.now().timestamp()
        #print("\n Use Current AccessToken, start: {0}, elapsed time: {1}".format(self.time_start,self.time_now-self.time_start))            
        if self.time_now-self.time_start > self.time_expire:
            AccessToken=self._query_refreshToken(self.RefreshToken)
            #print("\n Refresh AccessToken")                
        #Create Polygon        
        xmin,ymin,xmax,ymax=bbox[0],bbox[1],bbox[2],bbox[3]
        Polygon=[
                  [xmin,ymin],
                  [xmin,ymax],
                  [xmax,ymax],
                  [xmax,ymin],
                  [xmin,ymin]
                ]
        #Get measure_code and dimension_code
        cube_measure_code=self.cubedict[cube_code]['cubemeasure']['code']
        cube_dimensions=self.cubedict[cube_code]['cubedimensions']
        
        dimension_params=[]
        

        if cube_dimensions['type']=='TIME':
            cube_dimension_code=cube_dimensions['code']
            dimension_params.append({
            "code": cube_dimension_code,
            "values": [
            time_code
            ]
            })
        if cube_dimensions['code']=='SEASON':                
            dimension_params.append({
            "code": 'SEASON',
            "values": [
            season
            ]
            })
        if cube_dimensions['code']=='STAGE':                
            dimension_params.append({
            "code": 'STAGE',
            "values": [
            stage
            ]
            })                
 
        #Query payload
        query_crop_raster={
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
              "workspaceCode": self.workspaces[self.version],
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
        resp_vp=requests.post(self.path_query,
                              headers={'Authorization':'Bearer {0}'.format(AccessToken)},
                                                       json=query_crop_raster)
        
        resp_vp = resp_vp.json()
        try:
            job_url=resp_vp['response']['links'][0]['href']
            print('Getting download url from: {0}'.format(job_url))    
            download_url=self._query_jobOutput(job_url)
            print('done download')
            return download_url     
        except:
            print('Error: Cannot get cropped raster URL')
  
    
    def _query_jobOutput(self,job_url):
     '''
              
                 
     '''
     contiue=True        
     while contiue:        
         resp = requests.get(job_url)
         resp=resp.json()
         print(resp)
         if self.print_job:
             print(resp)
         jobType=resp['response']['type']            
         if resp['response']['status']=='COMPLETED':
             contiue=False
             if jobType == 'CROP RASTER':
                 output=resp['response']['output']['downloadUrl']                
             elif jobType == 'AREA STATS':
                 results=resp['response']['output']
                 output=pd.DataFrame(results['items'],columns=results['header'])
             else:
                 print('ERROR: Invalid jobType')                
             return output
         if resp['response']['status']=='COMPLETED WITH ERRORS':
             contiue=False
             print(resp['response']['log'])             
    
  
  
    
    
class Popup(qtw.QWidget):
        def __init__(self, cube_code, MasterList):
            super().__init__()
            layout = qtw.QGridLayout()
            for x in MasterList:
               if str(x.get('code')) == cube_code:                 
                  keylist=['caption', 'description']+list(x.get('additionalInfo').keys())
                  valuelist=[x.get('caption'), x.get('description')]+list(x.get('additionalInfo').values())
                  
                  keyitems = len(keylist)-1
                  keyposition = 0
                  while keyposition <= keyitems:
                          y=qtw.QLabel(str(keylist[keyposition]))
                          y.setWordWrap(True)
                          y.setStyleSheet("border: 1px solid black;")
                          y.setTextInteractionFlags(qtc.Qt.TextInteractionFlag.TextSelectableByMouse)
                          layout.addWidget(y,keyposition,0)
                            
                          y=qtw.QLabel(str(valuelist[keyposition]))
                          y.setMaximumWidth(1200)
                          y.setWordWrap(True)
                          y.setStyleSheet("border: 1px solid black;")
                          y.setTextInteractionFlags(qtc.Qt.TextInteractionFlag.TextSelectableByMouse)
                          layout.addWidget(y,keyposition,1)
                          
                          keyposition +=1
                  break         
                  
                    
                  
               

            self.setLayout(layout)
            
        


        
if __name__ == '__main__':
    app = qtw.QApplication([]) 
    
    widget = WaPORwidgiet()
    widget.show()
    
    app.exec()
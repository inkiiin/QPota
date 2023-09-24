#!/usr/bin/env python3
import requests, sys, os, time, threading, json
import Hamlib
import atexit
import pandas as pd
from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QDir, QLocale, QRect, QTimer
from PyQt5.QtGui import QFontDatabase, QIcon, QImage, QPixmap

DATA_PATH = f'{os.path.dirname(os.path.abspath(__file__))}/data'
DIALOG = f'{DATA_PATH}/dialog.ui'
SETTINGS = f'{DATA_PATH}/settings.json'
RIGPORT='127.0.0.1:4532'
HEADER_LABELS=['Activator','Frequency','Age']
SPOTURL='https://api.pota.app/spot/activator'
USERURL='https://api.pota.app/stats/user'

uix=100
uiy=100        

class MainWindow(QtWidgets.QMainWindow):
    dataAvailable = False
    iconlist = []
    sorted_df = []
    rigport = RIGPORT
    settings = []
    
    def __init__(self, parent=None):
        """Initialize class variables"""
        super().__init__(parent)
        uic.loadUi(DIALOG, self)
        self.loadSettings()
        self.move(uix,uiy)
        self.spotlist = self.findChild(QtWidgets.QTableWidget, "tableWidget")
        self.spotlist.cellClicked.connect(self.setTRX) 
        self.spotlist.setColumnCount(3)
        self.spotlist.setHorizontalHeaderLabels(HEADER_LABELS)
        Hamlib.rig_set_debug(Hamlib.RIG_DEBUG_NONE)
        self.rig = Hamlib.Rig(Hamlib.RIG_MODEL_NETRIGCTL)
        self.rig.state.rigport.pathname = self.rigport
        self.rig.open()

    def loadSettings(self):
        global uix
        global uiy
        with open(SETTINGS) as f:
            global settings
            self.settings = json.load(f)
            if self.settings != None:
                if self.settings['rigport']!=None:
                    self.rigport=self.settings['rigport']
                if self.settings['x']!=None:
                    uix=int(self.settings['x'])
                if self.settings['y']!=None:
                    uiy=int(self.settings['y'])

    def setTRX(self,row,column):
        dfrow = self.sorted_df.loc[self.sorted_df['activator'] == self.spotlist.item(row, 0).text()]
        freq = int(float(dfrow['frequency'].values[0])*1000)
        mode = dfrow['mode'].values[0]

        if mode == 'CW':
            self.rig.set_mode(Hamlib.RIG_MODE_CW)
        elif mode == 'SSB':
            if freq < 10000:
                self.rig.set_mode(Hamlib.RIG_MODE_LSB)
            else:
                self.rig.set_mode(Hamlib.RIG_MODE_USB)
        elif mode == 'FM':
            self.rig.set_mode(Hamlib.RIG_MODE_FM)
        else:
            self.rig.set_mode(Hamlib.RIG_MODE_USB)

        self.rig.set_freq(Hamlib.RIG_VFO_CURR,int(freq))

    def getIcon(self, activator):
        icon = QPixmap()
        ico = QIcon(icon)
        resp = requests.get(url=f"{USERURL}/{activator}")
        if resp.status_code == 200:
            activatorid=resp.json()['gravatar']
            resp = requests.get(url=f"https://www.gravatar.com/avatar/{activatorid}?s=32&d=identicon")
            if resp.status_code == 200:
                icon = QPixmap()
                icon.loadFromData(resp.content)
                ico = QIcon(icon)
        return ico
            
    def saveUIPosition(self):
        with open(SETTINGS,'w') as f:
            self.settings['rigport']=self.rigport
            self.settings['x']=uix
            self.settings['y']=uiy
            json.dump(self.settings,f)

    def getBandFromFrequency(self,frequency):
        if 1800 <= frequency <= 2000:
            return '160m'
        if 3500 <= frequency <= 4000:
            return '80m'
        if 5330 <= frequency <= 5405:
            return '60m'
        if 7000 <= frequency <= 7300:
            return '40m'
        if 10100 <= frequency <= 10150:
            return '30m'
        if 14000 <= frequency <= 14350:
            return '20m'
        if 18068 <= frequency <= 18168:
            return '17m'
        if 21000 <= frequency <= 21450:
            return '15m'
        if 24890 <= frequency <= 24990:
            return '12m'
        if 28000 <= frequency <= 29700:
            return '10m'
        if 50000 <= frequency <= 54000:
            return '6m'
        if 144000 <= frequency <= 148000:
            return '2m'
        if 420000 <= frequency <= 450000:
            return '70cm'
        return 'OOB'

    def refreshSpotList(self):
        global uix
        global uiy

        try:
            if self.dataAvailable:
                irow=0
                self.spotlist.clearContents()
                for index, row in self.sorted_df.iterrows():
                    band = self.getBandFromFrequency(row['frequency'])
                    if self.settings['bands'][band] and row['mode']!='':
                        if self.settings['modes'][row['mode']]:
                            self.spotlist.setRowCount(irow+1)
                            self.spotlist.setVerticalHeaderItem(irow, self.iconlist[irow])
                            self.spotlist.setItem(irow, 0, QtWidgets.QTableWidgetItem(f"{row['activator']}"))
                            self.spotlist.setItem(irow, 1, QtWidgets.QTableWidgetItem(f"{row['frequency']}"))
                            self.spotlist.setItem(irow, 2, QtWidgets.QTableWidgetItem(f"{1800-row['expire']}s"))
                            irow+=1
                self.dataAvailable=False
            uix=self.x()
            uiy=self.y()

        except Exception as e:
            print(f'Error refreshSpotList(): {e}')
        
    def workerThread(self):
        while 1:
            if self.dataAvailable==False:
                try:
                    resp = requests.get(url=SPOTURL)
                    df = pd.read_json(resp.text)
                    self.sorted_df = df.sort_values(by=['expire'], ascending=False)
                    
                    self.iconlist = []
                    for index, row in self.sorted_df.iterrows():
                        band = self.getBandFromFrequency(row['frequency'])
                        if self.settings['bands'][band] and row['mode']!='':
                            if self.settings['modes'][row['mode']]:
                                itm = QtWidgets.QTableWidgetItem()
                                itm.setIcon(self.getIcon(f"{row['activator']}".split('/')[0]))
                                self.iconlist.append(itm)      
                    self.dataAvailable=True     
                    time.sleep(30)
                except Exception as e:
                    print(f'Error workerThread(): {e}')
            time.sleep(1)

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
window.setWindowTitle(f"QPota")
window.show()

timer = QTimer(window)
timer.timeout.connect(window.refreshSpotList)

x = threading.Thread(target=window.workerThread, daemon=True)
x.start()
atexit.register(window.saveUIPosition)

def run():
    timer.start(1000)
    sys.exit(app.exec())

if __name__ == "__main__":
    run()
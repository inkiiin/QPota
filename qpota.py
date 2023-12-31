#!/usr/bin/env python3
import requests, sys, os, time, threading, json, io
import atexit
import socket
import pandas as pd
from PyQt5 import QtCore, QtWidgets, uic
from PyQt5.QtCore import QDir, QLocale, QRect, QTimer
from PyQt5.QtGui import QFontDatabase, QIcon, QImage, QPixmap, QColor

DATA_PATH = f'{os.path.dirname(os.path.abspath(__file__))}/data'
DIALOG = f'{DATA_PATH}/dialog.ui'
SETTINGS = f'{DATA_PATH}/settings.json'
RIGPORT='127.0.0.1:4533'
HEADER_LABELS=['Activator','Frequency','Age']


SPOTURL='https://api.pota.app/spot/activator'
USERURL='https://api.pota.app/stats/user'
SPOTTINGURL='https://api.pota.app/spot' 
HUNTEDURL='https://api.pota.app/spot/hunted'

uix=100
uiy=100        

class MainWindow(QtWidgets.QMainWindow):
    dataAvailable = False
    iconlist = []
    sorted_df = []
    rigport = RIGPORT
    settings = []
    lastclickedactivator =""
    imidiateRefresh=False
    lastcmd= 'V VFOA M CW 500 F 7033000'
    
    def __init__(self, parent=None):
        """Initialize class variables"""
        super().__init__(parent)
        uic.loadUi(DIALOG, self)
        self.loadSettings()
        self.move(uix,uiy)
        self.btn_CALL = self.findChild(QtWidgets.QPushButton, "btn_CALL")
        self.btn_CALL.clicked.connect(self.send_mycall)
        self.btn_GM= self.findChild(QtWidgets.QPushButton, "btn_GM")
        self.btn_GM.clicked.connect(self.send_gm)
        self.btn_GA = self.findChild(QtWidgets.QPushButton, "btn_GA")
        self.btn_GA.clicked.connect(self.send_ga)
        self.btn_EE = self.findChild(QtWidgets.QPushButton, "btn_EE")
        self.btn_EE.clicked.connect(self.send_ee)
        self.btn_15 = self.findChild(QtWidgets.QPushButton, "btn_15")
        self.btn_15.clicked.connect(self.setSpeed_15)
        self.btn_20 = self.findChild(QtWidgets.QPushButton, "btn_20")
        self.btn_20.clicked.connect(self.setSpeed_20)
        self.spotlist = self.findChild(QtWidgets.QTableWidget, "tableWidget")
        self.spotlist.cellClicked.connect(self.setTRX) 
        self.spotlist.setColumnCount(3)
        self.spotlist.setHorizontalHeaderLabels(HEADER_LABELS)

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
                if self.settings['mycall']!=None:
                    self.btn_CALL.setText(self.settings["mycall"]) 

    def colorizeCall(self, call):
        try:
            for row in range(self.spotlist.rowCount()): 
                self.spotlist.item(row, 0).setBackground( QColor('#404040'))
                self.spotlist.item(row, 1).setBackground( QColor('#404040'))
                self.spotlist.item(row, 2).setBackground( QColor('#404040'))

            if(self.lastclickedactivator!=''):
                
                itms=self.spotlist.findItems(call,QtCore.Qt.MatchFlag.MatchContains)
                if itms:
                    row=itms[0].row()
                    if row>=0:
                        self.spotlist.item(row, 0).setBackground( QColor('#005500'))
                        self.spotlist.item(row, 1).setBackground( QColor('#005500'))
                        self.spotlist.item(row, 2).setBackground( QColor('#005500'))
        except Exception as e:
            print(f'Error colorizeCall(): {e}')

    def setTRX(self,row,column):
        try:
            self.lastclickedactivator = self.spotlist.item(row, 0).text()
            self.colorizeCall(self.spotlist.item(row, 0).text())
            dfrow = self.sorted_df.loc[self.sorted_df['activator'] == self.spotlist.item(row, 0).text()]
            freq = int(float(dfrow['frequency'].values[0])*1000)
            mode = dfrow['mode'].values[0]

            CMD = 'V VFOA '
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if modifiers == QtCore.Qt.ShiftModifier:
                self.markAsHunted(dfrow)
                return
                
            if mode == 'CW':
                CMD += 'M CW 500 ' 
            elif mode == 'SSB':
                if freq < 10000:
                    CMD += 'M LSB 2700 '
                else:
                    CMD += 'M USB 2700 '
            elif mode == 'FM':
                CMD += 'M FM 15000 '
            else:
                CMD += 'M USB 2700 '

            CMD += f'F {int(freq)}'
            
            self.lastcmd=CMD
            
            os.system(f'rigctl -m 2 -r {self.rigport} {CMD}')
        except Exception as e:
            print(f'Error setTRX(): {e}')

    def setPower_5w(self):
        self.setPower(5)
    
    def setPower_20w(self):
        self.setPower(20)
        
    def setPower_100w(self):
        self.setPower(100)
        
    def setPower(self, power):
        try:
            CMD = f'L RFPOWER {float(power/100.0)}'
            os.system(f'rigctl -m 2 -r {self.rigport} {CMD}')
            
        except Exception as e:
            print(f'Error setPower(): {e}')

    def setSpeed_15(self):
        self.setSpeed(15)

    def setSpeed_20(self):
        self.setSpeed(20)

    def setSpeed(self, speed):
        try:
            CMD = f'L KEYSPD {speed}'
            os.system(f'rigctl -m 2 -r {self.rigport} {CMD}')
            
        except Exception as e:
            print(f'Error setSpeed(): {e}')
    
    def send_mycall(self):
        self.sendMorse(self.settings["mycall"])

    def send_gm(self):
        self.sendMorse(f'BK GM UR 55N 55N 73 TU')

    def send_ga(self):
        self.sendMorse(f'BK GA UR 55N 55N 73 TU')

    def send_ee(self):
        self.sendMorse(f'EE')
    
    def sendMorse(self, text):
        try:
            CMD = f'b "{text}"'
            os.system(f'rigctl -m 2 -r {self.rigport} {CMD}')
            
        except Exception as e:
            print(f'Error sendMorse(): {e}')
    
    def setTune(self):
        os.system(f'rigctl -m 2 -r {self.rigport} M AM 0')
        self.setPower_20w()
        os.system(f'rigctl -m 2 -r {self.rigport} T 1')
        time.sleep(3)
        os.system(f'rigctl -m 2 -r {self.rigport} T 0')
        os.system(f'rigctl -m 2 -r {self.rigport} {self.lastcmd}')

    def getIcon(self, activator):
        icon = QPixmap()
        ico = QIcon(icon)
        resp = requests.get(url=f"{USERURL}/{activator}")
        if resp.status_code == 200:
            activatorid=resp.json()['gravatar']
            resp = requests.get(url=f'https://www.gravatar.com/avatar/{activatorid}?s=32&d=identicon')
            if resp.status_code == 200:
                icon = QPixmap()
                icon.loadFromData(resp.content)
                ico = QIcon(icon)
        return ico
    
    def getHunted(self, activator, reference, mode, band):
        for index, row in self.df_hunted.iterrows():
            if row["activator"]==activator and row["reference"]==reference and row["mode"]==mode and row["band"]==band:
                return True
        return False
            
    def saveUIPosition(self):
        with open(SETTINGS,'w') as f:
            self.settings['rigport']=self.rigport
            self.settings['x']=uix
            self.settings['y']=uiy
            json.dump(self.settings,f)

    def markAsHunted(self, dfrow):
        try:
            payload = '{'+f'"activator":"{dfrow["activator"].values[0]}","spotter":"{self.settings["mycall"]}","frequency":"{dfrow["frequency"].values[0]}","reference":"{dfrow["reference"].values[0]}","mode":"{dfrow["mode"].values[0]}","source":"Web","comments":""'+'}'
            r = requests.post(SPOTTINGURL, data=payload)
            if r.status_code == 200:
                self.imidiateRefresh=True
                self.lastclickedactivator=''
                
        except Exception as e:
            print(f'Error markAsHunted(): {e}')

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
    
    def getModeFromSpot(self,mode):
        if mode == 'CW':
            return 'CW'
        if mode == 'SSB':
            return 'SSB'
        if mode == 'FM':
            return 'FM'
        if mode == 'AM':
            return 'AM'
        if mode == 'RTTY':
            return 'DIG'
        if mode == 'JT9':
            return 'DIG'
        if mode == 'JS8':
            return 'DIG'
        if mode == 'FT8':
            return 'DIG'
        if mode == 'FT4':
            return 'DIG'
        return 'OTHER'
    
    def shouldAdd(self, row):
        band = self.getBandFromFrequency(row['frequency'])
        mode = self.getModeFromSpot(row['mode'])
        if self.settings['bands'][band] and row['reference']!='':
            if self.settings['modes'][mode]:
                if not "QRT" in row['comments'].upper():
                    if not self.getHunted(row['activator'],row['reference'],row['mode'],self.getBandFromFrequency(int(row['frequency']))):
                        return True
        return False

    def refreshSpotList(self):
        global uix
        global uiy

        try:
            if self.dataAvailable:
                irow=0
                self.spotlist.clearContents()
                self.spotlist.setRowCount(0)
                for index, row in self.sorted_df.iterrows():
                    if self.shouldAdd(row):
                        self.spotlist.setRowCount(irow+1)
                        self.spotlist.setVerticalHeaderItem(irow, self.iconlist[irow])
                        self.spotlist.setItem(irow, 0, QtWidgets.QTableWidgetItem(f"{row['activator']}"))
                        self.spotlist.setItem(irow, 1, QtWidgets.QTableWidgetItem(f"{row['frequency']}"))
                        self.spotlist.setItem(irow, 2, QtWidgets.QTableWidgetItem(f"{1800-row['expire']}s"))
                        irow+=1
                        self.colorizeCall(self.lastclickedactivator)
                self.dataAvailable=False
            
            uix=self.x()
            uiy=self.y()

        except Exception as e:
            print(f'Error refreshSpotList(): {e}')
        
    def workerThread(self):
        while 1:
            if self.dataAvailable==False:
                try:
                    resp = requests.get(url=f'{HUNTEDURL}/{self.settings["mycall"]}')
                    if resp.status_code == 200:
                        self.df_hunted = pd.read_json(io.StringIO(resp.text))
                    resp = requests.get(url=SPOTURL)
                    if resp.status_code == 200:
                        df = pd.read_json(io.StringIO(resp.text))     
                        self.sorted_df = df.sort_values(by=['expire'], ascending=False)                  
                        self.iconlist = []
                        for index, row in self.sorted_df.iterrows():
                            if self.shouldAdd(row):
                                itm = QtWidgets.QTableWidgetItem()
                                itm.setIcon(self.getIcon(f"{row['activator']}".split('/')[0]))
                                self.iconlist.append(itm)      
                    self.dataAvailable=True  
                    self.imidiateRefresh=False
                    self.timecounter=30
                    if self.timecounter > 0 and not self.imidiateRefresh:   
                        time.sleep(1)
                        self.timecounter-=1
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

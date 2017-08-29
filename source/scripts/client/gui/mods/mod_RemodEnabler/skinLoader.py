import binascii
import datetime
import time

import BigWorld
import PYmodsCore
import ResMgr
import SoundGroups
import glob
import shutil
import os
import traceback
import weakref
from adisp import AdispException, async, process
from functools import partial
from gui.Scaleform.daapi.view.lobby.LobbyView import LobbyView
from gui.Scaleform.daapi.view.login.LoginView import LoginView
from gui.Scaleform.framework.managers.loaders import ViewLoadParams
from gui.app_loader.loader import g_appLoader
from gui.Scaleform.daapi.view.battle.classic.battle_end_warning_panel import _WWISE_EVENTS
from gui.Scaleform.daapi.view.battle.shared.minimap.settings import MINIMAP_ATTENTION_SOUND_ID
from gui.Scaleform.daapi.view.meta.LoginQueueWindowMeta import LoginQueueWindowMeta
from helpers import getClientVersion
from zipfile import ZipFile
from . import g_config


def skinsPresenceCheck():
    dirSect = ResMgr.openSection('vehicles/skins/textures/')
    if dirSect is not None and dirSect.keys():
        g_config.data['skinsFound'] = True


texReplaced = False
skinsChecked = False
g_config.data['skinsFound'] = False
skinsPresenceCheck()
clientIsNew = True
skinsModelsMissing = True
needToReReadSkinsModels = False
modelsDir = BigWorld.curCV + '/vehicles/skins/models/'
skinVehNamesLDict = {}


class RemodEnablerLoading(LoginQueueWindowMeta):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.lines = []
        self.curPercentage = 0
        g_config.loadingProxy = weakref.proxy(self)

    def _populate(self):
        super(self.__class__, self)._populate()
        self.__initTexts()

    def __initTexts(self):
        self.updateTitle(g_config.i18n['UI_loading_header_CRC32'])
        self.updateMessage()
        self.as_setCancelLabelS(g_config.i18n['UI_loading_bugReport'])
        self.as_showAutoLoginBtnS(False)

    def updateTitle(self, title):
        self.as_setTitleS(title)

    def updateMessage(self):
        self.as_setMessageS(''.join(line.join(("<p align='left'>", "</p>")) for line in self.lines))

    def addLine(self, line):
        if len(self.lines) == 8:
            del self.lines[0]
        self.lines.append(line)
        self.updateMessage()

    def onComplete(self):
        self.lines[-1] += g_config.i18n['UI_loading_done'].join(("<font color='#00FF00'>", '</font>'))
        self.updateMessage()
        SoundGroups.g_instance.playSound2D(MINIMAP_ATTENTION_SOUND_ID)

    def addBar(self, pkgName):
        self.curPercentage = 0
        self.addLine(g_config.i18n['UI_loading_package'] % pkgName)
        self.addLine(self.createBar())

    def createBar(self):
        red = 510 - 255 * self.curPercentage / 50
        green = 255 * self.curPercentage / 50
        return "<font color='#007BFF' face='Arial'>%s</font><font color='#{0:0>2x}{1:0>2x}00'>  %s%%</font>".format(
            red if red < 255 else 255, green if green < 255 else 255) % (
                   u'\u2593' * (self.curPercentage / 4) + u'\u2591' * (25 - self.curPercentage / 4), self.curPercentage)

    def updatePercentage(self, percentage):
        self.curPercentage = percentage
        self.lines[-1] = self.createBar()
        self.updateMessage()

    def onBarComplete(self):
        del self.lines[-1]
        self.onComplete()

    def onTryClosing(self):
        return False

    def onCancelClick(self):
        BigWorld.wg_openWebBrowser('http://www.koreanrandom.com/forum/topic/22800-')

    def onWindowClose(self):
        g_config.loadingProxy = None
        self.destroy()


def CRC32_from_file(filename, localPath):
    buf = str(ResMgr.openSection(filename).asBinary)
    buf = binascii.crc32(buf) & 0xFFFFFFFF & localPath.__hash__()
    return buf


@async
@process
def skinCRC32All(callback):
    global texReplaced, skinVehNamesLDict
    CRC32cache = g_config.skinsCache['CRC32']
    skinsPath = 'vehicles/skins/textures/'
    dirSect = ResMgr.openSection(skinsPath)
    if dirSect is not None and dirSect.keys():
        g_config.data['skinsFound'] = True
        print 'RemodEnabler: listing %s for CRC32' % skinsPath
        g_config.loadingProxy.addLine(g_config.i18n['UI_loading_skins'])
        CRC32 = 0
        resultList = []
        for skin in PYmodsCore.remDups(dirSect.keys()):
            g_config.loadingProxy.addLine(g_config.i18n['UI_loading_skinPack'] % os.path.basename(skin))
            skinCRC32 = 0
            skinSect = ResMgr.openSection(skinsPath + skin + '/vehicles/')
            for nation in [] if skinSect is None else PYmodsCore.remDups(skinSect.keys()):
                nationCRC32 = 0
                nationSect = ResMgr.openSection(skinsPath + skin + '/vehicles/' + nation)
                for vehicleName in [] if nationSect is None else PYmodsCore.remDups(nationSect.keys()):
                    vehicleCRC32 = 0
                    skinVehNamesLDict.setdefault(vehicleName.lower(), []).append(skin)
                    vehicleSect = ResMgr.openSection(skinsPath + skin + '/vehicles/' + nation + '/' + vehicleName)
                    for texture in [] if vehicleSect is None else (
                            texName for texName in PYmodsCore.remDups(vehicleSect.keys()) if texName.endswith('.dds')):
                        localPath = 'vehicles/' + nation + '/' + vehicleName + '/' + texture
                        texPath = skinsPath + skin + '/' + localPath
                        textureCRC32 = CRC32_from_file(texPath, localPath)
                        vehicleCRC32 ^= textureCRC32
                    nationCRC32 ^= vehicleCRC32
                    yield doFuncCall()
                skinCRC32 ^= nationCRC32
            g_config.loadingProxy.onComplete()
            if skinCRC32 in resultList:
                print 'RemodEnabler: deleting duplicate skins pack:', skin.replace(os.sep, '/')
                shutil.rmtree(skin)
                continue
            CRC32 ^= skinCRC32
            resultList.append(skinCRC32)
        if CRC32cache is not None and str(CRC32) == CRC32cache:
            print 'RemodEnabler: skins textures were not changed'
        else:
            if CRC32cache is None:
                print 'RemodEnabler: skins textures were reinstalled (or you deleted the CRC32 cache)'
            else:
                print 'RemodEnabler: skins textures were changed'
            g_config.skinsCache['CRC32'] = str(CRC32)
            texReplaced = True
    else:
        print 'RemodEnabler: skins folder is empty'
    BigWorld.callback(0.0, partial(callback, True))


@async
def modelsCheck(callback):
    global clientIsNew, skinsModelsMissing, needToReReadSkinsModels
    lastVersion = g_config.skinsCache['version']
    if lastVersion:
        if getClientVersion() == lastVersion:
            clientIsNew = False
        else:
            print 'RemodEnabler: skins client version changed'
    else:
        print 'RemodEnabler: skins client version cache not found'

    if os.path.isdir(modelsDir):
        if len(glob.glob(modelsDir + '*')):
            skinsModelsMissing = False
        else:
            print 'RemodEnabler: skins models dir is empty'
    else:
        print 'RemodEnabler: skins models dir not found'
    needToReReadSkinsModels = g_config.data['skinsFound'] and (clientIsNew or skinsModelsMissing or texReplaced)
    if g_config.data['skinsFound'] and clientIsNew:
        if os.path.isdir(modelsDir):
            shutil.rmtree(modelsDir)
        g_config.skinsCache['version'] = getClientVersion()
    if g_config.data['skinsFound'] and not os.path.isdir(modelsDir):
        os.makedirs(modelsDir)
    elif not g_config.data['skinsFound'] and os.path.isdir(modelsDir):
        print 'RemodEnabler: no skins found, deleting %s' % modelsDir
        shutil.rmtree(modelsDir)
    elif texReplaced and os.path.isdir(modelsDir):
        shutil.rmtree(modelsDir)
        os.makedirs(modelsDir)
    g_config.loadJson('skinsCache', g_config.skinsCache, g_config.configPath, True)
    BigWorld.callback(0.0, partial(callback, True))


@async
@process
def modelsProcess(callback):
    if needToReReadSkinsModels:
        g_config.loadingProxy.updateTitle(g_config.i18n['UI_loading_header_models_unpack'])
        SoundGroups.g_instance.playSound2D(_WWISE_EVENTS.APPEAR)
        modelFileFormats = ('.model', '.visual', '.visual_processed')
        print 'RemodEnabler: unpacking vehicle packages'
        for vehPkgPath in glob.glob('./res/packages/vehicles*.pkg') + glob.glob('./res/packages/shared_content*.pkg'):
            completionPercentage = 0
            filesCnt = 0
            g_config.loadingProxy.addBar(os.path.basename(vehPkgPath))
            vehPkg = ZipFile(vehPkgPath)
            fileNamesList = filter(
                lambda x: x.startswith('vehicles') and 'normal' in x and os.path.splitext(x)[1] in modelFileFormats,
                vehPkg.namelist())
            allFilesCnt = len(fileNamesList)
            for fileNum, memberFileName in enumerate(fileNamesList):
                if not needToReReadSkinsModels:
                    continue
                for skinName in skinVehNamesLDict.get(os.path.normpath(memberFileName).split('\\')[2].lower(), []):
                    processMember(memberFileName, skinName)
                    filesCnt += 1
                    if not filesCnt % 25:
                        yield doFuncCall()
                currentPercentage = int(100 * float(fileNum) / float(allFilesCnt))
                if currentPercentage != completionPercentage:
                    completionPercentage = currentPercentage
                    g_config.loadingProxy.updatePercentage(completionPercentage)
                    yield doFuncCall()
            vehPkg.close()
            g_config.loadingProxy.onBarComplete()
    BigWorld.callback(0.0, partial(callback, True))


@async
def doFuncCall(callback):
    BigWorld.callback(0.0, partial(callback, None))


# noinspection PyPep8,PyPep8
def processMember(memberFileName, skinName):
    skinDir = modelsDir.replace('%s/' % BigWorld.curCV, '') + skinName + '/'
    texDir = skinDir.replace('models', 'textures')
    skinsSign = 'vehicles/skins/'
    if '.model' in memberFileName:
        oldModel = ResMgr.openSection(memberFileName)
        newModelPath = skinDir + memberFileName
        curModel = ResMgr.openSection(newModelPath, True)
        curModel.copy(oldModel)
        if curModel is None:
            print skinDir + memberFileName
        if curModel.has_key('parent') and skinsSign not in curModel['parent'].asString:
            curParent = skinDir + curModel['parent'].asString
            curModel.writeString('parent', curParent.replace('\\', '/'))
        if skinsSign not in curModel['nodefullVisual'].asString:
            curVisual = skinDir + curModel['nodefullVisual'].asString
            curModel.writeString('nodefullVisual', curVisual.replace('\\', '/'))
        curModel.save()
    elif '.visual' in memberFileName:
        oldVisual = ResMgr.openSection(memberFileName)
        newVisualPath = skinDir + memberFileName
        curVisual = ResMgr.openSection(newVisualPath, True)
        curVisual.copy(oldVisual)
        for curName, curSect in curVisual.items():
            if curName != 'renderSet':
                continue
            for curSubName, curSubSect in curSect['geometry'].items():
                if curSubName != 'primitiveGroup':
                    continue
                for curPrimName, curProp in curSubSect['material'].items():
                    if curPrimName != 'property' or not curProp.has_key('Texture'):
                        continue
                    curTexture = curProp['Texture'].asString
                    if skinsSign not in curTexture and ResMgr.isFile(texDir + curTexture):
                        curDiff = texDir + curTexture
                        curProp.writeString('Texture', curDiff.replace('\\', '/'))
                    elif skinsSign in curTexture and not ResMgr.isFile(curTexture):
                        curDiff = curTexture.replace(texDir, '')
                        curProp.writeString('Texture', curDiff.replace('\\', '/'))

        curVisual.writeString('primitivesName', os.path.splitext(memberFileName)[0])
        curVisual.save()


@process
def skinLoader():
    global skinsChecked
    if g_config.data['enabled'] and g_config.data['skinsFound'] and not skinsChecked:
        lobbyApp = g_appLoader.getDefLobbyApp()
        if lobbyApp is not None:
            lobbyApp.loadView(ViewLoadParams('RemodEnablerLoading'))
        else:
            return
        jobStartTime = time.time()
        try:
            yield skinCRC32All()
            yield modelsCheck()
            yield modelsProcess()
        except AdispException:
            traceback.print_exc()
        print 'RemodEnabler: total models check time:', datetime.timedelta(seconds=round(time.time() - jobStartTime))
        BigWorld.callback(1, partial(SoundGroups.g_instance.playSound2D, 'enemy_sighted_for_team'))
        BigWorld.callback(2, g_config.loadingProxy.onWindowClose)
        skinsChecked = True


@PYmodsCore.overrideMethod(LoginView, '_populate')
def new_Login_populate(base, self):
    base(self)
    g_config.data['isInHangar'] = False
    if g_config.data['enabled']:
        BigWorld.callback(3.0, skinLoader)


@PYmodsCore.overrideMethod(LobbyView, '_populate')
def new_Lobby_populate(base, self):
    base(self)
    g_config.data['isInHangar'] = True

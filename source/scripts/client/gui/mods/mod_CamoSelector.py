# -*- coding: utf-8 -*-
import time

import BigWorld
import CurrentVehicle
import Keys
import PYmodsCore
import ResMgr
import heapq
import items.vehicles
import nations
import random
import traceback
import weakref
from Account import Account
from CurrentVehicle import g_currentPreviewVehicle, g_currentVehicle
from gui import InputHandler, SystemMessages, g_tankActiveCamouflage
from gui.ClientHangarSpace import ClientHangarSpace
from gui.Scaleform.daapi.settings.views import VIEW_ALIAS
from gui.Scaleform.daapi.view.lobby.LobbyView import _LobbySubViewsCtrl
from gui.Scaleform.daapi.view.lobby.customization.main_view import MainView
from gui.Scaleform.framework import ScopeTemplates, ViewSettings, ViewTypes, g_entitiesFactories
from gui.Scaleform.framework.entities.abstract.AbstractWindowView import AbstractWindowView
from gui.Scaleform.framework.managers.loaders import ViewLoadParams
from gui.app_loader import g_appLoader
from gui.customization import g_customizationController
from gui.customization.data_aggregator import DataAggregator
from gui.customization.shared import CUSTOMIZATION_TYPE
from helpers import i18n
from items import _xml
from items.vehicles import CAMOUFLAGE_KINDS, CAMOUFLAGE_KIND_INDICES
from vehicle_systems.CompoundAppearance import CompoundAppearance


class CamoSelectorUI(AbstractWindowView):
    def _populate(self):
        super(self.__class__, self)._populate()
        if self._isDAAPIInited():
            _config.UIProxy = weakref.proxy(self)

    def py_onSyncData(self):
        # noinspection PyUnresolvedReferences
        texts = {
            'header': _config.i18n['UI_flash_header'],
            'nations': map(lambda x: i18n.makeString('#nations:%s' % x), nations.NAMES) + [
                _config.i18n['UI_flash_camoMode_modded'], _config.i18n['UI_flash_camoMode_international']],
            'camouflages': [[] for _ in xrange(len(nations.NAMES) + 2)],
            'randomOptions': {'text': _config.i18n['UI_flash_randomOptions_text'],
                              'tooltip': _config.tb.createTooltip('randomOptions', 'flash'),
                              'options': [_config.i18n['UI_flash_randomOptions_OFF'],
                                          _config.i18n['UI_flash_randomOptions_overrideRandom'],
                                          _config.i18n['UI_flash_randomOptions_includeInRandom']]},
            'useFor': {'header': _config.tb.createLabel('useFor_header', 'flash'),
                       'ally': _config.tb.createLabel('useFor_ally', 'flash'),
                       'enemy': _config.tb.createLabel('useFor_enemy', 'flash')},
            'kinds': {'header': _config.tb.createLabel('kinds_header', 'flash'),
                      'winter': _config.tb.createLabel('kinds_winter', 'flash'),
                      'summer': _config.tb.createLabel('kinds_summer', 'flash'),
                      'desert': _config.tb.createLabel('kinds_desert', 'flash')},
            'installTooltip': _config.i18n['UI_flash_installTooltip'],
            'save': _config.i18n['UI_flash_save']}
        settings = [[] for _ in xrange(len(nations.NAMES) + 2)]
        for idx, nation in enumerate(nations.NAMES + ('modded', 'international')):
            nationID = min(idx, len(nations.NAMES) - 1)
            camouflages = items.vehicles.g_cache.customization(nationID)['camouflages']
            camoNames = {camouflage['name']: camoID for camoID, camouflage in camouflages.items()}
            for camoName in camoNames.keys():
                if nation == 'modded':
                    if camoName not in _config.camouflages['modded']:
                        del camoNames[camoName]
                elif nation == 'international':
                    if camoName not in _config.origInterCamo:
                        del camoNames[camoName]
                elif camoName in _config.interCamo:
                    del camoNames[camoName]
            for camoName in sorted(camoNames.keys()):
                camoID = camoNames[camoName]
                camouflageDesc = camouflages[camoID]
                camouflage = _config.camouflages.get(nation, {}).get(camoName, {})
                texts['camouflages'][idx].append(camoName)
                camoSettings = {'randomOption': camouflage.get('random_mode', 2),
                                'camoInShop': g_customizationController.dataAggregator._elementIsInShop(
                                    camoID, 0, nationID),
                                'isInternational': camoName in _config.interCamo,
                                'useFor': {'ally': camouflage.get('useForAlly', True),
                                           'enemy': camouflage.get('useForEnemy', True)},
                                'kinds': {}}
                for key, kind in CAMOUFLAGE_KINDS.items():
                    if camouflage.get('kinds') is not None:
                        camoSettings['kinds'][key] = key in camouflage['kinds']
                    else:
                        camoSettings['kinds'][key] = kind == camouflageDesc['kind']
                settings[idx].append(camoSettings)
        self.flashObject.as_syncData({'texts': texts, 'settings': settings, 'ids': _config.backup})
        self.changeNation(self.getCurrentNation())

    @staticmethod
    def getCurrentNation():
        if g_currentPreviewVehicle.isPresent():
            vDesc = g_currentPreviewVehicle.item.descriptor
        elif g_currentVehicle.isPresent():
            vDesc = g_currentVehicle.item.descriptor
        else:
            raise AttributeError('g_currentVehicle.item.descriptor not found')
        return vDesc.type.customizationNationID

    def changeNation(self, nationID):
        _config.backupNationID = nationID
        if self._isDAAPIInited():
            self.flashObject.as_changeNation(nationID)

    def onWindowClose(self):
        _config.activePreviewCamo = None
        SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_camouflageRestore'],
                                   SystemMessages.SM_TYPE.CustomizationForGold)
        PYmodsCore.refreshCurrentVehicle()
        _config.UIProxy = None
        self.destroy()

    def as_isModalS(self):
        if self._isDAAPIInited():
            return False

    @staticmethod
    def py_onSettings(settings):
        for idx, nation in enumerate(nations.NAMES + ('modded', 'international')):
            nationID = min(idx, len(nations.NAMES) - 1)
            camouflages = items.vehicles.g_cache.customization(nationID)['camouflages']
            nationConf = _config.camouflages.setdefault(nation, {})
            camoNames = {camouflage['name']: camoID for camoID, camouflage in camouflages.items()}
            for camoName in camoNames.keys():
                if nation == 'modded':
                    if camoName not in _config.camouflages['modded']:
                        del camoNames[camoName]
                elif nation == 'international':
                    if camoName not in _config.origInterCamo:
                        del camoNames[camoName]
                elif camoName in _config.interCamo:
                    del camoNames[camoName]
            for camoNum, camoName in enumerate(sorted(camoNames.keys())):
                nationConf.setdefault(camoName, {})
                camoID = camoNames[camoName]
                camouflageDesc = camouflages[camoID]
                camoInShop = g_customizationController.dataAggregator._elementIsInShop(camoID, 0, nationID)
                isInter = camoName in _config.interCamo
                newSettings = settings[idx][camoNum]
                nationConf[camoName]['random_mode'] = newSettings.randomOption
                nationConf[camoName]['useForAlly'] = newSettings.useFor.ally
                nationConf[camoName]['useForEnemy'] = newSettings.useFor.enemy
                enabledKinds = []
                for key in ('winter', 'summer', 'desert'):
                    if getattr(newSettings.kinds, key):
                        enabledKinds.append(key)
                    nationConf[camoName]['kinds'] = ','.join(enabledKinds)
                for confFolderName in _config.configFolders:
                    configFolder = _config.configFolders[confFolderName]
                    if camoName in configFolder:
                        PYmodsCore.loadJson(_config.ID, 'settings', dict((key, nationConf[key]) for key in configFolder),
                                            _config.configPath + 'camouflages/' + confFolderName + '/', True, False)
                if nationConf[camoName]['random_mode'] == 2 or nationConf[camoName]['random_mode'] == 1 and not isInter:
                    del nationConf[camoName]['random_mode']
                kindNames = filter(None, nationConf[camoName]['kinds'].split(','))
                if len(kindNames) == 1 and kindNames[0] == CAMOUFLAGE_KIND_INDICES[camouflageDesc['kind']] or camoInShop:
                    del nationConf[camoName]['kinds']
                for team in ('Ally', 'Enemy'):
                    if nationConf[camoName]['useFor%s' % team]:
                        del nationConf[camoName]['useFor%s' % team]
                if not nationConf[camoName]:
                    del nationConf[camoName]
            if nation in _config.camouflages and not nationConf and nation != 'modded':
                del _config.camouflages[nation]
        newSettings = {}
        if _config.disable:
            newSettings['disable'] = _config.disable
        for nation in nations.NAMES + ('international',):
            if nation in _config.camouflages:
                newSettings[nation] = _config.camouflages[nation]
        PYmodsCore.loadJson(_config.ID, 'settings', newSettings, _config.configPath, True)

        SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_camouflageSave'],
                                   SystemMessages.SM_TYPE.CustomizationForGold)
        PYmodsCore.refreshCurrentVehicle()

    @staticmethod
    def py_printLog(*args):
        for arg in args:
            print arg

    @staticmethod
    def py_onShowPreset(nationID, mode, camoID):
        nationName = ('modded', 'international', nations.NAMES[nationID])[mode]
        camouflages = items.vehicles.g_cache.customization(nationID)['camouflages']
        camoNames = {camouflage['name']: camoID for camoID, camouflage in camouflages.items()}
        for camoName in camoNames.keys():
            if nationName == 'modded':
                if camoName not in _config.camouflages['modded']:
                    del camoNames[camoName]
            elif nationName == 'international':
                if camoName not in _config.origInterCamo:
                    del camoNames[camoName]
            elif camoName in _config.interCamo:
                del camoNames[camoName]
        _config.activePreviewCamo = sorted(camoNames.keys())[int(camoID)]
        SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_camouflagePreview'] +
                                   _config.activePreviewCamo.join(('<b>', '</b>')),
                                   SystemMessages.SM_TYPE.CustomizationForGold)
        _config.backup['mode'] = mode
        newIdx = nationID if mode == 2 else (len(nations.NAMES) + mode - 2)
        _config.backup['camoID'][newIdx] = camoID
        PYmodsCore.refreshCurrentVehicle()

    @staticmethod
    def py_onApplyPreset():
        installSelectedCamo()


class ConfigInterface(PYmodsCore.PYmodsConfigInterface):
    def __init__(self):
        self.disable = []
        self.hangarCamoCache = {}
        self.camouflagesCache = {}
        self.camouflages = {}
        self.configFolders = {}
        self.currentOverriders = dict.fromkeys(('Ally', 'Enemy'))
        self.interCamo = []
        self.origInterCamo = []
        self.changedNations = []
        self.activePreviewCamo = None
        self.UIProxy = None
        self.backupNationID = None
        self.backup = {'mode': 0, 'camoID': (len(nations.NAMES) + 2) * [0]}
        self.isModAdded = False
        super(ConfigInterface, self).__init__()

    def init(self):
        self.ID = '%(mod_ID)s'
        self.version = '2.5.6 (%(file_compile_date)s)'
        self.author = '%s (thx to tratatank, Blither!)' % self.author
        self.defaultKeys = {'selectHotkey': [Keys.KEY_F5, [Keys.KEY_LCONTROL, Keys.KEY_RCONTROL]],
                            'selectHotKey': ['KEY_F5', ['KEY_LCONTROL', 'KEY_RCONTROL']]}
        self.data = {'enabled': True, 'doRandom': True, 'useBought': True, 'hangarCamoKind': 0,
                     'fullAlpha': False, 'disableWithDefault': False,
                     'selectHotkey': self.defaultKeys['selectHotkey'], 'selectHotKey': self.defaultKeys['selectHotKey']}
        self.i18n = {
            'UI_description': 'Camouflage selector',
            'UI_flash_header': 'Camouflages setup',
            'UI_flash_header_tooltip': ('Advanced settings for camouflages added by CamoSelector by '
                                        '<font color=\'#DD7700\'><b>Polyacov_Yury</b></font>'),
            'UI_flash_camoMode_modded': 'Modded',
            'UI_flash_camoMode_international': 'International',
            'UI_flash_randomOptions_text': 'Random selection mode',
            'UI_flash_randomOptions_tooltip': (
                ' • <b>OFF</b>: camouflage is disabled.\n • <b>Override random selection</b>: this camouflage gets '
                'included into a list of camouflages which appear <b>instead of</b> default ones when a random option is '
                'being selected.\n • <b>Include in random selection</b>: this camouflage is included into a list of '
                'camouflages which may appear <b>along with</b> default ones when a random option is being selected. '
                'Please note that these camouflages get <b>overridden</b> by ones that have an option above selected.'),
            'UI_flash_randomOptions_OFF': 'OFF',
            'UI_flash_randomOptions_overrideRandom': 'Override random selection',
            'UI_flash_randomOptions_includeInRandom': 'Include in random selection',
            'UI_flash_useFor_header_text': 'Use this camouflage for:',
            'UI_flash_useFor_header_tooltip': (
                'This camouflage will be used for these groups of tanks.\n'
                '<b>Attention</b>: a camouflage with no tick set will be considered disabled.'),
            'UI_flash_useFor_ally_text': 'Player and allies',
            'UI_flash_useFor_enemy_text': 'Enemies',
            'UI_flash_kinds_header_text': 'Camouflage kinds:',
            'UI_flash_kinds_header_tooltip': (
                'This camouflage will appear on these kinds of maps.\n'
                '<b>Attention</b>: a camouflage with no tick set will be considered disabled.'),
            'UI_flash_kinds_winter_text': 'Winter',
            'UI_flash_kinds_summer_text': 'Summer',
            'UI_flash_kinds_desert_text': 'Desert',
            'UI_flash_installTooltip': '{HEADER}Install{/HEADER}{BODY}"Buy" this camouflage for selected tank.{/BODY}',
            'UI_flash_save': 'Save',
            'UI_setting_doRandom_text': 'Select random camouflages',
            'UI_setting_doRandom_tooltip': (
                'If enabled, mod will select a random available camouflage if no other option is provided.'),
            'UI_setting_useBought_text': 'Use bought camouflages in battle',
            'UI_setting_useBought_tooltip': "If enabled, mod will preserve bought camouflages on other players' tanks.",
            'UI_setting_selectHotkey_text': 'Camouflage select hotkey',
            'UI_setting_selectHotkey_tooltip': (
                'This hotkey will permanently install currently selected preview camouflage to current tank.'),
            'UI_setting_disableWithDefault_text': 'Disable for vehicles with default camouflage',
            'UI_setting_disableWithDefault_tooltip': 'If enabled, mod will ignore vehicles with a default camouflage.',
            'UI_setting_fullAlpha_text': 'Non-transparent modded camouflages',
            'UI_setting_fullAlpha_tooltip': 'If enabled, all modded camouflages lose their transparency.\n'
                                            'Some call this "dirt-less skins".',
            'UI_setting_hangarCamoKind_text': 'Hangar camouflage kind',
            'UI_setting_hangarCamoKind_tooltip': 'This setting controls a kind which is used in hangar.',
            'UI_setting_hangarCamo_winter': 'Winter', 'UI_setting_hangarCamo_summer': 'Summer',
            'UI_setting_hangarCamo_desert': 'Desert', 'UI_setting_hangarCamo_random': 'Random',
            'UI_camouflagePreview': '<b>Camouflage Selector:</b>\nCamouflage previewing:\n',
            'UI_camouflagePreviewError': '<b>Camouflage Selector:</b>\nCamouflage not found:\n',
            'UI_camouflageRestore': '<b>Camouflage Selector:</b>\nLoading previous camouflage.',
            'UI_camouflageSave': '<b>Camouflage Selector:</b>\nSaving custom camouflage settings.',
            'UI_camouflageSelect': '<b>Camouflage Selector:</b>\nInstalling selected camouflages.',
            'UI_installCamouflage': ('<b>Camouflage Selector:</b>\nCamouflage installed: <b>{name}</b>, '
                                     'camouflage kind: <b>{kind}</b>'),
            'UI_installCamouflage_already': ('<b>Camouflage Selector:</b>\nCamouflage <b>already</b> installed: '
                                             '<b>{name}</b>, camouflage kind: <b>{kind}</b>'),
            'UI_customOrInvalid': ('<b>Camouflage Selector:</b>\nCustom or invalid camouflage detected for '
                                   '<b>{kind}</b> camouflages: <b>{name}</b>'),
            'UI_customOrInvalid_winter': 'winter', 'UI_customOrInvalid_summer': 'summer',
            'UI_customOrInvalid_desert': 'desert'}
        super(ConfigInterface, self).init()

    def createTemplate(self):
        return {'modDisplayName': self.i18n['UI_description'],
                'settingsVersion': 200,
                'enabled': self.data['enabled'],
                'column1': [self.tb.createOptions('hangarCamoKind', [self.i18n['UI_setting_hangarCamo_%s' % x] for x in
                                                                     ('winter', 'summer', 'desert', 'random')]),
                            self.tb.createControl('doRandom'),
                            self.tb.createControl('disableWithDefault')],
                'column2': [self.tb.createHotKey('selectHotkey'),
                            self.tb.createEmpty(), self.tb.createEmpty(),
                            self.tb.createControl('useBought'),
                            self.tb.createControl('fullAlpha')]}

    def onMSADestroy(self):
        try:
            from gui.mods import mod_remodenabler
        except StandardError:
            PYmodsCore.refreshCurrentVehicle()

    def onApplySettings(self, settings):
        if 'fullAlpha' in settings and settings['fullAlpha'] != self.data['fullAlpha']:
            self.changedNations[:] = []
            items.vehicles.g_cache._Cache__customization = [None for _ in nations.NAMES]
        super(self.__class__, self).onApplySettings(settings)
        self.hangarCamoCache.clear()
        if self.isModAdded:
            kwargs = dict(id='CamoSelectorUI', enabled=self.data['enabled'])
            try:
                BigWorld.g_modsListApi.updateModification(**kwargs)
            except AttributeError:
                BigWorld.g_modsListApi.updateMod(**kwargs)

    def readCamouflages(self, doShopCheck):
        self.configFolders.clear()
        self.camouflages = {'modded': {}}
        self.camouflagesCache = PYmodsCore.loadJson(self.ID, 'camouflagesCache', self.camouflagesCache, self.configPath)
        try:
            camoDirPath = '../' + self.configPath + 'camouflages'
            camoDirSect = ResMgr.openSection(camoDirPath)
            camoNames = set(
                (x for x in camoDirSect.keys() if ResMgr.isDir(camoDirPath + '/' + x)) if camoDirSect is not None else [])
            for camoName in camoNames:
                self.configFolders[camoName] = confFolder = set()
                settings = PYmodsCore.loadJson(self.ID, 'settings', {}, self.configPath + 'camouflages/' + camoName + '/')
                for key in settings:
                    confFolder.add(key)
                self.camouflages['modded'].update(settings)
        except StandardError:
            traceback.print_exc()

        self.interCamo = [x['name'] for x in items.vehicles.g_cache.customization(0)['camouflages'].itervalues()]
        for nationID in xrange(1, len(nations.NAMES)):
            camoNames = [x['name'] for x in items.vehicles.g_cache.customization(nationID)['camouflages'].itervalues()]
            self.interCamo = [x for x in self.interCamo if x in camoNames]
        self.origInterCamo = [x for x in self.interCamo if x not in self.camouflages['modded']]
        settings = PYmodsCore.loadJson(self.ID, 'settings', {}, self.configPath)
        if 'disable' in settings:
            if not settings['disable']:
                del settings['disable']
            else:
                self.disable = settings['disable']
        for nation in settings.keys():
            if nation not in nations.NAMES:
                if nation != 'international':
                    del settings[nation]
                    continue
                nationID = 0
            else:
                nationID = nations.INDICES[nation]
            camouflages = items.vehicles.g_cache.customization(nationID)['camouflages']
            nationConf = settings[nation]
            camoNames = [camouflage['name'] for camouflage in camouflages.values()]
            for camoName in nationConf:
                if camoName not in camoNames:
                    del nationConf[camoName]
            for camoID, camouflage in camouflages.items():
                camoName = camouflage['name']
                if camoName not in nationConf:
                    continue
                camoInShop = not doShopCheck or g_customizationController.dataAggregator._elementIsInShop(
                    camoID, 0, nationID)
                if nationConf[camoName].get('random_mode') == 2 or nationConf[camoName].get(
                        'random_mode') == 1 and camoName not in self.interCamo:
                    del nationConf[camoName]['random_mode']
                kinds = nationConf[camoName].get('kinds')
                if kinds is not None:
                    kindNames = filter(None, kinds.split(','))
                    if len(kindNames) == 1 and kindNames[0] == CAMOUFLAGE_KIND_INDICES[
                            camouflage['kind']] or camoInShop and doShopCheck:
                        del nationConf[camoName]['kinds']
                        if camoInShop:
                            print '%s: in-shop camouflage kind changing is disabled (name: %s)' % (self.ID, camoName)
                for team in ('Ally', 'Enemy'):
                    if nationConf[camoName].get('useFor%s' % team):
                        del nationConf[camoName]['useFor%s' % team]
                if not nationConf[camoName]:
                    del nationConf[camoName]
            if not nationConf:
                del settings[nation]
            else:
                self.camouflages[nation] = nationConf
        newSettings = {}
        if self.disable:
            newSettings['disable'] = self.disable
        for nation in settings:
            newSettings[nation] = settings[nation]
        PYmodsCore.loadJson(self.ID, 'settings', newSettings, self.configPath, True)

    def registerSettings(self):
        super(self.__class__, self).registerSettings()
        # noinspection PyArgumentList
        g_entitiesFactories.addSettings(
            ViewSettings('CamoSelectorUI', CamoSelectorUI, 'CamoSelector.swf', ViewTypes.WINDOW, None,
                         ScopeTemplates.GLOBAL_SCOPE, False))
        kwargs = dict(
            id='CamoSelectorUI', name=self.i18n['UI_flash_header'], description=self.i18n['UI_flash_header_tooltip'],
            icon='gui/flash/CamoSelector.png', enabled=self.data['enabled'], login=False, lobby=True,
            callback=lambda: g_appLoader.getDefLobbyApp().loadView(ViewLoadParams('CamoSelectorUI')))
        try:
            BigWorld.g_modsListApi.addModification(**kwargs)
        except AttributeError:
            BigWorld.g_modsListApi.addMod(**kwargs)
        self.isModAdded = True


# noinspection PyUnboundLocalVariable,PyUnboundLocalVariable
@PYmodsCore.overrideMethod(items.vehicles, '_vehicleValues')
def new_vehicleValues(_, xmlCtx, section, sectionName, defNationID):
    section = section[sectionName]
    if section is None:
        return
    else:
        ctx = (xmlCtx, sectionName)
        for vehName, subsection in section.items():
            if 'all' not in vehName:
                if ':' not in vehName:
                    vehName = ':'.join((nations.NAMES[defNationID], vehName))
                try:
                    nationID, vehID = items.vehicles.g_list.getIDsByName(vehName)
                except Exception:
                    _xml.raiseWrongXml(xmlCtx, sectionName, "unknown vehicle name '%s'" % vehName)

                yield items.vehicles.VehicleValue(vehName, items.makeIntCompactDescrByID('vehicle', nationID, vehID), ctx,
                                                  subsection)
            else:
                for vehNameAll in items.vehicles.g_list._VehicleList__ids.keys():
                    nationID, vehID = items.vehicles.g_list.getIDsByName(vehNameAll)
                    yield items.vehicles.VehicleValue(vehNameAll,
                                                      items.makeIntCompactDescrByID('vehicle', nationID, vehID),
                                                      ctx, subsection)


_config = ConfigInterface()
statistic_mod = PYmodsCore.Analytics(_config.ID, _config.version, 'UA-76792179-7', _config.configFolders)


def lobbyKeyControl(event):
    if event.isKeyDown() and not _config.isMSAWindowOpen:
        if PYmodsCore.checkKeys(_config.data['selectHotkey']):
            installSelectedCamo()


def inj_hkKeyEvent(event):
    LobbyApp = g_appLoader.getDefLobbyApp()
    try:
        if LobbyApp and _config.data['enabled']:
            lobbyKeyControl(event)
    except StandardError:
        print 'CamoSelector: ERROR at inj_hkKeyEvent'
        traceback.print_exc()


InputHandler.g_instance.onKeyDown += inj_hkKeyEvent
InputHandler.g_instance.onKeyUp += inj_hkKeyEvent


@PYmodsCore.overrideMethod(items.vehicles.Cache, 'customization')
def new_customization(base, self, nationID):
    origDescr = base(self, nationID)
    if _config.data['enabled'] and _config.configFolders and nationID not in _config.changedNations:
        _config.changedNations.append(nationID)
        for configDir in _config.configFolders:
            modDescr = items.vehicles._readCustomization(
                '../' + _config.configPath + 'camouflages/' + configDir + '/settings.xml', nationID, (0, 65535))
            if 'custom_camo' in modDescr['camouflageGroups']:
                if 'custom_camo' not in origDescr['camouflageGroups']:
                    origDescr['camouflageGroups']['custom_camo'] = modDescr['camouflageGroups']['custom_camo']
                    origDescr['camouflageGroups']['custom_camo']['ids'][:] = []
                del modDescr['camouflageGroups']['custom_camo']
            newID = max((max(origDescr['camouflages'].iterkeys()) + 1, 5001))
            camouflages = modDescr['camouflages'].values()
            modDescr['camouflages'].clear()
            for camo in camouflages:
                if _config.data['fullAlpha']:
                    colors = []
                    for color in camo['colors'][:3]:
                        rgba = []
                        for idx in xrange(3):
                            rgba.append(color - (color >> 8 << 8))
                            color = color >> 8
                        rgba.append(255)
                        colors.append(rgba[0] + (rgba[1] << 8) + (rgba[2] << 16) + (rgba[3] << 24))
                    colors.append(camo['colors'][3])
                    camo['colors'] = tuple(colors)
                modDescr['camouflages'][newID] = camo
                origDescr['camouflageGroups']['custom_camo']['ids'].append(newID)
                newID += 1
            origDescr = items.vehicles._joinCustomizationParams(nationID, modDescr, origDescr)
        self._Cache__customization[nationID] = origDescr
    return origDescr


@PYmodsCore.overrideMethod(DataAggregator, '_elementIsInShop')
def new_elementIsInShop(base, self, criteria, cType, nationID):
    if cType == CUSTOMIZATION_TYPE.CAMOUFLAGE:
        customization = items.vehicles.g_cache.customization(nationID)
        if customization['camouflages'][criteria]['name'] in _config.camouflages['modded']:
            return False
    return base(self, criteria, cType, nationID)


def readInstalledCamouflages(self):
    if g_currentPreviewVehicle.isPresent():
        vDesc = g_currentPreviewVehicle.item.descriptor
    elif g_currentVehicle.isPresent():
        vDesc = g_currentVehicle.item.descriptor
    else:
        return
    nationName, vehName = vDesc.name.split(':')
    if _config.camouflagesCache.get(nationName, {}).get(vehName) is None:
        return
    for idx in xrange(3):
        self.showGroup(0, idx)
        if _config.camouflagesCache[nationName][vehName].get(CAMOUFLAGE_KIND_INDICES[idx]) is None:
            continue
        camoKindName = CAMOUFLAGE_KIND_INDICES[idx]
        camoName = _config.camouflagesCache[nationName][vehName][camoKindName]
        for itemIdx, item in enumerate(g_customizationController.carousel.items):
            if item['element']._rawData['name'] == camoName:
                self.installCustomizationElement(itemIdx)
                break
        else:
            SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_customOrInvalid'].format(
                kind=_config.i18n['UI_customOrInvalid_%s' % CAMOUFLAGE_KIND_INDICES[idx]], name=camoName),
                                       SystemMessages.SM_TYPE.CustomizationForGold)
    g_customizationController._dataAggregator.start()
    try:
        self.backToSelectorGroup()
    except Exception as e:
        if False:
            print e


def installSelectedCamo():
    if g_currentPreviewVehicle.isPresent():
        vDesc = g_currentPreviewVehicle.item.descriptor
    elif g_currentVehicle.isPresent():
        vDesc = g_currentVehicle.item.descriptor
    else:
        return
    nationName, vehName = vDesc.name.split(':')
    nationID = vDesc.type.customizationNationID
    compDescr = vDesc.type.compactDescr
    assert nations.NAMES[nationID] == nationName, (nationName, nations.NAMES[nationID])
    if g_customizationController.slots.currentSlotsData is None:
        activeCamo = g_tankActiveCamouflage['historical'].get(compDescr)
        if activeCamo is None:
            activeCamo = g_tankActiveCamouflage.get(compDescr, 0)
        customization = items.vehicles.g_cache.customization(nationID)
        if _config.activePreviewCamo is not None:
            camoNames = {camouflage['name']: camoID for camoID, camouflage in customization['camouflages'].items()}
            camoID = camoNames[_config.activePreviewCamo]
            if compDescr in _config.hangarCamoCache:
                del _config.hangarCamoCache[compDescr]
        elif compDescr in _config.hangarCamoCache:
            camoID = _config.hangarCamoCache[compDescr][activeCamo][0]
        else:
            return
        camouflage = customization['camouflages'][camoID]
        camoName = camouflage['name']
        nationConf = _config.camouflages.get(nations.NAMES[nationID])
        interConf = _config.camouflages.get('international', {})
        camoKindNums = (camouflage['kind'],)
        if camoName in _config.camouflages['modded']:
            camoKindNames = filter(None, _config.camouflages['modded'].get(camoName, {}).get('kinds', '').split(','))
            camoKindNums = tuple(CAMOUFLAGE_KINDS[name] for name in camoKindNames)
        elif camoName in interConf:
            kindsStr = interConf.get(camoName, {}).get('kinds')
            if kindsStr is not None:
                camoKindNames = filter(None, kindsStr.split(','))
                camoKindNums = tuple(CAMOUFLAGE_KINDS[name] for name in camoKindNames)
        elif nationConf is not None:
            kindsStr = nationConf.get(camoName, {}).get('kinds')
            if kindsStr is not None:
                camoKindNames = filter(None, kindsStr.split(','))
                camoKindNums = tuple(CAMOUFLAGE_KINDS[name] for name in camoKindNames)
        for camoKindNum in camoKindNums:
            if _config.camouflagesCache.get(nationName, {}).get(vehName, {}).get(
                    CAMOUFLAGE_KIND_INDICES[camoKindNum]) == camoName:
                SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_installCamouflage_already'].format(
                    name=camoName, kind=_config.i18n['UI_setting_hangarCamo_%s' % CAMOUFLAGE_KIND_INDICES[camoKindNum]]),
                                           SystemMessages.SM_TYPE.CustomizationForGold)
                continue
            _config.camouflagesCache.setdefault(nationName, {}).setdefault(vehName, {})[
                CAMOUFLAGE_KIND_INDICES[camoKindNum]] = camoName
            SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_installCamouflage'].format(
                name=camoName, kind=_config.i18n['UI_setting_hangarCamo_%s' % CAMOUFLAGE_KIND_INDICES[camoKindNum]]),
                                       SystemMessages.SM_TYPE.CustomizationForGold)
            PYmodsCore.loadJson(_config.ID, 'camouflagesCache', _config.camouflagesCache, _config.configPath, True)
        return
    camoCache = list(vDesc.camouflages)
    for item in g_customizationController.cart.items:
        if item['type'] != CUSTOMIZATION_TYPE.CAMOUFLAGE:
            continue
        camoKindNum = item['object']._rawData['kind']
        camoName = item['object']._rawData['name']
        _config.camouflagesCache.setdefault(nationName, {}).setdefault(vehName, {})[
            CAMOUFLAGE_KIND_INDICES[camoKindNum]] = camoName
        camoCache[camoKindNum] = (item['object'].getID(), int(time.time()), 7)
    selectedKinds = []
    for camoKind in _config.camouflagesCache.get(nationName, {}).get(vehName, {}):
        selectedKinds.append(CAMOUFLAGE_KINDS[camoKind])
    slotList = heapq.nsmallest(1, selectedKinds, key=lambda x: abs(x - g_customizationController.slots.currentSlotIdx))
    slotIdx = slotList[0] if slotList else 0
    g_tankActiveCamouflage[compDescr] = slotIdx
    vDesc.camouflages = tuple(camoCache)
    _config.hangarCamoCache[compDescr] = tuple(camoCache)
    if vehName in _config.camouflagesCache.get(nationName, {}) and not _config.camouflagesCache[nationName][vehName]:
        del _config.camouflagesCache[nationName][vehName]
    if nationName in _config.camouflagesCache and not _config.camouflagesCache[nationName]:
        del _config.camouflagesCache[nationName]
    PYmodsCore.loadJson(_config.ID, 'camouflagesCache', _config.camouflagesCache, _config.configPath, True)
    PYmodsCore.refreshCurrentVehicle()
    SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_camouflageSelect'],
                               SystemMessages.SM_TYPE.CustomizationForGold)


@PYmodsCore.overrideMethod(MainView, 'removeSlot')
def new_removeSlot(base, self, cType, slotIdx):
    if cType == CUSTOMIZATION_TYPE.CAMOUFLAGE:
        if g_currentPreviewVehicle.isPresent():
            vDesc = g_currentPreviewVehicle.item.descriptor
        else:
            vDesc = g_currentVehicle.item.getCustomizedDescriptor()
        nationName, vehName = vDesc.name.split(':')
        item = [item for item in g_customizationController.cart.items if item['idx'] == slotIdx][0]
        camoKind = CAMOUFLAGE_KIND_INDICES[slotIdx]
        camoName = item['object']._rawData['name']
        if _config.camouflagesCache.get(nationName, {}).get(vehName) is not None:
            vehDict = _config.camouflagesCache[nationName][vehName]
            if vehDict.get(camoKind) is not None and vehDict[camoKind] == camoName:
                del vehDict[camoKind]
            PYmodsCore.loadJson(_config.ID, 'camouflagesCache', _config.camouflagesCache, _config.configPath, True)
    base(self, cType, slotIdx)


@PYmodsCore.overrideMethod(_LobbySubViewsCtrl, '_LobbySubViewsCtrl__onViewLoaded')
def new_onViewLoaded(base, self, view, *_):
    if view is not None and view.settings is not None:
        alias = view.settings.alias
        if alias == VIEW_ALIAS.LOBBY_CUSTOMIZATION and alias in self._LobbySubViewsCtrl__loadingSubViews:
            BigWorld.callback(0.0, g_customizationController.events.onCartFilled)
    base(self, view)


@PYmodsCore.overrideMethod(_LobbySubViewsCtrl, '_LobbySubViewsCtrl__onViewLoadCanceled')
def new_onViewLoadCanceled(base, self, name, item, *_):
    if item is not None and item.pyEntity is not None:
        alias = item.pyEntity.settings.alias
        if alias == VIEW_ALIAS.LOBBY_CUSTOMIZATION and alias in self._LobbySubViewsCtrl__loadingSubViews:
            BigWorld.callback(0.0, g_customizationController.events.onCartFilled)
    base(self, name, item)


@PYmodsCore.overrideMethod(_LobbySubViewsCtrl, '_LobbySubViewsCtrl__onViewLoadError')
def new_onViewLoadError(base, self, name, msg, item, *_):
    if item is not None and item.pyEntity is not None:
        alias = item.pyEntity.settings.alias
        if alias == VIEW_ALIAS.LOBBY_CUSTOMIZATION and alias in self._LobbySubViewsCtrl__loadingSubViews:
            BigWorld.callback(0.0, g_customizationController.events.onCartFilled)
    base(self, name, msg, item)


@PYmodsCore.overrideMethod(MainView, '_populate')
def new_MV_populate(base, self):
    base(self)
    if _config.data['enabled']:
        readInstalledCamouflages(self)


def updateGUIState():
    if _config.UIProxy is None:
        return
    nationID = CamoSelectorUI.getCurrentNation()
    if nationID is not None and _config.backupNationID != nationID:
        _config.UIProxy.changeNation(nationID)


@PYmodsCore.overrideMethod(CurrentVehicle._CurrentVehicle, 'selectVehicle')
def new_selectVehicle(base, self, vehInvID=0):
    base(self, vehInvID)
    updateGUIState()


@PYmodsCore.overrideMethod(CurrentVehicle._CurrentPreviewVehicle, 'selectVehicle')
def new_selectPreviewVehicle(base, self, *args):
    base(self, *args)
    updateGUIState()


@PYmodsCore.overrideMethod(Account, 'onBecomeNonPlayer')
def new_onBecomeNonPlayer(base, self):
    base(self)
    _config.hangarCamoCache.clear()
    _config.currentOverriders = dict.fromkeys(('Ally', 'Enemy'))


@PYmodsCore.overrideMethod(CompoundAppearance, '_CompoundAppearance__getCamouflageParams')
def new_ca_getCamouflageParams(base, self, vDesc, vID):
    result = base(self, vDesc, vID)
    if 'modded' not in _config.camouflages:
        _config.readCamouflages(False)
    if (not _config.data['enabled'] or result[0] is not None and _config.data['useBought'] or vDesc.name in _config.disable
            or vDesc.type.hasCustomDefaultCamouflage and _config.data['disableWithDefault']):
        return result
    nationName, vehName = vDesc.name.split(':')
    isPlayer = vID == BigWorld.player().playerVehicleID
    isAlly = BigWorld.player().guiSessionProvider.getArenaDP().getVehicleInfo(vID).team == BigWorld.player().team
    curTeam = 'Ally' if isAlly else 'Enemy'
    otherTeam = 'Ally' if not isAlly else 'Enemy'
    camoKind = BigWorld.player().arena.arenaType.vehicleCamouflageKind
    camoKindName = CAMOUFLAGE_KIND_INDICES[camoKind]
    nationID = vDesc.type.customizationNationID
    camouflages = items.vehicles.g_cache.customization(nationID)['camouflages']
    camoNames = {camouflage['name']: id for id, camouflage in camouflages.items()}
    if isPlayer and _config.camouflagesCache.get(nationName, {}).get(vehName, {}).get(camoKindName) is not None:
        for camoName in camoNames:
            if camoName == _config.camouflagesCache[nationName][vehName][camoKindName]:
                return camoNames[camoName], int(time.time()), 7
    selectedCamouflages = []
    overriders = []
    for key in ('modded', 'international', nationName):
        for camoName in _config.camouflages.get(key, {}):
            if camoName not in camoNames:
                continue
            camoConfig = _config.camouflages[key][camoName]
            camouflage = camouflages[camoNames[camoName]]
            if camoConfig.get('random_mode', 2) != 1:
                continue
            if camoKindName not in camoConfig.get('kinds', CAMOUFLAGE_KIND_INDICES[camouflage['kind']]):
                continue
            if not camoConfig.get('useFor%s' % curTeam, True):
                continue
            if camouflage['allow'] and vDesc.type.compactDescr not in camouflage['allow'] or \
                    vDesc.type.compactDescr in camouflage['deny']:
                continue
            if vDesc.type.compactDescr in camouflage['tiling']:
                overriders.append(camoName)
            else:
                print 'CamoSelector: a vehicle was not whitelisted and (or) blacklisted, but is missing:', vehName
                print camouflage['tiling']
    if overriders:
        if _config.currentOverriders[curTeam] is None:
            otherOverrider = _config.currentOverriders[otherTeam]
            if len(overriders) > 1 and otherOverrider in overriders:
                overriders.remove(otherOverrider)
            _config.currentOverriders[curTeam] = overriders[vID % len(overriders)]
        selectedCamouflages = [camoNames[_config.currentOverriders[curTeam]]]
    if _config.data['doRandom'] and not selectedCamouflages:
        for camoID, camouflage in camouflages.items():
            camoName = camouflage['name']
            checked = {'modded': False, 'international': False, nationName: False}
            for key in checked:
                if camoName not in _config.camouflages.get(key, {}):
                    continue
                checked[key] = True
                camoConfig = _config.camouflages[key][camoName]
                if camoConfig.get('random_mode', 2) != 2:
                    continue
                if not camoConfig.get('useFor%s' % curTeam, True):
                    continue
                if camouflage['allow'] and vDesc.type.compactDescr not in camouflage['allow'] or \
                        vDesc.type.compactDescr in camouflage['deny']:
                    continue
                if vDesc.type.compactDescr not in camouflage['tiling']:
                    continue
                if camoKindName not in camoConfig.get('kinds', CAMOUFLAGE_KIND_INDICES[camouflage['kind']]):
                    continue
                selectedCamouflages.append(camoID)
            if not any(checked.values()):
                if camouflage['kind'] == CAMOUFLAGE_KINDS[camoKindName]:
                    selectedCamouflages.append(camoID)
    if not selectedCamouflages:
        selectedCamouflages.append(None)
    camouflageId = vID % len(selectedCamouflages)
    return selectedCamouflages[camouflageId], int(time.time()), 7


@PYmodsCore.overrideMethod(ClientHangarSpace, 'recreateVehicle')
def new_cs_recreateVehicle(base, self, vDesc, vState, onVehicleLoadedCallback=None):
    if _config.data['enabled']:
        if 'modded' not in _config.camouflages:
            _config.readCamouflages(True)
        nationID = vDesc.type.customizationNationID
        customization = items.vehicles.g_cache.customization(nationID)
        if _config.activePreviewCamo is not None:
            for camoID, camouflage in customization['camouflages'].items():
                if camouflage['name'] == _config.activePreviewCamo:
                    vDesc.camouflages = tuple((camoID, time.time(), 7) for _ in xrange(3))
                    break
            else:
                SystemMessages.pushMessage('PYmods_SM' + _config.i18n['UI_camouflagePreviewError'] +
                                           _config.activePreviewCamo.join(('<b>', '</b>')),
                                           SystemMessages.SM_TYPE.CustomizationForGold)
                print 'CamoSelector: camouflage not found for nation %s: %s' % (nationID, _config.activePreviewCamo)
                _config.activePreviewCamo = None
        elif vDesc.type.compactDescr in _config.hangarCamoCache:
            vDesc.camouflages = _config.hangarCamoCache[vDesc.type.compactDescr]
        elif vDesc.name not in _config.disable and not (
                vDesc.type.hasCustomDefaultCamouflage and _config.data['disableWithDefault']):
            nationName, vehName = vDesc.name.split(':')
            selectedForVeh = _config.camouflagesCache.get(nationName, {}).get(vehName, {})
            selectedCamo = {}
            camoByKind = {0: [], 1: [], 2: []}
            for camoID, camouflage in customization['camouflages'].items():
                camoName = camouflage['name']
                nationConf = _config.camouflages.get(nationName)
                interConf = _config.camouflages.get('international', {})
                camoKindNames = (CAMOUFLAGE_KIND_INDICES[camouflage['kind']],)
                if camoName in _config.camouflages['modded']:
                    camoKindNames = filter(None,
                                           _config.camouflages['modded'].get(camoName, {}).get('kinds', '').split(','))
                elif camoName in interConf:
                    kindsStr = interConf.get(camoName, {}).get('kinds')
                    if kindsStr is not None:
                        camoKindNames = filter(None, kindsStr.split(','))
                elif nationConf is not None:
                    kindsStr = nationConf.get(camoName, {}).get('kinds')
                    if kindsStr is not None:
                        camoKindNames = filter(None, kindsStr.split(','))
                for camoKindName in camoKindNames:
                    if selectedForVeh.get(camoKindName) is not None:
                        if camouflage['name'] == selectedForVeh[camoKindName]:
                            selectedCamo[CAMOUFLAGE_KINDS[camoKindName]] = camoID
                    camoByKind[CAMOUFLAGE_KINDS[camoKindName]].append(camoID)
            for kind in camoByKind:
                if not camoByKind[kind]:
                    camoByKind[kind].append(None)
            tmpCamouflages = []
            for idx in xrange(3):
                if vDesc.camouflages[idx][0] is not None:
                    tmpCamouflages.append(vDesc.camouflages[idx])
                elif selectedCamo.get(idx) is not None:
                    tmpCamouflages.append((selectedCamo[idx], int(time.time()), 7))
                elif _config.data['doRandom']:
                    tmpCamouflages.append((random.choice(camoByKind[idx]), int(time.time()), 7))
                else:
                    tmpCamouflages.append(vDesc.camouflages[idx])
            vDesc.camouflages = tuple(tmpCamouflages)
            _config.hangarCamoCache[vDesc.type.compactDescr] = tuple(tmpCamouflages)
            if _config.data['hangarCamoKind'] < 3:
                idx = _config.data['hangarCamoKind']
            else:
                idx = random.randrange(3)
            g_tankActiveCamouflage[vDesc.type.compactDescr] = idx
    base(self, vDesc, vState, onVehicleLoadedCallback)

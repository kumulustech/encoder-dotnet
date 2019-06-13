import json

from encoders.base import Encoder as BaseEncoder, RangeSetting as BaseRangeSetting, \
    Setting as BaseSetting, \
    EncoderConfigException, EncoderRuntimeException, \
    SettingConfigException, SettingRuntimeException, q


class IntToStrValueEncoder:

    @staticmethod
    def encode(value):
        return str(int(value))

    @staticmethod
    def decode(data):
        return int(data)


class IntToBoolValueEncoder:

    @staticmethod
    def encode(value):
        return str(bool(value))

    @staticmethod
    def decode(data):
        return int(data)


class DotnetRangeSetting(BaseRangeSetting):
    value_encoder = None

    def __init__(self, config=None):
        self.allowed_options.add('unit')
        super().__init__(config)
        if self.value_encoder is None:
            raise NotImplementedError('You must provide value encoder for setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))

    def format_value(self, value):
        raise NotImplementedError()

    def get_value_encoder(self):
        if callable(self.value_encoder):
            # pylint: disable=not-callable
            return self.value_encoder()
        return self.value_encoder

    def encode_option(self, value):
        """
        Encodes single primitive value into a list of primitive values (zero or more).

        :param value: Single primitive value
        :return list: List of multiple primitive values
        """
        value = self.validate_value(value)
        encoded_value = self.get_value_encoder().encode(value)
        return self.format_value(encoded_value)

    def decode_option(self, data):
        raise NotImplementedError()

class RegistryRangeSetting(DotnetRangeSetting):
    path = None

    def __init__(self, config=None):
        super().__init__(config)
        if self.path is None:
            raise NotImplementedError('You must provide path for registry setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))
        if self.default is None:
            raise NotImplementedError('You must provide the (system\'s) default value for registry settings. Missing in setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))

    def describe(self):
        descr = {
            'type': self.type,
            'min': self.min,
            'max': self.max,
            'step': self.step,
            'unit': self.unit,
            'default': self.default,
            # 'path': self.path, # TODO: add-hoc custom registry settings may be possible by creating a subclass that derives its filter from the config
        }
        return self.name, descr

    def encode_describe(self):
        return '"{path}" = Get-ItemProperty -Path "{path}"'.format(path=self.path)

    def format_value(self, value):
        return 'Set-ItemProperty -Path "{path}" -Name "{name}" -Value {value}\n'.format(path=self.path, name=self.name, value=value)

    def decode_option(self, data):
        """
        Decodes describe data dict back into single primitive value of the current setting.

        :param data: dict of describe data
        :return: Single primitive value
        """
        reg = data.get(self.path, None)
        if not reg:
            raise EncoderRuntimeException("Registry path {} for setting {} was not found in describe data".format(self.path, self.name))

        # NOTE: Until registry options are set, getting the registry path will return no keys but each of the settings does have a system default value
        #    which will be considered to be in effect in cases where the path in data has no keys
        value = reg.get(self.name, self.default)
        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))

class RegistryBooleanSetting(RegistryRangeSetting):
    value_encoder = IntToStrValueEncoder()
    type = 'bool'
    min = 0
    max = 1
    step = 1
    freeze_range = 1

class UriEnableCacheSetting(RegistryBooleanSetting):
    name = 'UriEnableCache'
    path = r'HKLM:\System\CurrentControlSet\Services\Http\Parameters'
    default = 1

class UriScavengerPeriodSetting(RegistryRangeSetting):
    value_encoder = IntToStrValueEncoder()
    name = 'UriScavengerPeriod'
    path = r'HKLM:\System\CurrentControlSet\Services\Http\Parameters'
    unit = 'seconds'
    default = 120
    min = 10
    max = 0xFFFFFFFF
    step = 1
    relaxable = False
    freeze_range = True

class WebConfigRangeSetting(DotnetRangeSetting):
    filter = None
    name_override = None

    def __init__(self, config=None):
        super().__init__(config)
        if self.filter is None:
            raise NotImplementedError('You must provide a filter for web config setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))

    def describe(self):
        descr = {
            'type': self.type,
            'min': self.min,
            'max': self.max,
            'step': self.step,
            'unit': self.unit,
            'default': self.default,
            # 'filter': self.filter, # TODO: add-hoc custom webconfig lists may be possible by creating a subclass that derives its filter from the config
        }
        return self.name, descr


    # NOTE: only runs once per unique setting filter property (per path)
    def encode_describe(self, path):
        return 'Get-WebConfiguration -pspath "{}" -filter "{}"'.format(path, self.filter)

    def format_value(self, path, value):
        return 'Set-WebConfigurationProperty -Filter "{filter}" -PSPath "{path}" -Name "{name}" -Value {value}\n'.format(filter=self.filter, path=path, name=self.name_override or self.name, value=value)

    def encode_option(self, path, value):
        """
        Encodes single primitive value into a list of primitive values (zero or more).

        :param value: Single primitive value
        :return list: List of multiple primitive values
        """
        value = self.validate_value(value)
        encoded_value = self.get_value_encoder().encode(value)
        return self.format_value(path, encoded_value)

    def decode_option(self, data, path):
        """
        Decodes dict of primitive values back into single primitive value.

        :param data: dict of setting values for the given path and filter of the current setting class
        :param path: path string from parent WebConfigSetting config_list
        :return: Single primitive value
        """
        name_locator = self.name_override if self.name_override else self.name
        try:
            value = data[name_locator]
        except KeyError:
            raise EncoderRuntimeException("Unable to located value of setting by name(_override) {}"
                    " within the describe data provided".format( name_locator))
        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))

class WebConfigBooleanSetting(WebConfigRangeSetting):
    value_encoder = IntToBoolValueEncoder()
    type = 'bool'
    min = 0
    max = 1
    step = 1
    freeze_range = 1

class WebConfigCacheEnabledSetting(WebConfigBooleanSetting):
    name = 'WebConfigCacheEnabled'
    name_override = 'enabled' # <- Wouldn't be descriptive enough in the context of a settings file
    filter = 'system.webServer/caching'
    default = 1

class WebConfigEnableKernelCacheSetting(WebConfigBooleanSetting):
    name = 'WebConfigEnableKernelCache'
    name_override = 'enableKernelCache'
    filter = 'system.webServer/caching'
    default = 1

class WebConfigMaxResponseSizeSetting(WebConfigRangeSetting):
    name = 'WebConfigMaxResponseSize'
    name_override = 'maxResponseSize'
    filter = 'system.webServer/caching'
    default = 262144
    unit = 'bytes'

class WebConfigSetting(BaseSetting):
    name = 'WebConfig'
    type = 'config_list'
    allowed_options = { 'path', 'values' } # Encoder has no settings that directly apply for this aggregate setting yet

    
    def describe(self, adjust_config = None, encoder_settings = None):
        if adjust_config:
            if not encoder_settings:
                raise EncoderRuntimeException("If adjust_config is provided, encoder_settings becomes required for nested settings")
            descr = {
                'type': self.type,
            }
            wc_settings_described = {}
            for setting in filter(lambda setting: isinstance(setting, WebConfigRangeSetting), encoder_settings.values()):
                wc_settings_described.update((setting.describe(),))
            if not adjust_config.get("WebConfig") or len(adjust_config.get("WebConfig")) < 1:
                descr['value'] = [
                    {
                        'path': '[WEB_CONFIG_PATH]',
                        'values': wc_settings_described
                    },
                ]
            else:
                descr['value'] = []
                for wc in adjust_config["WebConfig"]["value"]:
                    descr['value'].append({
                        'path': wc['path'],
                        'values': wc_settings_described
                    })

        else:
            return {
                'type': self.type,
                'value': [
                    {
                        'path': '[WEB_CONFIG_PATH]',
                        'values': {
                            '[WebConfig_SETTING_NAME': '[WebConfig_SETTING_VALUE]',
                            '...': '...'
                        }
                    },
                ]
            }

        return self.name, descr

    def encode_describe(self, adjust_driver_config, encoder_settings): # encoder_settings should be filtered so that irrelevant settings are not included
        if not adjust_driver_config.get("WebConfig"):
            return '' # TODO: should this get settings for path 'MACHINE/WEBROOT/APPHOST' by default when no paths are in config?

        webconfig = adjust_driver_config["WebConfig"]
        if len(webconfig['value']) < 1 or len(encoder_settings.keys()) < 1:
            return '' # TODO: should this get settings for path 'MACHINE/WEBROOT/APPHOST' by default when no paths are in config?

        describe_ps_lines = '\t"WebConfig" = @{\n'
        for path_value in webconfig['value']:
            path = path_value['path']
            describe_ps_lines += '\t\t"{}" = @{{\n'.format(path)
            filters_done = set() # encode_describe only needs to run once per unique webconfig filter per path
            for setting in encoder_settings.values():
                if not isinstance(setting, WebConfigRangeSetting):
                    continue # TODO: should this raise an error instead?
                
                if setting.filter in filters_done:
                    continue

                describe_ps_lines += '\t\t\t"{}" = {}\n'.format(setting.filter, setting.encode_describe(path))
                filters_done.add(setting.filter)
            describe_ps_lines += '\t\t}\n'
        describe_ps_lines += '\t}\n'
        
        return describe_ps_lines


    
    def validate_value(self, value, encoder_settings):
        if not isinstance(value, list):
            raise EncoderRuntimeException('Setting {} must have its value be a list or undefined. '
                                         'It is currently {}.'.format(q(self.name), self.config.__class__.__name__))

        unrecognized_values = list(filter(lambda val_item: len(val_item.keys() - self.allowed_options) > 0, value ))
        if len(unrecognized_values) > 0:
            raise EncoderRuntimeException('Cannot recognize option(s) {} for setting {}. '
                                        'Supported setting: {}.'.format(', '.join(map(lambda val: ', '.join(val.keys() - self.allowed_options), unrecognized_values)), q(self.name),
                                                                            ', '.join(self.allowed_options)))

        if(len(value) == 0):
            raise EncoderRuntimeException('No values have been provided for setting WebConfig.')

        for path_values_dict in value:
            values_dict = path_values_dict['values']
            for value_name in values_dict.keys():
                try:
                    setting_instance = encoder_settings[value_name]
                except KeyError:
                    raise EncoderRuntimeException('Setting "{}" is not supported in dotnet encoder webconfig setting.'.format(value_name))
            
                setting_instance.validate_value(values_dict[value_name].get('value'))
        
        return value

    def encode_option(self, value, encoder_settings):
        if value is None:
            return ''
        value = self.validate_value(value, encoder_settings)
        encoded = 'Import-Module WebAdministration\n'
        for path_values_dict in value:
            values_dict = path_values_dict['values']
            for name, val in values_dict.items():
                try:
                    setting = encoder_settings[name]
                except KeyError:
                    raise EncoderRuntimeException('Setting {} was not included in the encoder configuration'.format(name))
                try:
                    encoded += setting.encode_option(path_values_dict['path'], val.get('value', val) if isinstance(val, dict) else val)
                except KeyError:
                    raise EncoderRuntimeException('Setting path is required for all webconfig settings')

        return encoded

    def decode_option(self, data, encoder_settings):
        wc = data.get("WebConfig")
        if not wc:
            return None
        if not isinstance(wc, dict):
            raise EncoderRuntimeException('Describe WebConfig data {} must have its value be a dict or undefined. '
                                         'It is currently {}.'.format(q(self.name), wc.__class__.__name__))
        if len(wc.keys()) < 0:
            return None
        

        decoded_values = []
        for path, pathval in wc.items():
            cur_decode = { 'path': path, 'values': {} }
            for filt, filterval in pathval.items():
                for wc_setting in filter(lambda s: isinstance(s, WebConfigRangeSetting) and s.filter == filt, encoder_settings.values()):
                    cur_decode['values'].update({ wc_setting.name: {
                            'value': wc_setting.decode_option(filterval, path)
                        }})
            decoded_values.append(cur_decode)

        return decoded_values


class Encoder(BaseEncoder):
    # config is value dict of the 'encoder' key
    def __init__(self, config):
        super().__init__(config)
        self.settings = {} # Dict of { setting_name => instantiated_setting_class }

        requested_settings = self.config.get('settings') or {}
        for name, setting in requested_settings.items():
            try:
                setting_class = globals()['{}Setting'.format(name)]
            except KeyError:
                raise EncoderConfigException('Setting "{}" is not supported in dotnet encoder.'.format(name))
            self.settings[name] = setting_class(setting)

    def describe(self, adjust_config = None):
        settings = {}
        if not adjust_config:
            # Return settings in flat format
            for setting in self.settings.values():
                settings.update(setting.describe())
        else:
            # handle flat settings
            for setting in filter(lambda setting: isinstance(setting, RegistryRangeSetting), self.settings.values()):
                settings.update((setting.describe(),))
            # return others in nested format
            for setting in filter(lambda setting: setting.type == 'config_list', self.settings.values()):
                settings.update((setting.describe(adjust_config, self.settings),))
            
        return settings

    def _encode_multi(self, values):
        encoded = ''
        values_to_encode = values.copy()

        encoded += self.config.get('before', '')

        for name, setting in self.settings.items():
            set_val = values_to_encode.pop(name, None)
            if set_val is None:
                continue
            if setting.type == 'config_list': # nested settings need access the the encoder's instantiated settings for validation of sub-settings
                encoded += setting.encode_option(set_val, self.settings)
            else:
                encoded += setting.encode_option(set_val)

        encoded += self.config.get('after', '')

        if values_to_encode:
            raise EncoderRuntimeException('We received settings to encode we do not support: {}'
                                          ''.format(', '.join(values_to_encode.keys())))

        return encoded
    
    def encode_multi(self, values, expected_type=None):
        encoded = self._encode_multi(values)
        expected_type = str if expected_type is None else expected_type
        if expected_type in ('str', str):
            return encoded
        if expected_type in ('list', list):
            return encoded.split('\n')
        raise EncoderConfigException('Unrecognized expected_type passed on encode in dotnet encoder: {}. '
                                     'Supported: "list", "str"'.format(q(expected_type)))

    def _decode_multi(self, data):
        decoded = {}
        for name, setting in filter(lambda kv: not isinstance(kv[1], WebConfigRangeSetting) , self.settings.items()):
            if setting.type == 'config_list':
                decoded[name] = setting.decode_option(data, self.settings)
            else:
                decoded[name] = setting.decode_option(data)
        
        return decoded

    # Operates on the output of powershell describe script generated by encode_describe of this encoder
    def decode_multi(self, data):
        if isinstance(data, str):
            data = json.loads(data)
        return self._decode_multi(data)

    def encode_describe(self, adjust_driver_config):
        reg_paths_done = set()
        describe_ps_script = ''
        if adjust_driver_config.get("WebConfig"):
            describe_ps_script += 'Import-Module WebAdministration\n'
        describe_ps_script += '@{\n'
        for setting in self.settings.values():
            if setting.type == 'config_list':
                describe_ps_script += setting.encode_describe(adjust_driver_config, dict(filter(lambda kv: isinstance(kv[1], WebConfigRangeSetting), self.settings.items())))
            elif isinstance(setting, WebConfigRangeSetting):
                continue # settings of this type are handlesd by the encode_describe of the WebConfigSetting class
            elif isinstance(setting, RegistryRangeSetting): # TODO: change this if there is a new base class for all registry settings
                # Registry settings only need their encode_describe called once per unique registry path
                if(setting.path in reg_paths_done):
                    continue
                    
                describe_ps_script += '\t{}\n'.format(setting.encode_describe())
                reg_paths_done.add(setting.path)

        describe_ps_script += '} | ConvertTo-Json\n'
        return describe_ps_script

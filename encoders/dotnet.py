import json

from encoders.base import Encoder as BaseEncoder, RangeSetting as BaseRangeSetting, \
    Setting as BaseSetting, \
    EncoderConfigException, EncoderRuntimeException, \
    SettingConfigException, SettingRuntimeException, q


# Value encoders
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


# Dotnet base class
class DotnetRangeSetting(BaseRangeSetting):
    value_encoder = None
    system_default = None

    def __init__(self, config=None):
        super().__init__(config)
        if self.value_encoder is None:
            raise NotImplementedError('You must provide value encoder for dotnet setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))
        
        if self.system_default is None: # feel free to remove this in the case of dotnet settings with no system defaults
            raise NotImplementedError('You must provide system_default for dotnet setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))
    
    def describe(self):
        retVal = super().describe()
        retVal[1]['system_default'] = self.system_default
        if self.default:
            retVal[1]['default'] = self.default
        retVal[1].pop('unit')
        if self.unit and self.unit != '':
            retVal[1]['unit'] = self.unit
        return retVal

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
        if isinstance(data, dict):
            return self.decode_option_json(data)
        elif isinstance(data, str):
            return self.decode_option_ps1(data)
        else:
            raise SettingRuntimeException('Unrecognized data type passed on decode_option in dotnet encoder setting: {}. '
                                    'Supported: "dict (loaded json)", "str (powershell script)"'.format(q(data.__class__.__name__)))

    def decode_option_json(self, data):
        raise NotImplementedError()

    def decode_option_ps1(self, data):
        raise NotImplementedError()


# Registry base classes
class RegistryRangeSetting(DotnetRangeSetting):
    path = None

    def __init__(self, config=None):
        super().__init__(config)
        if self.path is None:
            raise NotImplementedError('You must provide path for registry setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))

    def encode_describe(self):
        return '"{path}" = Get-ItemProperty -Path "{path}"'.format(path=self.path)

    def format_value(self, value):
        return 'Set-ItemProperty -Path "{path}" -Name "{name}" -Value {value}\n'.format(path=self.path, name=self.name, value=value)

    def decode_option_json(self, data):
        """
        Decodes describe data dict back into single primitive value of the current setting.

        :param data: dict of describe data
        :return: Single primitive value
        """
        reg = data.get(self.path, None)
        if not reg:
            raise SettingRuntimeException("Registry path {} for setting {} was not found in describe data".format(self.path, self.name))

        # NOTE: Until registry options are set, getting the registry path will return no keys but each of the settings does have a system default value
        #    which will be considered to be in effect in cases where the path in data has no keys
        value = reg.get(self.name, self.system_default)
        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))
    
    def decode_option_ps1(self, data):
        lines = data.split('\n')
        # TODO?: refactor below so that it won't break when parameter order of source is different than expected/not sourced from this encoder
        setting_line = list(filter(lambda l: l.startswith('Set-ItemProperty -Path "{}" -Name "{}" -Value '.format(self.path, self.name)), lines))
        if len(setting_line) > 1:
            raise SettingRuntimeException("Found more than one value for registry setting {} in the provided powershel text:\n{}", q(self.name), data)
        if len(setting_line) < 1:
            value = self.system_default # Even if registry settings are not adjusted, the system default value is in effect
        else:
            value = setting_line[0].split()[-1]

        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))



# TODO: abstract this behaviour into interface equivalent
class RegistryBooleanSetting(RegistryRangeSetting):
    value_encoder = IntToStrValueEncoder()
    min = 0
    max = 1
    step = 1
    relaxable = False


# Webconfig base classes
# TODO: finish impelementing handling of path param to functions for support of hierarchical settings
class WebConfigRangeSetting(DotnetRangeSetting):
    default_path = 'MACHINE/WEBROOT/APPHOST'
    filter = None
    name_override = None

    def __init__(self, config=None):
        super().__init__(config)
        if self.filter is None:
            raise NotImplementedError('You must provide a filter for web config setting {} '
                                      'handled by class {}'.format(q(self.name), self.__class__.__name__))

    # NOTE: only runs once per unique setting filter property (per path)
    def encode_describe(self, path=None):
        if path is None:
            path = self.default_path 
        return 'Get-WebConfiguration -pspath "{}" -filter "{}"'.format(path, self.filter)

    def format_value(self, value, path=None):
        if path is None:
            path = self.default_path 
        return 'Set-WebConfigurationProperty -Filter "{filter}" -PSPath "{path}" -Name "{name}" -Value {value}\n'.format(filter=self.filter, path=path, name=self.name_override or self.name, value=value)

    def encode_option(self, value, path=None):
        """
        Encodes single primitive value into a list of primitive values (zero or more).

        :param value: Single primitive value
        :return list: List of multiple primitive values
        """
        if path is None:
            path = self.default_path 
        value = self.validate_value(value)
        encoded_value = self.get_value_encoder().encode(value)
        return self.format_value(encoded_value, path)

    def decode_option(self, data, path=None):
        if isinstance(data, dict):
            return self.decode_option_json(data, path)
        elif isinstance(data, str):
            return self.decode_option_ps1(data, path)
        else:
            raise SettingRuntimeException('Unrecognized data type passed on decode_option in dotnet encoder setting: {}. '
                                    'Supported: "dict (loaded json)", "str (powershell script)"'.format(q(data.__class__.__name__)))

    def decode_option_json(self, data, path=None):
        """
        Decodes dict of primitive values back into single primitive value.

        :param data: dict of setting values for the given path and filter of the current setting class
        :param path: path string from parent WebConfigSetting config_list
        :return: Single primitive value
        """
        if path is None:
            path = self.default_path 

        wc = data.get("WebConfig")
        if not wc:
            return None
        if not isinstance(wc, dict):
            raise SettingRuntimeException('Describe WebConfig data {} must have its value be a dict or undefined. '
                                         'It is currently {}.'.format(q(self.name), wc.__class__.__name__))
        if len(wc.keys()) < 0:
            return None

        name_locator = self.name_override if self.name_override else self.name
        try:
            value = wc[path][self.filter][name_locator]
        except KeyError:
            raise SettingRuntimeException("Unable to located value of setting in path '{}' under filter '{}' by name(_override) '{}'"
                    " within the describe data provided".format( path, self.filter, name_locator))
        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))

    def decode_option_ps1(self, data, path=None):
        lines = data.split('\n')
        # TODO?: refactor below so that it won't break when parameter order of source is different than expected/not sourced from this encoder
        setting_line = list(filter(
            lambda l: l.startswith('Set-WebConfigurationProperty -Filter "{}" -PSPath "{}" -Name "{}" -Value '.format(
                self.filter, 
                path if path else self.default_path, 
                self.name_override if self.name_override else self.name)), 
            lines))
        if len(setting_line) > 1:
            raise SettingRuntimeException("Found more than one value for registry setting {} in the provided powershel text:\n{}", q(self.name), data)
        if len(setting_line) < 1:
            value = self.system_default # If web config settings are not adjusted, the system default value is in effect so long as the site exists
        else:
            value = setting_line[0].split()[-1]

        try:
            return self.get_value_encoder().decode(value)
        except ValueError as e:
            raise SettingRuntimeException('Invalid value to decode for setting {}. '
                                            'Error: {}. Arg: {}'.format(q(self.name), str(e), value))

class WebConfigBooleanSetting(WebConfigRangeSetting):
    value_encoder = IntToBoolValueEncoder()
    min = 0
    max = 1
    step = 1
    relaxable = False


# Derived Settings classes
## Registry
class UriEnableCacheSetting(RegistryBooleanSetting):
    name = 'UriEnableCache'
    path = r'HKLM:\System\CurrentControlSet\Services\Http\Parameters'
    system_default = 1

class UriScavengerPeriodSetting(RegistryRangeSetting):
    value_encoder = IntToStrValueEncoder()
    name = 'UriScavengerPeriod'
    path = r'HKLM:\System\CurrentControlSet\Services\Http\Parameters'
    unit = 'seconds'
    system_default = 120
    min = 10
    max = 0xFFFFFFFF
    step = 1
    relaxable = False

## Web Configuration (IIS)
class WebConfigCacheEnabledSetting(WebConfigBooleanSetting):
    name = 'WebConfigCacheEnabled'
    name_override = 'enabled' # <- Wouldn't be descriptive enough in the context of a settings file
    filter = 'system.webServer/caching'
    system_default = 1

class WebConfigEnableKernelCacheSetting(WebConfigBooleanSetting):
    name = 'WebConfigEnableKernelCache'
    name_override = 'enableKernelCache'
    filter = 'system.webServer/caching'
    system_default = 1

# TODO if needed
# class WebConfigMaxResponseSizeSetting(WebConfigRangeSetting):
#     name = 'WebConfigMaxResponseSize'
#     name_override = 'maxResponseSize'
#     filter = 'system.webServer/caching'
#     default = 262144
#     unit = 'bytes'


# Encoder Class
class Encoder(BaseEncoder):
    # config is value dict of the 'encoder' key
    def __init__(self, config):
        super().__init__(config)
        self.settings = {} # Dict of { setting_name => instantiated_setting_class }

        requested_settings = self.config.get('settings', {})
        for name, enc_set_config in requested_settings.items():
            try:
                setting_class = globals()['{}Setting'.format(name)]
            except KeyError:
                raise EncoderConfigException('Setting "{}" is not supported in dotnet encoder.'.format(name))
            self.settings[name] = setting_class(enc_set_config)

    # TODO: implement hierarchical settings; this function will need optional path arguments
    def describe(self):
        settings = {}
        for setting in self.settings.values():
            settings.update((setting.describe(),))
        return settings

    def _encode_multi(self, values):
        encoded = ''
        values_to_encode = values.copy()

        encoded += self.config.get('before', '')

        webConfSettings = dict(filter(lambda s: isinstance(s[1], WebConfigRangeSetting), self.settings.items()))
        webAdmImported = False
        for name, setting in webConfSettings.items():
            # TODO: implement hierarchical settings; check for delimeter here to split path from webconfig setting name, pass into encode_option below
            set_val = values_to_encode.pop(name, None)
            if set_val is None:
                continue
            if not webAdmImported:
                encoded += 'Import-Module WebAdministration\n'
                webAdmImported = True

            #if [setting name contained delimeter]
                # [split name into (path, name)]
                # encoded += setting.encode_option(set_val, path)
            # else:
            encoded += setting.encode_option(set_val)

        otherSettings = dict(filter(lambda s: not webConfSettings.get(s[0]), self.settings.items()))
        for name, setting in otherSettings.items():
            # TODO: implement hierarchical settings; check for delimeter here to split path from webconfig setting name, pass into encode_option below
            set_val = values_to_encode.pop(name, None)
            if set_val is None:
                continue
            #if [setting name contained delimeter]
                # [split name into (path, name)]
                # encoded += setting.encode_option(set_val, path)
            # else:
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
        for name, setting in self.settings.items():
            # TODO: change decode_option to return tuple to support heierarchical config
            decoded[name] = setting.decode_option(data)
        
        return decoded

    # Operates on the output of powershell describe script generated by encode_describe of this encoder
    def decode_multi(self, data):
        # TODO test if data is json or ps1 script
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                pass    # Assuming data is a string representing a PS1 script
        else:
            # TODO?: add support for list of ps1 lines
            if not isinstance(data, dict):
                raise EncoderRuntimeException('Unrecognized data type passed on decode in dotnet encoder: {}. '
                                        'Supported: "dict", "str"'.format(q(data.__class__.__name__)))

        return self._decode_multi(data)

    # TODO: hierarchical support; add paths param 
    def encode_describe(self):
        reg_paths_done = set()
        describe_ps_script = 'Import-Module WebAdministration\n'
        
        describe_ps_script += '@{\n'
        describe_ps_script += '\t"WebConfig" = @{\n'
        # TODO: iterate paths if multiple and assign path here
        path = 'MACHINE/WEBROOT/APPHOST'
        describe_ps_script += '\t\t"{}" = @{{\n'.format(path)
        filters_done = set() # encode_describe only needs to run once per unique webconfig filter per path
        for setting in filter(lambda s: isinstance(s, WebConfigRangeSetting), self.settings.values()):
                
            if setting.filter in filters_done:
                continue

            describe_ps_script += '\t\t\t"{}" = {}\n'.format(setting.filter, setting.encode_describe(path))
            filters_done.add(setting.filter)
        # close path object brace
        describe_ps_script += '\t\t}\n'
        # close WebConfig object brace
        describe_ps_script += '\t}\n'

        
        for setting in filter(lambda s: isinstance(s, RegistryRangeSetting), self.settings.values()):
            # Registry settings only need their encode_describe called once per unique registry path
            if(setting.path in reg_paths_done):
                continue
                
            describe_ps_script += '\t{}\n'.format(setting.encode_describe())
            reg_paths_done.add(setting.path)

        describe_ps_script += '} | ConvertTo-Json\n'
        return describe_ps_script


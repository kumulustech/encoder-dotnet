# Base exception
import importlib
from abc import ABC

EncoderException = type('EncoderException', (BaseException,), {})

# User-related exceptions
EncoderConfigException = type('EncoderConfigException', (EncoderException,), {})
EncoderRuntimeException = type('EncoderRuntimeException', (EncoderException,), {})
SettingConfigException = type('SettingConfigException', (EncoderException,), {})
SettingRuntimeException = type('SettingRuntimeException', (EncoderException,), {})


def q(v):
    return '"{}"'.format(v)


class Setting(ABC):
    name = None
    type = None
    allowed_options = {'default'}

    def __init__(self, config=None):
        if not config:
            config = {}
        self.config = config
        self.check_class_defaults()
        self.check_config()

    def check_class_defaults(self):
        if self.name is None:
            raise NotImplementedError(
                'Setting with its handler class name {} must have '
                'attribute `name` defined.'.format(self.__class__.__name__))
        if self.type is None:
            raise NotImplementedError(
                'Setting with its handler class name {} must have '
                'attribute `type` defined.'.format(self.__class__.__name__))

    def check_config(self):
        if not isinstance(self.config, dict):
            raise SettingConfigException('Setting {} must have its configuration to be a dictionary or undefined. '
                                         'It is currently {}.'.format(q(self.name), self.config.__class__.__name__))
        for option in self.config.keys():
            if option not in self.allowed_options:
                raise SettingConfigException('Cannot recognize option {} for setting {}. '
                                             'Supported setting: {}.'.format(q(option), q(self.name),
                                                                             ', '.join(self.allowed_options)))

    # describe setting as defined in encoder config
    def describe(self):
        raise NotImplementedError()

    # produce a string to be executed to describe the setting's value
    def encode_describe(self):
        raise NotImplementedError()

    def encode_option(self, values):
        raise NotImplementedError()

    def decode_option(self, data):
        raise NotImplementedError()


class RangeSetting(Setting, ABC):
    relaxable = True
    freeze_range = False
    type = 'range'
    unit = ''

    def __init__(self, config=None):
        self.allowed_options.update({'min', 'max', 'step'})
        super().__init__(config)
        self.min = self.config.get('min', getattr(self, 'min', None))
        self.max = self.config.get('max', getattr(self, 'max', None))
        self.step = self.config.get('step', getattr(self, 'step', None))
        self.default = self.config.get('default', getattr(self, 'default', None))

    def check_config(self):
        super().check_config()
        default_min = getattr(self, 'min', None)
        default_max = getattr(self, 'max', None)
        default_step = getattr(self, 'step', None)
        minv = self.config.get('min', default_min)
        maxv = self.config.get('max', default_max)
        step = self.config.get('step', default_step)
        if minv is None:
            raise SettingConfigException(
                'No min value configured for setting {} in jvm encoder.'.format(q(self.name)))
        if maxv is None:
            raise SettingConfigException(
                'No max value configured for setting {} in jvm encoder.'.format(q(self.name)))
        if step is None:
            raise SettingConfigException(
                'No step value configured for setting {} in jvm encoder.'.format(q(self.name)))
        if not isinstance(minv, (int, float)):
            raise SettingConfigException('Min value must be a number in setting {} of jvm encoder. '
                                         'Found {}.'.format(q(self.name), q(minv)))
        if not isinstance(maxv, (int, float)):
            raise SettingConfigException('Max value must be a number in setting {} of jvm encoder. '
                                         'Found {}.'.format(q(self.name), q(maxv)))
        if not isinstance(step, (int, float)):
            raise SettingConfigException('Step value must be a number in setting {} of jvm encoder. '
                                         'Found {}.'.format(q(self.name), q(step)))
        if minv > maxv:
            raise SettingConfigException('Lower boundary is higher than upper boundary in setting {} '
                                         'of jvm encoder.'.format(q(self.name)))
        if minv != maxv:
            if step < 0:
                raise SettingConfigException('Step for setting {} must be a positive number.'
                                             ''.format(q(self.name)))
            if step == 0:
                raise SettingConfigException(
                    'Step for setting {} cannot be zero when min != max.'.format(q(self.name)))
        if step != 0 and (maxv - minv) % step > 0:
            raise SettingConfigException(
                'Step value for setting {} must allow to get from {} to {} in equal steps. Its current value is {}. '
                'The size of the last step would be {}.'.format(q(self.name), minv, maxv, step, (maxv - minv) % step))
        # Freeze range for change from config
        if self.freeze_range:
            if default_min is None:
                raise NotImplementedError('Min value for setting {} must be configured to allow '
                                          'freeze of the range.'.format(q(self.name)))
            if default_max is None:
                raise NotImplementedError('Max value for setting {} must be configured to allow '
                                          'freeze of the range.'.format(q(self.name)))
            if default_step is None:
                raise NotImplementedError('Max value for setting {} must be configured to allow '
                                          'freeze of the range.'.format(q(self.name)))
            c = self.config
            if c.get('min') or c.get('max') or c.get('step'):
                raise SettingConfigException('Cannot change min, max or step in setting {}.'.format(q(self.name)))
        # Relaxation of boundaries
        if self.relaxable is False:
            if default_min is None:
                raise NotImplementedError('Default min value for setting {} must be configured '
                                          'to disallow its relaxation.'.format(q(self.name)))
            elif minv < default_min:
                raise SettingConfigException('Min value for setting {} cannot be lower than {}. '
                                             'It is {} now.'.format(q(self.name),
                                                                    default_min, minv))
            if default_max is None:
                raise NotImplementedError('Default max value for setting {} must be configured '
                                          'to disallow its relaxation.'.format(q(self.name)))
            elif maxv > default_max:
                raise SettingConfigException('Max value for setting {} cannot be lower than {}. '
                                             'It is {} now.'.format(q(self.name), default_max, maxv))
            if default_step is None:
                raise NotImplementedError('Default step value for setting {} must be configured '
                                          'to disallow its change.'.format(q(self.name)))
            elif step % default_step > 0:
                raise SettingConfigException('Step value for setting {} must be multiple of provided default {}. '
                                             'It is {} now.'.format(q(self.name), default_step, step))

    def describe(self):
        descr = {
            'type': self.type,
            'min': self.min,
            'max': self.max,
            'step': self.step,
            'unit': self.unit,
        }
        return self.name, descr

    def validate_value(self, value):
        if value is None:
            raise SettingRuntimeException('No value provided for setting {}'.format(self.name))
        if not isinstance(value, (float, int)):
            raise SettingRuntimeException('Value in setting {} must be either integer or float. '
                                          'Found {}.'.format(q(self.name), q(value)))
        if value < self.min:
            raise SettingRuntimeException('Value {} is violating lower bound '
                                          'in setting {}'.format(q(value), q(self.name)))
        if value > self.max:
            raise SettingRuntimeException('Value {} is violating upper bound '
                                          'in setting {}'.format(q(value), q(self.name)))
        if self.min < self.max and self.step > 0 and (value - self.min) % self.step != 0:
            raise SettingRuntimeException('Value {} is violating step requirement '
                                          'in setting {}. Step is size {}'.format(q(value), q(self.name),
                                                                                  self.step))
        return value


class Encoder(ABC):

    def __init__(self, config):
        self.config = config

    def describe(self):
        """
        Returns available settings and their respective limits based on provided configuration at the initialization stage.

        Only to be implemented for multi-value encoders.

        Example:
            {
                "GCTimeRatio": {
                    "min": 1,
                    "max": 99.999,
                    "unit": "ratio",
                },
                "InitialHeapSize": {
                    "min": 128,
                    "max": 6144,
                    "unit": "megabytes",
                },
                "MaximumHeapSize": {
                    "min": 6144,
                    "max": 12288,
                    "unit": "megabytes",
                }
            }


        :return: Dictionary of available setting names as keys and their respective limits as values as a dictionary.
        """
        raise NotImplementedError()

    def encode_multi(self, values, expected_type=None):
        """
        Converts a dictionary of setting names and their respective values, where values are dictionaries containing
        at least one key - "value".

        Only to be implemented for multi-value encoders.

        Example:
            encode({"GCTimeRatio": {"value": 35},
                    "InitialHeapSize": {"value": 512},
                    "MaximumHeapSize": {"value": 2048}}) will produce "-XX:GCTimeRatio=35 -Xms512mb -Xmx2g"


        :param values: Dictionary of setting names and their respective values.
        :param expected_type: Any value for encoder to make a decision on what to return.
        :return: Primitive output data.
        """
        raise NotImplementedError()

    def decode_multi(self, data):
        """
        Converts a single primitive data type into a dictionary of setting names and their respective values.

        Only to be implemented for multi-value encoders.

        Example:
            decode("-XX:GCTimeRatio=35 -Xms512mb -Xmx2g")
            will produce {"GCTimeRatio": 35, "InitialHeapSize": 512, "MaximumHeapSize": 2048}


        :param data: Encoded primitive type data to transform back to its decoded dictionary format.
        :return: Dictionary of settings and their respective values.
        """
        raise NotImplementedError()

    def encode_describe(self, adjust_driver_config):
        """
        Utilizes dynamically derived setting parameters from the adjust driver configuration in addition to static setting parameters from
        the encoder config to derive the requisite command(s) to describe the current values of said settings

        Example:
            encode_describe(json.loads("{"WebConfig":{"value":{"path":"MACHINE/WEBROOT/APPHOST","values":{"WebConfigCacheEnabled":{"value": 1},"WebConfigEnableKernelCache":{"value": 1}}}}}"))
            will produce the string:
            
            "$output = @{
                "WebConfig" = @{
                    "MACHINE/WEBROOT/APPHOST" = @{
                        "system.webServer/caching" = Get-WebConfiguration -pspath "MACHINE/WEBROOT/APPHOST" -filter "system.webServer/caching"
                    }
                }
            } | ConvertTo-Json"

            values:
              WebConfigCacheEnabled: 
                value: 1
              WebConfigEnableKernelCache: 
                value: 1


        :param adjust_driver_config: Configuration section of the adjust driver, needed in some cases for settings to encode a describe command
        :return: String of executable script/code used by adjust driver describe to get the current setting values
        """
        raise NotImplementedError()


# TODO: delete me
# def load_setting(encoder, setting):
#     if isinstance(encoder, str) and isinstance(setting, str):
#         try:
#             return importlib.getattr(importlib.import_module('encoders.{}'.format(encoder)), setting)
#         except ImportError:
#             raise ImportError('Unable to import encoder {}'.format(q(encoder)))
#         except AttributeError:
#             raise AttributeError('Were not able to import encoder\'s class from encoders.{}'.format(encoder))
#     else:
#         raise NotImplementedError('load_setting only works with str params')

def load_encoder(encoder):
    if isinstance(encoder, str):
        try:
            return importlib.import_module('encoders.{}'.format(encoder)).Encoder
        except ImportError:
            raise ImportError('Unable to import encoder {}'.format(q(encoder)))
        except AttributeError:
            raise AttributeError('Were not able to import encoder\'s class from encoders.{}'.format(encoder))
    return encoder


def validate_config(config):
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise EncoderConfigException('Configuration object for jvm encoder is expected to be a dictionary')
    if not config.get('name'):
        raise EncoderConfigException('No encoder name specified')
    return config


def encode(config, values, expected_type=None, adjust_config=None):
    """
    Helper function. Encodes a dictionary of setting names and their respective values (in the form of a
    dictionary with at least one key - "value") using encoder provided in the folder "encoders/" and located using
    the value of the key "name" from the config argument.

    Workflow:
      1. Takes encoder section dictionary from config and a dictionary of input data to encode.
      2. Calls an encoder by its name from "encoders/" folder passing it requested input data.
      3. Returns the output into the place of interest.

    Config example (yaml):
        a: 1
        b: 2
        c:
            d: False
        settings:
            x:
                min: 1
                max: 5
                step: 1
                default: 2
            y:
                min: 1
                step: 2

    :param config: encoder section dictionary of configuration and requested settings
    :param values: Dictionary with values to encode ({"setting": {"value": 1}})
    :param expected_type: Any value telling the encoder in what format to return the encoded values.
    :return: Encoded values of expected type, and a set of encoded setting names
    """
    config = validate_config(config)
    encoder_klass = load_encoder(config['name'])
    encoder = encoder_klass(config)
    if adjust_config:
        settings = encoder.describe(adjust_config)
    else:
        settings = encoder.describe()
    encodable = {name: values.get(name, {}).get('value') for name in settings.keys()}
    config_expected_type = config.get('expected_type')
    if expected_type and config_expected_type:
        raise EncoderConfigException('Cannot set `expected_type` both in the config and in the driver.\n'
                                     'Got from the config: {}.\nGot from the driver: {}.'
                                     ''.format(q(config_expected_type), q(expected_type)))
    return encoder.encode_multi(encodable, expected_type=expected_type or config_expected_type), set(encodable)


# def describe(config, data):
def describe(config, data, adjust_config=None):
    """
    Helper function. Given configuration dictionary with a list of requested settings returns their respective limits
    and current values provided in argument "data".

    :param config: See function `encode` for details.
    :param data: See method `describe` of class Encoder for details
    :return: Available settings with their respective limits and current values.
    """
    config = validate_config(config)
    encoder_klass = load_encoder(config['name'])
    encoder = encoder_klass(config)
    if adjust_config:
        settings = encoder.describe(adjust_config)
    else:
        settings = encoder.describe()
    decoded = encoder.decode_multi(data)
    descriptor = {name: {**setting, 'value': decoded[name]} for name, setting in settings.items()}
    return descriptor

# TODO: define encode_describe(encoder_config, adjust_config)
def encode_describe(encoder_config, adjust_config):
    """
    Helper function. Given configuration dictionary of encoder configuration, and dictionary of adjust configuration returns
    the command(s) needed to describe the current values of settings

    :param encoder_config: encoder configuration section
    :param adjust_config: adjust driver configuration section
    :return: String of powershell commands to be executed to retrieve the current state of settings for the purpose of describe()
    """
    encoder_config = validate_config(encoder_config)
    encoder_klass = load_encoder(encoder_config['name'])
    encoder = encoder_klass(encoder_config)
    return encoder.encode_describe(adjust_config)
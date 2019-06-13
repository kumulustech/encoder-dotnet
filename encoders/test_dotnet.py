import pytest

import os
import importlib
import yaml

import encoders.base as enc
from encoders.base import q, EncoderConfigException, \
    SettingConfigException, \
    SettingRuntimeException

config_path = os.environ.get('OPTUNE_CONFIG', './config.yaml')

def load_config():
    try:
        config = yaml.load(open(config_path))
    except yaml.YAMLError as e:
        raise EncoderConfigException('Could not parse config file located at "{}". '
                        'Please check its contents. Error: {}'.format(config_path, str(e)))
    return validate_config(config)

def validate_config(config):
    try:
        enc_config = config['ws2012']['iis8']['encoder']
    except KeyError:
        raise EncoderConfigException("Unable to locate encoder config subsection in config file {}".format(config_path))
    try:
        set_config = config['ws2012']['iis8']['settings']
    except KeyError:
        raise EncoderConfigException("Unable to locate settings config subsection in config file {}".format(config_path))


    if not isinstance(enc_config, dict):
        raise EncoderConfigException('Configuration object for dotnet encoder not found')
    if not enc_config.get('name'):
        raise EncoderConfigException('No encoder name specified')
    
    return enc_config, set_config

def load_encoder(encoder):
    if isinstance(encoder, str):
        try:
            return importlib.import_module('encoders.{}'.format(encoder)).Encoder
        except ImportError:
            raise ImportError('Unable to import encoder {}'.format(q(encoder)))
        except AttributeError:
            raise AttributeError('Were not able to import encoder\'s class from encoders.{}'.format(encoder))
    return encoder

def write_test_output_file(fname, data):
    fext = '.yaml' if isinstance(data, dict) or isinstance(data, tuple) else '.txt'
    f = open('output_{}{}'.format(fname, fext), 'w')
    if fext == '.yaml':
        # http://signal0.com/2013/02/06/disabling_aliases_in_pyyaml.html
        noalias_dumper = yaml.dumper.SafeDumper
        noalias_dumper.ignore_aliases = lambda self, data: True
        yaml.dump(data, f, Dumper=noalias_dumper, default_flow_style=False)
    else:
        f.write(data)

    f.close()

describe_data = """\
{
    "WebConfig":  {
                      "MACHINE/WEBROOT/APPHOST":          {
                                                               "system.webServer/caching":  {
                                                                                                "value":  "Microsoft.IIs.PowerShell.Framework.ConfigurationSection",
                                                                                                "enabled":  true,
                                                                                                "enableKernelCache":  true,
                                                                                                "maxCacheSize":  0,
                                                                                                "maxResponseSize":  262144,
                                                                                                "profiles":  {
                                                                                                                 "value":  "Microsoft.IIs.PowerShell.Framework.ConfigurationElement",
                                                                                                                 "Collection":  ""
                                                                                                             },
                                                                                                "PSPath":  "MACHINE/WEBROOT/APPHOST/TestSite",
                                                                                                "Location":  "",
                                                                                                "ConfigurationPathType":  10,
                                                                                                "ItemXPath":  "/system.webServer/caching"
                                                                                            }
                                                           },
                      "MACHINE/WEBROOT/APPHOST/TestSite":  {
                                                               "system.webServer/caching":  {
                                                                                                "value":  "Microsoft.IIs.PowerShell.Framework.ConfigurationSection",
                                                                                                "enabled":  false,
                                                                                                "enableKernelCache":  false,
                                                                                                "maxCacheSize":  0,
                                                                                                "maxResponseSize":  262144,
                                                                                                "profiles":  {
                                                                                                                 "value":  "Microsoft.IIs.PowerShell.Framework.ConfigurationElement",
                                                                                                                 "Collection":  ""
                                                                                                             },
                                                                                                "PSPath":  "MACHINE/WEBROOT/APPHOST/TestSite",
                                                                                                "Location":  "",
                                                                                                "ConfigurationPathType":  10,
                                                                                                "ItemXPath":  "/system.webServer/caching"
                                                                                            }
                                                           }
                  },
    "HKLM:\\\\System\\\\CurrentControlSet\\\\Services\\\\Http\\\\Parameters":  {
                                                                         "UriEnableCache":  1,
                                                                         "PSPath":  "Microsoft.PowerShell.Core\\\\Registry::HKEY_LOCAL_MACHINE\\\\System\\\\CurrentControlSet\\\\Services\\\\Http\\\\Parameters",
                                                                         "PSParentPath":  "Microsoft.PowerShell.Core\\\\Registry::HKEY_LOCAL_MACHINE\\\\System\\\\CurrentControlSet\\\\Services\\\\Http",
                                                                         "PSChildName":  "Parameters",
                                                                         "PSDrive":  {
                                                                                         "CurrentLocation":  "",
                                                                                         "Name":  "HKLM",
                                                                                         "Provider":  "Microsoft.PowerShell.Core\\\\Registry",
                                                                                         "Root":  "HKEY_LOCAL_MACHINE",
                                                                                         "Description":  "The configuration settings for the local computer",
                                                                                         "Credential":  "System.Management.Automation.PSCredential",
                                                                                         "DisplayRoot":  null
                                                                                     },
                                                                         "PSProvider":  {
                                                                                            "ImplementingType":  "Microsoft.PowerShell.Commands.RegistryProvider",
                                                                                            "HelpFile":  "System.Management.Automation.dll-Help.xml",
                                                                                            "Name":  "Registry",
                                                                                            "PSSnapIn":  "Microsoft.PowerShell.Core",
                                                                                            "ModuleName":  "Microsoft.PowerShell.Core",
                                                                                            "Module":  null,
                                                                                            "Description":  "",
                                                                                            "Capabilities":  80,
                                                                                            "Home":  "",
                                                                                            "Drives":  "HKLM HKCU"
                                                                                        }
                                                                     }
}"""


def test_describe():
    enc_config, set_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    settings = encoder.describe(set_config)
    write_test_output_file('test_describe', settings)
    # TODO: implement test
    assert True

def test_encode_multi():
    enc_config, set_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    settings = encoder.describe(set_config)
    encodable = {name: set_config.get(name, {}).get('value') for name in settings.keys()}
    config_expected_type = enc_config.get('expected_type')
    encoded = encoder.encode_multi(encodable, expected_type=config_expected_type)
    write_test_output_file('test_encode_multi', encoded)
    # TODO: implement test
    assert True


def test_decode_multi():
    enc_config, _ = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    decoded = encoder.decode_multi(describe_data)
    write_test_output_file('test_decode_multi', decoded)
    # TODO: implement test
    assert True


def test_encode_describe():
    enc_config, set_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    describe = encoder.encode_describe(set_config)
    write_test_output_file('test_encode_describe', describe)
    # TODO: implement test
    assert True

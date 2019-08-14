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
        enc_config = config['ec2win']['web']['encoder']
    except KeyError:
        raise EncoderConfigException("Unable to locate encoder config subsection in config file {}".format(config_path))


    if not isinstance(enc_config, dict):
        raise EncoderConfigException('Configuration object for dotnet encoder not found')
    if not enc_config.get('name'):
        raise EncoderConfigException('No encoder name specified')
    
    return enc_config

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

describe_data_json = """\
{
    "WebConfig":  {
                      "MACHINE/WEBROOT/APPHOST":          {
                                                               "system.webServer/caching":  {
                                                                                                "value":  "Microsoft.IIs.PowerShell.Framework.ConfigurationSection",
                                                                                                "enabled":  false,
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

describe_data_ps1 = r"""\
Import-Module WebAdministration
Set-WebConfigurationProperty -Filter "system.webServer/caching" -PSPath "False" -Name "enabled" -Value MACHINE/WEBROOT/APPHOST
Set-WebConfigurationProperty -Filter "system.webServer/caching" -PSPath "True" -Name "enableKernelCache" -Value MACHINE/WEBROOT/APPHOST
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Services\Http\Parameters" -Name "UriEnableCache" -Value 1
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Services\Http\Parameters" -Name "UriScavengerPeriod" -Value 240
"""

encode_data = {
    "application": {
        "components": {
            "web": {
                "settings": {
                    "UriEnableCache": {"value": 1},
                    "UriScavengerPeriod": {"value": 240},
                    "WebConfigCacheEnabled": {"value": 0},
                    "WebConfigEnableKernelCache": {"value": 1},
                    "inst_type": {"value": "t2.micro"},
                }
            }
        }
    }
}

def test_describe():
    enc_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    settings = encoder.describe()
    write_test_output_file('test_describe', settings)
    # TODO: implement test
    assert True

def test_encode_multi():
    enc_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    settings = encoder.describe()
    encodable = {name: encode_data['application']['components']['web']['settings'].get(name, {}).get('value') for name in settings.keys()}
    config_expected_type = enc_config.get('expected_type')
    encoded = encoder.encode_multi(encodable, expected_type=config_expected_type)
    write_test_output_file('test_encode_multi', encoded)
    # TODO: implement test
    assert True


def test_decode_multi_json():
    enc_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    decoded = encoder.decode_multi(describe_data_json)
    write_test_output_file('test_decode_multi_json', decoded)
    # TODO: implement test
    assert True

def test_decode_multi_ps1():
    enc_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    decoded = encoder.decode_multi(describe_data_ps1)
    write_test_output_file('test_decode_multi_ps1', decoded)
    # TODO: implement test
    assert True

def test_encode_describe():
    enc_config = load_config()
    encoder_klass = load_encoder(enc_config['name'])
    encoder = encoder_klass(enc_config)
    describe = encoder.encode_describe()
    write_test_output_file('test_encode_describe', describe)
    # TODO: implement test
    assert True

def test_static_describe_json():
    enc_config = load_config()
    described = enc.describe(enc_config, describe_data_json)
    write_test_output_file('test_static_describe_json', described)
    assert True

def test_static_describe_ps1():
    enc_config = load_config()
    described = enc.describe(enc_config, describe_data_ps1)
    write_test_output_file('test_static_describe_ps1', described)
    assert True

def test_static_encode():
    enc_config = load_config()
    encoded = enc.encode(enc_config, encode_data['application']['components']['web']['settings'])
    write_test_output_file('test_static_encode', encoded[0])
    assert True

"""Gateway config must expand secret templates before adapters receive routes."""
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_gateway_loader_expands_webhook_route_secret_template():
    from gateway.config import Platform, load_gateway_config

    fake_home = Path('/tmp/fake_hermes_webhook_env_expansion')

    def fake_exists(self):
        return str(self).endswith('config.yaml')

    yaml_config = {
        'platforms': {
            'webhook': {
                'enabled': True,
                'extra': {
                    'routes': {
                        'receipt': {'secret': '${BK_APEX_BRIDGE_APEX_SECRET}'}
                    }
                },
            }
        }
    }

    with patch.dict(os.environ, {'BK_APEX_BRIDGE_APEX_SECRET': 'test-webhook-secret'}), \
         patch('gateway.config.get_hermes_home', return_value=fake_home), \
         patch.object(Path, 'exists', fake_exists), \
         patch('builtins.open', create=True) as mock_file, \
         patch('yaml.safe_load', return_value=yaml_config):
        mock_file.return_value.__enter__ = lambda stream: stream
        mock_file.return_value.__exit__ = MagicMock(return_value=False)
        config = load_gateway_config()

    route = config.platforms[Platform.WEBHOOK].extra['routes']['receipt']
    assert route['secret'] == 'test-webhook-secret'
"""Global strategy validation and real save/load retain portable documents."""
import copy
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from agent.battle.core.advanced_strategy import default_advanced_strategy
from agent.battle_editor.server import create_server
from agent.battle_editor.validation import DEFAULTS, validate_battle


class GlobalStrategyValidationTests(unittest.TestCase):
    def test_backend_new_document_defaults_match_shared_runtime_contract(self):
        self.assertEqual(DEFAULTS['newBattle']['maaAdvancedStrategy'], default_advanced_strategy())

    def test_strategy_only_no_formation_and_no_turns_validate_without_mutation(self):
        for data in ({'maaAdvancedStrategy': {}}, {'maaAdvancedStrategy': default_advanced_strategy()},
                     {'actions': []}, {'team': None, 'actions': None, 'maaAdvancedStrategy': {'maxTurns': 55}},
                     copy.deepcopy(DEFAULTS['newBattle'])):
            with self.subTest(data=data):
                before = copy.deepcopy(data)
                report = validate_battle(data)
                self.assertTrue(report['valid'], report)
                self.assertEqual(data, before)
                self.assertFalse(any(i['code'] == 'preserved_field' and i['path'] == 'maaAdvancedStrategy' for i in report['issues']))

    def test_unrelated_json_and_invalid_known_values_remain_blocked(self):
        for data in ({}, {'future': True}, {'team': False, 'maaAdvancedStrategy': {}},
                     {'maaAdvancedStrategy': None}, {'maaAdvancedStrategy': {'maxTurns': 101}},
                     {'maaAdvancedStrategy': {'openingHand': {'enabled': True}}},
                     {'maaAdvancedStrategy': {'nativeStrategyOverrides': {'brave_chain_weight': '20'}}}):
            with self.subTest(data=data):
                self.assertFalse(validate_battle(data)['valid'])

    def test_precise_paths_and_future_fields_are_preserved(self):
        data = {'maaAdvancedStrategy': {'preset': 'np', 'maxTurns': 65, 'openingHand': {'future': None},
                                     'future': {'keep': [None, False]}, 'nativeStrategyOverrides': {'future': True}}}
        before = copy.deepcopy(data)
        self.assertTrue(validate_battle(data)['valid'])
        self.assertEqual(data, before)
        data['maaAdvancedStrategy']['openingHand']['maxWaitTurns'] = 6
        report = validate_battle(data)
        self.assertFalse(report['valid'])
        self.assertIn('maaAdvancedStrategy.openingHand.maxWaitTurns', [i['path'] for i in report['issues']])


class GlobalStrategyHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='advanced_strategy_')
        self.root = Path(self.temp.name)
        web = self.root / 'assets/web/battle-editor'
        web.mkdir(parents=True)
        (web / 'index.html').write_text('<!doctype html><title>strategy</title>', 'utf-8')
        self.server = create_server(self.root, 0)
        self.server._catalog = {'servants': []}
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.stop()
        self.thread.join(5)
        self.server.server_close()
        self.temp.cleanup()

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        headers = {'X-Editor-Token': self.server.token, 'Content-Type': 'application/json'}
        connection.request(method, path, None if body is None else json.dumps(body), headers)
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        return response.status, result

    def test_save_reload_draft_and_partial_editor_document_keep_strategy_exactly(self):
        data = {'maaAdvancedStrategy': {'preset': 'brave', 'maxTurns': 52, 'autoServantSkills': False,
                                      'openingHand': {'enabled': False, 'maxWaitTurns': 3},
                                      'future': {'keep': [None, False]}}, 'future': '保留'}
        status, saved = self.request('POST', '/api/battles', {'name': '仅全局策略.json', 'data': data})
        self.assertEqual(status, 201, saved)
        self.assertEqual(saved['data'], data)
        status, loaded = self.request('GET', '/api/battles/%E4%BB%85%E5%85%A8%E5%B1%80%E7%AD%96%E7%95%A5.json')
        self.assertEqual(status, 200)
        self.assertEqual(loaded['data'], data)
        self.assertNotIn('team', loaded['data'])
        self.assertNotIn('actions', loaded['data'])
        status, draft = self.request('PUT', '/api/drafts/strategy-test', {'data': data, 'revision': 0})
        self.assertEqual(status, 200, draft)
        self.assertEqual(draft['data'], data)
        changed = copy.deepcopy(data)
        changed['maaAdvancedStrategy']['preset'] = 'mighty'
        status, updated = self.request('PUT', '/api/battles/%E4%BB%85%E5%85%A8%E5%B1%80%E7%AD%96%E7%95%A5.json', {'data': changed, 'expectedHash': loaded['hash']})
        self.assertEqual(status, 200, updated)
        self.assertEqual(updated['data'], changed)

    def test_invalid_advanced_strategy_cannot_be_formally_saved(self):
        status, result = self.request('POST', '/api/battles', {'name': '无效策略.json', 'data': {'maaAdvancedStrategy': {'maxTurns': 0}}})
        self.assertEqual(status, 422)
        self.assertEqual(result['error']['code'], 'validation_failed')


if __name__ == '__main__':
    unittest.main()

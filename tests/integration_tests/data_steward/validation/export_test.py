import json
import os
import unittest

import mock

import bq_utils
import common
import gcs_utils
from tests import test_util
from tests.test_util import FAKE_HPO_ID
from validation import export, main

BQ_TIMEOUT_RETRIES = 3


class ExportTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print(
            '\n**************************************************************')
        print(cls.__name__)
        print('**************************************************************')
        dataset_id = bq_utils.get_dataset_id()
        test_util.delete_all_tables(dataset_id)
        test_util.populate_achilles()

    def setUp(self):
        self.hpo_bucket = gcs_utils.get_hpo_bucket(FAKE_HPO_ID)

    def _empty_bucket(self):
        bucket_items = gcs_utils.list_bucket(self.hpo_bucket)
        for bucket_item in bucket_items:
            gcs_utils.delete_object(self.hpo_bucket, bucket_item['name'])

    def _test_report_export(self, report):
        data_density_path = os.path.join(export.EXPORT_PATH, report)
        result = export.export_from_path(data_density_path, FAKE_HPO_ID)
        return result
        # TODO more strict testing of result payload. The following doesn't work because field order is random.
        # actual_payload = json.dumps(result, sort_keys=True, indent=4, separators=(',', ': '))
        # expected_path = os.path.join(test_util.TEST_DATA_EXPORT_SYNPUF_PATH, report + '.json')
        # with open(expected_path, 'r') as f:
        #     expected_payload = f.read()
        #     self.assertEqual(actual_payload, expected_payload)
        # return result

    @mock.patch('validation.export.is_hpo_id')
    def test_export_data_density(self, mock_is_hpo_id):
        # INTEGRATION TEST
        mock_is_hpo_id.return_value = True
        export_result = self._test_report_export('datadensity')
        expected_keys = [
            'CONCEPTS_PER_PERSON', 'RECORDS_PER_PERSON', 'TOTAL_RECORDS'
        ]
        for expected_key in expected_keys:
            self.assertTrue(expected_key in export_result)
        self.assertEqual(
            len(export_result['TOTAL_RECORDS']['X_CALENDAR_MONTH']), 283)

    @mock.patch('validation.export.is_hpo_id')
    def test_export_person(self, mock_is_hpo_id):
        # INTEGRATION TEST
        mock_is_hpo_id.return_value = True
        export_result = self._test_report_export('person')
        expected_keys = [
            'BIRTH_YEAR_HISTOGRAM', 'ETHNICITY_DATA', 'GENDER_DATA',
            'RACE_DATA', 'SUMMARY'
        ]
        for expected_key in expected_keys:
            self.assertTrue(expected_key in export_result)
        self.assertEqual(
            len(export_result['BIRTH_YEAR_HISTOGRAM']['DATA']['COUNT_VALUE']),
            72)

    @mock.patch('validation.export.is_hpo_id')
    def test_export_achillesheel(self, mock_is_hpo_id):
        # INTEGRATION TEST
        mock_is_hpo_id.return_value = True
        export_result = self._test_report_export('achillesheel')
        self.assertTrue('MESSAGES' in export_result)
        self.assertEqual(len(export_result['MESSAGES']['ATTRIBUTENAME']), 14)

    @mock.patch('validation.export.is_hpo_id')
    def test_run_export(self, mock_is_hpo_id):
        # validation/main.py INTEGRATION TEST
        mock_is_hpo_id.return_value = True
        folder_prefix = 'dummy-prefix-2018-03-24/'
        main._upload_achilles_files(FAKE_HPO_ID, folder_prefix)
        main.run_export(datasource_id=FAKE_HPO_ID, folder_prefix=folder_prefix)
        bucket_objects = gcs_utils.list_bucket(self.hpo_bucket)
        actual_object_names = [obj['name'] for obj in bucket_objects]
        for report in common.ALL_REPORT_FILES:
            prefix = folder_prefix + common.ACHILLES_EXPORT_PREFIX_STRING + FAKE_HPO_ID + '/'
            expected_object_name = prefix + report
            self.assertIn(expected_object_name, actual_object_names)

        datasources_json_path = folder_prefix + common.ACHILLES_EXPORT_DATASOURCES_JSON
        self.assertIn(datasources_json_path, actual_object_names)
        datasources_json = gcs_utils.get_object(self.hpo_bucket,
                                                datasources_json_path)
        datasources_actual = json.loads(datasources_json)
        datasources_expected = {
            'datasources': [{
                'name': FAKE_HPO_ID,
                'folder': FAKE_HPO_ID,
                'cdmVersion': 5
            }]
        }
        self.assertDictEqual(datasources_expected, datasources_actual)

    def test_run_export_without_datasource_id(self):
        # validation/main.py INTEGRATION TEST
        with self.assertRaises(RuntimeError):
            main.run_export(datasource_id=None, target_bucket=None)

    @mock.patch('validation.export.is_hpo_id')
    def test_run_export_with_target_bucket_and_datasource_id(
        self, mock_is_hpo_id):
        # validation/main.py INTEGRATION TEST
        mock_is_hpo_id.return_value = True
        folder_prefix = 'dummy-prefix-2018-03-24/'
        bucket_nyc = gcs_utils.get_hpo_bucket('nyc')
        main.run_export(datasource_id=FAKE_HPO_ID,
                        folder_prefix=folder_prefix,
                        target_bucket=bucket_nyc)
        bucket_objects = gcs_utils.list_bucket(bucket_nyc)
        actual_object_names = [obj['name'] for obj in bucket_objects]
        for report in common.ALL_REPORT_FILES:
            prefix = folder_prefix + common.ACHILLES_EXPORT_PREFIX_STRING + FAKE_HPO_ID + '/'
            expected_object_name = prefix + report
            self.assertIn(expected_object_name, actual_object_names)
        datasources_json_path = folder_prefix + common.ACHILLES_EXPORT_DATASOURCES_JSON
        self.assertIn(datasources_json_path, actual_object_names)
        datasources_json = gcs_utils.get_object(bucket_nyc,
                                                datasources_json_path)
        datasources_actual = json.loads(datasources_json)
        datasources_expected = {
            'datasources': [{
                'name': FAKE_HPO_ID,
                'folder': FAKE_HPO_ID,
                'cdmVersion': 5
            }]
        }
        self.assertDictEqual(datasources_expected, datasources_actual)

    def tearDown(self):
        self._empty_bucket()
        bucket_nyc = gcs_utils.get_hpo_bucket('nyc')
        test_util.empty_bucket(bucket_nyc)

    @classmethod
    def tearDownClass(cls):
        dataset_id = bq_utils.get_dataset_id()
        test_util.delete_all_tables(dataset_id)
